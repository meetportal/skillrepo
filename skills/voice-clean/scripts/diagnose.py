import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicelib import (
    FRAME_HOP_S,
    SAMPLE_RATE,
    astats,
    band_balance,
    band_ratio_db,
    decode,
    ebur128,
    frame_db,
    hum_peaks,
    level_masks,
    listen_points,
    mean_db,
    parse_window,
    probe_channels,
    runs,
    spectrum_png,
    stft_power,
    to_db,
    transient_events,
    window_mask,
    write_wav,
)

HUM_ALERT_DB = 6.0
LOW_SNR_DB = 30.0
NOISY_FLOOR_DBFS = -50.0


def deess_intensity(sibilance_rel_total_db):
    if sibilance_rel_total_db > -3.0:
        return 0.6
    if sibilance_rel_total_db > -5.0:
        return 0.5
    return 0.4


def nonspeech_bursts(frame_levels, speech_mask, floor, low_band_db, body_band_db):
    count = min(len(frame_levels), len(low_band_db))
    outside_speech = ~speech_mask[:count]
    loud = frame_levels[:count] > floor + 12
    candidates = outside_speech & loud & (low_band_db[:count] > body_band_db[:count] + 3)
    return [(round(s * FRAME_HOP_S, 2), round(e * FRAME_HOP_S, 2)) for s, e in runs(candidates, 3)]


def longest_quiet_window(frame_levels, floor, margin_db=3.0, min_s=0.2):
    quiet = runs((frame_levels < floor + margin_db) & (frame_levels > -90), int(min_s / FRAME_HOP_S))
    if not quiet:
        return None
    start, end = max(quiet, key=lambda run: run[1] - run[0])
    return [round((start + 2) * FRAME_HOP_S, 2), round((end - 2) * FRAME_HOP_S, 2)]


def recommend(report):
    advice = []
    params = {}
    floor = report["room_tone_p5_dbfs"]
    snr = report["snr_db"]
    if snr >= 35 and floor <= -55:
        advice.append({"issue": "clean stationary room tone", "evidence": f"floor {floor} dBFS, SNR {snr} dB", "action": "preset dialogue (no denoiser); the expander keeps the floor under the raw file"})
    elif snr >= LOW_SNR_DB and floor <= NOISY_FLOOR_DBFS:
        params["afftdn_nf"] = int(round(min(max(floor - 1, -80), -20)))
        advice.append({"issue": "moderate stationary noise", "evidence": f"floor {floor} dBFS, SNR {snr} dB", "action": "A/B dialogue, dialogue-nr (room_tone=<quiet window>) and dialogue-df; keep the one that passes the floor gate with the lowest pause kurtosis"})
    else:
        advice.append({"issue": "noisy recording", "evidence": f"floor {floor} dBFS, SNR {snr} dB", "action": "A/B dialogue-df and deepfilter-full; listen for warble on vowels"})
    if report.get("room_tone_window_s"):
        start, end = report["room_tone_window_s"]
        params["room_tone"] = f"{report['input']}@{start}:{end}"
    hum = {freq: value for freq, value in report["hum_peak_above_local_db"].items() if value >= HUM_ALERT_DB}
    if hum:
        strongest = max(hum, key=hum.get)
        fundamental = 50 if int(strongest) % 50 == 0 else 60
        params["hum_hz"] = fundamental
        advice.append({"issue": "mains hum", "evidence": f"peaks {hum}", "action": f"preset dialogue-hum with hum_hz={fundamental}"})
    sibilance = report["speech_band_balance_db"].get("5k-10k")
    if sibilance is not None:
        params["deess_i"] = deess_intensity(sibilance)
        if params["deess_i"] > 0.4:
            advice.append({"issue": "sibilance", "evidence": f"5-10k at {sibilance} dB of total speech energy", "action": f"deess_i={params['deess_i']} for this clip"})
    if report["plosive_events"]:
        advice.append({"issue": "plosive pops", "evidence": f"{len(report['plosive_events'])} low bursts, strongest at {report['plosive_events'][0]['t']} s", "action": "keep highpass_hz at 80; raise to 100 only if pops remain audible"})
    if report["nonspeech_bursts"]:
        advice.append({"issue": "low-frequency non-speech events (bumps, handling, murmurs); confirm by ear", "evidence": f"{report['nonspeech_bursts'][:6]}", "action": "cut them out first; if a kept range has rustle use preset arnndn-rustle or deepfilter-full on that clip"})
    if report["hard_clipped_samples"] > 0:
        advice.append({"issue": "clipping", "evidence": f"{report['hard_clipped_samples']} samples at full scale", "action": "add adeclip as the first stage and flag the take for a reshoot"})
    if report["true_peak_dbtp"] is not None and report["true_peak_dbtp"] > -1.0:
        advice.append({"issue": "hot transient", "evidence": f"true peak {report['true_peak_dbtp']} dBTP", "action": "the peak_limit stage at the end of every preset handles it"})
    if report.get("stereo_difference_rms_dbfs") is not None and report["stereo_difference_rms_dbfs"] < -50:
        advice.append({"issue": "dual mono", "evidence": f"L-R difference {report['stereo_difference_rms_dbfs']} dBFS", "action": "downmix by averaging: -af pan=mono|c0=0.5*c0+0.5*c1 (never -ac 1, which sums to +3 dB on float output)"})
    return advice, params


def diagnose(path, out_dir, noise_window=None, write_png=True):
    stem = Path(path).stem
    channels = probe_channels(path)
    stereo_difference = None
    if channels == 2:
        stereo = decode(path, keep_channels=True)
        stereo_difference = round(float(to_db(np.sqrt(np.mean((stereo[:, 0] - stereo[:, 1]) ** 2)))), 1)
    samples = decode(path)
    mono_path = Path(out_dir) / f"{stem}.mono.wav"
    write_wav(mono_path, samples)
    levels = frame_db(samples)
    masks = level_masks(levels)
    freqs, power = stft_power(samples)
    floor = masks["floor_p5_dbfs"]
    pause_mask = masks["pause"]
    if noise_window:
        pause_mask = window_mask(len(levels), [noise_window])
    room_tone = mean_db(levels, pause_mask) if noise_window else floor
    speech_rms = mean_db(levels, masks["speech"])
    hum, noise_bands = hum_peaks(samples, SAMPLE_RATE, pause_mask)
    sibilants, plosives = transient_events(freqs, power, levels, floor)
    count = min(power.shape[1], len(levels))
    low_band = to_db(power[(freqs >= 20) & (freqs < 300), :count].sum(0), power=True)
    body_band = to_db(power[(freqs >= 300) & (freqs < 3000), :count].sum(0), power=True)
    loudness = ebur128(mono_path)
    stats = astats(mono_path)
    report = {
        "input": str(path),
        "channels": channels,
        "duration_s": round(len(samples) / SAMPLE_RATE, 3),
        "stereo_difference_rms_dbfs": stereo_difference,
        "lufs_i_mono": loudness["lufs_i"],
        "lra_lu": loudness["lra_lu"],
        "true_peak_dbtp": loudness["true_peak_dbtp"],
        "sample_peak_dbfs": round(stats.get("peak_level_db", float("nan")), 2),
        "rms_dbfs": round(stats.get("rms_level_db", float("nan")), 2),
        "dc_offset": stats.get("dc_offset"),
        "astats_noise_floor_dbfs": round(stats.get("noise_floor_db", float("nan")), 1),
        "hard_clipped_samples": int(np.sum(np.abs(samples) >= 0.999)),
        "room_tone_p5_dbfs": round(room_tone, 1),
        "room_tone_source": f"window {noise_window[0]}-{noise_window[1]} s" if noise_window else "p5 of 30 ms RMS frames",
        "speech_rms_dbfs": round(speech_rms, 1),
        "speech_p90_dbfs": round(masks["speech_p90_dbfs"], 1),
        "snr_db": round(speech_rms - room_tone, 1),
        "noise_spectrum_db_per_hz": noise_bands,
        "hum_peak_above_local_db": hum,
        "speech_band_balance_db": band_balance(freqs, power, masks["speech"]),
        "sibilance_5k10k_vs_300_3k_db": band_ratio_db(freqs, power, masks["speech"], (5000, 10000), (300, 3000)),
        "presence_2k5_5k_vs_300_3k_db": band_ratio_db(freqs, power, masks["speech"], (2500, 5000), (300, 3000)),
        "sibilant_events": sibilants[:12],
        "plosive_events": plosives[:12],
        "nonspeech_bursts": nonspeech_bursts(levels, masks["speech"], floor, low_band, body_band),
        "listen": listen_points(samples),
        "room_tone_window_s": longest_quiet_window(levels, floor),
    }
    report["recommendations"], report["suggested_params"] = recommend(report)
    if write_png:
        report["spectrum_png"] = spectrum_png(mono_path, Path(out_dir) / f"{stem}.spectrum.png")
    mono_path.unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description="Measure dialogue audio and recommend a cleaning chain.")
    parser.add_argument("inputs", nargs="+", help="audio or video files")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--noise-window", type=parse_window, help="start:end seconds of pure room tone, overrides the p5 estimate")
    parser.add_argument("--no-png", action="store_true")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = {}
    for path in args.inputs:
        report = diagnose(path, out_dir, args.noise_window, not args.no_png)
        combined[Path(path).stem] = report
        (out_dir / f"{Path(path).stem}.diagnosis.json").write_text(json.dumps(report, indent=1))
        bands = report["speech_band_balance_db"]
        print(
            f"{Path(path).stem}: floor {report['room_tone_p5_dbfs']} dBFS, SNR {report['snr_db']} dB, "
            f"I {report['lufs_i_mono']} LUFS, TP {report['true_peak_dbtp']} dBTP, 5-10k {bands.get('5k-10k')} dB, "
            f"hum max {max(report['hum_peak_above_local_db'].values())} dB, plosives {len(report['plosive_events'])}, "
            f"bursts {len(report['nonspeech_bursts'])}"
        )
        for item in report["recommendations"]:
            print(f"  - {item['issue']}: {item['action']} ({item['evidence']})")
        print(f"  suggested params: {report['suggested_params']}")
    (out_dir / "diagnosis.json").write_text(json.dumps(combined, indent=1))


if __name__ == "__main__":
    main()
