import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchors import AnchorError, load_json, resolve_tree

MODES = ("talk", "card", "takeover", "hidden")


def caption_modes(beats, duration):
    windows = []
    for beat in beats:
        mode = beat.get("mode", "talk")
        if mode not in MODES:
            raise SystemExit(f"beat {beat['id']}: mode {mode!r} not in {MODES}")
        if mode != "talk":
            windows.append((beat.get("modeFrom", beat["from"]), beat.get("modeTo", beat["to"]), mode))
    points = sorted({0.0, duration, *[w[0] for w in windows], *[w[1] for w in windows]})
    modes = []
    for start, end in zip(points, points[1:]):
        middle = (start + end) / 2
        active = [w[2] for w in windows if w[0] <= middle < w[1]]
        mode = active[-1] if active else "talk"
        if modes and modes[-1]["mode"] == mode and abs(modes[-1]["to"] - start) < 1e-6:
            modes[-1]["to"] = end
        else:
            modes.append({"from": round(start, 3), "to": round(end, 3), "mode": mode})
    return modes


def main():
    parser = argparse.ArgumentParser(description="Resolve a beat map source (anchors, per-beat caption mode) into beatmap.json with captionModes.")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--input", required=True, help="beat map source: {beats:[{id, component, mode, from, to, props, modeFrom?, modeTo?}], accents, topLogo?}")
    parser.add_argument("--out", required=True)
    parser.add_argument("--extra-sec", type=float, default=0.0, help="seconds after the A-roll covered by beats (end card)")
    args = parser.parse_args()

    cues = load_json(args.cues)
    try:
        source = resolve_tree(load_json(args.input), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    beats = source["beats"]
    for beat in beats:
        if beat["from"] >= beat["to"]:
            sys.exit(f"beat {beat['id']}: from {beat['from']} is not before to {beat['to']}")
    duration = cues["duration"] + args.extra_sec
    beatmap = {
        "beats": beats,
        "captionModes": source.get("captionModes") or caption_modes(beats, duration),
        "accents": source.get("accents", []),
    }
    if "topLogo" in source:
        beatmap["topLogo"] = source["topLogo"]
    Path(args.out).write_text(json.dumps(beatmap, indent=2) + "\n")
    for beat in beats:
        print(f"{beat['id']:8s} {beat['component']:16s} {beat['from']:6.2f}-{beat['to']:6.2f}  {beat.get('mode', 'talk')}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
