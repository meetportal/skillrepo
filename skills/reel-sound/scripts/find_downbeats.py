import argparse
import sys
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import decode_mono, write_json

ANALYSIS_RATE = 22050
HOP = 512
BEATS_PER_BAR = 4


def track_beats(samples, sample_rate=ANALYSIS_RATE, start_bpm=110.0):
    onset_env = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sample_rate, hop_length=HOP, start_bpm=start_bpm, tightness=200,
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate, hop_length=HOP)
    intervals = np.diff(beat_times)
    if len(intervals) > 8:
        slope = np.polyfit(np.arange(len(beat_times)), beat_times, 1)[0]
        return 60.0 / float(slope), beat_times, beat_frames
    return float(np.atleast_1d(tempo)[0]), beat_times, beat_frames


def beat_features(samples, beat_frames, sample_rate=ANALYSIS_RATE):
    spectrum = np.abs(librosa.stft(samples, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=2048)
    low_band = spectrum[(freqs >= 30) & (freqs <= 150)].sum(axis=0)
    low_flux = np.maximum(0.0, np.diff(low_band, prepend=low_band[:1]))
    kick = np.array([low_flux[max(0, f - 2):f + 3].max() for f in beat_frames])
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate, hop_length=HOP)
    chroma_sync = librosa.util.sync(chroma, beat_frames, aggregate=np.median)[:, :len(beat_frames)]
    chroma_change = np.r_[0.0, np.linalg.norm(np.diff(chroma_sync, axis=1), axis=0)]
    bar_novelty = np.zeros(len(beat_frames))
    for i in range(BEATS_PER_BAR, len(beat_frames) - BEATS_PER_BAR):
        after = chroma_sync[:, i:i + BEATS_PER_BAR].mean(axis=1)
        before = chroma_sync[:, i - BEATS_PER_BAR:i].mean(axis=1)
        bar_novelty[i] = np.linalg.norm(after - before)
    return {"kick": kick, "chroma_change": chroma_change, "bar_novelty": bar_novelty}


def zscore(values):
    spread = values.std()
    return (values - values.mean()) / spread if spread > 0 else values * 0.0


PHASE_WEIGHTS = {"bar_novelty": 1.0, "chroma_change": 0.5, "kick": 0.5}


def downbeat_phase(features):
    score = sum(weight * zscore(features[name]) for name, weight in PHASE_WEIGHTS.items())
    phase_scores = np.array([score[phase::BEATS_PER_BAR].mean() for phase in range(BEATS_PER_BAR)])
    ranked = np.sort(phase_scores)[::-1]
    confidence = float((ranked[0] - ranked[1]) / (phase_scores.std() + 1e-9))
    return int(np.argmax(phase_scores)), [float(v) for v in phase_scores], confidence


def analyse_track(path, start_bpm=110.0, forced_phase=None):
    samples = decode_mono(path, ANALYSIS_RATE)
    tempo, beat_times, beat_frames = track_beats(samples, ANALYSIS_RATE, start_bpm)
    phase, phase_scores, confidence = downbeat_phase(beat_features(samples, beat_frames))
    if forced_phase is not None:
        phase = forced_phase
    downbeats = beat_times[phase::BEATS_PER_BAR]
    intervals = np.diff(beat_times)
    return {
        "tempo_bpm": round(tempo, 2),
        "beat_period_s": round(60.0 / tempo, 4),
        "beat_interval_cv": round(float(intervals.std() / intervals.mean()), 4) if len(intervals) else None,
        "downbeat_phase": phase,
        "phase_scores": [round(s, 3) for s in phase_scores],
        "phase_confidence": round(confidence, 2),
        "beats": [round(float(t), 4) for t in beat_times],
        "downbeats": [round(float(t), 4) for t in downbeats],
        "duration_s": round(len(samples) / ANALYSIS_RATE, 3),
    }


def nearest(values, x):
    index = int(np.argmin(np.abs(values - x)))
    return float(values[index]), float(x - values[index])


def best_offset(downbeats, targets, weights, duration, track_length, tolerance, min_offset, max_offset):
    candidates = sorted({round(float(d - t), 4) for d in downbeats for t in targets})
    best = None
    for offset in candidates:
        if offset < min_offset or offset > max_offset or offset + duration > track_length:
            continue
        errors = np.array([nearest(downbeats, t + offset)[1] for t in targets])
        hits = float(np.sum(weights * (np.abs(errors) <= tolerance)))
        cost = float(np.sum(weights * np.abs(errors)))
        key = (-hits, cost)
        if best is None or key < best[0]:
            best = (key, offset, errors)
    if best is None:
        raise SystemExit("track is shorter than the requested duration for every candidate offset")
    return best[1], best[2]


def plan_sections(downbeats, targets, duration, offset, tolerance, track_length):
    sections = [{"out_start": 0.0, "src_start": offset}]
    for target in targets:
        if target <= 0.0:
            continue
        current = sections[-1]
        playhead = current["src_start"] + (target - current["out_start"])
        landing, error = nearest(downbeats, playhead)
        if abs(error) <= tolerance:
            continue
        if landing + (duration - target) > track_length:
            raise SystemExit(f"edit at {target:.2f}s would run past the end of the track")
        sections.append({"out_start": round(float(target), 4), "src_start": round(landing, 4)})
    for index, section in enumerate(sections):
        section["out_end"] = sections[index + 1]["out_start"] if index + 1 < len(sections) else round(duration, 4)
        section["out_start"] = round(section["out_start"], 4)
    return sections


def source_time(sections, out_time):
    section = [s for s in sections if s["out_start"] <= out_time + 1e-9][-1]
    return section["src_start"] + (out_time - section["out_start"])


def parse_targets(text):
    targets, weights = [], []
    for item in text.split(","):
        time_text, _, weight_text = item.strip().partition(":")
        targets.append(float(time_text))
        weights.append(float(weight_text) if weight_text else 1.0)
    return np.array(targets), np.array(weights)


def main():
    parser = argparse.ArgumentParser(description="Track beats and downbeats of a music bed and find the start offset (and optional bar-line edits) that land downbeats on given output times.")
    parser.add_argument("music", help="music file (any format ffmpeg reads)")
    parser.add_argument("--targets", required=True, help="comma separated output times in seconds, optional :weight, e.g. 0:3,8.0,16.0,40.0:2")
    parser.add_argument("--duration", type=float, required=True, help="output timeline duration in seconds")
    parser.add_argument("--tolerance", type=float, default=0.06, help="max downbeat error in seconds that counts as a hit (default 0.06, 1.5 frames at 25 fps)")
    parser.add_argument("--min-offset", type=float, default=0.0, help="earliest allowed music start position in seconds (skip a soft intro)")
    parser.add_argument("--max-offset", type=float, default=float("inf"), help="latest allowed music start position in seconds")
    parser.add_argument("--allow-edits", action="store_true", help="add bar-line music edits at targets that the single offset misses")
    parser.add_argument("--start-bpm", type=float, default=110.0, help="tempo prior for the tracker")
    parser.add_argument("--phase", type=int, choices=range(BEATS_PER_BAR), help="force the downbeat phase (beat index 0-3) after a listen")
    parser.add_argument("--grid", choices=["downbeats", "beats"], default="downbeats", help="snap targets to downbeats, or to any beat when the downbeat confidence is low")
    parser.add_argument("--out", required=True, help="output json path")
    args = parser.parse_args()

    analysis = analyse_track(args.music, args.start_bpm, args.phase)
    downbeats = np.array(analysis[args.grid])
    targets, weights = parse_targets(args.targets)
    offset, errors = best_offset(downbeats, targets, weights, args.duration, analysis["duration_s"], args.tolerance, args.min_offset, args.max_offset)
    if args.allow_edits:
        sections = plan_sections(downbeats, sorted(targets), args.duration, offset, args.tolerance, analysis["duration_s"])
    else:
        sections = [{"out_start": 0.0, "src_start": round(offset, 4), "out_end": round(args.duration, 4)}]
    target_report = []
    for target in targets:
        source = source_time(sections, float(target))
        landing, error = nearest(downbeats, source)
        target_report.append({"time": float(target), "source_time": round(source, 4), "nearest_grid_point": round(landing, 4), "error_ms": round(error * 1000, 1)})
    result = {
        "music": str(Path(args.music).resolve()),
        **{k: analysis[k] for k in ("tempo_bpm", "beat_period_s", "beat_interval_cv", "downbeat_phase", "phase_scores", "phase_confidence", "duration_s")},
        "grid": args.grid,
        "offset": round(offset, 4),
        "sections": sections,
        "targets": target_report,
        "downbeats": analysis["downbeats"],
        "beats": analysis["beats"],
    }
    write_json(args.out, result)
    hits = sum(1 for t in target_report if abs(t["error_ms"]) <= args.tolerance * 1000)
    print(f"tempo {analysis['tempo_bpm']} BPM, bar {analysis['beat_period_s'] * BEATS_PER_BAR:.3f}s, downbeat phase {analysis['downbeat_phase']} (confidence {analysis['phase_confidence']}, below 1.0 means listen and pass --phase or use --grid beats)")
    print(f"offset {offset:.3f}s, sections {len(sections)}, targets on the {args.grid} grid {hits}/{len(target_report)}")
    for t in target_report:
        print(f"  out {t['time']:7.2f}s  src {t['source_time']:7.3f}s  grid error {t['error_ms']:+7.1f} ms")


if __name__ == "__main__":
    main()
