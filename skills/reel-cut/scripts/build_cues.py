import argparse
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import audio_segments, clip_key, load_json, video_segments, write_json


def bare(text):
    return re.sub(r"[^a-z0-9']", "", text.lower())


def face_box(metrics, name, frames):
    clip = metrics.get(name)
    if not clip:
        return None
    rows = clip["per_frame"]
    boxes = np.array([rows[f]["face"][:4] for f in frames if 0 <= f < len(rows) and rows[f]["face"]], dtype=np.float64)
    if not len(boxes):
        return None
    return {
        "cx": round(float(np.median(boxes[:, 0] + boxes[:, 2] / 2)), 1),
        "cy": round(float(np.median(boxes[:, 1] + boxes[:, 3] / 2)), 1),
        "w": round(float(np.median(boxes[:, 2])), 1),
        "h": round(float(np.median(boxes[:, 3])), 1),
    }


def keyword_onsets(words, keywords):
    tokens = [bare(word["text"]) for word in words]
    found, missing = {}, []
    for entry in keywords:
        phrase = entry if isinstance(entry, str) else entry["text"]
        wanted_occurrence = 1 if isinstance(entry, str) else int(entry.get("n", 1))
        target = [bare(token) for token in phrase.split() if bare(token)]
        hits = [i for i in range(len(tokens) - len(target) + 1) if tokens[i:i + len(target)] == target]
        if len(hits) < wanted_occurrence:
            missing.append(phrase)
            continue
        found[phrase] = round(words[hits[wanted_occurrence - 1]]["start"], 3)
    return found, missing


def speech_overlaps(words, start, end):
    return any(word["start"] < end and start < word["end"] for word in words)


def merge_windows(windows):
    merged = []
    for window in sorted(windows, key=lambda w: w["start"]):
        if merged and window["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], window["end"])
            if window["reason"] not in merged[-1]["reason"]:
                merged[-1]["reason"] += "; " + window["reason"]
        else:
            merged.append(dict(window))
    return merged


def main():
    parser = argparse.ArgumentParser(description="Write cues.json for Stage 2: shots with face boxes, cuts, words, keyword onsets, mandatory cover windows and forced punch times.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--words", required=True, help="words.out.json (corrected Caption[])")
    parser.add_argument("--frame-metrics", help="frame_metrics.py output in A-roll pixel space")
    parser.add_argument("--config", help="JSON {keywords: [phrase | {text, n}], cover: [{start, end, reason}], needs_punch: [{t, reason}]}")
    parser.add_argument("--micro-jump-frames", type=int, default=6, help="a cut inside one clip that skips this many source frames or fewer needs a scale change")
    parser.add_argument("--cover-hold-frames", type=int, default=5, help="a frozen-frame stretch this long or longer under speech must be covered by a full-frame graphic")
    parser.add_argument("--cover-pad-frames", type=int, default=1)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    edl = load_json(args.edl)
    fps = edl["fps"]
    config = load_json(args.config) if args.config else {}
    captions = load_json(args.words)
    words = [{"i": i, "text": c["text"].strip(), "start": round(c["startMs"] / 1000, 3), "end": round(c["endMs"] / 1000, 3)} for i, c in enumerate(captions)]
    metrics = load_json(args.frame_metrics)["clips"] if args.frame_metrics else {}
    shots = video_segments(edl)
    segments, cuts, punches, covers = [], [], [], []
    for index, shot in enumerate(shots):
        start, end = round(shot["out_start"] / fps, 3), round(shot["out_end"] / fps, 3)
        segment = {
            "index": index,
            "clip": Path(shot["clip"]).name,
            "start": start,
            "end": end,
            "src_in": round(shot["src_in"] / fps, 3),
            "src_out": round(shot["src_out"] / fps, 3),
            "face": face_box(metrics, clip_key(shot["clip"]), range(shot["src_in"], shot["src_out"])),
        }
        if shot["holds"]:
            segment["holds"] = [[round(a / fps, 3), round(b / fps, 3)] for a, b in shot["holds"]]
        segments.append(segment)
        if index:
            cuts.append(start)
            previous = shots[index - 1]
            skipped = shot["first"] - previous["last"] - 1
            if previous["clip"] == shot["clip"] and 0 < skipped <= args.micro_jump_frames:
                punches.append({"t": start, "reason": f"micro jump cut: {skipped} source frames skipped in one take; force a scale change"})
        for hold_start, hold_end in shot["holds"]:
            a, b = hold_start / fps, hold_end / fps
            if hold_end - hold_start >= args.cover_hold_frames and speech_overlaps(words, a, b):
                pad = args.cover_pad_frames / fps
                covers.append({"start": round(max(0.0, a - pad), 3), "end": round(min(edl["duration"], b + pad), 3), "reason": f"frozen frame under speech ({hold_end - hold_start} frames) hiding soft or blurred source frames"})
    for entry in config.get("cover", []):
        covers.append({"start": entry["start"], "end": entry["end"], "reason": entry.get("reason", "set in the cue config")})
    for entry in config.get("needs_punch", []):
        punches.append({"t": entry["t"], "reason": entry.get("reason", "set in the cue config")})
    keywords, missing = keyword_onsets(words, config.get("keywords", []))
    if missing:
        raise SystemExit(f"keywords not found in the words: {missing}")
    seen = set()
    unique_punches = []
    for punch in sorted(punches, key=lambda p: p["t"]):
        if punch["t"] not in seen:
            seen.add(punch["t"])
            unique_punches.append(punch)
    cues = {
        "duration": edl["duration"],
        "fps": fps,
        "segments": segments,
        "cuts": cuts,
        "audio_splices": [round(seg["out_start"] / fps, 3) for seg in audio_segments(edl)[1:]],
        "words": words,
        "keywords": keywords,
        "cover": merge_windows(covers),
        "needs_punch": unique_punches,
    }
    write_json(args.out, cues)
    print(f"{len(segments)} shots, cuts at {cuts}")
    print(f"needs_punch: {[(p['t'], p['reason']) for p in unique_punches]}")
    print(f"cover: {cues['cover']}")
    print(f"keywords: {keywords}")


if __name__ == "__main__":
    main()
