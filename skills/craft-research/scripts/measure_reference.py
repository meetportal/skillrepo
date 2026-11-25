import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT = 360, 640
TO_720P = 720 / WIDTH
CORNER_720P = float(np.hypot(360, 640))


def low_priority():
    prefix = []
    if shutil.which("nice"):
        prefix += ["nice", "-n", "19"]
    if shutil.which("ionice"):
        prefix += ["ionice", "-c", "3"]
    return prefix


def probe_fps(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout.strip()
    num, _, den = out.partition("/")
    return float(num) / float(den or 1)


def frames(video, threads):
    command = [*low_priority(), "ffmpeg", "-v", "error", "-threads", str(threads), "-i", str(video),
               "-vf", f"scale={WIDTH}:{HEIGHT}:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    size = WIDTH * HEIGHT
    try:
        while True:
            chunk = process.stdout.read(size)
            if len(chunk) < size:
                break
            yield np.frombuffer(chunk, np.uint8).reshape(HEIGHT, WIDTH).astype(np.float32)
    finally:
        process.stdout.close()
        process.wait()


def tiles(band):
    rows = [(0, HEIGHT // 3), (HEIGHT // 3, 2 * HEIGHT // 3), (2 * HEIGHT // 3, HEIGHT)]
    cols = [(0, WIDTH // 3), (WIDTH // 3, 2 * WIDTH // 3), (2 * WIDTH // 3, WIDTH)]
    out = []
    for y0, y1 in rows:
        pieces = [(a, b) for a, b in ((y0, min(y1, band[0])), (max(y0, band[1]), y1)) if b - a >= 48]
        if not pieces:
            continue
        y0, y1 = max(pieces, key=lambda p: p[1] - p[0])
        for x0, x1 in cols:
            out.append((y0, y1, x0, x1))
    return out


def similarity(shifts, centres, weights):
    centre = np.array([WIDTH / 2, HEIGHT / 2])
    rows, values, w = [], [], []
    for (dx, dy), (cx, cy), weight in zip(shifts, centres, weights):
        rows += [[1, 0, cx - centre[0]], [0, 1, cy - centre[1]]]
        values += [dx, dy]
        w += [weight, weight]
    a, b, sw = np.array(rows), np.array(values), np.sqrt(np.array(w))
    solution, *_ = np.linalg.lstsq(a * sw[:, None], b * sw, rcond=None)
    return solution


def local_median(values, radius):
    out = np.empty_like(values)
    for i in range(len(values)):
        window = np.concatenate([values[max(0, i - radius):i], values[i + 1:i + 1 + radius]])
        out[i] = np.median(window) if len(window) else 0.0
    return out


def runs(mask, min_len, bridge):
    edges = np.diff(np.concatenate([[0], np.asarray(mask, int), [0]]))
    spans = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))
    merged = []
    for start, end in spans:
        if merged and start - merged[-1][1] <= bridge:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return [(int(a), int(b)) for a, b in merged if b - a >= min_len]


def words_stats(path, pause_min):
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = data.get("words", [])
    words = []
    for w in data:
        if "startMs" in w:
            words.append((w["startMs"] / 1000, w["endMs"] / 1000))
        else:
            words.append((float(w["start"]), float(w["end"])))
    words.sort()
    if len(words) < 2:
        return {}
    span = words[-1][1] - words[0][0]
    pauses = [b[0] - a[1] for a, b in zip(words, words[1:]) if b[0] - a[1] >= pause_min]
    return {"words": len(words), "words_per_sec": round(len(words) / span, 2), "pause_total_sec": round(sum(pauses), 2),
            "pause_per_15s": round(sum(pauses) * 15 / span, 2), "pauses": len(pauses)}


def measure(video, args):
    fps = probe_fps(video)
    band = (int(round(args.band[0] * HEIGHT)), int(round(args.band[1] * HEIGHT)))
    keep = np.ones(HEIGHT, bool)
    keep[band[0]:band[1]] = False
    boxes = tiles(band)
    windows = {(y1 - y0, x1 - x0): cv2.createHanningWindow((x1 - x0, y1 - y0), cv2.CV_32F) for y0, y1, x0, x1 in boxes}
    centres = [((x0 + x1) / 2, (y0 + y1) / 2) for y0, y1, x0, x1 in boxes]
    def fit(a, b):
        shifts, weights, used = [], [], []
        for (y0, y1, x0, x1), centre in zip(boxes, centres):
            shift, response = cv2.phaseCorrelate(a[y0:y1, x0:x1], b[y0:y1, x0:x1], windows[(y1 - y0, x1 - x0)])
            if response >= args.min_response:
                shifts.append(shift)
                weights.append(response)
                used.append(centre)
        if len(used) < 3:
            return np.zeros(3)
        return similarity(shifts, used, weights)

    stride = args.push_stride
    diffs, tile_hits, fits, slow = [], [], [], []
    history = []
    count = 0
    for frame in frames(video, args.threads):
        count += 1
        history = (history + [frame])[-(stride + 1):]
        if count == 1:
            continue
        previous = history[-2]
        delta = np.abs(frame - previous)
        diffs.append(float(delta[keep].mean()))
        tile_hits.append(sum(float(delta[y0:y1, x0:x1].mean()) > args.tile_cut for y0, y1, x0, x1 in boxes))
        fits.append(fit(previous, frame))
        slow.append(fit(history[0], frame)[2] / stride if len(history) == stride + 1 else np.nan)
    if count < 3:
        raise SystemExit(f"{video}: decoded {count} frames")
    diffs, fits = np.array(diffs), np.array(fits)
    duration = count / fps
    median = local_median(diffs, 12)
    cut = (diffs > np.maximum(args.cut_diff, args.cut_ratio * median)) & (np.array(tile_hits) >= args.cut_tiles)
    speed = TO_720P * np.hypot(fits[:, 0], fits[:, 1]) + np.abs(fits[:, 2]) * CORNER_720P
    speed[cut] = 0.0
    moving = (speed > args.hold_px) & ~cut
    moves = runs(speed > args.move_px, args.move_min_frames, 2)
    in_move = np.zeros(len(speed), bool)
    for a, b in moves:
        in_move[a:b] = True
    spike = (diffs > np.maximum(args.event_diff, args.event_ratio * median)) & ~cut & ~in_move
    cut_near = np.convolve(cut.astype(int), np.ones(stride, int))[:len(cut)] > 0
    slow = np.array(slow)
    hold = ~cut_near & ~in_move & ~np.isnan(slow)
    push = np.abs(slow[hold]) * 100 if hold.any() else np.array([0.0])
    cut_starts, previous_cut = [], None
    for i in np.flatnonzero(cut):
        if previous_cut is None or (i - previous_cut) / fps >= args.cut_min_gap:
            cut_starts.append(i)
        previous_cut = i
    cut_times = [round((i + 1) / fps, 3) for i in cut_starts]
    event_times = sorted(cut_times + [round((a + 1) / fps, 3) for a, _ in moves] + [round((i + 1) / fps, 3) for i in np.flatnonzero(spike)])
    merged = []
    for t in event_times:
        if not merged or t - merged[-1] >= args.merge:
            merged.append(t)
    marks = [0.0, *merged, round(duration, 3)]
    gaps = np.diff(marks)
    peaks = [float(speed[a:b].max()) for a, b in moves]
    return {
        "video": Path(video).name,
        "duration_sec": round(duration, 2),
        "fps": round(fps, 3),
        "frames": count,
        "caption_band": [args.band[0], args.band[1]],
        "cuts": len(cut_times),
        "cuts_per_10s": round(len(cut_times) * 10 / duration, 2),
        "visual_events": len(merged),
        "visual_events_per_10s": round(len(merged) * 10 / duration, 2),
        "median_gap_sec": round(float(np.median(gaps)), 2),
        "max_gap_sec": round(float(gaps.max()), 2),
        "moving_frames_pct": round(100 * float(moving.mean()), 1),
        "hold_frames_pct": round(100 * float(((speed <= args.hold_px) & ~cut).mean()), 1),
        "moves": len(moves),
        "moves_per_10s": round(len(moves) * 10 / duration, 2),
        "move_peak_px_per_frame_720p_median": round(float(np.median(peaks)), 1) if peaks else 0.0,
        "move_peak_px_per_frame_720p_p75": round(float(np.percentile(peaks, 75)), 1) if peaks else 0.0,
        "push_pct_per_frame_on_holds_median": round(float(np.median(push)), 3),
        "push_pct_per_frame_on_holds_p75": round(float(np.percentile(push, 75)), 3),
        "cut_times": cut_times,
        "event_times": merged,
        "moves_sec": [[round((a + 1) / fps, 3), round((b + 1) / fps, 3), round(p, 1)] for (a, b), p in zip(moves, peaks)],
    }


ROWS = [
    ("duration_sec", "duration (s)"), ("fps", "fps"), ("cuts_per_10s", "cuts per 10 s"),
    ("visual_events_per_10s", "visual events per 10 s"), ("median_gap_sec", "median gap between visual events (s)"),
    ("max_gap_sec", "longest gap (s)"), ("moving_frames_pct", "moving frames (%)"), ("hold_frames_pct", "hold frames (%)"),
    ("moves_per_10s", "camera moves per 10 s"), ("move_peak_px_per_frame_720p_median", "move peak px/frame at 720p, median"),
    ("move_peak_px_per_frame_720p_p75", "move peak px/frame at 720p, p75"),
    ("push_pct_per_frame_on_holds_median", "push %/frame on holds, median"), ("push_pct_per_frame_on_holds_p75", "push %/frame on holds, p75"),
    ("words_per_sec", "words/s"), ("pause_total_sec", "pauses >= 0.25 s, total (s)"), ("pause_per_15s", "pauses >= 0.25 s per 15 s (s)"),
]


def main():
    parser = argparse.ArgumentParser(
        description="Measure a reference reel in numbers: decode at 360x640 grey, mask the caption band, count scene cuts and visual "
                    "events (cuts, camera moves, graphic changes), and fit 3x3 tile phase correlation (cv2.phaseCorrelate) to a "
                    "translation + scale model per frame for moving frames, moves per 10 s, move peak speed at 720p and push rate on "
                    "holds; words/s and pauses when a word file is given. Prints a markdown table and writes JSON.")
    parser.add_argument("video", help="reference reel (any ffmpeg-readable file, vertical)")
    parser.add_argument("--out", help="write the measurements as JSON here")
    parser.add_argument("--words", help="word timings: Caption[] (startMs), a [{text, start, end}] list or cues.json")
    parser.add_argument("--band", type=float, nargs=2, default=(0.55, 0.86), metavar=("TOP", "BOTTOM"), help="caption band to mask, as fractions of the height (default 0.55 0.86)")
    parser.add_argument("--cut-diff", type=float, default=12.0, help="mean abs grey difference (0-255) a cut must exceed (default 12)")
    parser.add_argument("--cut-ratio", type=float, default=3.0, help="and this multiple of the local median difference (default 3)")
    parser.add_argument("--cut-min-gap", type=float, default=0.12, help="a run of cut frames each closer than this many seconds to the one before is one transition (a wipe, dissolve or flash) and counts once, at its first frame (default 0.12)")
    parser.add_argument("--cut-tiles", type=int, default=6, help="and at least this many of the tiles must change (default 6)")
    parser.add_argument("--tile-cut", type=float, default=8.0, help="tile mean abs difference that counts as changed (default 8)")
    parser.add_argument("--event-diff", type=float, default=3.0, help="difference spike that counts as a graphic event (default 3)")
    parser.add_argument("--event-ratio", type=float, default=2.5, help="and this multiple of the local median (default 2.5)")
    parser.add_argument("--hold-px", type=float, default=0.3, help="frames at or under this speed (720p px/frame) are holds (default 0.3)")
    parser.add_argument("--move-px", type=float, default=2.0, help="a camera move is a run of frames above this speed (default 2.0)")
    parser.add_argument("--move-min-frames", type=int, default=3, help="shortest move in frames (default 3)")
    parser.add_argument("--merge", type=float, default=0.2, help="visual events closer than this many seconds count once (default 0.2)")
    parser.add_argument("--min-response", type=float, default=0.6, help="tiles whose phase correlation peak is under this are textureless or noise and are left out of the fit; under 3 tiles the frame counts as still (default 0.6)")
    parser.add_argument("--push-stride", type=int, default=5, help="frames between the two images used for the push rate on holds; small per-frame zooms are below phase correlation precision (default 5)")
    parser.add_argument("--pause-min", type=float, default=0.25, help="pauses at least this long count (default 0.25)")
    parser.add_argument("--threads", type=int, default=2, help="ffmpeg decoder threads (default 2)")
    args = parser.parse_args()

    started = time.time()
    result = measure(args.video, args)
    if args.words:
        result.update(words_stats(args.words, args.pause_min))
    result["elapsed_sec"] = round(time.time() - started, 1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    lines = [f"| metric | {result['video']} |", "|---|---|"]
    lines += [f"| {label} | {result[key]} |" for key, label in ROWS if key in result]
    sys.stdout.write("\n".join(lines) + "\n")
    print(f"measured {result['frames']} frames in {result['elapsed_sec']} s", file=sys.stderr)


if __name__ == "__main__":
    main()
