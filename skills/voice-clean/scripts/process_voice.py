import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicelib import (
    SAMPLE_RATE,
    alignment_lag_samples,
    apply_chain,
    decode,
    ebur128,
    load_preset,
    parse_assignments,
    resolve_stages,
    write_wav,
)


def load_clip_params(path):
    if not path:
        return {}
    text = Path(path).read_text()
    if str(path).endswith((".yaml", ".yml")):
        import yaml
        return yaml.safe_load(text) or {}
    return json.loads(text)


def clip_entry(clip_params, clip):
    for key in (Path(clip).stem, Path(clip).name, clip):
        if key in clip_params:
            return clip_params[key]
    return {}


def audio_clip(item):
    return item.get("a_clip") or item["clip"]


def range_boundaries(ranges, sample_rate=SAMPLE_RATE):
    edges = [0.0]
    for item in ranges:
        edges.append(edges[-1] + float(item["a_out"]) - float(item["a_in"]))
    return [int(round(edge * sample_rate)) for edge in edges]


def crossfade_compose(renders, assignment, boundaries, length, crossfade_samples):
    output = np.zeros(length)
    spans = list(zip(boundaries[:-1], boundaries[1:]))
    spans[-1] = (spans[-1][0], max(spans[-1][1], length))
    for (start, end), key in zip(spans, assignment):
        output[start:min(end, length)] = renders[key][start:min(end, length)]
    half = crossfade_samples // 2
    for index in range(1, len(assignment)):
        previous, following = assignment[index - 1], assignment[index]
        if previous == following or half == 0:
            continue
        center = boundaries[index]
        start, end = max(0, center - half), min(length, center + half)
        ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, end - start))
        output[start:end] = renders[previous][start:end] * (1 - ramp) + renders[following][start:end] * ramp
    return output


def describe(samples, path):
    loudness = ebur128(path)
    return {
        "samples": int(len(samples)),
        "duration_s": round(len(samples) / SAMPLE_RATE, 6),
        "sample_peak_dbfs": round(float(20 * np.log10(max(np.max(np.abs(samples)), 1e-12))), 2),
        **loudness,
    }


def main():
    parser = argparse.ArgumentParser(description="Apply a voice chain preset to a dialogue wav, optionally with per-clip settings from an EDL.")
    parser.add_argument("--input", required=True, help="dialogue audio (any ffmpeg-readable file); decoded to 48 kHz mono")
    parser.add_argument("--output", required=True, help="output wav (48 kHz mono)")
    parser.add_argument("--preset", default="chain09", help="preset name from presets/ or a path to a .json/.yaml preset")
    parser.add_argument("--set", dest="assignments", action="append", default=[], help="param override name=value, repeatable, applies to every region")
    parser.add_argument("--edl", help="EDL json with ranges[{clip,a_in,a_out}]; the input is the concatenation of those ranges")
    parser.add_argument("--clip-params", help="json/yaml mapping clip stem to {preset?, param: value} overrides")
    parser.add_argument("--crossfade-ms", type=float, default=5.0, help="crossfade where neighbouring regions use different settings")
    parser.add_argument("--deep-filter", help="path to the deep-filter binary for presets with a deepfilter stage")
    parser.add_argument("--subtype", default="FLOAT", choices=["FLOAT", "PCM_24", "PCM_16"], help="wav sample format; FLOAT keeps peaks above 0 dBFS for the master stage")
    parser.add_argument("--report", help="write a json report here")
    args = parser.parse_args()

    source = decode(args.input)
    length = len(source)
    global_overrides = parse_assignments(args.assignments)
    clip_params = load_clip_params(args.clip_params)

    ranges = []
    edl_total = None
    if args.edl:
        edl = json.loads(Path(args.edl).read_text())
        ranges = edl["ranges"]
        boundaries = range_boundaries(ranges)
        edl_total = boundaries[-1] / SAMPLE_RATE
        if abs(boundaries[-1] - length) > SAMPLE_RATE * 0.04:
            print(f"warning: EDL audio total {edl_total:.3f} s differs from input {length / SAMPLE_RATE:.3f} s by more than one frame", file=sys.stderr)
    else:
        boundaries = [0, length]

    configs = {}
    assignment = []
    targets = [{**item, "clip": audio_clip(item)} for item in ranges] or [{"clip": ""}]
    for item in targets:
        entry = dict(clip_entry(clip_params, item["clip"])) if item["clip"] else {}
        preset_ref = entry.pop("preset", args.preset)
        overrides = {**global_overrides, **{key: str(value) for key, value in entry.items()}}
        key = json.dumps([preset_ref, overrides], sort_keys=True)
        configs.setdefault(key, {"preset": preset_ref, "overrides": overrides})
        assignment.append(key)

    renders = {}
    with tempfile.TemporaryDirectory() as workdir:
        for index, (key, config) in enumerate(configs.items()):
            preset = load_preset(config["preset"])
            stages, params = resolve_stages(preset, config["overrides"])
            config["params"] = params
            config["stages"] = stages
            render_path = Path(workdir) / f"render_{index}.wav"
            config["latencies"] = []
            renders[key] = apply_chain(args.input, render_path, stages, args.deep_filter, latencies=config["latencies"])
            print(f"rendered {preset['name']} {config['overrides'] or ''}".rstrip(), flush=True)

    if len(configs) == 1:
        processed = next(iter(renders.values()))
    else:
        processed = crossfade_compose(renders, assignment, boundaries, length, int(SAMPLE_RATE * args.crossfade_ms / 1000))

    write_wav(args.output, processed, subtype=args.subtype)
    written = decode(args.output)
    lag = alignment_lag_samples(source, written)
    report = {
        "input": describe(source, args.input),
        "output": describe(written, args.output),
        "length_difference_samples": int(len(written) - length),
        "alignment_lag_samples": lag,
        "edl_audio_total_s": edl_total,
        "configs": [{"preset": c["preset"], "overrides": c["overrides"], "stages": c["stages"], "compensated_latency_samples": c["latencies"]} for c in configs.values()],
        "regions": [
            {
                "index": index,
                "clip": Path(item.get("clip", "")).stem,
                "start_s": round(boundaries[index] / SAMPLE_RATE, 4),
                "end_s": round(boundaries[index + 1] / SAMPLE_RATE, 4),
                "config": list(configs).index(key),
            }
            for index, (item, key) in enumerate(zip(targets, assignment))
        ],
    }
    print(json.dumps({key: report[key] for key in ("input", "output", "length_difference_samples", "alignment_lag_samples")}, indent=1))
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
