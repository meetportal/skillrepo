import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import audio_segments, clip_key, load_json, write_json


def output_words(edl, transcript):
    fps = edl["fps"]
    segments = audio_segments(edl)
    paths = {clip_key(seg["clip"]): seg["clip"] for seg in segments}
    placed = []
    for name, clip in transcript["clips"].items():
        path = paths.get(name)
        if not path:
            continue
        for word in clip["words"]:
            middle = (word["start"] + word["end"]) / 2
            for seg in segments:
                if seg["clip"] != path:
                    continue
                src_start, src_end = seg["src_in"] / fps, seg["src_out"] / fps
                if src_start <= middle < src_end:
                    shift = seg["out_start"] / fps - src_start
                    placed.append({"text": word["word"], "start": max(word["start"], src_start) + shift, "end": min(word["end"], src_end) + shift})
                    break
    placed.sort(key=lambda item: item["start"])
    return placed


def main():
    parser = argparse.ArgumentParser(description="EDL + aligned source words -> Remotion Caption[] on the output timeline. Timing only: the spoken text is kept as transcribed; caption text is corrected later by reel-captions.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--transcript", required=True, help="align_words.py output (source time)")
    parser.add_argument("--out", required=True, help="words.retimed.json")
    args = parser.parse_args()
    edl = load_json(args.edl)
    words = output_words(edl, load_json(args.transcript))
    captions = []
    for word in words:
        start_ms, end_ms = int(round(word["start"] * 1000)), int(round(word["end"] * 1000))
        captions.append({"text": " " + word["text"], "startMs": start_ms, "endMs": end_ms, "timestampMs": int(round((start_ms + end_ms) / 2)), "confidence": None})
    write_json(args.out, captions)
    print(f"{len(captions)} words on the output timeline ({edl['duration']:.2f}s)")
    print(" ".join(word["text"] for word in words))


if __name__ == "__main__":
    main()
