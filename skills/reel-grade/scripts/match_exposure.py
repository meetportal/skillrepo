import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

GAMMA_PATTERN = re.compile(r"^eq=gamma=([0-9.]+)$")


def video_windows(edl):
    fps = edl["fps"]
    windows = []
    for entry in edl["ranges"]:
        clip = Path(entry["clip"]).stem
        start, end = round(entry["v_in"] * fps), round(entry["v_out"] * fps)
        if windows and windows[-1]["clip"] == clip and windows[-1]["end"] == start:
            windows[-1]["end"] = end
        else:
            windows.append({"clip": clip, "start": start, "end": end})
    return [{"clip": w["clip"], "from": round(w["start"] / fps, 3), "to": round(w["end"] / fps, 3)} for w in windows]


def current_segment_gamma(grade, clip, start, end):
    middle = (start + end) / 2
    for segment in grade.get("segments", []):
        if segment["clip"] == clip and segment["from"] <= middle < segment["to"]:
            for item in segment["filters"]:
                match = GAMMA_PATTERN.match(item)
                if match:
                    return float(match.group(1)), segment
            return 1.0, segment
    return 1.0, None


def extra_gamma(measured, target):
    current, wanted = (measured - 16) / 219, (target - 16) / 219
    if not (0 < current < 1 and 0 < wanted < 1):
        return 1.0
    return math.log(current) / math.log(wanted)


def gamma_at(entry, constant, source_time):
    if entry and entry.get("gamma_keys"):
        keys = sorted(entry["gamma_keys"])
        return float(np.interp(source_time, [k[0] for k in keys], [k[1] for k in keys]))
    return constant


def keyframes(samples, window, measured, entry, constant, target, bin_seconds, limits):
    offset = window["from"] - measured["start"]
    bins = {}
    for sample in samples:
        if sample.get("skin_y") is None or not (measured["start"] <= sample["t"] < measured["end"]):
            continue
        bins.setdefault(int((sample["t"] + offset - window["from"]) // bin_seconds), []).append(sample)
    keys = []
    for index in sorted(bins):
        group = bins[index]
        if len(group) < 2:
            continue
        source_time = round(window["from"] + (index + 0.5) * bin_seconds, 3)
        skin = float(np.median([s["skin_y"] for s in group]))
        old = gamma_at(entry, constant, source_time)
        keys.append([source_time, round(min(limits[1], max(limits[0], old * extra_gamma(skin, target))), 3)])
    if len(keys) >= 2:
        values = np.array([k[1] for k in keys])
        smoothed = np.convolve(np.pad(values, 1, mode="edge"), np.ones(3) / 3, mode="valid")
        keys = [[k[0], round(float(v), 3)] for k, v in zip(keys, smoothed)]
    return keys


def main():
    parser = argparse.ArgumentParser(description="Per-segment exposure match: turn measured skin Y per A-roll segment into eq gamma overrides in the grade config.")
    parser.add_argument("--measure", required=True, help="measure_skin.py report made with --cues")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--grade", required=True, help="current grade JSON")
    parser.add_argument("--out", required=True, help="updated grade JSON (may be the same path)")
    parser.add_argument("--deadband", type=float, default=2.0, help="leave a segment alone when within this many code values of the target")
    parser.add_argument("--keyframe-spread", type=float, default=18.0, help="segments whose skin Y interquartile range exceeds this get a gamma ramp instead of one value")
    parser.add_argument("--keyframe-step", type=float, default=0.5, help="seconds per gamma keyframe")
    parser.add_argument("--min-gamma", type=float, default=0.6)
    parser.add_argument("--max-gamma", type=float, default=1.6)
    args = parser.parse_args()
    report = json.loads(Path(args.measure).read_text())
    edl = json.loads(Path(args.edl).read_text())
    grade = json.loads(Path(args.grade).read_text())
    grade.setdefault("segments", [])
    target = report["target_skin_y_tv"]
    windows = video_windows(edl)
    if len(windows) != len(report["segments"]):
        raise SystemExit(f"EDL has {len(windows)} video segments but the report has {len(report['segments'])}; re-measure with the matching cues.json")
    for window, measured in zip(windows, report["segments"]):
        skin = measured.get("skin_y")
        extra = measured.get("suggested_extra_eq_gamma")
        old, entry = current_segment_gamma(grade, window["clip"], window["from"], window["to"])
        spread = (measured.get("skin_y_p75") or 0) - (measured.get("skin_y_p25") or 0)
        if skin is not None and spread > args.keyframe_spread:
            keys = keyframes(report["samples"], window, measured, entry, old, target, args.keyframe_step, (args.min_gamma, args.max_gamma))
            if len(keys) >= 2:
                if entry is None:
                    entry = {"clip": window["clip"], "from": window["from"], "to": window["to"], "filters": []}
                    grade["segments"].append(entry)
                entry["filters"] = [item for item in entry["filters"] if not GAMMA_PATTERN.match(item)]
                entry["gamma_keys"] = keys
                print(f"{window['clip']} {window['from']:.2f}-{window['to']:.2f}: skin {skin} spread {spread:.1f} -> gamma ramp {keys}")
                continue
        if skin is None or extra is None or abs(skin - target) <= args.deadband:
            print(f"{window['clip']} {window['from']:.2f}-{window['to']:.2f}: skin {skin} keep gamma {old}")
            continue
        if entry is not None and entry.get("gamma_keys"):
            entry["gamma_keys"] = [[t, round(min(args.max_gamma, max(args.min_gamma, g * extra)), 3)] for t, g in entry["gamma_keys"]]
            print(f"{window['clip']} {window['from']:.2f}-{window['to']:.2f}: skin {skin} -> gamma ramp scaled x {extra}")
            continue
        new = round(min(args.max_gamma, max(args.min_gamma, old * extra)), 3)
        filters = [f"eq=gamma={new}"]
        if entry is None:
            grade["segments"].append({"clip": window["clip"], "from": window["from"], "to": window["to"], "filters": filters})
        else:
            entry["filters"] = [item for item in entry["filters"] if not GAMMA_PATTERN.match(item)] + filters
        print(f"{window['clip']} {window['from']:.2f}-{window['to']:.2f}: skin {skin} -> gamma {old} x {extra} = {new}")
    grade["segments"].sort(key=lambda s: (s["clip"], s["from"]))
    Path(args.out).write_text(json.dumps(grade, indent=1))


if __name__ == "__main__":
    main()
