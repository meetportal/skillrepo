import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[2] / "reel-ingest" / "scripts"))
from edl_lib import audio_segments, load_json, write_json
from media import decode_audio


def rms_db(signal, rate, window_s, hop_s):
    window, hop = int(rate * window_s), int(rate * hop_s)
    count = max(1, 1 + (len(signal) - window) // hop)
    squares = np.concatenate([[0.0], np.cumsum(signal.astype(np.float64) ** 2)])
    starts = np.arange(count) * hop
    return 20 * np.log10(np.sqrt((squares[starts + window] - squares[starts]) / window) + 1e-10), hop


def check_splice(audio, highs, rate, at, reference, args):
    center = int(round(at * rate))
    context = int(args.context * rate)
    lo, hi = max(0, center - context), min(len(audio), center + context)
    envelope, hop = rms_db(audio[lo:hi], rate, 0.01, 0.0025)
    times = lo / rate + (np.arange(len(envelope)) * hop + int(rate * 0.005)) / rate
    near = np.abs(times - at) <= args.dip_window
    dip = float(envelope[near].min()) if near.any() else reference
    high_env, high_hop = rms_db(highs[lo:hi], rate, 0.0025, 0.00125)
    high_times = lo / rate + (np.arange(len(high_env)) * high_hop) / rate
    at_splice = np.abs(high_times - at) <= 0.005
    around = ~(np.abs(high_times - at) <= 0.015)
    high_jump = float(high_env[at_splice].max() - np.percentile(high_env[around], 95)) if at_splice.any() else 0.0
    step = np.abs(np.diff(audio[lo:hi]))
    step_times = lo / rate + np.arange(len(step)) / rate
    step_ratio = float(step[np.abs(step_times - at) <= 0.002].max() / (np.percentile(step[np.abs(step_times - at) > 0.01], 99.9) + 1e-12))
    return {
        "at": round(at, 3),
        "room_tone_db": round(reference, 1),
        "min_db_at_splice": round(dip, 1),
        "dip_db": round(dip - reference, 1),
        "hf_burst_db": round(high_jump, 1),
        "step_ratio": round(step_ratio, 2),
        "ok": dip >= reference - args.max_dip and high_jump <= args.max_hf_burst and step_ratio <= args.max_step_ratio,
    }


def main():
    parser = argparse.ArgumentParser(description="Audio splice gate: room tone stays continuous (the 10 ms RMS at the splice never drops more than 3 dB under the quieter take's room-tone floor) and no click at any EDL audio splice.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--audio", required=True, help="voice_cut.wav")
    parser.add_argument("--context", type=float, default=0.5, help="seconds either side analysed for clicks")
    parser.add_argument("--floor-percentile", type=float, default=5.0, help="room tone of a take = this percentile of its 10 ms RMS")
    parser.add_argument("--dip-window", type=float, default=0.02)
    parser.add_argument("--max-dip", type=float, default=3.0, help="largest allowed drop under the local room tone, dB")
    parser.add_argument("--max-hf-burst", type=float, default=6.0, help="largest allowed 4 kHz+ burst over its surroundings, dB")
    parser.add_argument("--max-step-ratio", type=float, default=1.5, help="largest sample step at the splice over the 99.9th percentile step nearby")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    edl = load_json(args.edl)
    audio, rate = soundfile.read(args.audio, dtype="float64")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    highs = sosfilt(butter(4, 4000, "highpass", fs=rate, output="sos"), audio)
    segments = audio_segments(edl)
    floors = {}
    for clip in dict.fromkeys(seg["clip"] for seg in segments):
        source = decode_audio(clip, sample_rate=rate, channels=1)
        floors[clip] = float(np.percentile(rms_db(source, rate, 0.01, 0.005)[0], args.floor_percentile))
    rows = []
    for left, right in zip(segments[:-1], segments[1:]):
        reference = min(floors[left["clip"]], floors[right["clip"]])
        rows.append(check_splice(audio, highs, rate, right["out_start"] / edl["fps"], reference, args))
    report = {"splices": rows, "pass": all(row["ok"] for row in rows)}
    write_json(args.out, report)
    for row in rows:
        print(f"splice {row['at']:7.3f}s room {row['room_tone_db']:6.1f} dB, min {row['min_db_at_splice']:6.1f} dB (dip {row['dip_db']:+5.1f}), hf burst {row['hf_burst_db']:+5.1f} dB, step x{row['step_ratio']:.2f} {'ok' if row['ok'] else 'FAIL'}")
    print("PASS" if report["pass"] else "FAIL")
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
