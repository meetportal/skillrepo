import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import audio_segments, bare, clip_key, load_json, video_segments, write_json


def output_words(edl, transcript):
    fps = edl["fps"]
    segments = audio_segments(edl)
    paths = {clip_key(seg["clip"]): seg["clip"] for seg in segments}
    placed = []
    for name, clip in transcript["clips"].items():
        path = paths.get(name)
        if not path:
            continue
        for source_index, word in enumerate(clip["words"]):
            middle = (word["start"] + word["end"]) / 2
            for seg in segments:
                if seg["clip"] != path:
                    continue
                src_start, src_end = seg["src_in"] / fps, seg["src_out"] / fps
                if src_start <= middle < src_end:
                    shift = seg["out_start"] / fps - src_start
                    start = max(word["start"], src_start) + shift
                    end = min(word["end"], src_end) + shift
                    placed.append({"text": word["word"], "start": start, "end": end, "clip": name, "source_index": source_index, "spoken": word["word"]})
                    break
    placed.sort(key=lambda item: item["start"])
    return placed


def find_matches(words, tokens):
    size = len(tokens)
    hits = []
    for index in range(len(words) - size + 1):
        if [bare(word["text"]) for word in words[index:index + size]] == tokens:
            hits.append(index)
    return hits


def replace_span(words, index, size, text):
    span = words[index:index + size]
    new_tokens = text.split()
    if not new_tokens:
        del words[index:index + size]
        return
    if len(new_tokens) == size:
        for word, token in zip(span, new_tokens):
            word["text"] = token
        return
    start, end = span[0]["start"], span[-1]["end"]
    edges = np.linspace(start, end, len(new_tokens) + 1)
    spoken = " ".join(word["spoken"] for word in span)
    replacement = [dict(span[0], text=token, start=float(a), end=float(b), spoken=spoken) for token, a, b in zip(new_tokens, edges[:-1], edges[1:])]
    words[index:index + size] = replacement


def apply_corrections(words, corrections):
    applied = []
    by_index = sorted([c for c in corrections if "index" in c], key=lambda c: -c["index"])
    for correction in by_index:
        size = correction.get("count", 1)
        before = " ".join(w["text"] for w in words[correction["index"]:correction["index"] + size])
        replace_span(words, correction["index"], size, correction["text"])
        applied.append({"index": correction["index"], "from": before, "to": correction["text"]})
    for correction in [c for c in corrections if "match" in c]:
        tokens = [bare(token) for token in correction["match"].split()]
        hits = find_matches(words, tokens)
        if "occurrence" in correction:
            hits = [hits[correction["occurrence"]]] if len(hits) > correction["occurrence"] else []
        for index in reversed(hits):
            before = " ".join(w["text"] for w in words[index:index + len(tokens)])
            replace_span(words, index, len(tokens), correction["text"])
            if before != correction["text"]:
                applied.append({"at": round(words[index]["start"] if index < len(words) else -1, 3), "from": before, "to": correction["text"]})
        if not hits and correction.get("required", False):
            raise SystemExit(f"correction did not match: {correction['match']}")
    return applied


def face_for_segment(metrics, name, src_in, src_out):
    clip = metrics.get(name)
    if not clip:
        return None
    boxes = [row["face"][:4] for row in clip["per_frame"][src_in:src_out] if row["face"]]
    if not boxes:
        return None
    boxes = np.array(boxes, dtype=np.float64)
    return {
        "cx": round(float(np.median(boxes[:, 0] + boxes[:, 2] / 2)), 1),
        "cy": round(float(np.median(boxes[:, 1] + boxes[:, 3] / 2)), 1),
        "w": round(float(np.median(boxes[:, 2])), 1),
        "h": round(float(np.median(boxes[:, 3])), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="EDL + snapped words + corrections -> Remotion Caption[] (words.out.json) and cues.json on the output timeline.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--corrections", help="JSON list (or {'corrections': [...]}) of {match|index, text}")
    parser.add_argument("--frame-metrics", help="frame_metrics.py output in A-roll pixel space (same rotation, no scaling)")
    parser.add_argument("--out-words", required=True)
    parser.add_argument("--out-cues", required=True)
    args = parser.parse_args()
    edl = load_json(args.edl)
    transcript = load_json(args.transcript)
    fps = edl["fps"]
    words = output_words(edl, transcript)
    corrections = load_json(args.corrections) if args.corrections else []
    if isinstance(corrections, dict):
        corrections = corrections.get("corrections", [])
    applied = apply_corrections(words, corrections)
    captions = []
    for word in words:
        start_ms, end_ms = int(round(word["start"] * 1000)), int(round(word["end"] * 1000))
        captions.append({"text": " " + word["text"], "startMs": start_ms, "endMs": end_ms, "timestampMs": int(round((start_ms + end_ms) / 2)), "confidence": None})
    metrics = load_json(args.frame_metrics)["clips"] if args.frame_metrics else {}
    segments = []
    for index, seg in enumerate(video_segments(edl)):
        segments.append({
            "index": index,
            "clip": Path(seg["clip"]).name,
            "start": round(seg["out_start"] / fps, 3),
            "end": round(seg["out_end"] / fps, 3),
            "face": face_for_segment(metrics, clip_key(seg["clip"]), seg["src_in"], seg["src_out"]),
        })
    cues = {
        "duration": edl["duration"],
        "fps": fps,
        "segments": segments,
        "cuts": [segment["start"] for segment in segments[1:]],
        "words": [{"i": i, "text": word["text"], "start": round(word["start"], 3), "end": round(word["end"], 3)} for i, word in enumerate(words)],
    }
    write_json(args.out_words, captions)
    write_json(args.out_cues, cues)
    for item in applied:
        print(f"corrected: {item}")
    print(f"{len(captions)} words, {len(segments)} video segments, cuts at {cues['cuts']}")
    print(" ".join(word["text"] for word in words))


if __name__ == "__main__":
    main()
