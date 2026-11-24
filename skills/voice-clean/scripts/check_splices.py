import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicelib import SAMPLE_RATE, astats, decode

CONTEXT_S = 0.2
CLICK_RATIO_DB = 12.0
LOUD_SPLICE_DBFS = -25.0
DIP_DB = 6.0
DIP_WINDOW_S = 0.06
DIP_FRAME_S = 0.01


def audio_clip(item):
    return item.get("a_clip") or item["clip"]


def continuous_audio(previous, following):
    same_clip = Path(audio_clip(previous)).resolve() == Path(audio_clip(following)).resolve()
    return same_clip and abs(float(previous["a_out"]) - float(following["a_in"])) < 0.001


def edl_boundaries(edl):
    edges = [0.0]
    for item in edl["ranges"]:
        edges.append(edges[-1] + float(item["a_out"]) - float(item["a_in"]))
    return edges


def click_ratio_db(samples, center, half_window):
    curvature = np.abs(np.diff(samples, 2))
    start, end = max(0, center - half_window), min(len(curvature), center + half_window)
    context_half = int(SAMPLE_RATE * CONTEXT_S)
    context = np.concatenate([
        curvature[max(0, start - context_half):start],
        curvature[end:min(len(curvature), end + context_half)],
    ])
    inside = curvature[start:end]
    if len(inside) == 0 or len(context) == 0:
        return None
    reference = max(float(np.percentile(context, 99)), 1e-9)
    return round(float(20 * np.log10(max(float(inside.max()), 1e-12) / reference)), 1)


def ten_ms_levels(samples, start=0, end=None):
    frame = int(SAMPLE_RATE * DIP_FRAME_S)
    end = len(samples) if end is None else min(len(samples), end)
    start = max(0, start)
    count = (end - start) // frame
    if count <= 0:
        return np.array([])
    blocks = samples[start:start + count * frame].reshape(count, frame)
    return 10 * np.log10(np.maximum(np.mean(blocks ** 2, axis=1), 1e-12))


def room_floor_db(samples):
    levels = ten_ms_levels(samples)
    live = levels[levels > -90]
    return float(np.percentile(live if len(live) else levels, 5))


def dip_db(samples, center, floor_db):
    half = int(SAMPLE_RATE * DIP_WINDOW_S)
    inside = ten_ms_levels(samples, center - half, center + half)
    if len(inside) == 0:
        return None
    return round(floor_db - float(inside.min()), 1)


def main():
    parser = argparse.ArgumentParser(description="Measure peaks and click energy around every EDL splice in one or more cut audio files.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--audio", required=True, action="append", help="audio on the EDL output timeline, repeatable (for example the raw cut and the processed voice)")
    parser.add_argument("--window-ms", type=float, default=20.0, help="half width of the window around each splice")
    parser.add_argument("--out", help="write the json report here")
    args = parser.parse_args()

    edl = json.loads(Path(args.edl).read_text())
    boundaries = edl_boundaries(edl)
    half = args.window_ms / 1000
    half_samples = int(SAMPLE_RATE * half)
    decoded = {path: decode(path) for path in args.audio}
    floors = {path: room_floor_db(samples) for path, samples in decoded.items()}
    report = {"window_ms": args.window_ms, "room_floor_p5_dbfs": {Path(path).name: round(value, 1) for path, value in floors.items()}, "splices": [], "flagged": []}
    for index, time in enumerate(boundaries[1:-1], start=1):
        previous, following = edl["ranges"][index - 1], edl["ranges"][index]
        continuous = continuous_audio(previous, following)
        entry = {"index": index, "t": round(time, 4), "from_clip": Path(audio_clip(previous)).stem, "to_clip": Path(audio_clip(following)).stem, "continuous_audio": continuous}
        for path, samples in decoded.items():
            stats = astats(path, time - half, time + half)
            measured = {
                "peak_dbfs": round(stats.get("peak_level_db", float("-inf")), 1),
                "rms_dbfs": round(stats.get("rms_level_db", float("-inf")), 1),
                "click_ratio_db": click_ratio_db(samples, int(round(time * SAMPLE_RATE)), half_samples),
                "dip_below_room_floor_db": dip_db(samples, int(round(time * SAMPLE_RATE)), floors[path]),
            }
            entry[Path(path).name] = measured
            reasons = []
            if measured["click_ratio_db"] is not None and measured["click_ratio_db"] > CLICK_RATIO_DB:
                reasons.append(f"curvature spike {measured['click_ratio_db']} dB over context")
            if measured["dip_below_room_floor_db"] is not None and measured["dip_below_room_floor_db"] > DIP_DB:
                reasons.append(f"level dips {measured['dip_below_room_floor_db']} dB under the file's room-tone floor (p5 of 10 ms frames)")
            if measured["peak_dbfs"] > LOUD_SPLICE_DBFS:
                reasons.append(f"peak {measured['peak_dbfs']} dBFS at the splice")
            if reasons and not continuous:
                report["flagged"].append({"index": index, "t": round(time, 4), "audio": Path(path).name, "reasons": reasons})
        report["splices"].append(entry)
    for entry in report["splices"]:
        cells = "  ".join(
            f"{name}: pk {entry[name]['peak_dbfs']:>6} click {entry[name]['click_ratio_db']!s:>5} dip {entry[name]['dip_below_room_floor_db']!s:>5}"
            for name in (Path(path).name for path in args.audio)
        )
        kind = "continuous" if entry["continuous_audio"] else "splice"
        print(f"#{entry['index']:>2} {entry['t']:>8.3f}s {kind:<10} {entry['from_clip']}->{entry['to_clip']}  {cells}")
    report["splice_count"] = sum(1 for entry in report["splices"] if not entry["continuous_audio"])
    print(f"audio splices: {report['splice_count']}, continuous boundaries (video-only cuts): {len(report['splices']) - report['splice_count']}, flagged: {len(report['flagged'])}")
    for item in report["flagged"]:
        print(f"  #{item['index']} {item['t']} s {item['audio']}: {'; '.join(item['reasons'])}")
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
