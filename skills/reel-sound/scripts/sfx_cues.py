import argparse
import glob
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import (
    SAMPLE_RATE,
    db,
    decode_mono,
    ebur128,
    load_json,
    load_words,
    momentary_max,
    played_portion,
    sha256_file,
    write_json,
)

DUAL_MONO = "aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0"
LEVEL_CLASSES = {
    "pop": {"range": [-20.0, -14.0], "default": -17.0, "lu": -14.0, "lu_range": [-16.0, -12.0], "lu_ceiling": -4.0},
    "whoosh": {"range": [-18.0, -12.0], "default": -15.0, "lu": -17.0, "lu_range": [-19.0, -15.0], "lu_ceiling": -8.0},
    "impact": {"range": [-16.0, -10.0], "default": -13.0, "lu": -8.0, "lu_range": [-11.0, -6.0], "lu_ceiling": -3.0, "max_count": 3, "duck_bed_db": 2.5},
    "riser": {"range": [-24.0, -16.0], "default": -20.0, "lu": -18.0, "lu_range": [-20.0, -16.0], "lu_ceiling": -10.0, "max_count": 2},
    "tone": {"range": [-26.0, -18.0], "default": -22.0, "lu": -20.0, "lu_range": [-22.0, -18.0], "lu_ceiling": -12.0},
}
CATEGORY_LEVEL = {
    "pop": "pop", "click": "pop", "tick": "pop", "ding": "pop", "ui-blip": "pop", "glitch": "pop",
    "whoosh": "whoosh", "transition": "whoosh", "swell": "whoosh",
    "impact": "impact",
    "riser": "riser",
    "tone": "tone", "beep": "tone",
}
CATEGORY_ALIGN = {"whoosh": "peak", "transition": "peak", "swell": "peak", "riser": "peak"}
MASK_WINDOW = (-0.02, 0.06)
MASKING_LEVELS = {"pop", "whoosh", "impact"}
MIN_GAP_S = 0.08
ENVELOPE_WINDOW_S = 0.005
SWELL_WINDOW_S = 0.05
PEAK_REFINE_S = 0.01
PEAK_HOP_S = 0.001
GLINT_MAX_LU = -16.0
EVENT_KINDS = {"whoosh", "impact", "pop", "glint"}


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


def sliding_energy(samples, window_s, hop_s=PEAK_HOP_S):
    window = max(1, int(window_s * SAMPLE_RATE))
    hop = max(1, int(hop_s * SAMPLE_RATE))
    padded = np.pad(samples.astype(np.float64) ** 2, (window // 2, window - window // 2))
    cumulative = np.concatenate([[0.0], np.cumsum(padded)])
    starts = np.arange(0, len(samples), hop)
    return starts / SAMPLE_RATE, cumulative[starts + window] - cumulative[starts]


def swell_peak(samples):
    centres, coarse = sliding_energy(samples, SWELL_WINDOW_S)
    _, fine = sliding_energy(samples, PEAK_REFINE_S)
    around = np.abs(centres - centres[int(np.argmax(coarse))]) <= SWELL_WINDOW_S / 2
    return float(centres[np.flatnonzero(around)[int(np.argmax(fine[around]))]])


def measure_file(path):
    samples = decode_mono(path)
    fast, fast_step = envelope(samples, ENVELOPE_WINDOW_S)
    onset_index = int(np.argmax(fast >= fast.max() * 10 ** (-6 / 20)))
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) if len(samples) > 1 else np.zeros(1)
    freqs = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    return {
        "duration_s": round(len(samples) / SAMPLE_RATE, 3),
        "peak_dbfs": round(float(db(np.abs(samples).max())), 2),
        "onset_s": round(onset_index * fast_step, 3),
        "peak_s": round(swell_peak(samples), 3),
        "momentary_max_lufs": round(momentary_max(samples), 2),
        "centroid_hz": round(float((spectrum * freqs).sum() / (spectrum.sum() + 1e-12))),
        "sha256": sha256_file(path),
    }


def played_levels(path, trim_start, max_dur, fade_out):
    portion = played_portion(decode_mono(path), trim_start, max_dur, fade_out)
    if not len(portion):
        return -120.0, float("-inf")
    return round(float(db(np.abs(portion).max())), 2), round(momentary_max(portion), 2)


def align_offset(metrics, mode, entry):
    if entry.get("anchor_s") is not None and mode == entry.get("align"):
        return float(entry["anchor_s"])
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
    return [(w["start"], w["text"]) for w in load_words(words_path)]


def event_times(patterns):
    events = {}
    for pattern in patterns or []:
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise SystemExit(f"--events {pattern}: no file matches")
        for path in paths:
            doc = load_json(path)
            beat = doc.get("beat") or Path(path).stem
            for event in doc.get("events", []):
                kind = event.get("kind")
                if kind not in EVENT_KINDS:
                    raise SystemExit(f"{path}: event {event.get('id')} has kind {kind}, expected one of {sorted(EVENT_KINDS)}")
                events[f"{beat}.{event['id']}"] = {"t": float(event["t"]), "kind": kind, "source": path}
    return events


def normalise_word(text):
    return "".join(ch for ch in text.lower() if ch.isalnum())


def find_word(onsets, word, occurrence):
    target = normalise_word(word)
    matches = [t for t, text in onsets if normalise_word(text) == target]
    if len(matches) < occurrence:
        return None
    return matches[occurrence - 1]


def resolve_time(cue, beats, onsets, events):
    if cue.get("event"):
        if cue["event"] not in events:
            raise SystemExit(f"cue {cue['id']}: event {cue['event']} is not in the --events files; render the 3D beat first (reel-3d render3d.py) or fix the id")
        return events[cue["event"]]["t"] + cue.get("event_offset", 0.0), "event"
    if cue.get("word") and onsets:
        found = find_word(onsets, cue["word"], cue.get("occurrence", 1))
        if found is not None:
            return found + cue.get("word_offset", 0.0), "word"
    if cue.get("beat") not in beats:
        raise SystemExit(f"cue {cue['id']}: beat {cue.get('beat')} has no time")
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


def lu_gain(cue, level, level_class, event, voice, played_peak, played_mmax, warnings):
    target = float(cue.get("level_lu", level_class["lu"]))
    low, high = level_class["lu_range"]
    if "level_lu" in cue and not low <= target <= high:
        warnings.append(f"{cue['id']}: level_lu {target} is outside the {level} range {low} to {high} LU")
    if event and event["kind"] == "glint" and target > GLINT_MAX_LU:
        if "level_lu" in cue:
            warnings.append(f"{cue['id']}: glint cue lowered from {target} to {GLINT_MAX_LU} LU")
        target = GLINT_MAX_LU
    mix_gain = voice["target_i"] + target - played_mmax
    ceiling = float(cue.get("peak_ceiling_dbfs", level_class["lu_ceiling"]))
    capped = max(0.0, played_peak + mix_gain - ceiling)
    if capped > 0:
        warnings.append(f"{cue['id']}: peak ceiling {ceiling} dBFS caps the gain by {capped:.1f} dB, the cue sits at {target - capped:.1f} LU instead of {target}")
    return {
        "level_mode": "lu",
        "level_lu_target": target,
        "played_mmax_lufs": played_mmax,
        "peak_ceiling_dbfs": ceiling,
        "capped_db": round(capped, 2),
        "gain_db": round(mix_gain - capped - voice["gain_to_target_db"], 2),
        "mix_gain_db": round(mix_gain - capped, 2),
        "mix_peak_dbfs": round(played_peak + mix_gain - capped, 2),
    }


def peak_gain(cue, level, level_class, played_peak, warnings):
    target_peak = cue.get("peak_dbfs", level_class["default"])
    low, high = level_class["range"]
    if not low <= target_peak <= high:
        warnings.append(f"{cue['id']}: peak {target_peak} dBFS is outside the {level} range {low} to {high}")
    return {"level_mode": "peak", "peak_dbfs_target": target_peak, "gain_db": round(target_peak - played_peak, 2)}


def place(cue_doc, entries, beats_override, words_path, fps, max_nudge_frames, events, voice):
    beats = {**cue_doc.get("beats", {}), **(beats_override or {})}
    onsets = word_onsets(words_path)
    classes = {name: {**spec, **cue_doc.get("level_classes", {}).get(name, {})} for name, spec in LEVEL_CLASSES.items()}
    metrics_cache, rotation, last_used = {}, {}, {}
    placements, warnings = [], []
    nominal = {cue["id"]: resolve_time(cue, beats, onsets, events) for cue in cue_doc["cues"]}
    final_anchor = {}
    ordered_cues = [c for c in cue_doc["cues"] if not c.get("layer_of")] + [c for c in cue_doc["cues"] if c.get("layer_of")]
    for cue in ordered_cues:
        entry = choose_file(cue, entries, rotation, last_used)
        last_used[cue.get("category")] = entry["file"]
        metrics = metrics_cache.setdefault(entry["path"], measure_file(entry["path"]))
        level = cue.get("level") or CATEGORY_LEVEL.get(cue.get("category", entry["category"]), "pop")
        level_class = classes[level]
        mode = cue.get("align") or entry.get("align") or CATEGORY_ALIGN.get(cue.get("category", entry["category"]), "onset")
        anchor, source = nominal[cue["id"]]
        event = events.get(cue["event"]) if cue.get("event") else None
        nudged_frames = 0
        parent = cue.get("layer_of")
        if parent:
            if parent not in final_anchor:
                raise SystemExit(f"cue {cue['id']}: layer_of {parent} is not a top-level cue")
            anchor = final_anchor[parent] + (anchor - nominal[parent][0])
            source = f"layer:{parent}"
        elif event:
            if onsets and level in MASKING_LEVELS and not cue.get("allow_on_word") and masking_onset(anchor, onsets) is not None:
                warnings.append(f"{cue['id']}: 3D event {cue['event']} lands on a word onset; the cue stays on the picture, move the 3D land or set allow_on_word")
        elif onsets and level in MASKING_LEVELS and not cue.get("allow_on_word"):
            anchor, nudged_frames = avoid_consonant(anchor, onsets, fps, max_nudge_frames)
            if masking_onset(anchor, onsets) is not None:
                warnings.append(f"{cue['id']}: still on a word onset after a {max_nudge_frames}-frame nudge; move the visual or set allow_on_word")
        final_anchor[cue["id"]] = anchor
        offset = align_offset(metrics, mode, entry)
        start = anchor - offset
        trim_start = max(0.0, -start)
        played_peak, played_mmax = played_levels(entry["path"], trim_start, cue.get("max_dur"), cue.get("fade_out", 0.0))
        level_mode = cue.get("level_mode") or voice["mode"]
        if level_mode == "lu" and voice["integrated_lufs"] is None:
            raise SystemExit(f"cue {cue['id']}: level_mode lu needs --voice")
        gains = lu_gain(cue, level, level_class, event, voice, played_peak, played_mmax, warnings) if level_mode == "lu" else peak_gain(cue, level, level_class, played_peak, warnings)
        placements.append({
            "id": cue["id"],
            "visual": cue.get("visual", ""),
            "beat": cue.get("beat", ""),
            "event": cue.get("event"),
            "event_kind": event["kind"] if event else None,
            "time_source": source,
            "anchor_time": round(anchor, 4),
            "anchor_frame": round(anchor * fps),
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
            "license": entry.get("license"),
            "level": level,
            "file_peak_dbfs": played_peak,
            "file_duration_s": metrics["duration_s"],
            **gains,
            "duck_bed_db": cue.get("duck_bed_db", level_class.get("duck_bed_db", 0.0)),
            "layer_of": cue.get("layer_of"),
            "repeat_ok": bool(cue.get("repeat_ok")),
            "sha256": metrics["sha256"],
        })
        if trim_start > 0:
            warnings.append(f"{cue['id']}: {trim_start:.2f}s of the file falls before 0 and is trimmed")
    placements.sort(key=lambda p: (p["anchor_time"], p["layer_of"] is not None))
    return placements, warnings + rule_checks(placements, classes, cue_doc.get("density", {})) + event_checks(placements, events, fps)


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


def event_checks(placements, events, fps):
    problems = []
    by_event = {}
    for p in placements:
        if p["event"]:
            by_event.setdefault(p["event"], []).append(p)
    for key, event in sorted(events.items(), key=lambda item: item[1]["t"]):
        cues = by_event.get(key, [])
        land_frame = round(event["t"] * fps)
        if event["kind"] in ("impact", "whoosh") and not cues:
            problems.append(f"EVENT: {key} ({event['kind']} at {event['t']:.3f}s) has no cue")
        impacts = [p for p in cues if p["level"] == "impact"]
        if event["kind"] == "impact" and len(impacts) > 1:
            problems.append(f"RULE: {key} carries {len(impacts)} impacts, one impact per 3D land")
        for p in impacts:
            if p["anchor_frame"] != land_frame:
                problems.append(f"RULE: impact {p['id']} lands on frame {p['anchor_frame']}, the 3D land {key} is frame {land_frame}")
        if event["kind"] == "impact":
            whooshes = [p for p in placements if p["level"] == "whoosh" and p["layer_of"] in {i["id"] for i in impacts}]
            for p in whooshes:
                if p["anchor_frame"] != land_frame - 1:
                    problems.append(f"EVENT: whoosh {p['id']} peaks on frame {p['anchor_frame']}, one frame before the land {key} is {land_frame - 1}")
    return problems


def voice_reference(path, target_i, mode):
    if not path:
        if mode == "lu":
            raise SystemExit("--level-mode lu needs --voice")
        return {"mode": "peak", "integrated_lufs": None, "target_i": target_i, "gain_to_target_db": 0.0, "sha256": None}
    integrated = ebur128(path, DUAL_MONO)["integrated"]
    return {
        "mode": mode or "lu",
        "file": str(Path(path).resolve()),
        "sha256": sha256_file(path),
        "integrated_lufs": integrated,
        "target_i": target_i,
        "gain_to_target_db": round(target_i - integrated, 2),
    }


def inspect(entries, category):
    rows = [e for e in entries if not category or e["category"] == category]
    for entry in sorted(rows, key=lambda e: (e["category"], e["file"])):
        m = measure_file(entry["path"])
        anchor = f" anchor {entry['anchor_s']:.3f}s" if entry.get("anchor_s") is not None else ""
        print(f"{entry['category']:11s} {entry['file']:44s} dur {m['duration_s']:5.2f}s peak {m['peak_dbfs']:6.1f} M max {m['momentary_max_lufs']:6.1f} onset {m['onset_s']:5.3f}s swell {m['peak_s']:5.3f}s{anchor} centroid {m['centroid_hz']:5d} Hz  {entry.get('license', '')}")


def main():
    parser = argparse.ArgumentParser(description="Turn a beat, word or 3D-event anchored SFX cue list and an SFX library manifest into timed placements (attack-aligned, levelled in LU against the voice or by peak, variant-rotated), or inspect a library.")
    sub = parser.add_subparsers(dest="command", required=True)
    place_parser = sub.add_parser("place", help="resolve cues into placements")
    place_parser.add_argument("--cues", required=True, help="cue list json (beats map + cues)")
    place_parser.add_argument("--library", required=True, action="append", help="SFX manifest json listing files with category and licence (repeatable)")
    place_parser.add_argument("--beats", help="beat times that override the map inside the cue list: a json map of id to seconds, or a beat map with beats[{id, from}]")
    place_parser.add_argument("--words", help="words json (Caption[] with startMs, or cues.json words) for word anchors and consonant masking")
    place_parser.add_argument("--events", action="append", help="glob of reel-3d event files, e.g. '3d/*.json' (repeatable); cues with \"event\": \"<beatId>.<eventId>\" land on those times")
    place_parser.add_argument("--voice", help="the voice.wav the mix will use; enables LU levelling against its integrated loudness")
    place_parser.add_argument("--level-mode", choices=["lu", "peak"], help="lu: each cue's 400 ms momentary max sits a class offset under the voice (default when --voice is given); peak: class peak targets in dBFS")
    place_parser.add_argument("--target-i", type=float, default=-14.0, help="the loudness mix.py gains the voice to; used for the peak ceiling check in lu mode")
    place_parser.add_argument("--fps", type=float, help="frame rate for nudges (default: cue list fps or 25)")
    place_parser.add_argument("--max-nudge-frames", type=int, default=2)
    place_parser.add_argument("--allow-violations", action="store_true", help="write placements even when a RULE check fails")
    place_parser.add_argument("--out", required=True, help="placements json")
    inspect_parser = sub.add_parser("inspect", help="print timing and level metrics for library files")
    inspect_parser.add_argument("--library", required=True, action="append")
    inspect_parser.add_argument("--category")
    args = parser.parse_args()

    entries = [entry for path in args.library for entry in library_entries(path)]
    if args.command == "inspect":
        inspect(entries, args.category)
        return
    cue_doc = load_json(args.cues)
    beats_override = beat_times(args.beats) if args.beats else None
    fps = args.fps or cue_doc.get("fps", 25)
    voice = voice_reference(args.voice, args.target_i, args.level_mode)
    events = event_times(args.events)
    placements, warnings = place(cue_doc, entries, beats_override, args.words, fps, args.max_nudge_frames, events, voice)
    write_json(args.out, {"fps": fps, "level_mode": voice["mode"], "voice": voice, "events": events, "placements": placements, "warnings": warnings})
    if voice["integrated_lufs"] is not None:
        print(f"voice {voice['integrated_lufs']} LUFS (mix moves it {voice['gain_to_target_db']:+.2f} dB to {voice['target_i']}); level mode {voice['mode']}")
    for p in placements:
        layer = f" layer of {p['layer_of']}" if p["layer_of"] else ""
        nudge = f" nudged -{p['nudged_frames']}f" if p["nudged_frames"] else ""
        event = f" event {p['event']}" if p["event"] else ""
        level = f"{p['level_lu_target']:6.1f} LU  peak in mix {p['mix_peak_dbfs']:6.1f}" if p["level_mode"] == "lu" else f"{p['peak_dbfs_target']:6.1f} dBFS"
        print(f"{p['id']:5s} {p['anchor_time']:7.3f}s f{p['anchor_frame']:<5d} {p['level']:6s} {level} gain {p['gain_db']:+6.1f} align {p['align']}@{p['align_offset']:.3f} {Path(p['library_file']).name}{layer}{nudge}{event}")
    for w in warnings:
        print(w)
    if any(w.startswith("RULE") for w in warnings) and not args.allow_violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
