import argparse
import json
import sys
from pathlib import Path

from anchors import AnchorError, load_json, resolve_tree

EASES = ("cut", "push", "creep")


def clip_config(clips, clip_name):
    for key, config in clips.items():
        if key in clip_name:
            return config
    raise SystemExit(f"no clip config matches segment clip {clip_name!r}; keys: {list(clips)}")


def visual_shots(cues):
    boundaries = sorted({0.0, *[round(cut, 3) for cut in cues["cuts"] if 0 < cut < cues["duration"]], round(cues["duration"], 3)})
    shots = []
    for start, end in zip(boundaries, boundaries[1:]):
        def overlap(segment):
            return min(end, segment["end"]) - max(start, segment["start"])
        main = max(cues["segments"], key=overlap)
        shots.append({"index": len(shots), "start": start, "end": end, "clip": main["clip"]})
    return shots


def shot_keys(shots, config):
    keys = []
    previous_clip = None
    state_index = 0
    overrides = config.get("shots", {})
    for shot in shots:
        clip = clip_config(config["clips"], shot["clip"])
        states = clip["states"]
        if shot["clip"] != previous_clip:
            state_index = int(clip.get("startState", 0)) % len(states)
        else:
            state_index = (state_index + 1) % len(states)
        previous_clip = shot["clip"]
        key = {
            "t": shot["start"],
            "scale": states[state_index],
            "tx": clip.get("tx", 0),
            "ty": clip.get("ty", 0),
            "ease": "cut",
            "shot": shot["index"],
            "clip": shot["clip"],
        }
        key.update(overrides.get(str(shot["index"]), {}))
        keys.append(key)
    return keys


def state_before(keys, time):
    current = None
    for key in sorted(keys, key=lambda item: item["t"]):
        if key["t"] <= time:
            current = key
    return current


def apply_moves(keys, moves):
    planned = list(keys)
    for move in sorted(moves, key=lambda item: item["t"]):
        if move.get("ease") not in EASES:
            raise SystemExit(f"move ease must be one of {EASES}: {move}")
        anchor = state_before(planned, move["t"]) or {"scale": 1.0, "tx": 0, "ty": 0}
        scale = anchor["scale"] + move["delta"] if "delta" in move else move.get("scale", anchor["scale"])
        planned.append({
            "t": round(move["t"], 3),
            "scale": round(scale, 4),
            "tx": move.get("tx", anchor["tx"]),
            "ty": move.get("ty", anchor["ty"]),
            "ease": move["ease"],
            "note": move.get("note", ""),
        })
    return sorted(planned, key=lambda item: (item["t"], 0 if item["ease"] == "cut" else 1))


def check(keys, max_scale, push_gap):
    warnings = []
    for key in keys:
        if key["scale"] > max_scale + 1e-9:
            warnings.append(f"t={key['t']}: scale {key['scale']} clamped to {max_scale}")
            key["scale"] = max_scale
        if key["scale"] < 1.0:
            warnings.append(f"t={key['t']}: scale {key['scale']} raised to 1.0")
            key["scale"] = 1.0
    for previous, current in zip(keys, keys[1:]):
        if "shot" in current and abs(previous["scale"] - current["scale"]) < 0.03:
            warnings.append(f"cut at t={current['t']}: scale change {previous['scale']} -> {current['scale']} is under 0.03")
    pushes = [key for key in keys if key["ease"] == "push"]
    for previous, current in zip(pushes, pushes[1:]):
        if current["t"] - previous["t"] < push_gap:
            warnings.append(f"pushes at t={previous['t']} and t={current['t']} are closer than {push_gap} s")
    return warnings


def main():
    parser = argparse.ArgumentParser(description="Build a Remotion camera plan (keys with cut/push/creep) from cues.json and a shot config.")
    parser.add_argument("--cues", required=True, help="cues.json on the output timeline")
    parser.add_argument("--shots", required=True, help="shot config: clip states, per-shot overrides, moves with @word anchors")
    parser.add_argument("--out", required=True, help="camera_plan.json output path")
    parser.add_argument("--max-scale", type=float, default=1.2)
    parser.add_argument("--push-gap", type=float, default=3.0)
    args = parser.parse_args()

    cues = load_json(args.cues)
    try:
        shots = resolve_tree(load_json(args.shots), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    keys = apply_moves(shot_keys(visual_shots(cues), shots), shots.get("moves", []))
    warnings = check(keys, args.max_scale, args.push_gap)
    Path(args.out).write_text(json.dumps({"keys": keys, "warnings": warnings}, indent=2) + "\n")
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"wrote {args.out} with {len(keys)} keys")


if __name__ == "__main__":
    main()
