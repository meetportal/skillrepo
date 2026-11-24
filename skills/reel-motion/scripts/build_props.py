import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from anchors import AnchorError, load_json, resolve_tree

MODES = {"talk", "card", "takeover", "hidden"}
EASES = {"cut", "push", "creep"}


def probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    numerator, denominator = stream["r_frame_rate"].split("/")
    return float(stream["duration"]), float(numerator) / float(denominator)


def relative_media_path(media, public_dir):
    media_path = Path(media).resolve()
    public_path = Path(public_dir).resolve()
    try:
        return media_path.relative_to(public_path).as_posix()
    except ValueError:
        sys.exit(f"{media_path} is not inside the public dir {public_path}")


def camera_keys(plan, duration, max_scale, problems):
    keys = plan["keys"] if isinstance(plan, dict) else plan
    cleaned = []
    for key in keys:
        if key["ease"] not in EASES:
            problems.append(f"camera key at {key['t']}: ease {key['ease']!r} invalid")
        if not 0 <= key["t"] <= duration:
            problems.append(f"camera key at {key['t']}: outside 0..{duration}")
        scale = min(max(float(key["scale"]), 1.0), max_scale)
        cleaned.append({"t": float(key["t"]), "scale": scale, "tx": float(key.get("tx", 0)), "ty": float(key.get("ty", 0)), "ease": key["ease"]})
    return sorted(cleaned, key=lambda item: item["t"])


def check_beats(beats, duration, problems):
    seen = set()
    for beat in beats:
        for field in ("id", "component", "from", "to"):
            if field not in beat:
                problems.append(f"beat {beat.get('id', '?')}: missing {field}")
        if beat.get("id") in seen:
            problems.append(f"beat id {beat['id']} duplicated")
        seen.add(beat.get("id"))
        if not 0 <= beat.get("from", -1) < beat.get("to", -1) <= duration + 1e-6:
            problems.append(f"beat {beat.get('id')}: from/to {beat.get('from')}..{beat.get('to')} invalid for duration {duration}")
        beat.setdefault("props", {})


def check_modes(modes, problems):
    for mode in modes:
        if mode["mode"] not in MODES:
            problems.append(f"caption mode {mode['mode']!r} invalid")
        if mode["from"] >= mode["to"]:
            problems.append(f"caption mode {mode['mode']} {mode['from']}..{mode['to']} empty")


def check_words(words, duration, problems):
    previous_start = -1
    for word in words:
        if word["startMs"] < previous_start:
            problems.append(f"word {word['text']!r} at {word['startMs']} ms is out of order")
        if word["endMs"] < word["startMs"]:
            problems.append(f"word {word['text']!r} ends before it starts")
        if word["endMs"] > duration * 1000 + 40:
            problems.append(f"word {word['text']!r} ends after the reel")
        previous_start = word["startMs"]


def main():
    parser = argparse.ArgumentParser(description="Merge cues, words, beatmap and camera plan into Remotion props for the Reel composition.")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--words", required=True, help="Remotion Caption[] on the output timeline")
    parser.add_argument("--beatmap", required=True, help="{beats, captionModes, accents}; @word/@cut anchors allowed")
    parser.add_argument("--camera", required=True, help="camera plan {keys:[{t,scale,tx,ty,ease}]}")
    parser.add_argument("--aroll", required=True, help="A-roll video file inside --public-dir")
    parser.add_argument("--public-dir", required=True, help="directory passed to remotion as --public-dir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-scale", type=float, default=1.2)
    parser.add_argument("--extra-sec", type=float, default=0.0, help="seconds appended after the A-roll (for example an end card)")
    args = parser.parse_args()

    cues = load_json(args.cues)
    try:
        beatmap = resolve_tree(load_json(args.beatmap), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    words = load_json(args.words)
    fps = int(cues.get("fps", 25))
    duration = float(cues["duration"]) + args.extra_sec
    problems = []

    aroll_duration, aroll_fps = probe_duration(args.aroll)
    if abs(aroll_fps - fps) > 0.01:
        problems.append(f"A-roll fps {aroll_fps} differs from cues fps {fps}")
    if abs(aroll_duration - float(cues["duration"])) > 1.0 / fps + 1e-6:
        print(f"warning: A-roll duration {aroll_duration:.3f} differs from cues duration {cues['duration']:.3f} by more than one frame")

    camera = camera_keys(load_json(args.camera), duration, args.max_scale, problems)
    beats = beatmap.get("beats", [])
    modes = beatmap.get("captionModes", [])
    check_beats(beats, duration, problems)
    check_modes(modes, problems)
    check_words(words, duration, problems)
    if problems:
        sys.exit("props invalid:\n  " + "\n  ".join(problems))

    props = {
        "aroll": relative_media_path(args.aroll, args.public_dir),
        "durationSec": round(duration, 3),
        "fps": fps,
        "cues": {
            "segments": [
                {"index": s["index"], "clip": s["clip"], "start": s["start"], "end": s["end"], "face": s.get("face")}
                for s in cues["segments"]
            ],
            "cuts": cues["cuts"],
        },
        "camera": camera,
        "captions": [
            {"text": w["text"], "startMs": w["startMs"], "endMs": w["endMs"], "timestampMs": w.get("timestampMs"), "confidence": w.get("confidence")}
            for w in words
        ],
        "captionModes": modes,
        "beats": beats,
        "accents": beatmap.get("accents", []),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(props, indent=1) + "\n")
    print(f"wrote {os.path.abspath(args.out)}: {len(words)} words, {len(beats)} beats, {len(camera)} camera keys, {duration:.2f} s")


if __name__ == "__main__":
    main()
