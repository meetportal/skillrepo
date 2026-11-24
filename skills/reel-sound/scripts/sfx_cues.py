import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import SAMPLE_RATE, db, decode_mono, load_json, write_json

LEVEL_CLASSES = {
    "pop": {"range": [-20.0, -14.0], "default": -17.0},
    "whoosh": {"range": [-18.0, -12.0], "default": -15.0},
    "impact": {"range": [-16.0, -10.0], "default": -13.0, "max_count": 3, "duck_bed_db": 2.5},
    "riser": {"range": [-24.0, -16.0], "default": -20.0, "max_count": 2},
    "tone": {"range": [-26.0, -18.0], "default": -22.0},
}
CATEGORY_LEVEL = {
    "pop": "pop", "click": "pop", "tick": "pop", "ding": "pop", "ui-blip": "pop", "glitch": "pop",
    "whoosh": "whoosh", "transition": "whoosh",
    "impact": "impact",
    "riser": "riser",
}
CATEGORY_ALIGN = {"whoosh": "peak", "transition": "peak", "riser": "peak"}
MASK_WINDOW = (-0.02, 0.06)
MASKING_LEVELS = {"pop", "whoosh", "impact"}
MIN_GAP_S = 0.08
ENVELOPE_WINDOW_S = 0.005
SWELL_WINDOW_S = 0.05


def library_entries(manifest_path):
    manifest = load_json(manifest_path)
    root = Path(manifest_path).resolve().parent / manifest.get("root", ".")
    entries = []
    for key in ("files", "bundled", "default_kit"):
        for entry in manifest.get(key, []):
            if entry.get("file") and entry.get("category") and (root / entry["file"]).exists():
                entries.append({**entry, "path": str((root / entry["file"]).resolve())})
    return entries


def envelope(samples, window_s):
    window = max(1, int(window_s * SAMPLE_RATE))
    padded = np.pad(samples.astype(np.float64) ** 2, (0, (-len(samples)) % window))
    return np.sqrt(padded.reshape(-1, window).mean(axis=1)), window / SAMPLE_RATE


def portion_peak_dbfs(path, trim_start, max_dur):
    samples = decode_mono(path)
    start = int(trim_start * SAMPLE_RATE)
    end = len(samples) if not max_dur else start + int(max_dur * SAMPLE_RATE)
    portion = samples[start:end]
    return round(float(db(np.abs(portion).max())), 2) if len(portion) else -120.0


def measure_file(path):
    samples = decode_mono(path)
    fast, fast_step = envelope(samples, ENVELOPE_WINDOW_S)
    slow, slow_step = envelope(samples, SWELL_WINDOW_S)
    onset_index = int(np.argmax(fast >= fast.max() * 10 ** (-6 / 20)))
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) if len(samples) > 1 else np.zeros(1)
    freqs = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    return {
        "duration_s": round(len(samples) / SAMPLE_RATE, 3),
        "peak_dbfs": round(float(db(np.abs(samples).max())), 2),
        "onset_s": round(onset_index * fast_step, 3),
        "peak_s": round((int(np.argmax(slow)) + 0.5) * slow_step, 3),
        "centroid_hz": round(float((spectrum * freqs).sum() / (spectrum.sum() + 1e-12))),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    }


def align_offset(metrics, mode):
    if mode == "start":
        return 0.0
    if mode == "end":
        return metrics["duration_s"]
    if mode == "peak":
        return metrics["peak_s"]
    return metrics["onset_s"]


def beat_times(path):
    data = load_json(path)
    if isinstance(data, dict) and isinstance(data.get("beats"), list):
        return {b["id"]: float(b.get("from", b.get("start"))) for b in data["beats"]}
    return {key: float(value) for key, value in data.items()}


def word_onsets(words_path):
    if not words_path:
        return []
    data = load_json(words_path)
    items = data["words"] if isinstance(data, dict) else data
    onsets = []
    for item in items:
        if "startMs" in item:
            onsets.append((item["startMs"] / 1000.0, item["text"].strip()))
        else:
            onsets.append((float(item["start"]), str(item["text"]).strip()))
    return onsets


def normalise_word(text):
    return "".join(ch for ch in text.lower() if ch.isalnum())


def find_word(onsets, word, occurrence):
    target = normalise_word(word)
    matches = [t for t, text in onsets if normalise_word(text) == target]
    if len(matches) < occurrence:
        return None
    return matches[occurrence - 1]


def resolve_time(cue, beats, onsets):
    if cue.get("word") and onsets:
        found = find_word(onsets, cue["word"], cue.get("occurrence", 1))
        if found is not None:
            return found + cue.get("word_offset", 0.0), "word"
    if cue["beat"] not in beats:
        raise SystemExit(f"cue {cue['id']}: beat {cue['beat']} has no time")
    return beats[cue["beat"]] + cue.get("offset", 0.0), "beat"


def masking_onset(time, onsets):
    return next((t for t, _ in onsets if MASK_WINDOW[0] <= time - t <= MASK_WINDOW[1]), None)


def avoid_consonant(anchor, onsets, fps, max_frames):
    hit = masking_onset(anchor, onsets)
    if hit is None:
        return anchor, 0
    for frames in range(1, max_frames + 1):
        candidate = hit - frames / fps
        if masking_onset(candidate, onsets) is None:
            return candidate, round((anchor - candidate) * fps)
    return hit - max_frames / fps, round((anchor - hit) * fps) + max_frames


def choose_file(cue, entries, rotation, last_used):
    if cue.get("file"):
        matches = [e for e in entries if e["file"] == cue["file"]]
        if not matches:
            raise SystemExit(f"cue {cue['id']}: file {cue['file']} is not in the library")
        return matches[0]
    pool_names = cue.get("files") or sorted(e["file"] for e in entries if e["category"] == cue["category"])
    pool = [e for name in pool_names for e in entries if e["file"] == name]
    if not pool:
        raise SystemExit(f"cue {cue['id']}: no library file for category {cue.get('category')}")
    key = tuple(e["file"] for e in pool)
    index = rotation.get(key, 0)
    choice = pool[index % len(pool)]
    if len(pool) > 1 and choice["file"] == last_used.get(cue.get("category")):
        index += 1
        choice = pool[index % len(pool)]
    rotation[key] = index + 1
    return choice


def place(cue_doc, entries, beats_override, words_path, fps, max_nudge_frames):
    beats = {**cue_doc.get("beats", {}), **(beats_override or {})}
    onsets = word_onsets(words_path)
    classes = {**LEVEL_CLASSES, **cue_doc.get("level_classes", {})}
    metrics_cache, rotation, last_used = {}, {}, {}
    placements, warnings = [], []
    nominal = {cue["id"]: resolve_time(cue, beats, onsets) for cue in cue_doc["cues"]}
    final_anchor = {}
    ordered_cues = [c for c in cue_doc["cues"] if not c.get("layer_of")] + [c for c in cue_doc["cues"] if c.get("layer_of")]
    for cue in ordered_cues:
        entry = choose_file(cue, entries, rotation, last_used)
        last_used[cue.get("category")] = entry["file"]
        metrics = metrics_cache.setdefault(entry["path"], measure_file(entry["path"]))
        level = cue.get("level") or CATEGORY_LEVEL.get(cue.get("category", entry["category"]), "pop")
        level_class = classes[level]
        target_peak = cue.get("peak_dbfs", level_class["default"])
        low, high = level_class["range"]
        if not low <= target_peak <= high:
            warnings.append(f"{cue['id']}: peak {target_peak} dBFS is outside the {level} range {low} to {high}")
        mode = cue.get("align") or CATEGORY_ALIGN.get(cue.get("category", entry["category"]), "onset")
        anchor, source = nominal[cue["id"]]
        nudged_frames = 0
        parent = cue.get("layer_of")
        if parent:
            if parent not in final_anchor:
                raise SystemExit(f"cue {cue['id']}: layer_of {parent} is not a top-level cue")
            anchor = final_anchor[parent] + (anchor - nominal[parent][0])
            source = f"layer:{parent}"
        elif onsets and level in MASKING_LEVELS and not cue.get("allow_on_word"):
            anchor, nudged_frames = avoid_consonant(anchor, onsets, fps, max_nudge_frames)
        final_anchor[cue["id"]] = anchor
        if onsets and not parent and level in MASKING_LEVELS and not cue.get("allow_on_word") and masking_onset(anchor, onsets) is not None:
            warnings.append(f"{cue['id']}: still on a word onset after a {max_nudge_frames}-frame nudge; move the visual or set allow_on_word")
        offset = align_offset(metrics, mode)
        start = anchor - offset
        trim_start = max(0.0, -start)
        played_peak = portion_peak_dbfs(entry["path"], trim_start, cue.get("max_dur")) if trim_start or cue.get("max_dur") else metrics["peak_dbfs"]
        placements.append({
            "id": cue["id"],
            "visual": cue.get("visual", ""),
            "beat": cue["beat"],
            "time_source": source,
            "anchor_time": round(anchor, 4),
            "nudged_frames": nudged_frames,
            "align": mode,
            "align_offset": round(offset, 4),
            "start": round(max(0.0, start), 4),
            "trim_start": round(trim_start, 4),
            "max_dur": cue.get("max_dur"),
            "fade_out": cue.get("fade_out", 0.0),
            "file": entry["path"],
            "library_file": entry["file"],
            "category": entry["category"],
            "level": level,
            "peak_dbfs_target": target_peak,
            "file_peak_dbfs": played_peak,
            "file_duration_s": metrics["duration_s"],
            "gain_db": round(target_peak - played_peak, 2),
            "duck_bed_db": cue.get("duck_bed_db", level_class.get("duck_bed_db", 0.0)),
            "layer_of": cue.get("layer_of"),
            "repeat_ok": bool(cue.get("repeat_ok")),
            "sha256": metrics["sha256"],
        })
        if trim_start > 0:
            warnings.append(f"{cue['id']}: {trim_start:.2f}s of the file falls before 0 and is trimmed")
    placements.sort(key=lambda p: (p["anchor_time"], p["layer_of"] is not None))
    return placements, warnings + rule_checks(placements, classes, cue_doc.get("density", {}))


def rule_checks(placements, classes, density):
    problems = []
    for level, spec in classes.items():
        count = sum(1 for p in placements if p["level"] == level)
        if "max_count" in spec and count > spec["max_count"]:
            problems.append(f"RULE: {count} {level} events, max is {spec['max_count']}")
    events = [p for p in placements if not p["layer_of"]]
    low, high = density.get("min_events", 15), density.get("max_events", 30)
    if not low <= len(events) <= high:
        problems.append(f"RULE: {len(events)} SFX events, the band is {low} to {high}")
    ordered = sorted(events, key=lambda p: p["anchor_time"])
    for a, b in zip(ordered, ordered[1:]):
        if b["anchor_time"] - a["anchor_time"] < MIN_GAP_S:
            problems.append(f"RULE: {a['id']} and {b['id']} land {1000 * (b['anchor_time'] - a['anchor_time']):.0f} ms apart; layer them (layer_of) or move one")
    by_category = {}
    for p in sorted(placements, key=lambda p: p["anchor_time"]):
        previous = by_category.get(p["category"])
        if previous and not p["repeat_ok"] and previous["library_file"] == p["library_file"] and p["anchor_time"] - previous["anchor_time"] < 10.0:
            problems.append(f"VARIETY: {previous['id']} and {p['id']} reuse {p['library_file']} within 10 s")
        by_category[p["category"]] = p
    return problems


def inspect(entries, category):
    rows = [e for e in entries if not category or e["category"] == category]
    for entry in sorted(rows, key=lambda e: (e["category"], e["file"])):
        m = measure_file(entry["path"])
        print(f"{entry['category']:11s} {entry['file']:58s} dur {m['duration_s']:5.2f}s peak {m['peak_dbfs']:6.1f} onset {m['onset_s']:5.3f}s swell {m['peak_s']:5.3f}s centroid {m['centroid_hz']:5d} Hz  {entry.get('license', '')}")


def main():
    parser = argparse.ArgumentParser(description="Turn a beat-anchored SFX cue list and an SFX library manifest into timed placements (attack-aligned, gain-staged, variant-rotated), or inspect a library.")
    sub = parser.add_subparsers(dest="command", required=True)
    place_parser = sub.add_parser("place", help="resolve cues into placements")
    place_parser.add_argument("--cues", required=True, help="cue list json (beats map + cues)")
    place_parser.add_argument("--library", required=True, help="SFX manifest json listing files with category and licence")
    place_parser.add_argument("--beats", help="beat times that override the map inside the cue list: a json map of id to seconds, or a beat map with beats[{id, from}]")
    place_parser.add_argument("--words", help="words json (Caption[] with startMs, or cues.json words) for word anchors and consonant masking")
    place_parser.add_argument("--fps", type=float, help="frame rate for nudges (default: cue list fps or 25)")
    place_parser.add_argument("--max-nudge-frames", type=int, default=2)
    place_parser.add_argument("--allow-violations", action="store_true", help="write placements even when a RULE check fails")
    place_parser.add_argument("--out", required=True, help="placements json")
    inspect_parser = sub.add_parser("inspect", help="print timing and level metrics for library files")
    inspect_parser.add_argument("--library", required=True)
    inspect_parser.add_argument("--category")
    args = parser.parse_args()

    entries = library_entries(args.library)
    if args.command == "inspect":
        inspect(entries, args.category)
        return
    cue_doc = load_json(args.cues)
    beats_override = beat_times(args.beats) if args.beats else None
    fps = args.fps or cue_doc.get("fps", 25)
    placements, warnings = place(cue_doc, entries, beats_override, args.words, fps, args.max_nudge_frames)
    write_json(args.out, {"fps": fps, "placements": placements, "warnings": warnings})
    for p in placements:
        layer = f" layer of {p['layer_of']}" if p["layer_of"] else ""
        nudge = f" nudged -{p['nudged_frames']}f" if p["nudged_frames"] else ""
        print(f"{p['id']:5s} {p['anchor_time']:7.3f}s {p['level']:6s} {p['peak_dbfs_target']:6.1f} dBFS gain {p['gain_db']:+6.1f} align {p['align']}@{p['align_offset']:.3f} {Path(p['library_file']).name}{layer}{nudge}")
    for w in warnings:
        print(w)
    if any(w.startswith("RULE") for w in warnings) and not args.allow_violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
