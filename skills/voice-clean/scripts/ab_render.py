import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicelib import (
    FRAME_HOP_S,
    apply_chain,
    band_balance,
    band_ratio_db,
    decode,
    ebur128,
    frame_db,
    level_masks,
    listen_points,
    load_words,
    log_spectral_distance,
    mean_db,
    pause_kurtosis,
    pause_windows,
    word_softening,
    parse_assignments,
    parse_window,
    resolve_stages,
    load_preset,
    runs,
    spectrum_png,
    stft_power,
    window_mask,
    write_wav,
)

COMPARE_LUFS = -14.0
LISTEN_LUFS = -23.0


def source_masks(samples, noise_window):
    levels = frame_db(samples)
    masks = level_masks(levels)
    if noise_window:
        masks["noise"] = window_mask(len(levels), [noise_window])
    masks["levels"] = levels
    gate_zone = (levels > masks["floor_p5_dbfs"] + 3) & (levels < masks["floor_p5_dbfs"] + 20)
    masks["gate_zone"] = gate_zone
    masks["pause_windows"] = pause_windows(masks["pause"])
    masks["low_level"] = (levels >= masks["floor_p5_dbfs"] + 6) & (levels < masks["floor_p5_dbfs"] + 20)
    return masks


def pumping_metrics(levels_out, masks):
    levels_in = masks["levels"]
    count = min(len(levels_out), len(levels_in))
    gain = levels_out[:count] - levels_in[:count]
    speech_gain = np.median(gain[masks["speech"][:count]])
    pause_gain = np.median(gain[masks["pause"][:count]])
    zone = masks["gate_zone"][:count]
    steps = np.abs(np.diff(gain))[zone[1:] & zone[:-1]]
    pause_spreads = []
    for start, end in runs(masks["pause"][:count], 20):
        inner = levels_out[start + 3:end - 3]
        if len(inner) > 5:
            pause_spreads.append(float(np.percentile(inner, 95) - np.percentile(inner, 5)))
    return {
        "pause_depth_db": round(float(pause_gain - speech_gain), 1),
        "gate_zone_gain_step_db": round(float(np.median(steps)), 2) if len(steps) else None,
        "gate_zone_gain_step_p90_db": round(float(np.percentile(steps, 90)), 2) if len(steps) else None,
        "pause_level_spread_db": round(float(np.mean(pause_spreads)), 1) if pause_spreads else None,
    }


def measure(samples, path, masks, reference_power=None, freqs_power=None):
    levels = frame_db(samples)
    count = min(len(levels), len(masks["levels"]))
    levels = levels[:count]
    pause = masks["pause"][:count]
    speech = masks["speech"][:count]
    loudness = ebur128(path)
    freqs, power = freqs_power or stft_power(samples)
    pause_rms = mean_db(levels, pause)
    speech_rms = mean_db(levels, speech)
    result = {
        **loudness,
        "sample_peak_dbfs": round(float(20 * np.log10(max(np.max(np.abs(samples)), 1e-12))), 2),
        "floor_p5_dbfs": round(float(np.percentile(levels, 5)), 1),
        "pause_rms_dbfs": round(pause_rms, 1),
        "speech_rms_dbfs": round(speech_rms, 1),
        "snr_db": round(speech_rms - pause_rms, 1),
        "pause_rms_at_minus14_lufs_dbfs": round(pause_rms + COMPARE_LUFS - loudness["lufs_i"], 1) if loudness["lufs_i"] is not None else None,
        "low_level_rms_at_minus14_lufs_dbfs": round(mean_db(levels, masks["low_level"][:count]) + COMPARE_LUFS - loudness["lufs_i"], 1) if loudness["lufs_i"] is not None else None,
        "speech_band_balance_db": band_balance(freqs, power, speech),
        "sibilance_5k10k_vs_300_3k_db": band_ratio_db(freqs, power, speech, (5000, 10000), (300, 3000)),
        "presence_2k5_5k_vs_300_3k_db": band_ratio_db(freqs, power, speech, (2500, 5000), (300, 3000)),
        **pumping_metrics(levels, masks),
    }
    result["pause_kurtosis"], result["pause_kurtosis_windows"] = pause_kurtosis(samples, masks["pause_windows"])
    if "noise" in masks:
        noise_rms = mean_db(levels, masks["noise"][:count])
        result["noise_window_rms_dbfs"] = round(noise_rms, 1)
        result["speech_minus_noise_window_db"] = round(speech_rms - noise_rms, 1)
    if reference_power is not None:
        result["speech_lsd_vs_reference_db"] = log_spectral_distance(freqs, reference_power, power, speech)
    return result, (freqs, power)


def gate_activity(gated, ungated, masks, closed_db=3.0, bite_db=1.0):
    gated_levels = frame_db(gated)
    ungated_levels = frame_db(ungated)
    count = min(len(gated_levels), len(ungated_levels), len(masks["levels"]))
    live = masks["levels"][:count] > -90
    attenuation = np.where(live, ungated_levels[:count] - gated_levels[:count], 0.0)
    closures = runs(attenuation > closed_db, 3)
    speech = masks["speech"][:count]
    short_reopen = [
        round(closures[i][0] * FRAME_HOP_S, 2)
        for i in range(1, len(closures))
        if (closures[i][0] - closures[i - 1][1]) * FRAME_HOP_S < 0.15
    ]
    return {
        "closures": len(closures),
        "closed_time_s": round(float(np.sum(attenuation > closed_db)) * FRAME_HOP_S, 2),
        "max_attenuation_db": round(float(attenuation.max()), 1),
        "speech_frames_attenuated_pct": round(100.0 * float(np.mean(attenuation[speech] > bite_db)), 2) if speech.any() else 0.0,
        "reopen_within_150ms_at_s": short_reopen[:20],
        "closure_windows_s": [(round(a * FRAME_HOP_S, 2), round(b * FRAME_HOP_S, 2)) for a, b in closures[:40]],
    }


def listen_copy(path, out_path, lufs_i):
    if lufs_i is None:
        return None
    samples = decode(path)
    write_wav(out_path, samples * 10 ** ((LISTEN_LUFS - lufs_i) / 20))
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Render several voice chains on the same input and measure floor, SNR, loudness, tone and gate behaviour.")
    parser.add_argument("--input", required=True, action="append", help="audio or video file, repeatable")
    parser.add_argument("--presets", required=True, nargs="+", help="preset names or paths")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--reference", help="preset (one of --presets) whose output is the speech reference for log-spectral distance")
    parser.add_argument("--set", dest="assignments", action="append", default=[], help="param override name=value applied to every preset that has the param")
    parser.add_argument("--clip-set", action="append", default=[], help="per-input override stem:name=value")
    parser.add_argument("--noise-window", type=parse_window, help="start:end seconds of room tone measured in every output")
    parser.add_argument("--deep-filter", help="path to the deep-filter binary")
    parser.add_argument("--spectrograms", action="store_true", help="write a spectrum png per output")
    parser.add_argument("--gate-pair", action="append", default=[], help="WITH:WITHOUT preset names that differ only by a gate; reports when and how hard the gate closes")
    parser.add_argument("--listen-copies", action="store_true", help=f"also write loudness-matched copies at {LISTEN_LUFS} LUFS for fair listening")
    parser.add_argument("--words", help="word timings on the input timeline (json list with start/end in s, or startMs/endMs); with --reference, reports per-word RMS of each chain against the reference chain")
    parser.add_argument("--word-limit-db", type=float, default=1.0, help="a word quieter than in the reference chain by more than this fails the word-level gate")
    args = parser.parse_args()
    if args.words and len(args.input) != 1:
        raise SystemExit("--words needs exactly one --input")
    words = load_words(args.words) if args.words else None

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    overrides = parse_assignments(args.assignments)
    per_clip = {}
    for item in args.clip_set:
        stem, assignment = item.split(":", 1)
        per_clip.setdefault(stem, {}).update(parse_assignments([assignment]))
    presets = [load_preset(reference) for reference in args.presets]
    ordered = sorted(presets, key=lambda preset: preset["name"] != (args.reference or ""))
    results = {"presets": {}, "inputs": {}}

    for input_path in args.input:
        stem = Path(input_path).stem
        source = decode(input_path)
        source_path = out_dir / f"{stem}__source.wav"
        write_wav(source_path, source)
        masks = source_masks(source, args.noise_window)
        source_result, _ = measure(source, source_path, masks)
        entry = {"source": source_result, "chains": {}, "listen": listen_points(source)}
        print(f"{stem} source I {source_result['lufs_i']} floor@-14 {source_result['pause_rms_at_minus14_lufs_dbfs']} SNR {source_result['snr_db']} "
              f"kurt {source_result['pause_kurtosis']} over {len(masks['pause_windows'])} pauses", flush=True)
        if args.spectrograms:
            source_result["spectrum_png"] = spectrum_png(source_path, out_dir / f"{stem}__source.png")
        if args.listen_copies:
            source_result["listen_wav"] = listen_copy(source_path, out_dir / f"{stem}__source.listen.wav", source_result["lufs_i"])
        reference_power = None
        reference_samples = None
        for preset in ordered:
            names = set(preset["params"]) | {key for stage in preset["stages"] for key in re.findall(r"\{(\w+)\}", json.dumps(stage))}
            applied = {key: value for key, value in {**overrides, **per_clip.get(stem, {})}.items() if key in names}
            stages, params = resolve_stages(preset, applied)
            results["presets"].setdefault(preset["name"], {"description": preset.get("description", ""), "stages": stages})
            out_path = out_dir / f"{stem}__{preset['name']}.wav"
            latencies = []
            processed = apply_chain(input_path, out_path, stages, args.deep_filter, latencies=latencies)
            metrics, freqs_power = measure(processed, out_path, masks, reference_power)
            if args.reference and preset["name"] == args.reference:
                reference_power = freqs_power[1]
                reference_samples = processed
            metrics["floor_vs_source_db"] = round(metrics["pause_rms_at_minus14_lufs_dbfs"] - source_result["pause_rms_at_minus14_lufs_dbfs"], 1)
            metrics["floor_pass"] = metrics["floor_vs_source_db"] <= 0.0
            metrics["low_level_vs_source_db"] = round(metrics["low_level_rms_at_minus14_lufs_dbfs"] - source_result["low_level_rms_at_minus14_lufs_dbfs"], 1)
            if words and reference_samples is not None:
                metrics["word_levels_vs_reference"] = word_softening(processed, reference_samples, words, args.word_limit_db)
            metrics["wav"] = str(out_path)
            metrics["overrides"] = applied
            metrics["compensated_latency_samples"] = [item["latency_samples"] for item in latencies]
            if args.spectrograms:
                metrics["spectrum_png"] = spectrum_png(out_path, out_dir / f"{stem}__{preset['name']}.png")
            if args.listen_copies:
                metrics["listen_wav"] = listen_copy(out_path, out_dir / f"{stem}__{preset['name']}.listen.wav", metrics["lufs_i"])
            entry["chains"][preset["name"]] = metrics
            print(
                f"{stem} {preset['name']:<22} I {metrics['lufs_i']:>6} floor@-14 {metrics['pause_rms_at_minus14_lufs_dbfs']:>6} "
                f"SNR {metrics['snr_db']:>5} sib {metrics['sibilance_5k10k_vs_300_3k_db']:>5} "
                f"LSD {metrics.get('speech_lsd_vs_reference_db', '-')!s:>5} depth {metrics['pause_depth_db']:>6} "
                f"kurt {metrics['pause_kurtosis']!s:>5} vs-src {metrics['floor_vs_source_db']:>5} {'pass' if metrics['floor_pass'] else 'FAIL'} "
                f"breaths vs-src {metrics['low_level_vs_source_db']:>5}"
                + (f" words min {metrics['word_levels_vs_reference']['min_delta_db']} dB" if "word_levels_vs_reference" in metrics else ""),
                flush=True,
            )
        outputs = {}
        for pair in args.gate_pair:
            with_gate, without_gate = pair.split(":")
            outputs.setdefault(with_gate, decode(entry["chains"][with_gate]["wav"]))
            outputs.setdefault(without_gate, decode(entry["chains"][without_gate]["wav"]))
            activity = gate_activity(outputs[with_gate], outputs[without_gate], masks)
            entry.setdefault("gate", {})[pair] = activity
            print(f"{stem} gate {pair}: {activity['closures']} closures, {activity['closed_time_s']} s closed, "
                  f"speech frames attenuated {activity['speech_frames_attenuated_pct']} %, fast reopens {len(activity['reopen_within_150ms_at_s'])}")
        results["inputs"][stem] = entry
    (out_dir / "results.json").write_text(json.dumps(results, indent=1))
    print(f"wrote {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
