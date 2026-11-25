import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchors import AnchorError, load_json, resolve_document
from build_props import check_beat_times
from resolve_beatmap import caption_modes


def main():
    parser = argparse.ArgumentParser(
        description="Copy a props.json with its beats replaced by the given beat(s), for previewing one component over the real A-roll."
    )
    parser.add_argument("--props", required=True, help="a complete props.json (camera, captions, A-roll)")
    parser.add_argument("--beat", required=True, help="JSON with one beat {id, component, mode, from, to, props} or a list of beats; times inside props are seconds from the beat's from")
    parser.add_argument("--cues", help="cues.json, needed when the beat uses anchors")
    parser.add_argument("--out", required=True)
    parser.add_argument("--guides", action="store_true", help="overlay the layout zones and reserved areas")
    args = parser.parse_args()

    props = load_json(args.props)
    beats = load_json(args.beat)
    beats = beats if isinstance(beats, list) else [beats]
    if args.cues:
        try:
            beats = resolve_document({"beats": beats}, load_json(args.cues))["beats"]
        except AnchorError as error:
            sys.exit(f"anchor error: {error}")
    for beat in beats:
        for field in ("id", "component", "from", "to"):
            if field not in beat:
                sys.exit(f"beat is missing {field}: {beat}")
        if not isinstance(beat["from"], (int, float)) or not isinstance(beat["to"], (int, float)):
            sys.exit(f"beat {beat['id']}: from/to must be seconds (pass --cues to resolve anchors)")
        if not 0 <= beat["from"] < beat["to"] <= props["durationSec"] + 1e-6:
            sys.exit(f"beat {beat['id']}: {beat['from']}..{beat['to']} outside 0..{props['durationSec']}")
        beat.setdefault("props", {})
    problems = []
    check_beat_times(beats, problems)
    if problems:
        sys.exit("beat props invalid:\n  " + "\n  ".join(problems))
    props["beats"] = beats
    props["captionModes"] = caption_modes(beats, props["durationSec"], props["fps"])
    props["guides"] = args.guides
    Path(args.out).write_text(json.dumps(props, indent=1) + "\n")
    for beat in beats:
        start, end = round(beat["from"] * props["fps"]), round(beat["to"] * props["fps"])
        print(f"{beat['id']} {beat['component']} {beat['from']:.2f}-{beat['to']:.2f} s, frames {start}-{end - 1}, first frame still {start / props['fps']:.2f} s, entry still {(start + 4) / props['fps']:.2f} s, exit still {(end - 2) / props['fps']:.2f} s")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
