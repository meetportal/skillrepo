import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchors import AnchorError, load_json, resolve_tree

EASES = ("cut", "push", "creep", "hold", "kick", "glide")
MOVES = ("push", "glide", "creep")
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920
CORNER_RADIUS = math.hypot(FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
DEFAULT_MAX_SCALE = 1.2
MAX_SCALE_LIMIT = 1.3
PUSH_FRAMES = 8
PUSH_EASE = (0.16, 1.0, 0.3, 1.0)
CREEP_EASE = (0.37, 0.0, 0.63, 1.0)
KICK_DEFAULTS = {"px": 4.5, "frames": 7, "rollDeg": 0.2, "angleDeg": 60.0}
GLIDE_FRAMES = 18
GLIDE_RANGE = (12, 24)
CREEP_MIN_SHOT_SEC = 2.0
CREEP_MIN_AMOUNT = 0.02


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


def state_keys(keys):
    return [key for key in keys if key["ease"] != "kick"]


def state_before(keys, time, strictly=False):
    current = None
    for key in ordered(state_keys(keys)):
        if key["t"] < time or (not strictly and key["t"] <= time):
            current = key
    return current


def frame_of(seconds, fps):
    return math.floor(seconds * fps + 0.5)


def kick_params(move):
    params = {name: move.get(name, default) for name, default in KICK_DEFAULTS.items()}
    params["frames"] = int(params["frames"])
    if not 0 <= params["px"] <= 12 or not 2 <= params["frames"] <= 12 or not 0 <= params["rollDeg"] <= 1:
        raise SystemExit(f"kick needs px 0..12, frames 2..12, rollDeg 0..1: {move}")
    return params


def apply_moves(keys, moves):
    planned = list(keys)
    for move in sorted(moves, key=lambda item: item["t"]):
        if move.get("ease") not in EASES or move.get("ease") == "cut":
            raise SystemExit(f"move ease must be one of {EASES[1:]}: {move}")
        anchor = state_before(planned, move["t"]) or {"scale": 1.0, "tx": 0, "ty": 0}
        copies = move["ease"] in ("hold", "kick")
        if copies:
            scale = anchor["scale"]
        elif "delta" in move:
            scale = anchor["scale"] + move["delta"]
        else:
            scale = move.get("scale", anchor["scale"])
        key = {
            "t": round(move["t"], 3),
            "scale": round(scale, 4),
            "tx": anchor["tx"] if copies else move.get("tx", anchor["tx"]),
            "ty": anchor["ty"] if copies else move.get("ty", anchor["ty"]),
            "ease": move["ease"],
            "note": move.get("note", ""),
            **({"relative": True} if "delta" in move and not copies else {}),
        }
        if move["ease"] == "kick":
            key.update(kick_params(move))
        if move["ease"] == "glide":
            frames = int(move.get("frames", GLIDE_FRAMES))
            if not GLIDE_RANGE[0] <= frames <= GLIDE_RANGE[1]:
                raise SystemExit(f"glide frames must be {GLIDE_RANGE[0]}..{GLIDE_RANGE[1]}: {move}")
            key["frames"] = frames
        planned.append(key)
    return ordered(planned)


def shift_relative_moves(keys, cut_key, change):
    later = [key for key in keys if key["t"] >= cut_key["t"] and key is not cut_key]
    for key in ordered(later):
        if "shot" in key:
            break
        if key.get("relative") or key["ease"] in ("hold", "kick"):
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
        options = [value for value in (up, down) if 1.0 - 1e-9 <= value <= max_scale + 1e-9]
        following = next((other for other in ordered(keys) if "shot" in other and other["t"] > key["t"] + 1e-9), None)

        def clashes(value):
            if following is None:
                return False
            last = state_before(keys, following["t"], strictly=True)
            end = value if last is key else last["scale"] + (value - key["scale"] if last.get("relative") or last["ease"] in ("hold", "kick") else 0)
            return abs(end - following["scale"]) < min_change - 1e-9

        forced = min(options, key=lambda value: (clashes(value), abs(value - key["scale"]), -value)) if options else (up if up <= max_scale + 1e-9 else max(1.0, down))
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


def shot_at(shots, time):
    for shot in shots:
        if shot["start"] - 1e-6 <= time < shot["end"] - 1e-6:
            return shot
    return shots[-1] if shots else None


def shot_cut_key(keys, shot):
    return next((key for key in keys if key.get("shot") == shot["index"]), None)


def next_cut_key(keys, shot):
    return next((key for key in ordered(keys) if "shot" in key and key["t"] >= shot["end"] - 1e-6), None)


def creep_options(base, amount, max_scale, avoid, min_change):
    options = []
    for sign in (1, -1):
        reach = min(amount, max_scale - base) if sign > 0 else min(amount, base - 1.0)
        if reach <= 1e-9:
            continue
        delta = reach
        if avoid is not None:
            low, high = avoid - min_change - base, avoid + min_change - base
            end = sign * delta
            if low + 1e-9 < end < high - 1e-9:
                edge = low if sign > 0 else high
                delta = abs(edge) if sign * edge > 1e-9 else 0.0
        if delta > 1e-9:
            options.append(round(sign * delta, 4))
    return options


def creep_target(base, amount, max_scale, avoid=None, min_change=0.0):
    options = [delta for delta in creep_options(base, amount, max_scale, avoid, min_change) if abs(delta) >= CREEP_MIN_AMOUNT - 1e-9]
    if not options:
        return None
    away = 1 if avoid is None or base >= avoid else -1
    best = max(options, key=lambda delta: (abs(delta) >= amount - 1e-9, (delta > 0) == (away > 0), abs(delta)))
    return round(base + best, 4)


def auto_creep(keys, shots, amount, max_scale, fps, min_change):
    added = []
    notes = []
    if amount <= 0:
        return added, notes
    for shot in shots:
        if shot["end"] - shot["start"] < CREEP_MIN_SHOT_SEC - 1e-9:
            continue
        inside = [key for key in keys if shot["start"] - 1e-6 <= key["t"] < shot["end"] - 1e-6 and "shot" not in key]
        if any(key["ease"] in MOVES for key in inside):
            continue
        cut_key = shot_cut_key(keys, shot)
        if cut_key is None:
            continue
        following = next_cut_key(keys, shot)
        target = creep_target(cut_key["scale"], amount, max_scale, following["scale"] if following else None, min_change)
        if target is None:
            notes.append(f"auto creep skipped on the shot at t={shot['start']}: no room between 1.0, {max_scale} and the next cut")
            continue
        key = {
            "t": round(shot["start"] + 1 / fps, 3),
            "scale": target,
            "tx": cut_key["tx"],
            "ty": cut_key["ty"],
            "ease": "creep",
            "note": "auto creep",
            "relative": True,
            "auto": True,
            "shotIndex": shot["index"],
        }
        keys.append(key)
        added.append(key)
    keys.sort(key=lambda item: (item["t"], 0 if "shot" in item else 1))
    return added, notes


def refit_auto_creeps(keys, shots, amount, max_scale, min_change):
    notes = []
    for key in list(keys):
        if not key.get("auto"):
            continue
        shot = shots[key["shotIndex"]]
        cut_key = shot_cut_key(keys, shot)
        if cut_key is None:
            continue
        following = next_cut_key(keys, shot)
        target = creep_target(cut_key["scale"], amount, max_scale, following["scale"] if following else None, min_change)
        if target is None:
            notes.append(f"auto creep at t={key['t']}: removed after the forced punches, no room left")
            keys.remove(key)
        elif abs(target - key["scale"]) > 1e-9:
            notes.append(f"auto creep at t={key['t']}: retargeted {key['scale']} -> {target} after the forced punches")
            key["scale"] = target
    return notes


def forced_share_warning(keys):
    cuts = [key for key in keys if "shot" in key and key["shot"] > 0]
    forced = [key for key in cuts if key.get("forced")]
    if cuts and len(forced) * 2 > len(cuts):
        return [f"{len(forced)} of {len(cuts)} cuts were forced: the clip states do not alternate enough; set states or per-shot scales so cuts change by the min cut change on their own"]
    return []


def bezier_at(x, curve):
    x1, y1, x2, y2 = curve
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(60):
        t = (low + high) / 2
        value = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
        if value < x:
            low = t
        else:
            high = t
    t = (low + high) / 2
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3


def smootherstep(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def peak_step(ease, frames):
    frames = max(1, int(frames))
    return max(abs(ease((n + 1) / frames) - ease(n / frames)) for n in range(frames))


def kick_signal(n, frames):
    if n < 0 or n >= frames:
        return 0.0
    return (1 if n % 2 == 0 else -1) * (1 - n / frames) ** 1.5


def move_speeds(keys, fps, totals_end):
    rows = []
    timeline = ordered(state_keys(keys))
    for index, key in enumerate(timeline):
        if key["ease"] not in MOVES:
            continue
        before = state_before(keys, key["t"], strictly=True) or key
        distance = CORNER_RADIUS * abs(key["scale"] - before["scale"]) + math.hypot(key["tx"] - before["tx"], key["ty"] - before["ty"])
        if key["ease"] == "push":
            frames = PUSH_FRAMES
            step = peak_step(lambda u: bezier_at(u, PUSH_EASE), frames)
        elif key["ease"] == "glide":
            frames = key.get("frames", GLIDE_FRAMES)
            step = peak_step(smootherstep, frames)
        else:
            following = timeline[index + 1]["t"] if index + 1 < len(timeline) else totals_end
            frames = max(1, frame_of(following, fps) - frame_of(key["t"], fps))
            step = peak_step(lambda u: bezier_at(u, CREEP_EASE), frames)
        rows.append({"t": key["t"], "ease": key["ease"], "change": round(key["scale"] - before["scale"], 4), "frames": frames, "peak": distance * step})
    for key in keys:
        if key["ease"] != "kick":
            continue
        reach = key["px"] + CORNER_RADIUS * math.radians(key["rollDeg"])
        step = max(abs(kick_signal(n, key["frames"]) - kick_signal(n - 1, key["frames"])) for n in range(key["frames"] + 1))
        rows.append({"t": key["t"], "ease": "kick", "change": 0.0, "frames": key["frames"], "peak": reach * step})
    return sorted(rows, key=lambda row: row["t"])


def translate_headroom(state, face):
    (tx_min, tx_max), (ty_min, ty_max) = edge_limits(state["scale"], face)
    return min(tx_max - state["tx"], state["tx"] - tx_min, ty_max - state["ty"], state["ty"] - ty_min)


def check_glides(keys, shots, fps):
    warnings = []
    for key in keys:
        if key["ease"] != "glide":
            continue
        half = key["frames"] / 2 / fps
        shot = shot_at(shots, key["t"])
        if shot is None:
            continue
        if key["t"] - half < shot["start"] - 1e-6:
            moved = round(shot["start"] + half + 1 / fps, 3)
            warnings.append(f"glide at t={key['t']}: its {key['frames']} frames would start before the cut at {shot['start']}; moved to t={moved}")
            key["t"] = moved
        if key["t"] + half > shot["end"] + 1e-6:
            warnings.append(f"glide at t={key['t']}: it is still moving at the cut at {shot['end']}; shorten it or move it earlier")
    keys.sort(key=lambda item: (item["t"], 0 if "shot" in item else 1))
    return warnings


def check_kicks(keys, shots, fps, kick_gap, headroom_min):
    warnings = []
    kicks = [key for key in ordered(keys) if key["ease"] == "kick"]
    for previous, current in zip(kicks, kicks[1:]):
        if current["t"] - previous["t"] < kick_gap - 1e-9:
            warnings.append(f"kicks at t={previous['t']} and t={current['t']} are closer than {kick_gap} s")
    for kick in kicks:
        state = state_before(keys, kick["t"]) or {"scale": 1.0, "tx": 0.0, "ty": 0.0}
        headroom = translate_headroom(state, shot_face(shots, kick["t"]))
        if headroom < headroom_min - 1e-9:
            warnings.append(
                f"kick at t={kick['t']}: only {headroom:.1f} px of edge headroom at scale {state['scale']} (wants {headroom_min}); "
                "the renderer raises the scale for the kick frames, so raise the shot scale or move the kick"
            )
        for move in keys:
            if move["ease"] == "push" and move["t"] - 1e-6 <= kick["t"] < move["t"] + PUSH_FRAMES / fps - 1e-6:
                warnings.append(f"kick at t={kick['t']} lands inside the push at t={move['t']}; let the push stop on the hit")
    return warnings


def check(keys, shots, max_scale, push_gap, min_change):
    warnings = []
    for key in state_keys(keys):
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
    timeline = state_keys(keys)
    for previous, current in zip(timeline, timeline[1:]):
        if "shot" in current and current["shot"] > 0 and abs(previous["scale"] - current["scale"]) < min_change - 1e-9:
            warnings.append(f"cut at t={current['t']}: scale change {previous['scale']} -> {current['scale']} is under {min_change}")
    pushes = [key for key in keys if key["ease"] == "push"]
    for previous, current in zip(pushes, pushes[1:]):
        if current["t"] - previous["t"] < push_gap:
            warnings.append(f"pushes at t={previous['t']} and t={current['t']} are closer than {push_gap} s")
    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Build a Remotion camera plan (keys with cut/push/glide/creep/hold/kick) from cues.json and a shot config. "
        "Every cut and every cues.needs_punch time gets a punch-state change; quiet shots get an automatic creep; "
        "each move's peak corner speed is printed."
    )
    parser.add_argument("--cues", required=True, help="cues.json on the output timeline (optional needs_punch: [t | {t}])")
    parser.add_argument("--shots", required=True, help="shot config: clip states, per-shot overrides, moves with anchors")
    parser.add_argument("--out", required=True, help="camera_plan.json output path")
    parser.add_argument("--max-scale", type=float, default=DEFAULT_MAX_SCALE, help=f"scale ceiling (default {DEFAULT_MAX_SCALE}, at most {MAX_SCALE_LIMIT}); written to the plan as maxScale")
    parser.add_argument("--push-gap", type=float, default=3.0)
    parser.add_argument("--kick-gap", type=float, default=3.0, help="smallest gap between two kicks")
    parser.add_argument("--kick-headroom", type=float, default=6.0, help="edge headroom in px a kick wants without a scale raise")
    parser.add_argument("--min-cut-change", type=float, default=0.03, help="smallest scale change accepted on a cut")
    parser.add_argument("--punch-step", type=float, default=0.06, help="scale change used when a cut has to be forced")
    parser.add_argument("--auto-creep", type=float, default=0.06, help="creep added across every shot of 2 s or more without a push, glide or creep (0 disables)")
    parser.add_argument("--speed-limit", type=float, default=37.0, help="warn when a move's peak corner speed exceeds this many px per frame")
    args = parser.parse_args()

    if not 1.0 < args.max_scale <= MAX_SCALE_LIMIT + 1e-9:
        sys.exit(f"--max-scale must be above 1.0 and at most {MAX_SCALE_LIMIT}")
    cues = load_json(args.cues)
    fps = int(cues.get("fps", 25))
    try:
        config = resolve_tree(load_json(args.shots), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    shots = visual_shots(cues, fps)
    keys = apply_moves(shot_keys(shots, config), config.get("moves", []))
    warnings = []
    if args.max_scale > DEFAULT_MAX_SCALE + 1e-9:
        warnings.append(f"max scale {args.max_scale} is above {DEFAULT_MAX_SCALE}: the upscale softens; check stills at the ceiling for this camera body")
    warnings += check_glides(keys, shots, fps)
    warnings += force_punches(keys, args.min_cut_change, args.max_scale, args.punch_step)
    creeps, creep_notes = auto_creep(keys, shots, args.auto_creep, args.max_scale, fps, args.min_cut_change)
    warnings += creep_notes
    if creeps:
        rerun = force_punches(keys, args.min_cut_change, args.max_scale, args.punch_step)
        warnings += rerun
        if rerun:
            warnings += refit_auto_creeps(keys, shots, args.auto_creep, args.max_scale, args.min_cut_change)
        creeps = [key for key in creeps if key in keys]
    warnings += forced_share_warning(keys)
    warnings += check(keys, shots, args.max_scale, args.push_gap, args.min_cut_change)
    warnings += check_kicks(keys, shots, fps, args.kick_gap, args.kick_headroom)
    speeds = move_speeds(keys, fps, cues["duration"])
    for row in speeds:
        if row["peak"] > args.speed_limit:
            warnings.append(f"{row['ease']} at t={row['t']}: peak corner speed {row['peak']:.1f} px/frame is over {args.speed_limit}; spread it over more frames or move less")
    for key in keys:
        key.pop("auto", None)
        key.pop("shotIndex", None)
    plan = {"maxScale": args.max_scale, "keys": keys, "speeds": [{**row, "peak": round(row["peak"], 2)} for row in speeds], "warnings": warnings}
    Path(args.out).write_text(json.dumps(plan, indent=2) + "\n")
    for row in speeds:
        change = f" {row['change']:+.3f}" if row["ease"] != "kick" else ""
        print(f"speed: t={row['t']:6.2f} {row['ease']:5s}{change} over {row['frames']} f: peak {row['peak']:.1f} px/frame at the corner")
    if creeps:
        print(f"auto creep: {len(creeps)} shot(s) at t={', '.join(str(key['t']) for key in creeps)}")
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"wrote {args.out} with {len(keys)} keys")


if __name__ == "__main__":
    main()
