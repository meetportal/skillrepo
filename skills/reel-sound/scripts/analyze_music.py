import argparse
import sys
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from find_downbeats import ANALYSIS_RATE, BEATS_PER_BAR, HOP, analyse_track
from soundlib import decode_mono, ebur128, write_json

BANDS = [(20, 150, "sub_bass"), (150, 500, "low_mid"), (500, 1000, "mid"), (1000, 4000, "presence"), (4000, 11025, "air")]
PHONE_SPEAKER_CHAIN = "highpass=f=350:poles=2,highpass=f=350:poles=2,lowpass=f=9000"


def band_shares(samples):
    spectrum = np.abs(librosa.stft(samples, n_fft=4096, hop_length=2048)) ** 2
    freqs = librosa.fft_frequencies(sr=ANALYSIS_RATE, n_fft=4096)
    total = spectrum.sum()
    return {name: round(float(spectrum[(freqs >= low) & (freqs < high)].sum() / total * 100), 2) for low, high, name in BANDS}


def energy_curve(frames, step, duration):
    curve = []
    for start in np.arange(0.0, duration, step):
        values = [s for t, _, s in frames if start < t <= start + step and np.isfinite(s) and s > -70.0]
        curve.append(round(float(np.median(values)), 1) if values else None)
    return curve


def bar_features(samples, beats):
    frames = librosa.time_to_frames(beats, sr=ANALYSIS_RATE, hop_length=HOP)
    mfcc = librosa.feature.mfcc(y=samples, sr=ANALYSIS_RATE, n_mfcc=13, hop_length=HOP)
    chroma = librosa.feature.chroma_stft(y=samples, sr=ANALYSIS_RATE, hop_length=HOP)
    rms = librosa.feature.rms(y=samples, hop_length=HOP)
    stacked = np.vstack([zscore_rows(mfcc[1:]), zscore_rows(chroma), zscore_rows(rms)])
    return librosa.util.sync(stacked, frames, aggregate=np.mean)


def zscore_rows(matrix):
    return (matrix - matrix.mean(axis=1, keepdims=True)) / (matrix.std(axis=1, keepdims=True) + 1e-9)


def loop_candidates(samples, analysis, window_bars, min_loop_s, top):
    beats = np.array(analysis["beats"])
    phase = analysis["downbeat_phase"]
    features = bar_features(samples, beats)
    beat_count = features.shape[1]
    window = window_bars * BEATS_PER_BAR
    downbeat_indices = list(range(phase, beat_count - window, BEATS_PER_BAR))
    candidates = []
    for i in downbeat_indices:
        a = features[:, i:i + window].ravel()
        for j in downbeat_indices:
            if beats[j] - beats[i] < min_loop_s:
                continue
            b = features[:, j:j + window].ravel()
            similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            candidates.append((similarity, float(beats[i]), float(beats[j])))
    candidates.sort(reverse=True)
    return [{"similarity": round(s, 3), "loop_to_s": round(a, 3), "loop_from_s": round(b, 3), "loop_length_s": round(b - a, 3)} for s, a, b in candidates[:top]]


def analyse(path, step, window_bars, min_loop_s):
    samples = decode_mono(path, ANALYSIS_RATE)
    analysis = analyse_track(path)
    full = ebur128(path)
    phone = ebur128(path, PHONE_SPEAKER_CHAIN)
    centroid = librosa.feature.spectral_centroid(y=samples, sr=ANALYSIS_RATE, hop_length=2048)[0]
    curve = energy_curve(full["frames"], step, analysis["duration_s"])
    finite = [v for v in curve if v is not None]
    return {
        "file": str(Path(path).resolve()),
        "duration_s": analysis["duration_s"],
        "tempo_bpm": analysis["tempo_bpm"],
        "beat_interval_cv": analysis["beat_interval_cv"],
        "first_downbeat_s": analysis["downbeats"][0] if analysis["downbeats"] else None,
        "integrated_lufs": full["integrated"],
        "lra_lu": full["lra"],
        "true_peak_dbtp": full["true_peak"],
        "phone_speaker_retained_lu": round(phone["integrated"] - full["integrated"], 2),
        "spectral_centroid_hz": {"median": round(float(np.median(centroid))), "p10": round(float(np.percentile(centroid, 10))), "p90": round(float(np.percentile(centroid, 90)))},
        "band_energy_pct": band_shares(samples),
        "energy_curve_step_s": step,
        "energy_curve_lufs_s": curve,
        "energy_spread_lu": round(float(np.percentile(finite, 90) - np.percentile(finite, 10)), 1) if finite else None,
        "loops": loop_candidates(samples, analysis, window_bars, min_loop_s, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Measure candidate music beds: tempo, energy curve, spectral centroid, band balance, phone-speaker survival and bar-aligned loop points.")
    parser.add_argument("music", nargs="+", help="music files")
    parser.add_argument("--out", required=True, help="output json path")
    parser.add_argument("--step", type=float, default=4.0, help="energy curve window in seconds")
    parser.add_argument("--loop-window-bars", type=int, default=2, help="bars compared at each loop point")
    parser.add_argument("--min-loop", type=float, default=20.0, help="shortest loop length in seconds")
    args = parser.parse_args()
    results = [analyse(path, args.step, args.loop_window_bars, args.min_loop) for path in args.music]
    write_json(args.out, results)
    for r in results:
        bands = r["band_energy_pct"]
        best_loop = r["loops"][0] if r["loops"] else {}
        print(
            f"{Path(r['file']).name}: {r['duration_s']:.0f}s {r['tempo_bpm']} BPM cv {r['beat_interval_cv']} | I {r['integrated_lufs']} LUFS LRA {r['lra_lu']} | "
            f"centroid {r['spectral_centroid_hz']['median']} Hz | phone retained {r['phone_speaker_retained_lu']} LU | "
            f"bands sub {bands['sub_bass']} lowmid {bands['low_mid']} mid {bands['mid']} presence {bands['presence']} air {bands['air']} | "
            f"spread {r['energy_spread_lu']} LU | loop {best_loop.get('similarity')} ({best_loop.get('loop_length_s')}s)"
        )


if __name__ == "__main__":
    main()
