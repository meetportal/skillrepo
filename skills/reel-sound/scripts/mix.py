import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import SAMPLE_RATE, decode_mono, ebur128, last_json_block, load_json, probe_duration, write_json

DUAL_MONO = "aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0"
STEREO = f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
FLOAT_WAV = ["-c:a", "pcm_f32le", "-ar", str(SAMPLE_RATE)]
IMPACT_DIP_LEAD_S = 0.05
IMPACT_DIP_ATTACK_S = 0.04
IMPACT_DIP_HOLD_S = 0.35
IMPACT_DIP_RELEASE_S = 0.25
LIFT_RAMP_S = 0.3
PRE_LIMIT_MARGIN_DB = 0.5
SPEECH_MOMENTARY_BELOW_I = 8.0
METER_WARMUP_S = 3.0
GAP_MIN_S = 0.2
PRE_LIMIT_WARN_DB = 3.0
SILENCE_LUFS = -70.0


def ffmpeg(args):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{result.stderr[-3000:]}")
    return result


def run_graph(inputs, graph, output_label, out_path, work, extra=None):
    script = Path(work) / f"{Path(out_path).stem}.graph"
    script.write_text(graph)
    args = []
    for path in inputs:
        args += ["-i", str(path)]
    args += ["-filter_complex_script", str(script), "-map", f"[{output_label}]", *(extra or FLOAT_WAV), str(out_path)]
    ffmpeg(args)


def music_sections(args, duration):
    if args.music_plan:
        plan = load_json(args.music_plan)
        return plan["sections"]
    return [{"out_start": 0.0, "src_start": args.music_offset, "out_end": duration}]


def build_bed(args, duration, work):
    sections = music_sections(args, duration)
    xfade = args.music_xfade
    parts, labels = [], []
    for index, section in enumerate(sections):
        lead = xfade if index > 0 else 0.0
        tail = xfade if index + 1 < len(sections) else 0.0
        src_start = max(0.0, section["src_start"] - lead)
        length = section["out_end"] - section["out_start"] + lead + tail
        chain = f"[m{index}]atrim=start={src_start:.6f}:duration={length:.6f},asetpts=PTS-STARTPTS"
        if lead:
            chain += f",afade=t=in:d={lead:.4f}:curve=qsin"
        if tail:
            chain += f",afade=t=out:st={length - tail:.6f}:d={tail:.4f}:curve=qsin"
        delay_ms = round(max(0.0, section["out_start"] - lead) * 1000)
        chain += f",adelay={delay_ms}:all=1[s{index}]"
        parts.append(chain)
        labels.append(f"[s{index}]")
    split = f"[0:a]{STEREO},asplit={len(sections)}" + "".join(f"[m{i}]" for i in range(len(sections)))
    mix = "".join(labels) + f"amix=inputs={len(sections)}:normalize=0:duration=longest" if len(sections) > 1 else labels[0] + "anull"
    eq = f",{args.bed_eq}" if args.bed_eq else ""
    graph = ";".join([split, *parts, f"{mix}{eq},apad,atrim=end={duration:.6f}[bed]"])
    out = Path(work) / "bed_raw.wav"
    run_graph([args.music], graph, "bed", out, work)
    return out, sections


def automation_expression(placements, lift):
    terms = []
    for p in placements:
        depth = p.get("duck_bed_db") or 0.0
        if depth <= 0:
            continue
        a = p["anchor_time"] - IMPACT_DIP_LEAD_S
        b = p["anchor_time"] + IMPACT_DIP_HOLD_S + IMPACT_DIP_RELEASE_S
        terms.append(f"-{depth:.3f}*clip((t-{a:.4f})/{IMPACT_DIP_ATTACK_S},0,1)*clip(({b:.4f}-t)/{IMPACT_DIP_RELEASE_S},0,1)")
    if lift:
        start, gain_db = lift
        terms.append(f"+{gain_db:.3f}*clip((t-{start:.4f})/{LIFT_RAMP_S},0,1)")
    if not terms:
        return None
    return f"volume=volume='pow(10,({''.join(terms)})/20)':eval=frame"


def duck_bed(args, voice, voice_gain_db, bed_raw, bed_gain_db, threshold_db, automation, duration, work, name):
    chain_bed = f"[1:a]{STEREO},volume={bed_gain_db:.3f}dB[bed]"
    chain_key = f"[0:a]{DUAL_MONO},{STEREO},volume={voice_gain_db:.3f}dB,apad,atrim=end={duration:.6f}[key]"
    duck = (
        f"[bed][key]sidechaincompress=threshold={10 ** (threshold_db / 20):.6f}:ratio={args.duck_ratio}:"
        f"attack={args.duck_attack}:release={args.duck_release}:makeup=1:knee=2.82843"
    )
    tail = f",asetnsamples=n=480,{automation}" if automation else ""
    graph = ";".join([chain_bed, chain_key, f"{duck}{tail}[out]"])
    out = Path(work) / name
    run_graph([voice, bed_raw], graph, "out", out, work)
    return out


def gain_file(path, gain_db, filter_prefix, work, name):
    out = Path(work) / name
    ffmpeg(["-i", str(path), "-af", f"{filter_prefix},{STEREO},volume={gain_db:.3f}dB", *FLOAT_WAV, str(out)])
    return out


def frames_by_time(frames):
    return {round(t, 1): (m, s) for t, m, s in frames if t >= METER_WARMUP_S}


def duck_depth(unducked_frames, ducked_frames, voice_frames, voice_i):
    unducked = frames_by_time(unducked_frames)
    ducked = frames_by_time(ducked_frames)
    speech_m, speech_s = [], []
    for t, m, s in voice_frames:
        key = round(t, 1)
        if key not in unducked or key not in ducked:
            continue
        um, us = unducked[key]
        dm, ds = ducked[key]
        if not all(math.isfinite(v) and v > SILENCE_LUFS for v in (um, us, dm, ds)):
            continue
        if m > voice_i - SPEECH_MOMENTARY_BELOW_I:
            speech_m.append(um - dm)
        if math.isfinite(s) and s > voice_i - 3.0:
            speech_s.append(us - ds)
    median = lambda values: round(float(np.median(values)), 2) if values else None
    return {"speech_momentary_db": median(speech_m), "speech_short_term_db": median(speech_s), "speech_frames": len(speech_m)}


def frame_rms_db(path, frame_s):
    samples = decode_mono(path)
    size = int(frame_s * SAMPLE_RATE)
    usable = len(samples) // size * size
    return 10 * np.log10(np.mean(samples[:usable].astype(np.float64).reshape(-1, size) ** 2, axis=1) + 1e-12)


def duck_envelope(voice_ref, bed_unducked, bed_ducked, target_i):
    frame_s = 0.02
    voice = frame_rms_db(voice_ref, frame_s)
    unducked = frame_rms_db(bed_unducked, frame_s)
    ducked = frame_rms_db(bed_ducked, frame_s)
    count = min(len(voice), len(unducked), len(ducked))
    voice, unducked, ducked = voice[:count], unducked[:count], ducked[:count]
    reduction = unducked - ducked
    audible = unducked > -60.0
    speech = (voice > target_i - 12.0) & audible
    quiet = voice < target_i - 30.0
    rises, gap_lengths = [], []
    index = 0
    while index < count:
        if quiet[index]:
            end = index
            while end < count and quiet[end]:
                end += 1
            length = (end - index) * frame_s
            if length >= GAP_MIN_S and index > 0 and end < count and audible[index:end].all():
                rises.append(float(reduction[max(0, index - 2):index].mean() - reduction[index:end].min()))
                gap_lengths.append(round(length, 2))
            index = end
        else:
            index += 1
    return {
        "speech_reduction_db": round(float(np.median(reduction[speech])), 2) if speech.any() else None,
        "gaps_measured": len(rises),
        "gap_lengths_s": gap_lengths,
        "gap_rise_db_median": round(float(np.median(rises)), 2) if rises else None,
        "gap_rise_db_max": round(float(np.max(rises)), 2) if rises else None,
    }


def build_sfx(placements, duration, work):
    if not placements:
        return None
    parts, labels = [], []
    for index, p in enumerate(placements):
        available = p["file_duration_s"] - p["trim_start"]
        length = min(available, p["max_dur"]) if p.get("max_dur") else available
        chain = f"[{index}:a]{DUAL_MONO},{STEREO},atrim=start={p['trim_start']:.6f}:duration={length:.6f},asetpts=PTS-STARTPTS"
        fade = p.get("fade_out") or 0.0
        if fade > 0:
            chain += f",afade=t=out:st={max(0.0, length - fade):.6f}:d={min(fade, length):.6f}"
        chain += f",volume={p['gain_db']:.3f}dB,adelay={round(p['start'] * 1000)}:all=1[x{index}]"
        parts.append(chain)
        labels.append(f"[x{index}]")
    graph = ";".join([*parts, "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,apad,atrim=end={duration:.6f}[sfx]"])
    out = Path(work) / "sfx_bus.wav"
    run_graph([p["file"] for p in placements], graph, "sfx", out, work)
    return out


def sum_stems(stems, duration, out_path, work):
    inputs = [s for s in stems if s]
    labels = "".join(f"[{i}:a]" for i in range(len(inputs)))
    graph = f"{labels}amix=inputs={len(inputs)}:normalize=0:duration=longest,apad,atrim=end={duration:.6f}[mix]"
    run_graph(inputs, graph, "mix", out_path, work)


def measure_for_loudnorm(path):
    reading = ebur128(path)
    return {
        "input_i": reading["integrated"],
        "input_tp": reading["true_peak"],
        "input_lra": reading["lra"],
        "input_thresh": reading["threshold"],
    }


def master(args, mix_pre, duration, work):
    measured = measure_for_loudnorm(mix_pre)
    gain = args.target_i - measured["input_i"]
    ceiling = args.target_tp - gain - PRE_LIMIT_MARGIN_DB
    pre_limited = None
    source = mix_pre
    if measured["input_tp"] > ceiling:
        source = Path(work) / "mix_pre_peak_limited.wav"
        ffmpeg(["-i", str(mix_pre), "-af", f"alimiter=limit={10 ** (ceiling / 20):.6f}:level=false:attack=5:release=60:asc=1", *FLOAT_WAV, str(source)])
        pre_limited = {"ceiling_dbtp": round(ceiling, 2), "input_tp_before": measured["input_tp"], "peak_reduction_db": round(measured["input_tp"] - ceiling, 2)}
        measured = measure_for_loudnorm(source)
    lra_param = max(args.target_lra, math.ceil(measured["input_lra"] * 10 + 1) / 10)
    loudnorm = (
        f"loudnorm=I={args.target_i}:TP={args.target_tp}:LRA={lra_param}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:linear=true:print_format=json"
    )
    chain = f"{loudnorm},aresample={SAMPLE_RATE},alimiter=limit={args.safety_limit}:level=false,{STEREO},apad,atrim=end={duration:.6f}"
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-y", "-i", str(source), "-af", chain, "-c:a", "pcm_s24le", "-ar", str(SAMPLE_RATE), str(args.out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg loudnorm pass 2 failed:\n{result.stderr[-3000:]}")
    second = last_json_block(result.stderr)
    return {
        "pass1_ebur128": measured,
        "pre_limiter": pre_limited,
        "lra_parameter": lra_param,
        "normalization_type": second.get("normalization_type"),
        "loudnorm_gain_db": round(args.target_i - measured["input_i"], 2),
    }


def parse_lift(text):
    if not text:
        return None
    start, _, gain = text.partition(":")
    return float(start), float(gain)


def shifted(level, gain):
    return round(level + gain, 1) if level is not None else None


def segment_level(frames, start, end, use_short_term=True):
    values = [(s if use_short_term else m) for t, m, s in frames if start <= t <= end]
    values = [v for v in values if math.isfinite(v) and v > -70]
    return round(float(np.median(values)), 1) if values else None


def main():
    parser = argparse.ArgumentParser(description="Mix voice + sidechain-ducked music bed + placed SFX, then master with two-pass linear loudnorm and a safety limiter.")
    parser.add_argument("--voice", required=True, help="processed dialogue (mono or stereo), not loudness normalised")
    parser.add_argument("--music", required=True, help="music bed file")
    parser.add_argument("--music-plan", help="find_downbeats.py output; its sections define where the bed starts and where it is edited")
    parser.add_argument("--music-offset", type=float, default=0.0, help="music start position when no plan is given")
    parser.add_argument("--music-xfade", type=float, default=0.03, help="crossfade at music edits, seconds")
    parser.add_argument("--sfx", help="sfx_cues.py placements json")
    parser.add_argument("--duration", type=float, help="output duration in seconds (default: voice duration); audio is padded or trimmed to it")
    parser.add_argument("--out-pre", required=True, help="mix_pre.wav (float, before mastering)")
    parser.add_argument("--out", required=True, help="mastered mix.wav (24-bit stereo 48 kHz)")
    parser.add_argument("--report", help="write all measurements to this json")
    parser.add_argument("--stems-dir", help="keep the bed and SFX stems here")
    parser.add_argument("--target-i", type=float, default=-14.0)
    parser.add_argument("--target-tp", type=float, default=-1.5)
    parser.add_argument("--target-lra", type=float, default=7.0)
    parser.add_argument("--bed-under", type=float, default=10.0, help="unducked bed loudness below the voice, LU (default 10; plus the duck gives about 16)")
    parser.add_argument("--bed-eq", default="highpass=f=100:poles=2", help="filter chain applied to the bed before levelling ('' for none)")
    parser.add_argument("--bed-lift", help="start:dB raise of the bed after the talking ends, e.g. 46.9:4 for the end card")
    parser.add_argument("--duck-db", type=float, default=6.0, help="target sidechain gain reduction under speech, dB")
    parser.add_argument("--duck-threshold-db", type=float, help="fixed sidechain threshold in dBFS (skips calibration)")
    parser.add_argument("--duck-ratio", type=float, default=6.0)
    parser.add_argument("--duck-attack", type=float, default=15.0, help="ms")
    parser.add_argument("--duck-release", type=float, default=300.0, help="ms")
    parser.add_argument("--safety-limit", type=float, default=0.84, help="alimiter ceiling after loudnorm, linear (0.84 is -1.5 dBFS)")
    args = parser.parse_args()

    duration = args.duration or probe_duration(args.voice)
    placements = load_json(args.sfx)["placements"] if args.sfx else []
    temp = tempfile.TemporaryDirectory()
    work = Path(args.stems_dir) if args.stems_dir else Path(temp.name)
    work.mkdir(parents=True, exist_ok=True)

    voice_measure = ebur128(args.voice, f"{DUAL_MONO},{STEREO}")
    voice_gain = args.target_i - voice_measure["integrated"]
    voice_ref = gain_file(args.voice, voice_gain, DUAL_MONO, work, "voice_ref.wav")
    voice_frames = ebur128(voice_ref)["frames"]

    bed_raw, sections = build_bed(args, duration, work)
    bed_gain = (args.target_i - args.bed_under) - ebur128(bed_raw)["integrated"]
    bed_level = gain_file(bed_raw, bed_gain, "anull", work, "bed_unducked.wav")
    bed_level_frames = ebur128(bed_level)["frames"]

    slope = 1.0 - 1.0 / args.duck_ratio
    threshold_db = args.duck_threshold_db if args.duck_threshold_db is not None else args.target_i - args.duck_db / slope
    calibration = []
    for _ in range(1 if args.duck_threshold_db is not None else 3):
        ducked = duck_bed(args, args.voice, voice_gain, bed_raw, bed_gain, threshold_db, None, duration, work, "bed_ducked.wav")
        depth = duck_depth(bed_level_frames, ebur128(ducked)["frames"], voice_frames, args.target_i)
        calibration.append({"threshold_db": round(threshold_db, 2), **depth})
        measured = depth["speech_momentary_db"]
        if measured is None or abs(measured - args.duck_db) <= 0.75:
            break
        threshold_db -= (args.duck_db - measured) / slope

    envelope = duck_envelope(voice_ref, bed_level, ducked, args.target_i)
    automation = automation_expression(placements, parse_lift(args.bed_lift))
    bed_final = duck_bed(args, args.voice, voice_gain, bed_raw, bed_gain, threshold_db, automation, duration, work, "bed_final.wav")
    sfx_bus = build_sfx(placements, duration, work)
    Path(args.out_pre).parent.mkdir(parents=True, exist_ok=True)
    sum_stems([voice_ref, bed_final, sfx_bus], duration, args.out_pre, work)

    mastering = master(args, args.out_pre, duration, work)
    final = ebur128(args.out)
    gain = mastering["loudnorm_gain_db"]
    bed_final_frames = ebur128(bed_final)["frames"]
    speech_times = [t for t, m, s in voice_frames if m > args.target_i - SPEECH_MOMENTARY_BELOW_I]
    lift = parse_lift(args.bed_lift)
    bed_by_time = frames_by_time(bed_final_frames)
    pick = lambda times, idx: [bed_by_time[round(t, 1)][idx] for t in times if round(t, 1) in bed_by_time and bed_by_time[round(t, 1)][idx] > SILENCE_LUFS]
    speech_m = pick(speech_times, 0)
    lift_momentary = segment_level(bed_final_frames, lift[0] + 0.5, duration, use_short_term=False) if lift else None
    last_short_term = segment_level(bed_final_frames, duration - 0.15, duration)
    report = {
        "duration_s": round(duration, 3),
        "voice": {"input_integrated_lufs": voice_measure["integrated"], "gain_db": round(voice_gain, 2), "lra_lu": voice_measure["lra"]},
        "music": {"file": str(Path(args.music).resolve()), "sections": sections, "gain_db": round(bed_gain, 2), "eq": args.bed_eq},
        "ducking": {"target_db": args.duck_db, "threshold_db": round(threshold_db, 2), "ratio": args.duck_ratio, "attack_ms": args.duck_attack, "release_ms": args.duck_release, "calibration": calibration, "envelope": envelope},
        "bed_in_final_mix": {
            "unducked_integrated_lufs": round(args.target_i - args.bed_under + gain, 1),
            "under_speech_momentary_lufs": round(float(np.median(speech_m)) + gain, 1) if speech_m else None,
            "lift_window_momentary_lufs": shifted(lift_momentary, gain),
            "last_frame_short_term_lufs": shifted(last_short_term, gain),
        },
        "sfx": {"count": len(placements), "peak_shift_db": gain, "impact_dips": sum(1 for p in placements if (p.get("duck_bed_db") or 0) > 0)},
        "master": {**mastering, "final_integrated_lufs": final["integrated"], "final_true_peak_dbtp": final["true_peak"], "final_lra_lu": final["lra"], "final_duration_s": round(probe_duration(args.out), 4)},
    }
    gates = {
        "integrated_within_1_lu": abs(final["integrated"] - args.target_i) <= 1.0,
        "true_peak_at_or_below_target": final["true_peak"] is not None and final["true_peak"] <= args.target_tp,
        "lra_at_or_below_target": final["lra"] <= args.target_lra,
        "linear_mode": mastering["normalization_type"] == "linear",
        "duration_within_1ms": abs(report["master"]["final_duration_s"] - duration) <= 0.001,
    }
    report["gates"] = gates
    warnings = []
    if mastering["pre_limiter"] and mastering["pre_limiter"]["peak_reduction_db"] > PRE_LIMIT_WARN_DB:
        warnings.append(f"pre-loudnorm limiter took {mastering['pre_limiter']['peak_reduction_db']} dB off the peaks; lower the voice compressor threshold by 2 dB (or add a voice-stage limiter) and remix")
    if mastering["lra_parameter"] > args.target_lra:
        warnings.append(f"mix LRA {mastering['pass1_ebur128']['input_lra']} LU is above {args.target_lra}; loudnorm ran linear with LRA={mastering['lra_parameter']}, compress the voice more")
    report["warnings"] = warnings
    if args.report:
        write_json(args.report, report)
    print(f"voice in {voice_measure['integrated']} LUFS, gain {voice_gain:+.2f} dB; bed gain {bed_gain:+.2f} dB; {len(sections)} music section(s); {len(placements)} SFX")
    for row in calibration:
        print(f"duck calibration: threshold {row['threshold_db']} dBFS -> {row['speech_momentary_db']} dB under speech (ebur128 momentary), {row['speech_short_term_db']} dB (ebur128 short-term)")
    print(f"duck envelope: {envelope['speech_reduction_db']} dB under speech (20 ms RMS), bed rises {envelope['gap_rise_db_median']} dB median / {envelope['gap_rise_db_max']} dB max in {envelope['gaps_measured']} gaps of {GAP_MIN_S}s or more")
    bed = report["bed_in_final_mix"]
    print(f"bed in final mix: unducked {bed['unducked_integrated_lufs']} LUFS, under speech {bed['under_speech_momentary_lufs']} LUFS M, lift window {bed['lift_window_momentary_lufs']} LUFS M, last frame {bed['last_frame_short_term_lufs']} LUFS S")
    first = mastering["pass1_ebur128"]
    print(f"pass 1 (ebur128): I {first['input_i']} TP {first['input_tp']} LRA {first['input_lra']}; pre-limiter {mastering['pre_limiter']}; pass 2 loudnorm {mastering['normalization_type']} gain {gain:+.2f} dB")
    print(f"final: I {final['integrated']} LUFS, TP {final['true_peak']} dBTP, LRA {final['lra']} LU, duration {report['master']['final_duration_s']} s")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print("gates: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in gates.items()))
    temp.cleanup()
    if not all(gates.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
