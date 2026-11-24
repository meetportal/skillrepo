import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tone import tone_curve


def extra_mid(measured, target, limits):
    x, wanted = (measured - 16) / 219, (target - 16) / 219
    low, high = limits
    for _ in range(40):
        middle = math.sqrt(low * high)
        if tone_curve([x], mid=middle)[0] < wanted:
            low = middle
        else:
            high = middle
    return math.sqrt(low * high)


def clamp(value, limits):
    return round(min(limits[1], max(limits[0], value)), 3)


def clip_segment(grade, clip):
    for segment in grade.setdefault("segments", []):
        if segment["clip"] == clip and segment.get("mid_keys") is not None:
            return segment
    segment = {"clip": clip, "from": 0.0, "to": 1e6, "mid_keys": []}
    grade["segments"].append(segment)
    return segment


def current_mid(segment, source_time):
    keys = sorted(segment.get("mid_keys") or [])
    if not keys:
        return 1.0
    return float(np.interp(source_time, [k[0] for k in keys], [k[1] for k in keys]))


def source_samples(levels, cues):
    fps = cues["fps"]
    shots = {shot["index"]: shot for shot in cues["segments"]}
    by_clip = {}
    for sample in levels["samples"]:
        if sample.get("cheek_y") is None:
            continue
        shot = shots[sample["shot"]]
        t = sample["frame"] / fps
        if any(a <= t < b for a, b in shot.get("holds", [])):
            continue
        source_time = shot["src_in"] + (t - shot["start"]) - sum(max(0.0, min(b, t) - a) for a, b in shot.get("holds", []) if a < t)
        by_clip.setdefault(Path(shot["clip"]).stem, []).append((source_time, sample["cheek_y"]))
    return by_clip


def main():
    parser = argparse.ArgumentParser(description="Fit one continuous mid-tone curve per take over source time (tone mid_keys) so the landmark cheek patch sits at the target. Jump cuts inside a take then cannot jump in exposure, and light drift inside a take is followed.")
    parser.add_argument("--levels", required=True, help="cut_levels.py report of the current render")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--target", type=float, default=150.0)
    parser.add_argument("--bin", type=float, default=0.4, help="seconds per key")
    parser.add_argument("--smooth", type=float, default=0.8, help="half width in seconds of the moving median then mean applied to the per-bin corrections")
    parser.add_argument("--min-mid", type=float, default=0.8, help="mid below this darkens a whole frame into murk; a take that still reads hot needs a negative high instead")
    parser.add_argument("--max-mid", type=float, default=1.7)
    parser.add_argument("--edge-clear", type=float, default=0.12, help="the first and last frames of every shot get their own key (measured on the frames next to the cut) so the cheek matches across every cut; other keys this close to that edge are dropped")
    args = parser.parse_args()
    levels = json.loads(Path(args.levels).read_text())
    cues = json.loads(Path(args.cues).read_text())
    grade = json.loads(Path(args.grade).read_text())
    limits = (args.min_mid, args.max_mid)
    new_keys, old_segments = {}, {}
    for clip, samples in source_samples(levels, cues).items():
        segment = clip_segment(grade, clip)
        old_segments[clip] = dict(segment)
        times = np.array([s[0] for s in samples])
        values = np.array([s[1] for s in samples])
        centres, corrections = [], []
        for start in np.arange(times.min(), times.max() + args.bin, args.bin):
            inside = values[(times >= start) & (times < start + args.bin)]
            if len(inside):
                centres.append(start + args.bin / 2)
                corrections.append(math.log(extra_mid(float(np.median(inside)), args.target, (0.5, 2.5))))
        centres, corrections = np.array(centres), np.array(corrections)
        smoothed = np.array([float(np.median(corrections[np.abs(centres - c) <= args.smooth])) for c in centres])
        final = np.array([float(np.mean(smoothed[np.abs(centres - c) <= args.smooth])) for c in centres])
        new_keys[clip] = [[round(float(c), 3), clamp(current_mid(segment, c) * math.exp(k), limits)] for c, k in zip(centres, final)]
        print(f"{clip}: {len(samples)} samples, {len(centres)} bins")
    fps = cues["fps"]
    for cut, (left, right) in zip(levels["cuts"], zip(cues["segments"][:-1], cues["segments"][1:])):
        sides = [(Path(left["clip"]).stem, cut["cheek_before"], left["src_out"] - 1 / fps), (Path(right["clip"]).stem, cut["cheek_after"], right["src_in"])]
        if any(measured is None or clip not in new_keys for clip, measured, _ in sides):
            continue
        target = args.target
        for _ in range(2):
            plans = []
            for clip, measured, edge in sides:
                old = current_mid(old_segments[clip], edge)
                wanted = old * extra_mid(measured, target, (0.3, 3.0))
                mid = clamp(wanted, limits)
                achieved = 16 + 219 * float(tone_curve([(measured - 16) / 219], mid=mid / old)[0])
                plans.append((clip, edge, mid, achieved, mid != round(wanted, 3)))
            clamped = [plan for plan in plans if plan[4]]
            if not clamped or sides[0][0] != sides[1][0]:
                break
            target = float(np.mean([plan[3] for plan in clamped]))
        for clip, edge, mid, _, _ in plans:
            keys = [k for k in new_keys[clip] if abs(k[0] - edge) >= args.edge_clear] + [[round(edge, 3), mid]]
            new_keys[clip] = sorted(keys)
    for clip, keys in new_keys.items():
        clip_segment(grade, clip)["mid_keys"] = keys
        print(f"{clip}: {len(keys)} keys, mid {min(k[1] for k in keys):.3f}-{max(k[1] for k in keys):.3f}")
    Path(args.out).write_text(json.dumps(grade, indent=1))


if __name__ == "__main__":
    main()
