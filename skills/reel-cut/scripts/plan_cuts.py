import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import (
    DEFAULT_RULES, bare, clip_key, ends_sentence, expand_to_edl, is_list_marker, load_json, media_duration,
    seconds, to_frame, to_frame_ceil, to_frame_floor, windows_hit, write_json,
)


def resolve_clips(args, config, transcript):
    paths = {}
    for name, clip in transcript["clips"].items():
        candidate = Path(clip.get("file", ""))
        if candidate.is_absolute() and candidate.exists():
            paths[name] = str(candidate)
    for name, path in (config.get("clips") or {}).items():
        paths[name] = str(Path(path).resolve())
    for path in args.clips or []:
        paths[clip_key(path)] = str(Path(path).resolve())
    return paths


def exclusion_windows(args, transcript, rules):
    kinds = rules["exclude_kinds"]
    windows = {}
    sources = [transcript["clips"]]
    if args.exclusions:
        sources.append(load_json(args.exclusions)["clips"])
    for source in sources:
        for name, clip in source.items():
            merged = windows.setdefault(name, [])
            for kind in kinds:
                merged.extend(clip.get(kind, []) or [])
    for name, extra in (args.config_data.get("exclude") or {}).items():
        windows.setdefault(name, []).extend(extra)
    return windows


def auto_ranges(name, words, rules, fps, duration_frames, windows, trim):
    if trim:
        words = [w for w in words if w["start"] >= trim[0] and w["end"] <= trim[1]]
    if not words:
        return []
    ranges = []
    start = words[0]["start"] - rules["clip_head_pad"]
    for previous, following in zip(words[:-1], words[1:]):
        gap = following["start"] - previous["end"]
        if is_list_marker(previous["word"], rules["list_markers"]):
            tail, lead = rules["list_marker_tail"], rules["list_marker_lead"]
        elif ends_sentence(previous["word"]):
            tail, lead = rules["sentence_tail"], rules["sentence_lead"]
        else:
            tail, lead = rules["tail_pad"], rules["head_pad"]
        blemish = windows_hit(to_frame_floor(previous["end"], fps), to_frame_ceil(following["start"], fps), windows, fps)
        wants_cut = gap >= rules["tighten_min"] or (gap >= rules["optional_min"] and blemish)
        if wants_cut and tail + lead < gap:
            ranges.append([start, previous["end"] + tail])
            start = following["start"] - lead
    ranges.append([start, words[-1]["end"] + rules["clip_tail_pad"]])
    framed = []
    for range_start, range_end in ranges:
        frame_in = max(0, to_frame_floor(range_start, fps))
        frame_out = min(duration_frames, to_frame_ceil(range_end, fps))
        if framed and frame_in <= framed[-1]["out"]:
            framed[-1]["out"] = frame_out
        else:
            framed.append({"clip": name, "in": frame_in, "out": frame_out})
    for index, item in enumerate(framed):
        item["beat"] = f"{name}-{index + 1}"
    return framed


def manual_ranges(config_ranges, fps):
    ranges = []
    for item in config_ranges:
        entry = {"clip": item["clip"], "in": to_frame_floor(item["in"], fps), "out": to_frame_ceil(item["out"], fps), "beat": item.get("beat", "")}
        if "video_in" in item:
            entry["video_in"] = to_frame(item["video_in"], fps)
        if "video_out" in item:
            entry["video_out"] = to_frame(item["video_out"], fps)
        ranges.append(entry)
    return ranges


def joint_is_clean(ranges, index, offset, previous_offset, windows, durations, rules):
    guard = rules["guard_frames"]
    left, right = ranges[index], ranges[index + 1]
    video_in_left = left["in"] - previous_offset
    video_out_left = left["out"] - offset
    video_in_right = right["in"] - offset
    if video_out_left - video_in_left < 2 or video_in_right < 0 or video_out_left > durations[left["clip"]]:
        return False
    if video_in_right >= right["out"]:
        return False
    fps = rules["fps"]
    left_bad = windows_hit(video_out_left - guard, video_out_left, windows.get(left["clip"], []), fps)
    right_bad = windows_hit(video_in_right, video_in_right + guard, windows.get(right["clip"], []), fps)
    return not left_bad and not right_bad


def assign_offsets(ranges, windows, durations, rules, auto_offsets, warnings):
    previous_offset = 0
    for index in range(len(ranges) - 1):
        left, right = ranges[index], ranges[index + 1]
        explicit_left = left["out"] - left["video_out"] if "video_out" in left else None
        explicit_right = right["in"] - right["video_in"] if "video_in" in right else None
        if explicit_left is not None and explicit_right is not None and explicit_left != explicit_right:
            raise SystemExit(f"joint {index}: video_out offset {explicit_left} frames differs from next video_in offset {explicit_right} frames")
        explicit = explicit_left if explicit_left is not None else explicit_right
        if explicit is not None:
            offset = explicit
        elif auto_offsets:
            limit = rules["max_offset_frames"]
            candidates = sorted(range(-limit, limit + 1), key=lambda value: (abs(value), -value))
            offset = next((value for value in candidates if joint_is_clean(ranges, index, value, previous_offset, windows, durations, rules)), 0)
        else:
            offset = 0
        if not joint_is_clean(ranges, index, offset, previous_offset, windows, durations, rules):
            warnings.append(f"joint {index} ({left['clip']} -> {right['clip']}): blink or soft frame within {rules['guard_frames']} frames of the video cut")
        left["joint_offset"] = offset
        previous_offset = offset
    if ranges:
        ranges[-1]["joint_offset"] = 0
        first, last = ranges[0], ranges[-1]
        if "video_in" in first and first["video_in"] != first["in"]:
            raise SystemExit("first range: video_in must equal in (nothing before it to borrow video from)")
        if "video_out" in last and last["video_out"] != last["out"]:
            raise SystemExit("last range: video_out must equal out")
        fps = rules["fps"]
        if windows_hit(first["in"], first["in"] + rules["guard_frames"], windows.get(first["clip"], []), fps):
            warnings.append("first frames of the reel sit on a blink or soft window")


def validate_audio(ranges, words_by_clip, rules, fps):
    errors, warnings = [], []
    kept = {name: set() for name in words_by_clip}
    for index, item in enumerate(ranges):
        words = words_by_clip.get(item["clip"], [])
        edge_in, edge_out = item["in"] / fps, item["out"] / fps
        for word_index, word in enumerate(words):
            if word["start"] + 0.005 < edge_in < word["end"] - 0.005:
                errors.append(f"range {index} {item['clip']}: in {edge_in:.2f} cuts inside '{word['word']}' {word['start']}-{word['end']}")
            if word["start"] + 0.005 < edge_out < word["end"] - 0.005:
                errors.append(f"range {index} {item['clip']}: out {edge_out:.2f} cuts inside '{word['word']}' {word['start']}-{word['end']}")
            if edge_in <= word["start"] < edge_in + rules["min_head_pad"] - 1e-6:
                warnings.append(f"range {index} {item['clip']}: head pad {word['start'] - edge_in:.3f}s before '{word['word']}' under {rules['min_head_pad']}")
            if edge_out - rules["min_tail_pad"] + 1e-6 < word["end"] <= edge_out:
                warnings.append(f"range {index} {item['clip']}: tail pad {edge_out - word['end']:.3f}s after '{word['word']}' under {rules['min_tail_pad']}")
            if word["start"] >= edge_in - 0.005 and word["end"] <= edge_out + 0.005:
                kept[item["clip"]].add(word_index)
    dropped = []
    for name, words in words_by_clip.items():
        if not any(item["clip"] == name for item in ranges):
            continue
        for word_index, word in enumerate(words):
            if word_index not in kept[name]:
                dropped.append(f"{name} '{word['word']}' {word['start']}-{word['end']}")
    return errors, warnings, dropped


def envelope_db(path, sample_rate=16000):
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
        check=True, capture_output=True,
    )
    samples = np.frombuffer(result.stdout, np.float32).astype(np.float64)
    hop, window = sample_rate // 100, sample_rate * 3 // 100
    padded = np.pad(samples, (window // 2, window // 2))
    squares = np.concatenate([[0.0], np.cumsum(padded ** 2)])
    starts = np.arange(max(1, 1 + (len(padded) - window) // hop)) * hop
    return 20 * np.log10(np.sqrt((squares[starts + window] - squares[starts]) / window) + 1e-10)


def edge_energy_warnings(ranges, clip_paths, fps, fade, margin_db):
    warnings = []
    envelopes = {}
    for index, item in enumerate(ranges):
        name = item["clip"]
        if name not in envelopes:
            envelope = envelope_db(clip_paths[name])
            envelopes[name] = (envelope, float(np.percentile(envelope, 5)))
        envelope, floor = envelopes[name]
        for label, start, end in (("in", item["in"] / fps, item["in"] / fps + fade), ("out", item["out"] / fps - fade, item["out"] / fps)):
            window = envelope[int(round(start * 100)):max(int(round(start * 100)) + 1, int(round(end * 100)) + 1)]
            if len(window) and float(window.max()) > floor + margin_db:
                warnings.append(f"range {index} {name}: speech energy inside the {label} fade ({label} {start if label == 'in' else end:.2f}s, peak {float(window.max()) - floor:.0f} dB over floor)")
    return warnings


def joint_report(ranges, words_by_clip, fps):
    rows = []
    for index in range(len(ranges) - 1):
        left, right = ranges[index], ranges[index + 1]
        left_words = [w for w in words_by_clip.get(left["clip"], []) if w["end"] <= left["out"] / fps + 0.005]
        right_words = [w for w in words_by_clip.get(right["clip"], []) if w["start"] >= right["in"] / fps - 0.005]
        tail = round(left["out"] / fps - left_words[-1]["end"], 3) if left_words else None
        lead = round(right_words[0]["start"] - right["in"] / fps, 3) if right_words else None
        rows.append({
            "joint": index,
            "after": left_words[-1]["word"] if left_words else None,
            "before": right_words[0]["word"] if right_words else None,
            "tail": tail, "lead": lead,
            "residual_gap": round(tail + lead, 3) if tail is not None and lead is not None else None,
            "video_offset_frames": left["joint_offset"],
        })
    return rows


def add_quotes(edl, words_by_clip, clip_paths):
    names_by_path = {path: name for name, path in clip_paths.items()}
    for entry in edl["ranges"]:
        name = names_by_path[entry.get("a_clip", entry["clip"])]
        inside = [w["word"] for w in words_by_clip.get(name, []) if entry["a_in"] - 0.005 <= (w["start"] + w["end"]) / 2 < entry["a_out"]]
        entry["quote"] = " ".join(inside)


def main():
    parser = argparse.ArgumentParser(description="Transcript to EDL: gap rules, padding, list-marker breath, blink-aware J/L offsets, frame-exact ranges.")
    parser.add_argument("--transcript", required=True, help="snap_words.py output (clips -> words with energy-snapped times)")
    parser.add_argument("--config", help="cutlist JSON: order, clips, rules, trim, exclude, or explicit ranges")
    parser.add_argument("--clips", nargs="*", help="clip files (stem must match the transcript clip names)")
    parser.add_argument("--exclusions", help="frame_metrics.py output for blink/soft windows")
    parser.add_argument("--out", required=True, help="edl.json")
    parser.add_argument("--report", help="plan report JSON (joints, warnings, dropped words)")
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--force", action="store_true", help="write the EDL even when a cut lands inside a word")
    args = parser.parse_args()
    args.config_data = load_json(args.config) if args.config else {}
    config = args.config_data
    transcript = load_json(args.transcript)
    fps = args.fps or config.get("fps") or transcript.get("fps") or 25
    rules = dict(DEFAULT_RULES, **(config.get("rules") or {}))
    rules["fps"] = fps
    rules["list_markers"] = [bare(marker) for marker in rules["list_markers"]]
    clip_paths = resolve_clips(args, config, transcript)
    words_by_clip = {name: clip["words"] for name, clip in transcript["clips"].items()}
    windows = exclusion_windows(args, transcript, rules)
    order = config.get("order") or [item["clip"] for item in config.get("ranges", [])] or list(transcript["clips"])
    missing = [name for name in dict.fromkeys(order) if name not in clip_paths]
    if missing:
        raise SystemExit(f"no media path for clips: {missing} (pass --clips or config.clips)")
    durations = {name: to_frame_floor(media_duration(clip_paths[name]), fps) for name in dict.fromkeys(order)}
    if config.get("ranges"):
        ranges = manual_ranges(config["ranges"], fps)
        mode = "manual"
    else:
        ranges = []
        for name in order:
            ranges.extend(auto_ranges(name, words_by_clip[name], rules, fps, durations[name], windows.get(name, []), (config.get("trim") or {}).get(name)))
        mode = "auto"
    warnings = []
    assign_offsets(ranges, windows, durations, rules, config.get("auto_offsets", True), warnings)
    errors, pad_warnings, dropped = validate_audio(ranges, words_by_clip, rules, fps)
    warnings.extend(pad_warnings)
    warnings.extend(edge_energy_warnings(ranges, clip_paths, fps, rules["fade"], rules["edge_energy_margin_db"]))
    edl = expand_to_edl(ranges, clip_paths, fps)
    add_quotes(edl, words_by_clip, clip_paths)
    report = {
        "mode": mode,
        "rules": rules,
        "ranges": [{"clip": r["clip"], "in": seconds(r["in"], fps), "out": seconds(r["out"], fps), "joint_offset_frames": r["joint_offset"], "beat": r.get("beat", "")} for r in ranges],
        "joints": joint_report(ranges, words_by_clip, fps),
        "errors": errors,
        "warnings": warnings,
        "dropped_words": dropped,
        "duration": edl["duration"],
    }
    for row in report["ranges"]:
        print(f"{row['clip']} {row['in']:.2f}-{row['out']:.2f} offset={row['joint_offset_frames']} {row['beat']}")
    for row in report["joints"]:
        print(f"  joint {row['joint']}: '{row['after']}' | '{row['before']}' tail={row['tail']} lead={row['lead']} residual={row['residual_gap']} video_offset={row['video_offset_frames']}f")
    for message in errors:
        print(f"ERROR {message}")
    for message in warnings:
        print(f"WARN {message}")
    for word in dropped:
        print(f"DROPPED {word}")
    print(f"{len(edl['ranges'])} EDL ranges, duration {edl['duration']:.2f}s")
    if args.report:
        write_json(args.report, report)
    if errors and not args.force:
        raise SystemExit("cut inside a word: fix the cutlist or pass --force")
    write_json(args.out, edl)


if __name__ == "__main__":
    main()
