import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchors import AnchorError, load_json, resolve_tree

EASES = ("cut", "push", "creep", "hold")
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920


def clip_config(clips, clip_name):
    for key, config in clips.items():
        if key in clip_name:
            return config
    raise SystemExit(f"no clip config matches segment clip {clip_name!r}; keys: {list(clips)}")


def punch_times(cues, fps):
    times = []
    for entry in cues.get("needs_punch", []):
        if isinstance(entry, (int, float)):
            times.append(float(entry))
        elif isinstance(entry, dict) and "t" in entry:
            times.append(float(entry["t"]))
        else:
            raise SystemExit(f"cues.needs_punch entry must be a time or {{t}}: {entry!r}")
    times += [float(segment["start"]) for segment in cues["segments"] if segment.get("needs_punch")]
    return sorted({round(round(t * fps) / fps, 3) for t in times if 0 < t < cues["duration"]})


def visual_shots(cues, fps):
    cut_times = [round(cut, 3) for cut in cues["cuts"] if 0 < cut < cues["duration"]]
    forced = [t for t in punch_times(cues, fps) if all(abs(t - cut) * fps >= 1 for cut in cut_times)]
    boundaries = sorted({0.0, *cut_times, *forced, round(cues["duration"], 3)})
    shots = []
    for start, end in zip(boundaries, boundaries[1:]):
        def overlap(segment):
            return min(end, segment["end"]) - max(start, segment["start"])
        main = max(cues["segments"], key=overlap)
        shots.append({"index": len(shots), "start": start, "end": end, "clip": main["clip"], "face": main.get("face"), "needsPunch": start in forced})
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
        if shot["needsPunch"]:
            key["note"] = "needs_punch"
        key.update(overrides.get(str(shot["index"]), {}))
        keys.append(key)
    return keys


def ordered(keys):
    return sorted(keys, key=lambda item: (item["t"], 0 if "shot" in item else 1))


def state_before(keys, time, strictly=False):
    current = None
    for key in ordered(keys):
        if key["t"] < time or (not strictly and key["t"] <= time):
            current = key
    return current


def apply_moves(keys, moves):
    planned = list(keys)
    for move in sorted(moves, key=lambda item: item["t"]):
        if move.get("ease") not in EASES:
            raise SystemExit(f"move ease must be one of {EASES}: {move}")
        anchor = state_before(planned, move["t"]) or {"scale": 1.0, "tx": 0, "ty": 0}
        if move["ease"] == "hold":
            scale = anchor["scale"]
        elif "delta" in move:
            scale = anchor["scale"] + move["delta"]
        else:
            scale = move.get("scale", anchor["scale"])
        planned.append({
            "t": round(move["t"], 3),
            "scale": round(scale, 4),
            "tx": anchor["tx"] if move["ease"] == "hold" else move.get("tx", anchor["tx"]),
            "ty": anchor["ty"] if move["ease"] == "hold" else move.get("ty", anchor["ty"]),
            "ease": move["ease"],
            "note": move.get("note", ""),
            **({"relative": True} if "delta" in move and move["ease"] != "hold" else {}),
        })
    return ordered(planned)


def shift_relative_moves(keys, cut_key, change):
    later = [key for key in keys if key["t"] >= cut_key["t"] and key is not cut_key]
    for key in ordered(later):
        if "shot" in key:
            break
        if key.get("relative") or key["ease"] == "hold":
            key["scale"] = round(key["scale"] + change, 4)


def force_punches(keys, min_change, max_scale, punch_step):
    warnings = []
    for key in ordered(keys):
        if "shot" not in key or key["shot"] == 0:
            continue
        previous = state_before(keys, key["t"], strictly=True)
        if previous is None:
            continue
        if abs(previous["scale"] - key["scale"]) >= min_change:
            continue
        up = round(previous["scale"] + punch_step, 4)
        down = round(previous["scale"] - punch_step, 4)
        forced = up if up <= max_scale + 1e-9 else max(1.0, down)
        warnings.append(f"cut at t={key['t']}: scale {key['scale']} is within {min_change} of the previous {previous['scale']}, forced to {forced}")
        shift_relative_moves(keys, key, forced - key["scale"])
        key["scale"] = forced
        key["forced"] = True
    return warnings


def shot_face(shots, time):
    for shot in shots:
        if shot["start"] - 1e-6 <= time < shot["end"]:
            return shot.get("face")
    return shots[-1].get("face") if shots else None


def edge_limits(scale, face):
    extra = max(0.0, scale - 1.0)
    cx = face["cx"] if face else FRAME_WIDTH / 2
    cy = face["cy"] if face else FRAME_HEIGHT / 2
    return (-extra * (FRAME_WIDTH - cx), extra * cx), (-extra * (FRAME_HEIGHT - cy), extra * cy)


def check(keys, shots, max_scale, push_gap, min_change):
    warnings = []
    for key in keys:
        if key["scale"] > max_scale + 1e-9:
            warnings.append(f"t={key['t']}: scale {key['scale']} clamped to {max_scale}")
            key["scale"] = max_scale
        if key["scale"] < 1.0:
            warnings.append(f"t={key['t']}: scale {key['scale']} raised to 1.0")
            key["scale"] = 1.0
        face = shot_face(shots, key["t"])
        (tx_min, tx_max), (ty_min, ty_max) = edge_limits(key["scale"], face)
        for axis, value, low, high in (("tx", key["tx"], tx_min, tx_max), ("ty", key["ty"], ty_min, ty_max)):
            if value < low - 0.5 or value > high + 0.5:
                limit = high if value > 0 else low
                origin = (face or {}).get("cx" if axis == "tx" else "cy") or (FRAME_WIDTH / 2 if axis == "tx" else FRAME_HEIGHT / 2)
                needed = 1.0 + abs(value) / (origin if value > 0 else ((FRAME_WIDTH if axis == "tx" else FRAME_HEIGHT) - origin))
                warnings.append(
                    f"t={key['t']}: {axis} {value} exceeds the edge clamp {limit:.1f} at scale {key['scale']}; "
                    f"the render uses {limit:.1f} (scale {needed:.3f} would allow it)"
                )
    for previous, current in zip(keys, keys[1:]):
        if "shot" in current and current["shot"] > 0 and abs(previous["scale"] - current["scale"]) < min_change - 1e-9:
            warnings.append(f"cut at t={current['t']}: scale change {previous['scale']} -> {current['scale']} is under {min_change}")
    pushes = [key for key in keys if key["ease"] == "push"]
    for previous, current in zip(pushes, pushes[1:]):
        if current["t"] - previous["t"] < push_gap:
            warnings.append(f"pushes at t={previous['t']} and t={current['t']} are closer than {push_gap} s")
    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Build a Remotion camera plan (keys with cut/push/creep/hold) from cues.json and a shot config. "
        "Every cut and every cues.needs_punch time gets a punch-state change."
    )
    parser.add_argument("--cues", required=True, help="cues.json on the output timeline (optional needs_punch: [t | {t}])")
    parser.add_argument("--shots", required=True, help="shot config: clip states, per-shot overrides, moves with anchors")
    parser.add_argument("--out", required=True, help="camera_plan.json output path")
    parser.add_argument("--max-scale", type=float, default=1.2)
    parser.add_argument("--push-gap", type=float, default=3.0)
    parser.add_argument("--min-cut-change", type=float, default=0.03, help="smallest scale change accepted on a cut")
    parser.add_argument("--punch-step", type=float, default=0.06, help="scale change used when a cut has to be forced")
    args = parser.parse_args()

    cues = load_json(args.cues)
    fps = int(cues.get("fps", 25))
    try:
        config = resolve_tree(load_json(args.shots), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    shots = visual_shots(cues, fps)
    keys = apply_moves(shot_keys(shots, config), config.get("moves", []))
    warnings = force_punches(keys, args.min_cut_change, args.max_scale, args.punch_step)
    warnings += check(keys, shots, args.max_scale, args.push_gap, args.min_cut_change)
    Path(args.out).write_text(json.dumps({"keys": keys, "warnings": warnings}, indent=2) + "\n")
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"wrote {args.out} with {len(keys)} keys")


if __name__ == "__main__":
    main()
