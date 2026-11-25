import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT = 180, 320
REC709 = np.array([0.2126, 0.7152, 0.0722], np.float32)
FULL_ZONE = (0, 0, 1080, 1920)
THUMB_W, THUMB_H, GRID_COLS, GRID_ROWS = 108, 192, 10, 6


def decode(path, threads):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-threads", str(threads), "-i", str(path), "-map", "0:v:0",
         "-vf", f"scale={WIDTH}:{HEIGHT}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, HEIGHT, WIDTH, 3)


def grey(frame):
    frame = np.asarray(frame)
    return frame[..., 0] * np.float32(REC709[0]) + frame[..., 1] * np.float32(REC709[1]) + frame[..., 2] * np.float32(REC709[2])


def measure(frames, chunk=50):
    count = len(frames)
    out = {key: np.zeros(count, np.float32) for key in ("mean", "std", "p2", "p98", "sat", "diff")}
    pixels = frames.shape[1] * frames.shape[2]
    ranks = [int(0.02 * (pixels - 1)), int(0.98 * (pixels - 1))]
    previous = None
    for start in range(0, count, chunk):
        block = frames[start:start + chunk]
        size = len(block)
        scaled = grey(block).reshape(size, -1)
        luma = scaled / 255.0
        out["mean"][start:start + size] = luma.mean(axis=1)
        out["std"][start:start + size] = luma.std(axis=1)
        parted = np.partition(luma, ranks, axis=1)
        out["p2"][start:start + size] = parted[:, ranks[0]]
        out["p98"][start:start + size] = parted[:, ranks[1]]
        red, green, blue = block[..., 0], block[..., 1], block[..., 2]
        top = np.maximum(np.maximum(red, green), blue).reshape(size, -1)
        bottom = np.minimum(np.minimum(red, green), blue).reshape(size, -1)
        lit = top >= 16
        spread = (top - bottom).astype(np.float32) / np.maximum(top, 1).astype(np.float32)
        lit_count = lit.sum(axis=1)
        out["sat"][start:start + size] = np.where(lit_count > 0, (spread * lit).sum(axis=1) / np.maximum(lit_count, 1), 0.0)
        joined = scaled if previous is None else np.concatenate([previous[None], scaled])
        steps = np.abs(np.diff(joined, axis=0)).mean(axis=1)
        if previous is None:
            out["diff"][start + 1:start + size] = steps
        else:
            out["diff"][start:start + size] = steps
        previous = scaled[-1]
    return out


def to_frame(t, fps):
    return int(np.floor(float(t) * fps + 0.5))


def time_range(item):
    if isinstance(item, (list, tuple)):
        return float(item[0]), float(item[1])
    for lo, hi in (("start", "end"), ("from", "to"), ("s", "e")):
        if lo in item and hi in item:
            return float(item[lo]), float(item[hi])
    return None


def find_key(data, key):
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


def load_json(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else None


def plan_beats(reel):
    return list((reel.props or {}).get("beats") or (reel.beatmap or {}).get("beats", []))


def plan_camera(reel):
    camera = (reel.props or {}).get("camera")
    if isinstance(camera, list):
        return camera
    return (reel.camera or {}).get("keys", [])


def is_three(beat):
    return beat.get("component") == "VideoInsert" and isinstance((beat.get("props") or {}).get("three"), dict)


def beat_times(props):
    times = []
    for key, value in (props or {}).items():
        if key == "three":
            continue
        if key == "events" and isinstance(value, list):
            times += [float(e["t"]) for e in value if isinstance(e, dict) and isinstance(e.get("t"), (int, float))]
        elif key.endswith(("At", "Start", "End", "Times", "times")):
            values = value if isinstance(value, list) else [value]
            times += [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return times


def caption_pages(path, fps):
    data = load_json(path)
    if data is None:
        return []
    pages = data["pages"] if isinstance(data, dict) else data
    rows = []
    for page in pages:
        start = float(page["start"]) if "start" in page else float(page["startMs"]) / 1000
        end = float(page["end"]) if "end" in page else float(page["endMs"]) / 1000
        first = int(page["firstFrame"]) if "firstFrame" in page else to_frame(start, fps)
        last = int(page["endFrame"]) if "endFrame" in page else to_frame(end, fps)
        rows.append({**page, "start": start, "end": end, "firstFrame": first, "endFrame": last})
    return rows


def edl_holds(edl, fps):
    if not edl:
        return []
    frames, spans = 0, []
    for item in edl.get("ranges", []):
        length = round((float(item["a_out"]) - float(item["a_in"])) * fps)
        if item.get("v_hold") is not None:
            spans.append((frames, frames + length - 1))
        frames += length
    return spans


def planned_events(reel, captions_path, mix_report_path):
    fps, count = reel.fps, reel.frames
    points, windows, holds, three, end_cards = [], [], [], [], []
    cues = reel.cues or {}
    for t in cues.get("cuts", []):
        points.append((to_frame(t, fps), "cut"))
    for segment in cues.get("segments", []):
        for hold in segment.get("holds", []):
            span = (to_frame(hold[0], fps), to_frame(hold[1], fps) - 1)
            holds.append(span)
            windows.append((*span, "cue hold"))
    for span in edl_holds(reel.edl, fps):
        holds.append(span)
        windows.append((*span, "edl v_hold"))
    for beat in plan_beats(reel):
        start, end = to_frame(beat["from"], fps), to_frame(beat["to"], fps)
        points.append((start, f"beat {beat.get('id', '')} in"))
        points.append((end, f"beat {beat.get('id', '')} out"))
        for t in beat_times(beat.get("props")):
            points.append((to_frame(float(beat["from"]) + t, fps), f"beat {beat.get('id', '')} event"))
        if beat.get("component") == "EndCard":
            holds.append((to_frame(float(beat["from"]) + 1.0, fps), count - 1))
            end_cards.append((start, count - 1))
        if is_three(beat):
            three.append((start, end - 1, beat.get("id", "")))
    for key in plan_camera(reel):
        t = float(key["t"])
        frames = int(key.get("frames") or 0)
        if key.get("ease") == "kick" and frames:
            windows.append((to_frame(t, fps), to_frame(t, fps) + frames, "camera kick"))
        elif key.get("ease") == "glide" and frames:
            half = frames / 2 / fps
            windows.append((to_frame(t - half, fps), to_frame(t + half, fps), "camera glide"))
        else:
            points.append((to_frame(t, fps), f"camera {key.get('ease', '')}"))
    for page in caption_pages(captions_path, fps):
        points.append((page["firstFrame"], "caption in"))
        points.append((page["endFrame"], "caption out"))
    for path in sorted((reel.work / "3d").glob("*.json")):
        data = load_json(path) or {}
        for event in data.get("events", []):
            points.append((to_frame(event["t"], fps), f"3d {data.get('beat', path.stem)} {event.get('kind', '')}".strip()))
    dropouts = []
    for item in find_key(load_json(mix_report_path) or {}, "dropouts") or []:
        span = time_range(item)
        if span:
            dropouts.append(span)
            windows.append((to_frame(span[0], fps), to_frame(span[1], fps), "mix dropout"))
    exempt = np.zeros(count, bool)
    for frame, _ in points:
        exempt[max(0, frame - 1):min(count, frame + 2)] = True
    for lo, hi, _ in windows:
        exempt[max(0, lo - 1):min(count, hi + 2)] = True
    hold_mask = np.zeros(count, bool)
    for lo, hi in holds:
        hold_mask[max(0, lo):min(count, hi + 1)] = True
    end_card_mask = np.zeros(count, bool)
    for lo, hi in end_cards:
        end_card_mask[max(0, lo):hi + 1] = True
    three_mask = np.zeros(count, bool)
    for lo, hi, _ in three:
        three_mask[max(0, lo):min(count, hi + 1)] = True
    return {"points": points, "windows": windows, "holds": holds, "three": three, "dropouts": dropouts,
            "exempt": exempt, "hold_mask": hold_mask, "three_mask": three_mask,
            "end_card_mask": end_card_mask}


def runs(mask):
    spans, start = [], None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(mask) - 1))
    return spans


def local_median(diff, radius=8):
    out = np.zeros(len(diff), np.float32)
    for i in range(1, len(diff)):
        lo, hi = max(1, i - radius), min(len(diff), i + radius + 1)
        window = np.concatenate([diff[lo:i], diff[i + 1:hi]])
        out[i] = np.median(window) if len(window) else 0.0
    return out


def zone_pixels(zone):
    sx, sy = WIDTH / 1080, HEIGHT / 1920
    x0, y0, x1, y1 = zone
    return int(round(x0 * sx)), int(round(y0 * sy)), int(round(x1 * sx)), int(round(y1 * sy))


def beat_zone(beat, card_box):
    props = beat.get("props") or {}
    box = props.get("box") or props.get("bbox")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        return tuple(float(v) for v in box), "props.box"
    if isinstance(box, dict):
        if {"x0", "y0", "x1", "y1"} <= box.keys():
            return (box["x0"], box["y0"], box["x1"], box["y1"]), "props.box"
        if {"x", "y", "w", "h"} <= box.keys():
            return (box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]), "props.box"
    if beat.get("mode") in ("takeover", "hidden") or (beat.get("component") == "VideoInsert" and props.get("fit", "full") == "full"):
        return FULL_ZONE, "full frame"
    return card_box, "zones.card"


def zone_diff(frames, a, b, zone):
    x0, y0, x1, y1 = zone
    return float(np.abs(grey(frames[a, y0:y1, x0:x1]) - grey(frames[b, y0:y1, x0:x1])).mean())


def zone_detail(frames, index, zone):
    x0, y0, x1, y1 = zone
    dx, dy = max(1, (x1 - x0) // 10), max(1, (y1 - y0) // 10)
    luma = grey(frames[index, y0 + dy:y1 - dy, x0 + dx:x1 - dx]) / 255.0
    gy, gx = np.gradient(luma)
    return float(np.abs(gx).mean() + np.abs(gy).mean())


def entrances(frames, beats, fps, card_box, args):
    rows = []
    count = len(frames)
    for beat in beats:
        start = to_frame(beat["from"], fps)
        if start < 1 or start + 2 >= count:
            continue
        box, source = beat_zone(beat, card_box)
        zone = zone_pixels(box)
        d_in = zone_diff(frames, start - 1, start, zone)
        d_next = zone_diff(frames, start, start + 1, zone)
        detail = [zone_detail(frames, start, zone), zone_detail(frames, start + 1, zone)]
        reasons = []
        if d_in < args.entrance_min_diff:
            reasons.append(f"zone unchanged on the first frame (diff {d_in:.2f} < {args.entrance_min_diff})")
        if d_next > args.entrance_lag_ratio * d_in + 2.0:
            reasons.append(f"graphic first shows one frame late (diff {d_in:.1f} on f{start}, {d_next:.1f} on f{start + 1})")
        blank = [start + k for k, value in enumerate(detail) if value < args.entrance_blank]
        if blank:
            reasons.append(f"blank zone on f{blank[0]} (detail {min(detail):.4f} < {args.entrance_blank})")
        handoff = next((other for other in beats if other is not beat and beat_zone(other, card_box)[1] == source
                        and abs(to_frame(other["to"], fps) - start) <= 1), None)
        covered = None
        if handoff is not None:
            x0, y0, x1, y1 = zone
            covered = [float(v) for v in skin_share(frames[start - 1:start + 2, y0:y1, x0:x1], args.cover_rb)]
            if covered[1] > max(covered[0], covered[2]) + args.handoff_uncovered:
                reasons.append(f"A-roll shows through at the handoff from {handoff.get('id', '')} "
                               f"(skin share {covered[0]:.2f} / {covered[1]:.2f} / {covered[2]:.2f} on f{start - 1}-f{start + 1})")
        rows.append({"beat": beat.get("id", ""), "component": beat.get("component", ""), "frame": start,
                     "t": round(start / fps, 3), "zone": source, "diff_in": round(d_in, 2), "diff_next": round(d_next, 2),
                     "detail": [round(v, 4) for v in detail], "handoff": handoff.get("id", "") if handoff else None,
                     "skin_share": [round(v, 3) for v in covered] if covered else None, "empty": bool(reasons), "reasons": reasons})
    return rows


def segments(reel):
    rows = []
    for seg in (reel.cues or {}).get("segments", []):
        rows.append((f"seg{int(seg['index']):02d}", float(seg["start"]), float(seg["end"])))
    last = max((r[2] for r in rows), default=0.0)
    if reel.duration - last > 0.2:
        rows.append(("after A-roll" if rows else "whole reel", last, reel.duration))
    return rows


def segment_medians(reel, stats):
    out = []
    for name, start, end in segments(reel):
        lo, hi = to_frame(start, reel.fps), min(reel.frames, to_frame(end, reel.fps))
        if hi <= lo:
            continue
        out.append({"segment": name, "from": round(start, 2), "to": round(end, 2),
                    **{key: round(float(np.median(stats[key][lo:hi])), 3) for key in ("mean", "p2", "p98", "sat", "std")}})
    return out


def skin_share(frames, threshold):
    red = frames[..., 0].astype(np.int16)
    blue = frames[..., 2].astype(np.int16)
    return ((red - blue) > threshold).reshape(len(frames), -1).mean(axis=1)


def write_sheets(frames, fps, flags, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("full_*.jpg"):
        old.unlink()
    per_sheet = GRID_COLS * GRID_ROWS
    header = 24
    written = []
    for number, start in enumerate(range(0, len(frames), per_sheet)):
        sheet = np.zeros((header + THUMB_H * GRID_ROWS, THUMB_W * GRID_COLS, 3), np.uint8)
        end = min(len(frames), start + per_sheet) - 1
        cv2.putText(sheet, f"frames {start}-{end}  {start / fps:.2f}-{end / fps:.2f} s  red = flagged",
                    (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        for j in range(end - start + 1):
            index = start + j
            x, y = (j % GRID_COLS) * THUMB_W, header + (j // GRID_COLS) * THUMB_H
            tile = cv2.resize(frames[index], (THUMB_W, THUMB_H), interpolation=cv2.INTER_AREA)
            tile = cv2.cvtColor(tile, cv2.COLOR_RGB2BGR)
            flagged = index in flags
            cv2.rectangle(tile, (0, 0), (THUMB_W, 13), (0, 0, 220) if flagged else (0, 0, 0), -1)
            colour = (255, 255, 255) if flagged else (80, 230, 255)
            cv2.putText(tile, f"{index} {index / fps:.2f}", (2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.34, colour, 1, cv2.LINE_AA)
            if flagged:
                cv2.rectangle(tile, (1, 1), (THUMB_W - 2, THUMB_H - 2), (0, 0, 255), 3)
            sheet[y:y + THUMB_H, x:x + THUMB_W] = tile
        path = folder / f"full_{number:02d}.jpg"
        cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        written.append(str(path))
    return written


def card_zone(brand):
    box = ((brand or {}).get("layout") or {}).get("cardBox") or {"x0": 70, "y0": 1150, "x1": 950, "y1": 1480}
    return box["x0"], box["y0"], box["x1"], box["y1"]


def check(reel, args, frames, brand):
    fps, count = reel.fps, len(frames)
    stats = measure(frames)
    diff = stats["diff"]
    plan = planned_events(reel, args.captions_path, args.mix_report_path)
    exempt = plan["exempt"]
    median = local_median(diff)
    pop_mask = (diff > 3 * median + 1.0) & ~exempt
    pop_mask[0] = False
    tail = count - int(round(0.2 * fps))
    black_mask = stats["mean"] < 0.04
    black_mask[max(0, tail):] = False
    white_mask = (stats["mean"] > 0.93) & ~exempt & ~plan["end_card_mask"]
    extreme = black_mask | white_mask
    pop_mask &= ~extreme & ~np.concatenate([[False], extreme[:-1]])
    low = (diff < args.frozen_diff)
    low[0] = False
    frozen_warn, frozen_fail = [], []
    for lo, hi in runs(low & ~plan["hold_mask"]):
        if hi - lo + 1 < args.frozen_frames:
            continue
        span = {"from": lo - 1, "to": hi, "t": round((lo - 1) / fps, 3), "frames": hi - lo + 2}
        (frozen_fail if plan["three_mask"][lo:hi + 1].any() else frozen_warn).append(span)
    flat_three = [int(i) for i in np.flatnonzero(plan["three_mask"] & (stats["std"] < 0.01))]
    entrance_rows = entrances(frames, plan_beats(reel), fps, card_zone(brand), args)
    empty = [row for row in entrance_rows if row["empty"]]
    late = {row["frame"] + k for row in empty for k in (1, 2, 3)}
    pops, transitions = [], []
    for lo, hi in runs(pop_mask):
        outside = max(diff[lo - 1] if lo >= 1 else 0.0, diff[hi + 1] if hi + 1 < count else 0.0)
        if hi - lo + 1 > 2:
            transitions.append({"from": lo, "to": hi, "t": round(lo / fps, 3)})
        elif diff[lo:hi + 1].max() > outside and lo not in late:
            pops.append(int(lo))
    black = [{"from": lo, "to": hi, "t": round(lo / fps, 3)} for lo, hi in runs(black_mask)]
    white = [{"from": lo, "to": hi, "t": round(lo / fps, 3)} for lo, hi in runs(white_mask)]
    fails, warns = [], []
    if black:
        fails.append(f"black frames {fmt_spans(black)}")
    if white:
        fails.append(f"unplanned white frames {fmt_spans(white)}")
    if frozen_fail:
        fails.append(f"frozen inside a 3D beat {fmt_spans(frozen_fail)}")
    if flat_three:
        fails.append(f"uniform canvas (luma std < 0.01) inside a 3D beat on frames {compact(flat_three)}")
    if pops:
        warns.append(f"{len(pops)} unplanned pops at frames {compact(pops)}")
    if frozen_warn:
        warns.append(f"frozen spans of {args.frozen_frames}+ frames {fmt_spans(frozen_warn)}")
    if empty:
        warns.append("empty entrance frame: " + "; ".join(f"{row['beat']} {row['component']} f{row['frame']} ({row['t']:.2f}s)" for row in empty))
    flags = set(pops)
    for spans in (black, white, frozen_warn, frozen_fail):
        for span in spans:
            flags.update(range(span["from"], span["to"] + 1))
    flags.update(flat_three)
    flags.update(row["frame"] for row in empty)
    out_dir = Path(args.out_dir)
    np.savez_compressed(out_dir / "frames.npz", exempt=exempt, **stats)
    sheets = write_sheets(frames, fps, flags, out_dir / "sheets")
    held = float((diff[1:] < args.frozen_diff).mean() * 100) if count > 1 else 0.0
    status = "fail" if fails else ("warn" if warns else "pass")
    summary = "; ".join(fails + warns) if fails or warns else f"{count} frames: no black, white, frozen, pop or empty entrance"
    summary += f"; {len(sheets)} full sheets"
    return {
        "status": status, "summary": summary, "pops": pops, "black": black, "white": white,
        "frozen": frozen_warn, "transitions": transitions, "frozen_three": frozen_fail, "flat_three": flat_three, "entrances": entrance_rows,
        "segments": segment_medians(reel, stats), "held_percent": round(held, 1), "mean_diff": round(float(diff[1:].mean()), 3),
        "planned": {"points": len(plan["points"]), "windows": len(plan["windows"]), "holds": len(plan["holds"]),
                    "three": plan["three"], "dropouts": plan["dropouts"], "exempt_frames": int(exempt.sum())},
        "thresholds": {"pop": "diff > 3 x median(+-8) + 1.0", "black": 0.04, "white": 0.93, "frozen_diff": args.frozen_diff,
                       "frozen_frames": args.frozen_frames, "entrance_min_diff": args.entrance_min_diff,
                       "entrance_lag_ratio": args.entrance_lag_ratio, "entrance_blank": args.entrance_blank,
                       "handoff_uncovered": args.handoff_uncovered},
        "sheets": sheets, "npz": str(out_dir / "frames.npz"),
    }


def compact(numbers):
    numbers = sorted(numbers)
    parts, start = [], None
    for i, n in enumerate(numbers):
        if start is None:
            start = n
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            parts.append(str(start) if start == n else f"{start}-{n}")
            start = None
    return ", ".join(parts[:30]) + (" ..." if len(parts) > 30 else "")


def fmt_spans(spans):
    return ", ".join(f"f{s['from']}-{s['to']} ({s['t']:.2f}s)" if s["to"] != s["from"] else f"f{s['from']} ({s['t']:.2f}s)" for s in spans[:12])
