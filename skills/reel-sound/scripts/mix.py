import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import (
    SAMPLE_RATE,
    decode_mono,
    ebur128,
    integrated_lufs,
    last_json_block,
    load_json,
    load_words,
    momentary_curve,
    momentary_max,
    played_portion,
    power_track,
    probe_duration,
    read_stereo,
    sha256_file,
    track_lufs,
    write_float_wav,
    write_json,
)

DUAL_MONO = "aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0"
STEREO = f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
FLOAT_WAV = ["-c:a", "pcm_f32le", "-ar", str(SAMPLE_RATE)]
CONTROL_RATE = 1000
IMPACT_DIP_LEAD_S = 0.05
IMPACT_DIP_ATTACK_S = 0.04
IMPACT_DIP_HOLD_S = 0.35
IMPACT_DIP_RELEASE_S = 0.25
LIFT_RAMP_S = 0.3
DIP_RAMP_S = 0.05
RIDE_RAMP_S = 0.06
RIDE_MIN_DB = 2.0
RIDE_MAX_DB = 6.0
DROPOUT_OUT_S = 0.015
DROPOUT_IN_S = 0.03
VOICE_GAIN_RAMP_S = 0.02
ROOM_TONE_XFADE_S = 0.02
WORD_SPAN_MERGE_S = 0.3
WORD_DUCK_PRE_S = 0.08
WORD_DUCK_POST_S = 0.12
WORD_DUCK_ATTACK_S = 0.07
WORD_DUCK_RELEASE_S = 0.45
HOLD_BLOCK = 48
PRE_LIMIT_MARGIN_DB = 0.5
PRE_LIMIT_PASSES = 3
PRE_LIMIT_TOLERANCE_DB = 0.1
SPEECH_MOMENTARY_BELOW_I = 8.0
METER_WARMUP_S = 3.0
GAP_MIN_S = 0.2
PRE_LIMIT_WARN_DB = 3.0
SILENCE_LUFS = -70.0
RMS_FRAME_S = 0.02
MASKING_MIN_DB = 8.0
MIN_WORD_S = 0.01
LIMITER_WARN_DB = 1.0


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


def stale_voice_guard(args):
    if not args.voice_report:
        return None
    report = load_json(args.voice_report)
    problems = []
    voice_hash = sha256_file(args.voice)
    expected = (report.get("output") or {}).get("sha256")
    if voice_hash != expected:
        problems.append(f"--voice {args.voice} has sha256 {voice_hash[:16]}, the voice report output.sha256 is {str(expected)[:16]}: this voice.wav is not the output of that report")
    cut = args.voice_cut or (report.get("input") or {}).get("path")
    if not cut:
        problems.append("the voice report records no input path: pass --voice-cut voice_cut.wav")
    elif not Path(cut).exists():
        source = "--voice-cut" if args.voice_cut else "the voice report input path"
        problems.append(f"{source} {cut} does not exist, so the cut dialogue cannot be checked: pass --voice-cut with the current voice_cut.wav")
    else:
        cut_hash = sha256_file(cut)
        expected_input = (report.get("input") or {}).get("sha256")
        if cut_hash != expected_input:
            problems.append(f"{cut} has sha256 {cut_hash[:16]}, the voice report input.sha256 is {str(expected_input)[:16]}: the cut dialogue changed after voice-clean ran")
    failed = [name for name, passed in (report.get("gates") or {}).items() if not passed]
    if failed:
        problems.append(f"voice report gates failed: {', '.join(failed)}")
    if not report.get("gates"):
        problems.append("voice report has no gates")
    if problems:
        for problem in problems:
            print(f"VOICE GUARD: {problem}", file=sys.stderr)
        print("rerun voice-clean process_voice.py on the current voice_cut.wav, then remix", file=sys.stderr)
        raise SystemExit(2)
    return {"report": str(Path(args.voice_report).resolve()), "voice_sha256": voice_hash, "voice_cut": str(Path(cut).resolve()), "gates": report["gates"]}


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


def held_key(voice, hold_s, work):
    samples = decode_mono(voice)
    blocks = len(samples) // HOLD_BLOCK
    peaks = np.abs(samples[: blocks * HOLD_BLOCK]).reshape(blocks, HOLD_BLOCK).max(axis=1)
    width = max(1, round(hold_s * SAMPLE_RATE / HOLD_BLOCK))
    padded = np.concatenate([np.zeros(width - 1, dtype=peaks.dtype), peaks])
    held = np.lib.stride_tricks.sliding_window_view(padded, width).max(axis=1)
    raw = Path(work) / "duck_key.f32"
    np.repeat(held, HOLD_BLOCK).astype(np.float32).tofile(raw)
    out = Path(work) / "duck_key.wav"
    ffmpeg(["-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", str(raw), *FLOAT_WAV, str(out)])
    raw.unlink()
    return out


def parse_numbers(text, count, flag):
    parts = text.split(":")
    if len(parts) != count:
        raise SystemExit(f"{flag} {text}: expected {count} numbers separated by ':'")
    try:
        return [float(part) for part in parts]
    except ValueError:
        raise SystemExit(f"{flag} {text}: not a number")


def parse_window(text, flag):
    start, end = parse_numbers(text, 2, flag)
    if end <= start:
        raise SystemExit(f"{flag} {text}: end must be after start")
    return start, end


def parse_dip(text):
    start, end, depth = parse_numbers(text, 3, "--bed-dip")
    if end <= start or depth <= 0:
        raise SystemExit(f"--bed-dip {text}: needs start:end:dB with end > start and dB > 0")
    return start, end, depth


def parse_voice_gain(text):
    start, end, gain = parse_numbers(text, 3, "--voice-gain")
    if end <= start:
        raise SystemExit(f"--voice-gain {text}: end must be after start")
    return start, end, gain


def parse_room_tone_src(text):
    path, start, end = text.rsplit(":", 2)
    start, end = parse_window(f"{start}:{end}", "--room-tone-src")
    if not Path(path).exists():
        raise SystemExit(f"--room-tone-src {text}: {path} does not exist")
    return path, start, end


def parse_lift(text):
    if not text:
        return None
    start, _, gain = text.partition(":")
    return float(start), float(gain)


def control_times(count):
    return np.arange(count) / CONTROL_RATE


def window_ramp(t, start, end, ramp_in, ramp_out):
    return np.clip((t - (start - ramp_in)) / ramp_in, 0, 1) * np.clip(((end + ramp_out) - t) / ramp_out, 0, 1)


def to_samples(curve, count):
    return np.interp(np.arange(count) / SAMPLE_RATE, control_times(len(curve)), curve)


def words_in_range(words, duration):
    kept = []
    for word in words:
        start, end = max(0.0, word["start"]), min(word["end"], duration)
        if end - start >= MIN_WORD_S:
            kept.append({**word, "start": start, "end": end})
    return kept


def word_spans(words, merge_gap):
    spans = []
    for word in words:
        if spans and word["start"] - spans[-1][1] < merge_gap:
            spans[-1][1] = max(spans[-1][1], word["end"])
        else:
            spans.append([word["start"], word["end"]])
    return [tuple(span) for span in spans]


def one_pole(target, attack_s, release_s):
    up = 1.0 - math.exp(-1.0 / (attack_s * CONTROL_RATE))
    down = 1.0 - math.exp(-1.0 / (release_s * CONTROL_RATE))
    out = np.empty_like(target)
    level = float(target[0]) if len(target) else 0.0
    for index, goal in enumerate(target):
        level += (goal - level) * (up if goal > level else down)
        out[index] = level
    return out


def word_duck_db(spans, count, depth_db):
    target = np.zeros(count)
    for start, end in spans:
        a = max(0, int(math.floor((start - WORD_DUCK_PRE_S) * CONTROL_RATE)))
        b = min(count, int(math.ceil((end + WORD_DUCK_POST_S) * CONTROL_RATE)))
        target[a:b] = depth_db
    return one_pole(target, WORD_DUCK_ATTACK_S, WORD_DUCK_RELEASE_S)


def automation_db(placements, lift, dips, count):
    t = control_times(count)
    curve = np.zeros(count)
    events = []
    for p in placements:
        depth = p.get("duck_bed_db") or 0.0
        if depth <= 0:
            continue
        start = p["anchor_time"] - IMPACT_DIP_LEAD_S + IMPACT_DIP_ATTACK_S
        end = p["anchor_time"] + IMPACT_DIP_HOLD_S
        curve -= depth * window_ramp(t, start, end, IMPACT_DIP_ATTACK_S, IMPACT_DIP_RELEASE_S)
        events.append({"kind": "impact dip", "start": round(max(0.0, start - IMPACT_DIP_ATTACK_S), 3), "end": round(min(end + IMPACT_DIP_RELEASE_S, count / CONTROL_RATE), 3), "db": -depth, "detail": f"under {p['id']}"})
    for start, end, depth in dips:
        curve -= depth * window_ramp(t, start, end, DIP_RAMP_S, DIP_RAMP_S)
        events.append({"kind": "bed dip", "start": start, "end": end, "db": -depth, "detail": f"{int(DIP_RAMP_S * 1000)} ms ramps outside"})
    if lift:
        start, gain_db = lift
        curve += gain_db * np.clip((t - start) / LIFT_RAMP_S, 0, 1)
        events.append({"kind": "lift", "start": start, "end": None, "db": gain_db, "detail": f"{LIFT_RAMP_S} s ramp, held to the end"})
    return curve, events


def linear_gates(count, dropouts, tail_fade, duration):
    t = control_times(count)
    gain = np.ones(count)
    events = []
    for start, end in dropouts:
        gain *= 1.0 - window_ramp(t, start, end, DROPOUT_OUT_S, DROPOUT_IN_S)
        events.append({"kind": "dropout", "start": start, "end": end, "db": None, "detail": f"silent from {start} to {end}, {int(DROPOUT_OUT_S * 1000)} ms out, {int(DROPOUT_IN_S * 1000)} ms in"})
    if tail_fade > 0:
        gain *= np.clip((duration - t) / tail_fade, 0, 1)
        events.append({"kind": "tail fade", "start": round(duration - tail_fade, 3), "end": round(duration, 3), "db": None, "detail": "bed and SFX to silence"})
    return gain, events


def rms_db(x):
    return 10.0 * np.log10(np.mean(np.asarray(x, dtype=np.float64) ** 2) + 1e-12)


def word_margins(words, voice, others):
    rows = []
    for word in words:
        a, b = int(word["start"] * SAMPLE_RATE), int(word["end"] * SAMPLE_RATE)
        if b - a < MIN_WORD_S * SAMPLE_RATE or b > min(len(voice), len(others)):
            continue
        rows.append({"text": word["text"], "start": round(word["start"], 3), "end": round(word["end"], 3), "margin_db": round(rms_db(voice[a:b]) - rms_db(others[a:b]), 2)})
    return rows


def rides_db(words, voice, bed, min_margin, count):
    t = control_times(count)
    curve = np.zeros(count)
    events = []
    if min_margin <= 0:
        return curve, events
    for row in word_margins(words, voice, bed):
        shortfall = min_margin - row["margin_db"]
        if shortfall <= 0:
            continue
        depth = float(np.clip(shortfall, RIDE_MIN_DB, RIDE_MAX_DB))
        curve = np.maximum(curve, depth * window_ramp(t, row["start"], row["end"], RIDE_RAMP_S, RIDE_RAMP_S))
        events.append({"kind": "ride", "start": row["start"], "end": row["end"], "db": -round(depth, 2), "detail": f"'{row['text']}' margin {row['margin_db']} dB"})
    return -curve, events


def fit(data, count):
    if len(data) >= count:
        return data[:count]
    return np.pad(data, [(0, count - len(data))] + [(0, 0)] * (data.ndim - 1))


def voice_clip_gains(gains, count):
    t = control_times(count)
    curve = np.zeros(count)
    for start, end, gain in gains:
        curve += gain * window_ramp(t, start, end, VOICE_GAIN_RAMP_S, VOICE_GAIN_RAMP_S)
    return curve


def looped(region, length, xfade):
    out = region.copy()
    theta = (np.arange(xfade) + 0.5) / xfade * np.pi / 2
    fade_in, fade_out = np.sin(theta), np.cos(theta)
    while len(out) < length:
        out = np.concatenate([out[:-xfade], out[-xfade:] * fade_out + region[:xfade] * fade_in, region[xfade:]])
    return out[:length]


def room_tone_fill(source, holes, voice_gain_db, count):
    path, start, end = source
    region = decode_mono(path)[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)].astype(np.float64)
    xfade = int(ROOM_TONE_XFADE_S * SAMPLE_RATE)
    if len(region) < 4 * xfade:
        raise SystemExit(f"--room-tone-src region {start}-{end} is shorter than {4 * ROOM_TONE_XFADE_S:.2f} s")
    level = math.sqrt(np.mean(region ** 2))
    fill = np.zeros(count)
    events = []
    for hole_start, hole_end in holes:
        a = max(0, int((hole_start - ROOM_TONE_XFADE_S) * SAMPLE_RATE))
        b = min(count, int((hole_end + ROOM_TONE_XFADE_S) * SAMPLE_RATE))
        piece = looped(region, b - a, xfade)
        piece *= level / (math.sqrt(np.mean(piece ** 2)) + 1e-12)
        ramp = np.clip(np.minimum(np.arange(b - a), np.arange(b - a)[::-1]) / xfade, 0, 1)
        fill[a:b] += piece * np.sin(ramp * np.pi / 2) * 10 ** (voice_gain_db / 20)
        events.append({"kind": "room tone", "start": hole_start, "end": hole_end, "db": round(20 * math.log10(level + 1e-12) + voice_gain_db, 1), "detail": f"{Path(path).name} {start}-{end} s looped, {int(ROOM_TONE_XFADE_S * 1000)} ms crossfades (level dBFS RMS)"})
    return fill, events


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


def frame_rms_db(samples):
    size = int(RMS_FRAME_S * SAMPLE_RATE)
    mono = np.asarray(samples, dtype=np.float64)
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    usable = len(mono) // size * size
    return 10 * np.log10(np.mean(mono[:usable].reshape(-1, size) ** 2, axis=1) + 1e-12)


def duck_envelope(voice, unducked_bed, ducked_bed, target_i, spans):
    voice_db = frame_rms_db(voice)
    unducked = frame_rms_db(unducked_bed)
    ducked = frame_rms_db(ducked_bed)
    count = min(len(voice_db), len(unducked), len(ducked))
    voice_db, unducked, ducked = voice_db[:count], unducked[:count], ducked[:count]
    reduction = unducked - ducked
    audible = unducked > -60.0
    speech = (voice_db > target_i - 12.0) & audible
    quiet = voice_db < target_i - 30.0
    rises, gap_lengths = [], []
    index = 0
    while index < count:
        if quiet[index]:
            end = index
            while end < count and quiet[end]:
                end += 1
            length = (end - index) * RMS_FRAME_S
            if length >= GAP_MIN_S and index > 0 and end < count and audible[index:end].all():
                rises.append(float(reduction[max(0, index - 2):index].mean() - reduction[index:end].min()))
                gap_lengths.append(round(length, 2))
            index = end
        else:
            index += 1
    span_ranges, span_steps = [], []
    for start, end in spans:
        a, b = int(math.ceil(start / RMS_FRAME_S)), min(count, int(math.floor(end / RMS_FRAME_S)))
        inside = reduction[a:b][audible[a:b]]
        if len(inside) >= 2:
            span_ranges.append(float(inside.max() - inside.min()))
            span_steps.append(float(np.abs(np.diff(inside)).max()))
    return {
        "speech_reduction_db": round(float(np.median(reduction[speech])), 2) if speech.any() else None,
        "gaps_measured": len(rises),
        "gap_lengths_s": gap_lengths,
        "gap_rise_db_median": round(float(np.median(rises)), 2) if rises else None,
        "gap_rise_db_max": round(float(np.max(rises)), 2) if rises else None,
        "spans_measured": len(span_ranges),
        "span_gain_range_db_median": round(float(np.median(span_ranges)), 2) if span_ranges else None,
        "span_gain_range_db_max": round(float(np.max(span_ranges)), 2) if span_ranges else None,
        "span_step_db_max": round(float(np.max(span_steps)), 2) if span_steps else None,
    }


def placement_gain(p, target_i):
    if p.get("level_mode") == "lu":
        gain = target_i + p["level_lu_target"] - p["played_mmax_lufs"]
        return min(gain, p["peak_ceiling_dbfs"] - p["file_peak_dbfs"])
    return p["gain_db"]


def build_sfx(placements, count, target_i):
    bus = np.zeros(count)
    cues = []
    decoded = {}
    for p in placements:
        source = decoded.setdefault(p["file"], decode_mono(p["file"]))
        gain_db = placement_gain(p, target_i)
        signal = played_portion(source, p["trim_start"], p.get("max_dur"), p.get("fade_out") or 0.0) * 10 ** (gain_db / 20)
        start = int(round(p["start"] * SAMPLE_RATE))
        signal = signal[:max(0, count - start)]
        bus[start:start + len(signal)] += signal
        cues.append({"placement": p, "start": start, "signal": signal, "gain_db": round(gain_db, 2)})
    return bus, cues


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
    original_tp = measured["input_tp"]
    pre_limited = None
    source = mix_pre
    ceiling = args.target_tp - (args.target_i - measured["input_i"]) - PRE_LIMIT_MARGIN_DB
    for attempt in range(PRE_LIMIT_PASSES):
        if measured["input_tp"] + (args.target_i - measured["input_i"]) <= args.target_tp - PRE_LIMIT_TOLERANCE_DB:
            break
        if attempt:
            ceiling -= measured["input_tp"] + (args.target_i - measured["input_i"]) - (args.target_tp - PRE_LIMIT_MARGIN_DB)
        source = Path(work) / "mix_pre_peak_limited.wav"
        ffmpeg(["-i", str(mix_pre), "-af", f"alimiter=limit={10 ** (ceiling / 20):.6f}:level=false:attack=5:release=60:asc=1:latency=1", *FLOAT_WAV, str(source)])
        measured = measure_for_loudnorm(source)
        pre_limited = {"ceiling_dbtp": round(ceiling, 2), "input_tp_before": original_tp, "peak_reduction_db": round(original_tp - ceiling, 2), "passes": attempt + 1}
    lra_param = max(args.target_lra, math.ceil(measured["input_lra"] * 10 + 1) / 10)
    loudnorm = (
        f"loudnorm=I={args.target_i}:TP={args.target_tp}:LRA={lra_param}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:linear=true:print_format=json"
    )
    chain = f"{loudnorm},aresample={SAMPLE_RATE},alimiter=limit={args.safety_limit}:level=false:latency=1,{STEREO},apad,atrim=end={duration:.6f}"
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


def shifted(level, gain):
    return round(level + gain, 1) if level is not None else None


def segment_level(frames, start, end, use_short_term=True):
    values = [(s if use_short_term else m) for t, m, s in frames if start <= t <= end]
    values = [v for v in values if math.isfinite(v) and v > -70]
    return round(float(np.median(values)), 1) if values else None


def finite(value, digits=1):
    return round(value, digits) + 0.0 if value is not None and math.isfinite(value) else None


def limiter_reduction_db(cue, final, pre, master_gain_db):
    if not np.any(cue["signal"]):
        return None
    centres, loudness = momentary_curve(cue["signal"])
    centre = cue["start"] + int(centres[int(np.argmax(loudness))] * SAMPLE_RATE)
    half = int(0.2 * SAMPLE_RATE)
    a, b = max(0, centre - half), min(len(final), len(pre), centre + half)
    if b - a < half:
        return None
    return rms_db(final[a:b]) - rms_db(pre[a:b]) - master_gain_db


def cue_measurements(cues, master_gain_db, voice_final_i, fps, final, pre):
    rows = []
    for cue in cues:
        p = cue["placement"]
        measured = momentary_max(cue["signal"]) + master_gain_db
        relative = measured - voice_final_i
        target = p.get("level_lu_target")
        rows.append({
            "id": p["id"],
            "time": p["anchor_time"],
            "frame": round(p["anchor_time"] * fps),
            "visual": p.get("visual", ""),
            "event": p.get("event"),
            "class": p["level"],
            "file": p["library_file"],
            "level_mode": p.get("level_mode", "peak"),
            "target_lu": target,
            "measured_mmax_lufs": finite(measured, 2),
            "measured_lu": finite(relative, 2),
            "delta_lu": finite(relative - target, 2) if target is not None else None,
            "limiter_db": finite(limiter_reduction_db(cue, final, pre, master_gain_db), 2),
            "peak_dbfs": finite(20 * math.log10(np.abs(cue["signal"]).max() + 1e-12) + master_gain_db, 1),
            "gain_db": cue["gain_db"],
            "layer_of": p.get("layer_of"),
        })
    return rows


def beat_rows(beats_path, duration, stems, master_gain_db, words):
    data = load_json(beats_path)
    beats = data["beats"] if isinstance(data, dict) and "beats" in data else [{"id": k, "from": v} for k, v in data.items()]
    beats = sorted(beats, key=lambda b: float(b.get("from", 0.0)))
    tracks = {name: power_track(stem, dual_mono=False) for name, stem in stems.items() if name in ("voice", "others")}
    rows = []
    for index, beat in enumerate(beats):
        start = float(beat.get("from", beat.get("start", 0.0)))
        end = float(beat.get("to", beat.get("end", beats[index + 1]["from"] if index + 1 < len(beats) else duration)))
        a, b = int(start * SAMPLE_RATE), int(min(end, duration) * SAMPLE_RATE)
        levels = {name: finite(integrated_lufs(stem[a:b], dual_mono=False) + master_gain_db) for name, stem in stems.items() if name != "others"}
        margins = []
        for word in words:
            centre = (word["start"] + word["end"]) / 2
            if start <= centre < end:
                margins.append(track_lufs(tracks["voice"], centre) - track_lufs(tracks["others"], centre))
        rows.append({
            "beat": beat.get("id", str(index)),
            "component": beat.get("component"),
            "from": round(start, 3),
            "to": round(end, 3),
            "voice_lufs": levels.get("voice"),
            "bed_lufs": levels.get("bed"),
            "sfx_lufs": levels.get("sfx"),
            "words": len(margins),
            "speech_margin_median_lu": round(float(np.median(margins)), 1) if margins else None,
            "speech_margin_p10_lu": round(float(np.percentile(margins, 10)), 1) if margins else None,
        })
    return rows


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        lines.append("| " + " | ".join("" if value is None else str(value) for value in row) + " |")
    return lines


def write_cue_sheet(path, report, cue_rows, bed_events, beat_table, fps):
    lines = ["# Cue sheet", ""]
    mix = report["master"]
    lines += [
        f"Duration {report['duration_s']} s at {fps:g} fps. Final mix {mix['final_integrated_lufs']} LUFS, {mix['final_true_peak_dbtp']} dBTP, LRA {mix['final_lra_lu']} LU. "
        f"Voice in the final mix {report['voice']['final_integrated_lufs']} LUFS. Duck mode {report['ducking']['mode']}. "
        "SFX levels are LU relative to the voice integrated loudness in the final mix. Measured is the cue's 400 ms momentary max on the isolated SFX stem at the master gain; "
        "limiter is the gain change the two limiters made to the whole mix over that 400 ms window (mix.wav against mix_pre.wav at the master gain), so measured plus limiter is what plays.",
        "",
        "## SFX",
        "",
    ]
    lines += table(
        ["time s", "frame", "cue", "visual", "class", "target LU", "measured LU", "delta", "limiter dB", "peak dBFS", "file", "layer of / event"],
        [[f"{r['time']:.3f}", r["frame"], r["id"], r["visual"], r["class"], r["target_lu"], r["measured_lu"], r["delta_lu"], r["limiter_db"], r["peak_dbfs"], r["file"], r["layer_of"] or r["event"] or ""] for r in cue_rows],
    )
    lines += ["", "## Bed events", ""]
    lines += table(
        ["start s", "end s", "event", "dB", "detail"],
        [[e["start"], e["end"], e["kind"], e["db"], e["detail"]] for e in sorted(bed_events, key=lambda e: (e["start"] if e["start"] is not None else 0.0))],
    )
    if beat_table:
        lines += ["", "## Per beat (final-mix loudness, speech margin over 400 ms windows centred on words)", ""]
        lines += table(
            ["beat", "from s", "to s", "voice LUFS", "bed LUFS", "SFX LUFS", "words", "margin median LU", "margin p10 LU"],
            [[r["beat"], r["from"], r["to"], r["voice_lufs"], r["bed_lufs"], r["sfx_lufs"], r["words"], r["speech_margin_median_lu"], r["speech_margin_p10_lu"]] for r in beat_table],
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Mix voice + word-keyed (or sidechain) ducked music bed + placed SFX, then master with two-pass linear loudnorm and a safety limiter.")
    parser.add_argument("--voice", required=True, help="processed dialogue (mono or stereo), not loudness normalised")
    parser.add_argument("--voice-report", help="voice-clean process_voice.py report; exit 2 when --voice or the cut dialogue does not match its hashes or a gate failed")
    parser.add_argument("--voice-cut", help="the current voice_cut.wav to check against the report's input.sha256 (default: the input path recorded in the report)")
    parser.add_argument("--music", required=True, help="music bed file")
    parser.add_argument("--music-plan", help="find_downbeats.py output; its sections define where the bed starts and where it is edited")
    parser.add_argument("--music-offset", type=float, default=0.0, help="music start position when no plan is given")
    parser.add_argument("--music-xfade", type=float, default=0.03, help="crossfade at music edits, seconds")
    parser.add_argument("--sfx", help="sfx_cues.py placements json")
    parser.add_argument("--words", help="words json on the output timeline (words.out.json Caption[] or cues.json words); drives the word-keyed duck, rides and margins")
    parser.add_argument("--beats", help="beat map json with beats[{id, from, to}]; adds a per-beat loudness and margin table to the report")
    parser.add_argument("--cue-sheet", help="write a markdown cue sheet (every SFX with target and measured LU, every bed event) here")
    parser.add_argument("--fps", type=float, help="frame rate for the cue sheet (default: placements fps or 25)")
    parser.add_argument("--duration", type=float, help="output duration in seconds (default: voice duration); audio is padded or trimmed to it")
    parser.add_argument("--out-pre", required=True, help="mix_pre.wav (float, before mastering)")
    parser.add_argument("--out", required=True, help="mastered mix.wav (24-bit stereo 48 kHz)")
    parser.add_argument("--report", help="write all measurements to this json")
    parser.add_argument("--stems-dir", help="keep the voice, bed and SFX stems here")
    parser.add_argument("--target-i", type=float, default=-14.0)
    parser.add_argument("--target-tp", type=float, default=-1.5)
    parser.add_argument("--target-lra", type=float, default=7.0)
    parser.add_argument("--bed-under", type=float, default=10.0, help="unducked bed loudness below the voice, LU (default 10; plus the duck gives about 16)")
    parser.add_argument("--bed-eq", default="highpass=f=100:poles=2", help="filter chain applied to the bed before levelling ('' for none)")
    parser.add_argument("--bed-lift", help="start:dB raise of the bed after the talking ends, e.g. 46.9:4 for the end card")
    parser.add_argument("--duck-mode", choices=["words", "sidechain"], default="words", help="words: gain envelope keyed from --words (look-ahead, no pumping); sidechain: sidechaincompress keyed by the voice")
    parser.add_argument("--duck-db", type=float, default=6.0, help="bed reduction under speech, dB (both modes)")
    parser.add_argument("--duck-threshold-db", type=float, help="sidechain: fixed threshold in dBFS (skips calibration)")
    parser.add_argument("--duck-ratio", type=float, default=6.0, help="sidechain only")
    parser.add_argument("--duck-attack", type=float, default=15.0, help="sidechain only, ms")
    parser.add_argument("--duck-release", type=float, default=300.0, help="sidechain only, ms")
    parser.add_argument("--duck-hold", type=float, default=0.0, help="sidechain only: ms the key holds its peak after the voice drops")
    parser.add_argument("--auto-ride-min-margin", type=float, default=10.0, help="dip the bed under every word whose voice-to-bed RMS margin is below this, by the shortfall clamped to 2-6 dB with 60 ms ramps (0 turns rides off; needs --words)")
    parser.add_argument("--bed-dip", action="append", default=[], help="start:end:dB extra bed cut (50 ms ramps outside the window), repeatable")
    parser.add_argument("--dropout", action="append", default=[], help="start:end hard stop of the bed (15 ms fade out before start, 30 ms fade in after end), repeatable")
    parser.add_argument("--voice-gain", action="append", default=[], help="start:end:dB clip gain on the voice (20 ms ramps outside the window), repeatable")
    parser.add_argument("--room-tone-src", help="FILE:start:end clean room tone region from the processed --voice file, e.g. voice.wav:12.40:12.90")
    parser.add_argument("--room-tone-at", action="append", default=[], help="start:end splice hole to fill with the room tone region (looped, 20 ms crossfades, at the region's own level), repeatable")
    parser.add_argument("--tail-fade", type=float, default=0.0, help="fade the bed and SFX to silence over the last N seconds (the voice is untouched)")
    parser.add_argument("--safety-limit", type=float, default=0.84, help="alimiter ceiling after loudnorm, linear (0.84 is -1.5 dBFS)")
    args = parser.parse_args()

    if args.room_tone_at and not args.room_tone_src:
        raise SystemExit("--room-tone-at needs --room-tone-src")
    guard = stale_voice_guard(args)
    duration = args.duration or probe_duration(args.voice)
    count = int(round(duration * SAMPLE_RATE))
    control_count = int(math.ceil(duration * CONTROL_RATE)) + 1
    sfx_doc = load_json(args.sfx) if args.sfx else {}
    placements = sfx_doc.get("placements", [])
    fps = args.fps or sfx_doc.get("fps", 25)
    loaded = load_words(args.words) if args.words else []
    words = words_in_range(loaded, duration)
    if len(words) < len(loaded):
        print(f"words: {len(loaded) - len(words)} of {len(loaded)} fall outside 0-{duration:.3f} s or are shorter than {int(MIN_WORD_S * 1000)} ms after clipping; ignored")
    if args.duck_mode == "words" and not words:
        raise SystemExit("--duck-mode words needs --words (words.out.json); use --duck-mode sidechain without word timings")
    if args.auto_ride_min_margin > 0 and not words:
        print("rides off: no --words")
    temp = tempfile.TemporaryDirectory()
    work = Path(args.stems_dir) if args.stems_dir else Path(temp.name)
    work.mkdir(parents=True, exist_ok=True)

    voice_hash = sha256_file(args.voice)
    voice_measure = ebur128(args.voice, f"{DUAL_MONO},{STEREO}")
    voice_gain = args.target_i - voice_measure["integrated"]
    voice_ref_path = gain_file(args.voice, voice_gain, DUAL_MONO, work, "voice_ref.wav")
    voice = fit(read_stereo(voice_ref_path), count)
    clip_gains = [parse_voice_gain(text) for text in args.voice_gain]
    voice_events = [{"kind": "voice gain", "start": s, "end": e, "db": g, "detail": f"{int(VOICE_GAIN_RAMP_S * 1000)} ms ramps outside"} for s, e, g in clip_gains]
    if clip_gains:
        voice *= (10 ** (to_samples(voice_clip_gains(clip_gains, control_count), count) / 20))[:, None]
    if args.room_tone_src:
        fill, room_events = room_tone_fill(parse_room_tone_src(args.room_tone_src), [parse_window(text, "--room-tone-at") for text in args.room_tone_at], voice_gain, count)
        voice += fill[:, None]
        voice_events += room_events
    if clip_gains or args.room_tone_src:
        write_float_wav(voice_ref_path, voice)
    voice_frames = ebur128(voice_ref_path)["frames"]

    bed_raw, sections = build_bed(args, duration, work)
    bed_gain = (args.target_i - args.bed_under) - ebur128(bed_raw)["integrated"]
    bed_level_path = gain_file(bed_raw, bed_gain, "anull", work, "bed_unducked.wav")
    bed_level = fit(read_stereo(bed_level_path), count)
    spans = word_spans(words, WORD_SPAN_MERGE_S)

    calibration = []
    threshold_db = None
    if args.duck_mode == "sidechain":
        bed_level_frames = ebur128(bed_level_path)["frames"]
        slope = 1.0 - 1.0 / args.duck_ratio
        threshold_db = args.duck_threshold_db if args.duck_threshold_db is not None else args.target_i - args.duck_db / slope
        key = held_key(args.voice, args.duck_hold / 1000.0, work) if args.duck_hold > 0 else args.voice
        for _ in range(1 if args.duck_threshold_db is not None else 4):
            ducked_path = sidechain_duck(args, key, voice_gain, bed_raw, bed_gain, threshold_db, duration, work)
            depth = duck_depth(bed_level_frames, ebur128(ducked_path)["frames"], voice_frames, args.target_i)
            calibration.append({"threshold_db": round(threshold_db, 2), **depth})
            measured = depth["speech_momentary_db"]
            if measured is None or abs(measured - args.duck_db) <= 0.75:
                break
            threshold_db -= (args.duck_db - measured) / slope
        bed_ducked = fit(read_stereo(ducked_path), count)
        duck_curve = None
    else:
        duck_curve = word_duck_db(spans, control_count, args.duck_db)
        bed_ducked = bed_level * (10 ** (-to_samples(duck_curve, count) / 20))[:, None]
        write_float_wav(work / "bed_ducked.wav", bed_ducked)
    envelope = duck_envelope(voice, bed_level, bed_ducked, args.target_i, spans)

    dips = [parse_dip(text) for text in args.bed_dip]
    dropouts = [parse_window(text, "--dropout") for text in args.dropout]
    lift = parse_lift(args.bed_lift)
    auto_curve, bed_events = automation_db(placements, lift, dips, control_count)
    gate_curve, gate_events = linear_gates(control_count, dropouts, args.tail_fade, duration)
    pre_ride = bed_ducked * (10 ** (to_samples(auto_curve, count) / 20) * to_samples(gate_curve, count))[:, None]
    ride_curve, ride_events = rides_db(words, voice, pre_ride, args.auto_ride_min_margin, control_count) if words else (np.zeros(control_count), [])
    bed_final = pre_ride * (10 ** (to_samples(ride_curve, count) / 20))[:, None]
    write_float_wav(work / "bed_final.wav", bed_final)
    if duck_curve is not None:
        bed_events += [{"kind": "duck", "start": round(s, 3), "end": round(e, 3), "db": -args.duck_db, "detail": f"words, {int(WORD_DUCK_PRE_S * 1000)} ms pre, {int(WORD_DUCK_POST_S * 1000)} ms post"} for s, e in spans]
    bed_events += gate_events + ride_events + voice_events

    sfx_bus, cue_signals = build_sfx(placements, count, args.target_i)
    tail = to_samples(linear_gates(control_count, [], args.tail_fade, duration)[0], count)
    sfx_bus *= tail
    for cue in cue_signals:
        cue["signal"] = cue["signal"] * tail[cue["start"]:cue["start"] + len(cue["signal"])]
    sfx_stereo = np.repeat(sfx_bus[:, None], 2, axis=1)
    write_float_wav(work / "sfx_bus.wav", sfx_stereo)
    Path(args.out_pre).parent.mkdir(parents=True, exist_ok=True)
    write_float_wav(args.out_pre, voice + bed_final + sfx_stereo)

    mastering = master(args, args.out_pre, duration, work)
    final = ebur128(args.out)
    gain = mastering["loudnorm_gain_db"]
    voice_final_i = round(integrated_lufs(voice, dual_mono=False) + gain, 2)
    bed_final_frames = ebur128(work / "bed_final.wav")["frames"]
    speech_times = [t for t, m, s in voice_frames if m > args.target_i - SPEECH_MOMENTARY_BELOW_I]
    bed_by_time = frames_by_time(bed_final_frames)
    speech_m = [bed_by_time[round(t, 1)][0] for t in speech_times if round(t, 1) in bed_by_time and bed_by_time[round(t, 1)][0] > SILENCE_LUFS]
    lift_momentary = segment_level(bed_final_frames, lift[0] + 0.5, duration, use_short_term=False) if lift else None
    last_short_term = segment_level(bed_final_frames, duration - 0.15, duration)
    cue_rows = cue_measurements(cue_signals, gain, voice_final_i, fps, read_stereo(args.out), read_stereo(args.out_pre))
    margins = word_margins(words, voice, bed_final + sfx_stereo) if words else []
    margin_values = [row["margin_db"] for row in margins]
    beat_table = beat_rows(args.beats, duration, {"voice": voice, "bed": bed_final, "sfx": sfx_stereo, "others": bed_final + sfx_stereo}, gain, words) if args.beats else None
    lu_rows = [r for r in cue_rows if r["level_mode"] == "lu" and r["delta_lu"] is not None]

    report = {
        "duration_s": round(duration, 3),
        "voice_guard": guard,
        "voice": {"file": str(Path(args.voice).resolve()), "sha256": voice_hash, "input_integrated_lufs": voice_measure["integrated"], "gain_db": round(voice_gain, 2), "lra_lu": voice_measure["lra"], "final_integrated_lufs": voice_final_i, "clip_gains": [{"start": s, "end": e, "db": g} for s, e, g in clip_gains], "room_tone": [e for e in voice_events if e["kind"] == "room tone"]},
        "music": {"file": str(Path(args.music).resolve()), "sections": sections, "gain_db": round(bed_gain, 2), "eq": args.bed_eq},
        "ducking": {
            "mode": args.duck_mode,
            "depth_db": args.duck_db,
            **({"spans": len(spans), "merge_gap_s": WORD_SPAN_MERGE_S, "pre_ms": WORD_DUCK_PRE_S * 1000, "post_ms": WORD_DUCK_POST_S * 1000, "attack_ms": WORD_DUCK_ATTACK_S * 1000, "release_ms": WORD_DUCK_RELEASE_S * 1000, "control_rate_hz": CONTROL_RATE} if args.duck_mode == "words" else
               {"threshold_db": round(threshold_db, 2), "ratio": args.duck_ratio, "attack_ms": args.duck_attack, "release_ms": args.duck_release, "hold_ms": args.duck_hold, "calibration": calibration}),
            "envelope": envelope,
        },
        "bed_events": bed_events,
        "dropouts": [{"start": s, "end": e} for s, e in dropouts],
        "rides": {"min_margin_db": args.auto_ride_min_margin, "count": len(ride_events), "rides": ride_events},
        "bed_dips": [{"start": a, "end": b, "db": d} for a, b, d in dips],
        "tail_fade_s": args.tail_fade,
        "bed_in_final_mix": {
            "unducked_integrated_lufs": round(args.target_i - args.bed_under + gain, 1),
            "under_speech_momentary_lufs": round(float(np.median(speech_m)) + gain, 1) if speech_m else None,
            "lift_window_momentary_lufs": shifted(lift_momentary, gain),
            "last_frame_short_term_lufs": shifted(last_short_term, gain),
        },
        "word_margins": {
            "words": len(margin_values),
            "median_db": round(float(np.median(margin_values)), 2) if margin_values else None,
            "p10_db": round(float(np.percentile(margin_values, 10)), 2) if margin_values else None,
            "min_db": round(float(np.min(margin_values)), 2) if margin_values else None,
            "under_8_db": [row for row in margins if row["margin_db"] < MASKING_MIN_DB],
        },
        "sfx": {
            "count": len(placements),
            "level_mode": sfx_doc.get("level_mode", "peak"),
            "placements_voice_sha256": (sfx_doc.get("voice") or {}).get("sha256"),
            "peak_shift_db": gain,
            "impact_dips": sum(1 for p in placements if (p.get("duck_bed_db") or 0) > 0),
            "lu_delta_max": round(max(abs(r["delta_lu"]) for r in lu_rows), 2) if lu_rows else None,
            "limited_over_1_db": [r["id"] for r in cue_rows if r["limiter_db"] is not None and r["limiter_db"] < -LIMITER_WARN_DB],
            "cues": cue_rows,
        },
        "beats": beat_table,
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
        warnings.append(f"pre-loudnorm limiter took {mastering['pre_limiter']['peak_reduction_db']} dB off the peaks; process the voice with a voice-clean preset that ends in peak_limit (peak_plr_db 14) and remix")
    if mastering["lra_parameter"] > args.target_lra:
        warnings.append(f"mix LRA {mastering['pass1_ebur128']['input_lra']} LU is above {args.target_lra}; loudnorm ran linear with LRA={mastering['lra_parameter']}, compress the voice more")
    if report["sfx"]["placements_voice_sha256"] and report["sfx"]["placements_voice_sha256"] != voice_hash:
        warnings.append("sfx placements were levelled against a different voice.wav; LU cues are re-levelled here from their stored momentary max, rerun sfx_cues.py place --voice to refresh the placement report")
    if report["sfx"]["limited_over_1_db"]:
        warnings.append(f"the limiters take more than {LIMITER_WARN_DB:g} dB off the mix under SFX cues {', '.join(report['sfx']['limited_over_1_db'])}: their measured LU overstates what plays, lower those cues or the voice peaks")
    if args.room_tone_src and Path(args.room_tone_src.rsplit(":", 2)[0]).resolve() != Path(args.voice).resolve():
        warnings.append("--room-tone-src is not the --voice file: the fill gets the processed voice's mix gain but keeps its source's floor and timbre, take the region from voice.wav")
    if guard is None:
        warnings.append("no --voice-report: the voice was not checked against the voice-clean hashes")
    report["warnings"] = warnings
    if args.report:
        write_json(args.report, report)
    if args.cue_sheet:
        write_cue_sheet(args.cue_sheet, report, cue_rows, bed_events, beat_table, fps)
    print(f"voice in {voice_measure['integrated']} LUFS, gain {voice_gain:+.2f} dB; bed gain {bed_gain:+.2f} dB; {len(sections)} music section(s); {len(placements)} SFX")
    for row in calibration:
        print(f"duck calibration: threshold {row['threshold_db']} dBFS -> {row['speech_momentary_db']} dB under speech (ebur128 momentary), {row['speech_short_term_db']} dB (ebur128 short-term)")
    print(f"duck ({args.duck_mode}): {envelope['speech_reduction_db']} dB under speech (20 ms RMS), gain range inside {envelope['spans_measured']} word spans median {envelope['span_gain_range_db_median']} / max {envelope['span_gain_range_db_max']} dB, bed rises {envelope['gap_rise_db_median']} dB median / {envelope['gap_rise_db_max']} dB max in {envelope['gaps_measured']} gaps of {GAP_MIN_S}s or more")
    print(f"rides: {len(ride_events)} under {args.auto_ride_min_margin} dB; dropouts {len(dropouts)}; word margins median {report['word_margins']['median_db']} dB, p10 {report['word_margins']['p10_db']}, min {report['word_margins']['min_db']}")
    bed = report["bed_in_final_mix"]
    print(f"bed in final mix: unducked {bed['unducked_integrated_lufs']} LUFS, under speech {bed['under_speech_momentary_lufs']} LUFS M, lift window {bed['lift_window_momentary_lufs']} LUFS M, last frame {bed['last_frame_short_term_lufs']} LUFS S")
    if lu_rows:
        print(f"SFX LU levels: {len(lu_rows)} cues, max |measured - target| {report['sfx']['lu_delta_max']} LU")
    first = mastering["pass1_ebur128"]
    print(f"pass 1 (ebur128): I {first['input_i']} TP {first['input_tp']} LRA {first['input_lra']}; pre-limiter {mastering['pre_limiter']}; pass 2 loudnorm {mastering['normalization_type']} gain {gain:+.2f} dB")
    print(f"final: I {final['integrated']} LUFS, TP {final['true_peak']} dBTP, LRA {final['lra']} LU, duration {report['master']['final_duration_s']} s")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print("gates: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in gates.items()))
    temp.cleanup()
    if not all(gates.values()):
        raise SystemExit(2)


def sidechain_duck(args, key, voice_gain_db, bed_raw, bed_gain_db, threshold_db, duration, work):
    chain_bed = f"[1:a]{STEREO},volume={bed_gain_db:.3f}dB[bed]"
    chain_key = f"[0:a]{DUAL_MONO},{STEREO},volume={voice_gain_db:.3f}dB,apad,atrim=end={duration:.6f}[key]"
    duck = (
        f"[bed][key]sidechaincompress=threshold={10 ** (threshold_db / 20):.6f}:ratio={args.duck_ratio}:"
        f"attack={args.duck_attack}:release={args.duck_release}:makeup=1:knee=2.82843"
    )
    out = Path(work) / "bed_ducked.wav"
    run_graph([key, bed_raw], ";".join([chain_bed, chain_key, f"{duck}[out]"]), "out", out, work)
    return out


if __name__ == "__main__":
    main()
