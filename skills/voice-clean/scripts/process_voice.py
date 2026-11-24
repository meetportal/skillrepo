import argparse
import hashlib
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
    frame_db,
    level_masks,
    load_preset,
    load_words,
    matched_floor_dbfs,
    parse_assignments,
    resolve_stages,
    word_softening,
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
        "path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "samples": int(len(samples)),
        "duration_s": round(len(samples) / SAMPLE_RATE, 6),
        "sample_peak_dbfs": round(float(20 * np.log10(max(np.max(np.abs(samples)), 1e-12))), 2),
        **loudness,
    }


def plan_configs(targets, clip_params, default_preset, global_overrides, forced_preset=None):
    configs = {}
    assignment = []
    for item in targets:
        entry = dict(clip_entry(clip_params, item["clip"])) if item["clip"] else {}
        preset_ref = entry.pop("preset", default_preset)
        if forced_preset:
            preset_ref = forced_preset
        overrides = {**global_overrides, **{key: str(value) for key, value in entry.items()}}
        key = json.dumps([preset_ref, overrides], sort_keys=True)
        configs.setdefault(key, {"preset": preset_ref, "overrides": overrides})
        assignment.append(key)
    return configs, assignment


def render_timeline(input_path, configs, assignment, boundaries, length, crossfade_ms, deep_filter):
    renders = {}
    with tempfile.TemporaryDirectory() as workdir:
        for index, (key, config) in enumerate(configs.items()):
            preset = load_preset(config["preset"])
            stages, params = resolve_stages(preset, config["overrides"])
            config["stages"] = stages
            config["latencies"] = []
            renders[key] = apply_chain(input_path, Path(workdir) / f"render_{index}.wav", stages, deep_filter, latencies=config["latencies"])
            print(f"rendered {preset['name']} {config['overrides'] or ''}".rstrip(), flush=True)
    if len(configs) == 1:
        return next(iter(renders.values()))
    return crossfade_compose(renders, assignment, boundaries, length, int(SAMPLE_RATE * crossfade_ms / 1000))


def main():
    parser = argparse.ArgumentParser(description="Apply a voice chain preset to a cut dialogue wav with per-clip settings from the EDL, then gate the result on length, alignment, matched-loudness floor and per-word level.")
    parser.add_argument("--input", required=True, help="cut dialogue audio (any ffmpeg-readable file); decoded to 48 kHz mono")
    parser.add_argument("--output", required=True, help="output wav (48 kHz mono)")
    parser.add_argument("--preset", default="dialogue", help="preset name from presets/ or a path to a .json/.yaml preset")
    parser.add_argument("--set", dest="assignments", action="append", default=[], help="param override name=value, repeatable, applies to every region")
    parser.add_argument("--edl", help="EDL json with ranges[{clip,a_in,a_out}]; the input must be exactly the concatenation of those ranges")
    parser.add_argument("--clip-params", help="json/yaml mapping clip stem to {preset?, param: value} overrides")
    parser.add_argument("--crossfade-ms", type=float, default=5.0, help="crossfade where neighbouring regions use different settings")
    parser.add_argument("--deep-filter", help="path to the deep-filter binary for presets with a deepfilter stage")
    parser.add_argument("--subtype", default="FLOAT", choices=["FLOAT", "PCM_24", "PCM_16"], help="wav sample format; FLOAT keeps peaks above 0 dBFS for the master stage")
    parser.add_argument("--words", help="word timings on the cut timeline (start/end in s, or startMs/endMs); enables the per-word level gate")
    parser.add_argument("--reference-preset", default="tone-only", help="chain the per-word gate compares against (same per-clip overrides, no denoiser or expander)")
    parser.add_argument("--word-limit-db", type=float, default=1.0, help="fail when a word is this much quieter than in the reference chain")
    parser.add_argument("--report", help="write a json report here")
    args = parser.parse_args()

    source = decode(args.input)
    length = len(source)
    global_overrides = parse_assignments(args.assignments)
    clip_params = load_clip_params(args.clip_params)

    ranges = []
    edl_total = None
    if args.edl:
        ranges = json.loads(Path(args.edl).read_text())["ranges"]
        boundaries = range_boundaries(ranges)
        edl_total = boundaries[-1] / SAMPLE_RATE
        if abs(boundaries[-1] - length) > 1:
            raise SystemExit(f"EDL audio total {boundaries[-1]} samples ({edl_total:.4f} s) != input {length} samples ({length / SAMPLE_RATE:.4f} s): the input is not the cut of this EDL; re-render the cut dialogue first")
    else:
        boundaries = [0, length]

    targets = [{**item, "clip": audio_clip(item)} for item in ranges] or [{"clip": ""}]
    configs, assignment = plan_configs(targets, clip_params, args.preset, global_overrides)
    processed = render_timeline(args.input, configs, assignment, boundaries, length, args.crossfade_ms, args.deep_filter)
    write_wav(args.output, processed, subtype=args.subtype)
    written = decode(args.output)

    source_info = describe(source, args.input)
    output_info = describe(written, args.output)
    pause_mask = level_masks(frame_db(source))["pause"]
    floor_source = matched_floor_dbfs(source, source_info["lufs_i"], pause_mask)
    floor_output = matched_floor_dbfs(written, output_info["lufs_i"], pause_mask)
    lag = alignment_lag_samples(source, written)
    gates = {
        "length": len(written) == length,
        "alignment": lag == 0,
        "floor": floor_output is not None and floor_source is not None and floor_output <= floor_source,
    }
    word_report = None
    if args.words:
        reference_configs, reference_assignment = plan_configs(targets, clip_params, args.preset, global_overrides, args.reference_preset)
        reference = render_timeline(args.input, reference_configs, reference_assignment, boundaries, length, args.crossfade_ms, args.deep_filter)
        word_report = word_softening(written, reference, load_words(args.words), args.word_limit_db)
        gates["words"] = not word_report["softened_over_limit"]

    report = {
        "input": source_info,
        "output": output_info,
        "length_difference_samples": int(len(written) - length),
        "alignment_lag_samples": lag,
        "edl_audio_total_s": edl_total,
        "floor_at_minus14_lufs_dbfs": {"input": floor_source, "output": floor_output, "difference_db": round(floor_output - floor_source, 1) if None not in (floor_output, floor_source) else None},
        "word_levels_vs_reference": word_report,
        "gates": gates,
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
    print(json.dumps({key: report[key] for key in ("length_difference_samples", "alignment_lag_samples", "floor_at_minus14_lufs_dbfs", "gates")}, indent=1))
    if word_report:
        print(f"words: {word_report['words']}, median {word_report['median_delta_db']} dB, min {word_report['min_delta_db']} dB vs {args.reference_preset}, over limit {len(word_report['softened_over_limit'])}")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=1))
    failed = [name for name, passed in gates.items() if not passed]
    if failed:
        raise SystemExit(f"gates failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
