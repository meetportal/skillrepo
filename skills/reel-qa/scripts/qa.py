import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import butter, sosfiltfilt

SKILLS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS_DIR / "reel-export" / "scripts"))
from delivery_spec import check as spec_check
from delivery_spec import frame_rate, loudness, probe

GATES = ["spec", "loudness", "drift", "rhythm", "splices", "asr", "captions", "levels", "sheets", "first_frame"]
SAFE_BOX = (70, 220, 950, 1500)
SR = 48000


def load_json(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else None


def gate(status, summary, **data):
    return {"status": status, "summary": summary, **data}


class Reel:
    def __init__(self, path, work):
        self.path = Path(path)
        self.work = Path(work)
        info = probe(self.path)
        videos = [s for s in info["streams"] if s.get("codec_type") == "video"]
        audios = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        if not videos:
            raise SystemExit(f"{self.path}: no video stream")
        self.video = videos[0]
        self.audio = audios[0] if audios else None
        self.fps = frame_rate(self.video.get("r_frame_rate", "25/1")) or 25.0
        self.frames = int(self.video.get("nb_read_packets") or 0)
        self.duration = self.frames / self.fps if self.frames else float(self.video.get("duration") or 0)
        self.width = int(self.video["width"])
        self.height = int(self.video["height"])
        self.edl = load_json(self.work / "edl.json")
        self.cues = load_json(self.work / "cues.json")
        self.beatmap = load_json(self.work / "beatmap.json")
        self.camera = load_json(self.work / "camera_plan.json")
        self.props = load_json(self.work / "props.json")
        self._audio = None

    def audio_samples(self):
        if self._audio is None:
            raw = subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-i", str(self.path), "-map", "0:a:0", "-ar", str(SR), "-f", "f32le", "-"],
                check=True, capture_output=True,
            ).stdout
            channels = int(self.audio.get("channels") or 1)
            data = np.frombuffer(raw, dtype=np.float32)
            self._audio = data.reshape(-1, channels).mean(axis=1) if channels > 1 else data
        return self._audio

    def gray_frames(self, width, height):
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-nostdin", "-i", str(self.path), "-map", "0:v:0", "-vf", f"scale={width}:{height}:flags=area",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            check=True, capture_output=True,
        ).stdout
        return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width)

    def frames_at(self, path, numbers, width=None, height=None, pix_fmt="bgr24"):
        numbers = sorted(set(int(n) for n in numbers))
        if not numbers:
            return {}
        width = width or self.width
        height = height or self.height
        start = max(0.0, (numbers[0] - 1) / self.fps)
        expr = "+".join(f"eq(n\\,{n})" for n in numbers)
        scale = [] if (width, height) == (self.width, self.height) else [f"scale={width}:{height}:flags=area"]
        vf = ",".join([f"select='{expr}'"] + scale) if start == 0 else None
        if vf is None:
            window = "+".join(f"between(t\\,{(n - 0.5) / self.fps:.5f}\\,{(n + 0.5) / self.fps:.5f})" for n in numbers)
            vf = ",".join([f"select='{window}'"] + scale)
            cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.4f}", "-copyts", "-i", str(path)]
        else:
            cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
        cmd += ["-map", "0:v:0", "-vf", vf, "-fps_mode", "passthrough", "-frames:v", str(len(numbers)), "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"]
        raw = subprocess.run(cmd, check=True, capture_output=True).stdout
        if pix_fmt == "bgr24":
            size = width * height * 3
            shape = (height, width, 3)
        else:
            size = width * height * 3 // 2
            shape = None
        chunks = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
        out = {}
        for number, chunk in zip(numbers, chunks):
            array = np.frombuffer(chunk, dtype=np.uint8)
            out[number] = array.reshape(shape) if shape else array[: width * height].reshape(height, width)
        return out


def expected_duration(reel, args):
    if args.expected_duration is not None:
        return args.expected_duration, "--expected-duration"
    if reel.edl and args.extra_sec is not None:
        return reel.edl["duration"] + args.extra_sec, "edl.duration + --extra-sec"
    if reel.props and reel.props.get("durationSec"):
        return round(round(reel.props["durationSec"] * reel.fps) / reel.fps, 4), "props.json durationSec"
    if reel.edl:
        return reel.edl["duration"], "edl.duration (no end card given)"
    return None, "none"


def gate_spec(reel, args, ctx):
    expected, source = expected_duration(reel, args)
    result = spec_check(reel.path, expected_duration=expected)
    failed = [c for c in result["checks"] if not c["pass"]]
    summary = "all ffprobe checks pass" if not failed else "; ".join(f"{c['check']} {c['actual']} (want {c['expected']})" for c in failed)
    return gate("pass" if result["pass"] else "fail", summary, checks=result["checks"], expected_duration=expected, expected_source=source)


def gate_loudness(reel, args, ctx):
    if not reel.audio:
        return gate("fail", "no audio stream")
    values = loudness(reel.path)
    if values["I"] is None:
        return gate("fail", "ebur128 returned no reading (silent audio?)", **values)
    problems = []
    if abs(values["I"] - args.target_lufs) > 1.0:
        problems.append(f"I {values['I']} LUFS outside {args.target_lufs} +/- 1")
    if values["TP"] is None or values["TP"] > -1.5:
        problems.append(f"true peak {values['TP']} dBTP above -1.5")
    if values["LRA"] is None or values["LRA"] > 7.0:
        problems.append(f"LRA {values['LRA']} LU above 7")
    summary = f"I {values['I']} LUFS, TP {values['TP']} dBTP, LRA {values['LRA']} LU"
    return gate("fail" if problems else "pass", summary + ("; " + "; ".join(problems) if problems else ""), **values)


def envelope(samples, hop):
    usable = len(samples) // hop * hop
    frames = samples[:usable].reshape(-1, hop)
    return np.sqrt((frames ** 2).mean(axis=1) + 1e-12)


def read_wav_mono(path):
    import soundfile

    data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    data = data.mean(axis=1)
    if rate != SR:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
            check=True, capture_output=True,
        ).stdout
        data = np.frombuffer(raw, dtype=np.float32)
    return data


def window_lags(reference, candidate, span, hop=120, window_s=6.0, max_lag_s=0.4):
    ref_env = envelope(reference, hop)
    cand_env = envelope(candidate, hop)
    rate = SR / hop
    max_lag = int(max_lag_s * rate)
    win = int(window_s * rate)
    results = []
    start = 0
    end = min(len(ref_env), len(cand_env), int(span * rate))
    while start + win <= end:
        a = np.log10(ref_env[start:start + win] + 1e-6)
        a = (a - a.mean()) / (a.std() + 1e-9)
        best = (0, -2.0)
        for lag in range(-max_lag, max_lag + 1):
            lo, hi = start + lag, start + lag + win
            if lo < 0 or hi > len(cand_env):
                continue
            b = np.log10(cand_env[lo:hi] + 1e-6)
            b = (b - b.mean()) / (b.std() + 1e-9)
            corr = float(np.dot(a, b) / win)
            if corr > best[1]:
                best = (lag, corr)
        results.append({"from": round(start / rate, 2), "to": round((start + win) / rate, 2),
                        "lag_ms": round(best[0] / rate * 1000, 1), "corr": round(best[1], 3)})
        start += win
    return results


def voice_reference(reel, args):
    if args.voice_ref:
        return Path(args.voice_ref)
    return next((p for p in (reel.work / "voice.wav", reel.work / "voice_cut.wav") if p.is_file()), None)


def gate_drift(reel, args, ctx):
    if not reel.audio:
        return gate("fail", "no audio stream")
    audio_s = float(reel.audio.get("duration") or 0.0)
    gap = abs(reel.duration - audio_s)
    problems = []
    if gap > 0.040:
        problems.append(f"video {reel.duration:.3f}s vs audio {audio_s:.3f}s differ by {gap * 1000:.0f} ms")
    data = {"video_s": round(reel.duration, 4), "audio_s": round(audio_s, 4), "difference_ms": round(gap * 1000, 1)}
    ref_path = voice_reference(reel, args)
    status = "fail" if problems else "pass"
    if ref_path and ref_path.is_file():
        reference = read_wav_mono(ref_path)
        reference_s = len(reference) / SR
        span = min(reference_s, reel.edl["duration"] if reel.edl else reel.duration)
        lags = window_lags(reference, reel.audio_samples(), span)
        trusted = [w for w in lags if w["corr"] >= 0.5]
        worst = max((abs(w["lag_ms"]) for w in trusted), default=0.0)
        data.update(voice_reference=str(ref_path), reference_s=round(len(reference) / SR, 4), sync_windows=lags, worst_lag_ms=worst)
        if reel.edl and abs(reference_s - reel.edl["duration"]) > 0.040:
            problems.append(f"{ref_path.name} is {reference_s:.3f}s but the EDL is {reel.edl['duration']:.3f}s (stale voice render?)")
        if worst > 40:
            problems.append(f"delivered audio is offset from {ref_path.name} by up to {worst:.0f} ms (6 s windows, corr >= 0.5)")
        if not trusted:
            data["note"] = "no window correlated >= 0.5 with the reference voice; sync not measured"
        status = "fail" if problems else "pass"
    else:
        data["note"] = "no voice.wav or voice_cut.wav in the work folder; only durations checked"
    summary = "; ".join(problems) if problems else f"v/a differ by {gap * 1000:.0f} ms" + (
        f", worst voice lag {data['worst_lag_ms']:.0f} ms" if "worst_lag_ms" in data else "")
    return gate(status, summary, **data)


def scene_changes(reel, threshold, ratio):
    frames = reel.gray_frames(108, 192).astype(np.float32)
    diff = np.zeros(len(frames))
    diff[1:] = np.abs(frames[1:] - frames[:-1]).mean(axis=(1, 2))
    events = []
    for i in range(1, len(diff)):
        lo, hi = max(1, i - 12), min(len(diff), i + 13)
        local = np.median(diff[lo:hi])
        neighbourhood = diff[max(1, i - 2):min(len(diff), i + 3)]
        if diff[i] >= threshold and diff[i] >= ratio * max(local, 0.5) and diff[i] == neighbourhood.max():
            if not events or i - events[-1] > 2:
                events.append(i)
    return [round(i / reel.fps, 3) for i in events], diff


def camera_changes(camera):
    times, previous = [], None
    for key in (camera or {}).get("keys", []):
        state = (key.get("scale"), key.get("tx"), key.get("ty"))
        if key.get("ease") not in ("creep", "hold") and previous is not None and state != previous:
            times.append(float(key["t"]))
        previous = state
    return times


def takeover_covers(reel, t):
    for beat in (reel.beatmap or {}).get("beats", []):
        if beat.get("mode") == "takeover" and float(beat["from"]) <= t <= float(beat["to"]):
            return beat.get("id", "takeover")
    return None


def gate_rhythm(reel, args, ctx):
    measured, diff = scene_changes(reel, args.scene_threshold, args.scene_ratio)
    measured_frames = {round(t * reel.fps) for t in measured}
    planned_cuts = [float(t) for t in (reel.cues or {}).get("cuts", [])]
    missing, covered = [], []
    for t in planned_cuts:
        n = round(t * reel.fps)
        if not any(abs(n - m) <= 1 for m in measured_frames):
            cover = takeover_covers(reel, t)
            (covered if cover else missing).append(t if not cover else f"{t} ({cover})")
    sources = {"scene": measured}
    if reel.beatmap:
        beats = reel.beatmap.get("beats", [])
        sources["beats"] = sorted({float(b["from"]) for b in beats} | {float(b["to"]) for b in beats})
    if reel.camera:
        sources["camera"] = camera_changes(reel.camera)
    events = sorted({round(t, 2) for values in sources.values() for t in values if 0 <= t <= reel.duration})
    marks = [0.0] + events + [round(reel.duration, 3)]
    gaps = sorted(({"from": a, "to": b, "gap": round(b - a, 2)} for a, b in zip(marks, marks[1:])), key=lambda g: -g["gap"])
    measured_marks = [0.0] + measured + [round(reel.duration, 3)]
    measured_gap = max((b - a for a, b in zip(measured_marks, measured_marks[1:])), default=reel.duration)
    worst = gaps[0] if gaps else {"from": 0, "to": reel.duration, "gap": reel.duration}
    problems = []
    if worst["gap"] > args.max_gap:
        problems.append(f"no visual change for {worst['gap']:.2f}s ({worst['from']:.2f}-{worst['to']:.2f}), limit {args.max_gap}s")
    if missing:
        problems.append(f"cuts from cues.json not visible in the render at {missing} (stale render or stale cues?)")
    summary = "; ".join(problems) if problems else f"largest gap {worst['gap']:.2f}s ({worst['from']:.2f}-{worst['to']:.2f}), limit {args.max_gap}s"
    summary += f"; {len(planned_cuts) - len(missing) - len(covered)}/{len(planned_cuts)} planned cuts seen; scene detection alone {measured_gap:.2f}s"
    if not problems and measured_gap > args.max_gap:
        summary += " (beat and camera events from the plan close the gap: confirm on the sheets that they rendered)"
    status = "fail" if problems else ("warn" if measured_gap > args.max_gap else "pass")
    return gate(status, summary, largest_gaps=gaps[:5], scene_only_largest_gap=round(measured_gap, 2),
                counts={k: len(v) for k, v in sources.items()}, scene_changes=measured,
                cuts_missing=missing, cuts_under_takeover=covered)


def splice_times(edl):
    fps = edl["fps"]
    t_frames, previous, times = 0, None, []
    for item in edl["ranges"]:
        source = item.get("a_clip") or item["clip"]
        if previous is not None:
            prev_source, prev_out = previous
            if source != prev_source or abs(prev_out - item["a_in"]) > 0.5 / fps:
                times.append(round(t_frames / fps, 4))
        t_frames += round((item["a_out"] - item["a_in"]) * fps)
        previous = (source, item["a_out"])
    return times


def splice_metrics(samples, t, sos):
    centre = int(t * SR)
    lo, hi = centre - int(0.3 * SR), centre + int(0.3 * SR)
    if lo < 0 or hi > len(samples):
        return None
    segment = samples[lo:hi].astype(np.float64)
    mid = len(segment) // 2
    high = sosfiltfilt(sos, segment)
    hop = int(0.002 * SR)
    hf = 20 * np.log10(envelope(high, hop) + 1e-9)
    mid_hf = len(hf) // 2
    near = hf[mid_hf - 5:mid_hf + 6]
    context_hf = np.concatenate([hf[mid_hf - 25:mid_hf - 7], hf[mid_hf + 8:mid_hf + 26]])
    burst = float(near.max() - np.median(context_hf))
    step = np.abs(np.diff(segment))
    ms = SR // 1000
    step_near = step[mid - 10 * ms: mid + 10 * ms].max()
    step_context = np.percentile(np.concatenate([step[mid - 50 * ms: mid - 15 * ms], step[mid + 15 * ms: mid + 50 * ms]]), 99)
    full = 20 * np.log10(envelope(segment, 10 * ms) + 1e-9)
    mid_full = len(full) // 2
    hole = float(np.percentile(np.concatenate([full[: mid_full - 5], full[mid_full + 6:]]), 20) - full[mid_full - 5:mid_full + 6].min())
    return {"t": t, "hf_burst_db": round(burst, 1), "hf_peak_dbfs": round(float(near.max()), 1),
            "step_ratio": round(float(step_near / (step_context + 1e-12)), 2), "hole_db": round(hole, 1)}


def gate_splices(reel, args, ctx):
    if not reel.edl:
        return gate("skip", "no edl.json in the work folder")
    if not reel.audio:
        return gate("fail", "no audio stream")
    times = splice_times(reel.edl)
    if not times:
        return gate("pass", "EDL has no audio splices", splices=[])
    sos = butter(4, 5000, btype="highpass", fs=SR, output="sos")
    mix = reel.audio_samples()
    voice_path = voice_reference(reel, args)
    voice = read_wav_mono(voice_path) if voice_path and voice_path.is_file() else None
    click_source = str(voice_path) if voice is not None else "delivered mix (no voice stem found)"
    rows, clicks, holes = [], [], []
    for t in times:
        mix_metrics = splice_metrics(mix, t, sos)
        if mix_metrics is None:
            continue
        click_metrics = splice_metrics(voice, t, sos) if voice is not None else mix_metrics
        if click_metrics is None:
            continue
        metrics = {
            "t": t,
            "hf_burst_db": click_metrics["hf_burst_db"], "hf_peak_dbfs": click_metrics["hf_peak_dbfs"],
            "step_ratio": click_metrics["step_ratio"], "hole_db": mix_metrics["hole_db"],
            "voice_hole_db": click_metrics["hole_db"] if voice is not None else None,
            "mix_hf_burst_db": mix_metrics["hf_burst_db"], "mix_step_ratio": mix_metrics["step_ratio"],
        }
        metrics["click"] = metrics["hf_burst_db"] > args.click_db and metrics["step_ratio"] > 2.0 and metrics["hf_peak_dbfs"] > -60
        metrics["hole"] = metrics["hole_db"] > args.hole_db
        rows.append(metrics)
        if metrics["click"]:
            clicks.append(t)
        if metrics["hole"]:
            holes.append(t)
    status = "fail" if clicks else ("warn" if holes else "pass")
    summary = f"{len(rows)} splices, clicks on the voice stem at {clicks or 'none'}"
    if voice is None:
        summary = f"{len(rows)} splices, clicks on the delivered mix (no voice stem) at {clicks or 'none'}"
    if holes:
        summary += f"; room-tone holes over {args.hole_db} dB in the delivered mix at {holes} (listen; lay room tone under them if audible)"
    return gate(status, summary, splices=rows, click_source=click_source, hole_source=str(reel.path))


def gate_asr(reel, args, ctx):
    script = SKILLS_DIR / "reel-captions" / "scripts" / "asr_diff.py"
    words = reel.work / "words.out.json"
    if not script.is_file():
        return gate("error", f"{script.relative_to(SKILLS_DIR)} not found")
    if not words.is_file():
        return gate("skip", "no words.out.json in the work folder")
    out = Path(args.out_dir) / "asr_diff_delivered.json"
    cmd = [sys.executable, str(script), "--intended", str(words), "--out", str(out), "--model", args.asr_model]
    cmd += ["--heard", args.asr_heard] if args.asr_heard else ["--media", str(reel.path)]
    if args.asr_prompt:
        cmd += ["--prompt", args.asr_prompt]
    if args.dictionary:
        cmd += ["--dictionary", args.dictionary]
    if args.asr_allow:
        cmd += ["--allow", args.asr_allow]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1) or not out.is_file():
        return gate("error", f"asr_diff.py exited {result.returncode}: {result.stderr.strip()[-400:]}")
    report = json.loads(out.read_text())
    problems = [p for p in report.get("problems", []) if not p.get("allowed")]
    lines = [f"{p['at']:.2f}s {p['type']} intended={p['intended']!r} heard={p['heard']!r}" for p in problems]
    status = "fail" if result.returncode == 1 else "pass"
    summary = f"similarity {report.get('similarity')}, {len(problems)} blocking differences"
    return gate(status, summary, report=str(out), blocking=lines)


def page_box(page):
    if "bbox" in page:
        return [float(v) for v in page["bbox"]]
    return [float(page["x"]), float(page["y"]), float(page["x"]) + float(page["w"]), float(page["y"]) + float(page["h"])]


def page_time(page, key):
    return float(page[key]) if key in page else float(page[key + "Ms"]) / 1000


def gate_captions(reel, args, ctx):
    path = Path(args.captions_bbox) if args.captions_bbox else Path(args.out_dir) / "captions_bbox.json"
    data = load_json(path)
    if data is None:
        return gate("skip", f"no caption bbox file ({path}); export one from the caption renderer to gate the safe zone")
    pages = data["pages"] if isinstance(data, dict) else data
    x0s, y0s, x1s, y1s = SAFE_BOX
    bad = []
    for index, page in enumerate(pages):
        box = page_box(page)
        start, end = page_time(page, "start"), page_time(page, "end")
        reasons = []
        if box[0] < x0s or box[1] < y0s or box[2] > x1s or box[3] > y1s:
            reasons.append(f"bbox {[round(v) for v in box]} outside x {x0s}-{x1s}, y {y0s}-{y1s}")
        if end - start < 0.35:
            reasons.append(f"on screen {end - start:.2f}s < 0.35s")
        if reasons:
            bad.append({"page": index, "text": page.get("text", ""), "start": start, "problems": reasons})
    status = "fail" if bad else "pass"
    return gate(status, f"{len(pages)} pages, {len(bad)} outside the safe box or too short", violations=bad, source=str(path))


def signalstats(path, step):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0", "-vf",
         f"select='not(mod(n\\,{step}))',signalstats,metadata=print:file=-", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    rows, current = [], None
    for line in result.stdout.splitlines():
        if line.startswith("frame:"):
            match = re.search(r"pts_time:([\d.]+)", line)
            current = {"t": float(match.group(1)) if match else 0.0}
            rows.append(current)
        elif current is not None and "lavfi.signalstats." in line:
            key, value = line.split("lavfi.signalstats.")[1].split("=")
            if key in ("YMIN", "YLOW", "YAVG", "YHIGH", "YMAX"):
                current[key] = float(value)
    return rows


def level_segments(reel):
    segments = []
    if reel.cues:
        for seg in reel.cues.get("segments", []):
            segments.append({"name": f"seg{seg['index']:02d} {seg.get('clip', '')}".strip(), "start": float(seg["start"]), "end": float(seg["end"])})
        last = max((s["end"] for s in segments), default=0.0)
        if reel.duration - last > 0.2:
            segments.append({"name": "after A-roll (end card)", "start": last, "end": reel.duration})
    else:
        segments.append({"name": "whole reel", "start": 0.0, "end": reel.duration})
    return segments


def gate_levels(reel, args, ctx):
    stats = signalstats(reel.path, args.levels_step)
    segments = level_segments(reel)
    sample_numbers = {}
    for seg in segments:
        span = seg["end"] - seg["start"]
        for frac in (0.25, 0.5, 0.75):
            sample_numbers[min(reel.frames - 1, int((seg["start"] + span * frac) * reel.fps))] = seg["name"]
    raw = reel.frames_at(reel.path, sample_numbers.keys(), pix_fmt="yuv420p")
    aroll_path = reel.work / "aroll.mp4"
    aroll = {}
    if aroll_path.is_file() and reel.cues:
        a_numbers = [n for n in sample_numbers if n / reel.fps < reel.cues.get("duration", 0)]
        aroll = reel.frames_at(aroll_path, a_numbers, pix_fmt="yuv420p")
    rows, failures = [], []
    for seg in segments:
        frames = [r for r in stats if seg["start"] <= r["t"] < seg["end"]]
        if not frames:
            continue
        numbers = [n for n, name in sample_numbers.items() if name == seg["name"] and n in raw]
        p_lo = [float(np.percentile(raw[n], 0.1)) for n in numbers]
        p_hi = [float(np.percentile(raw[n], 99.9)) for n in numbers]
        row = {
            "segment": seg["name"], "from": round(seg["start"], 2), "to": round(seg["end"], 2),
            "YMIN": min(r["YMIN"] for r in frames), "YLOW": round(float(np.median([r["YLOW"] for r in frames])), 1),
            "YAVG": round(float(np.median([r["YAVG"] for r in frames])), 1), "YHIGH": round(float(np.median([r["YHIGH"] for r in frames])), 1),
            "YMAX": max(r["YMAX"] for r in frames),
            "p0.1": round(min(p_lo), 1) if p_lo else None, "p99.9": round(max(p_hi), 1) if p_hi else None,
        }
        deltas = [float(np.percentile(raw[n], 1) - np.percentile(aroll[n], 1)) for n in numbers if n in aroll]
        if deltas:
            row["black_p1_vs_aroll"] = round(float(np.median(deltas)), 1)
        rows.append(row)
        if row["p0.1"] is not None and (row["p0.1"] < 15 or row["p99.9"] > 236):
            failures.append(f"{seg['name']} p0.1 {row['p0.1']} p99.9 {row['p99.9']}")
    shifts = [r for r in rows if abs(r.get("black_p1_vs_aroll", 0)) >= 6]
    status = "fail" if failures else ("warn" if shifts else "pass")
    summary = f"{len(rows)} segments; legal range (p0.1 >= 15, p99.9 <= 236) " + ("violated: " + "; ".join(failures) if failures else "held")
    if shifts:
        summary += f"; black level differs from the A-roll by 6+ codes in {[r['segment'] for r in shifts]} (graphics over the frame, or a second range conversion)"
    return gate(status, summary, segments=rows)


def label(image, text, colour=(255, 255, 255)):
    cv2.rectangle(image, (0, 0), (image.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(image, text, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)
    return image


def sheet_events(reel):
    events = []
    for t in (reel.cues or {}).get("cuts", []):
        events.append(("cut", float(t), ""))
    for beat in (reel.beatmap or {}).get("beats", []):
        events.append(("beat", float(beat["from"]), f"{beat.get('id', '')} {beat.get('component', '')}".strip()))
    events.sort(key=lambda e: e[1])
    kept = []
    for event in events:
        if kept and abs(round(event[1] * reel.fps) - round(kept[-1][1] * reel.fps)) <= 2 and event[0] == kept[-1][0]:
            continue
        kept.append(event)
    return kept


def gate_sheets(reel, args, ctx):
    events = sheet_events(reel)
    if not events:
        return gate("skip", "no cues.json cuts or beatmap.json beats to sheet")
    folder = Path(args.out_dir) / "sheets"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.jpg"):
        old.unlink()
    radius, thumb_w, thumb_h = args.sheet_radius, 180, 320
    written = []
    for index, (kind, t, name) in enumerate(events):
        centre = round(t * reel.fps)
        numbers = [n for n in range(centre - radius, centre + radius + 1) if 0 <= n < reel.frames]
        frames = reel.frames_at(reel.path, numbers, thumb_w, thumb_h)
        tiles = []
        for n in numbers:
            tile = frames.get(n, np.zeros((thumb_h, thumb_w, 3), np.uint8)).copy()
            label(tile, f"f{n} {n - centre:+d}", (80, 80, 255) if n == centre else (255, 255, 255))
            if n == centre:
                cv2.rectangle(tile, (1, 1), (thumb_w - 2, thumb_h - 2), (0, 0, 255), 3)
            tiles.append(tile)
        strip = np.hstack(tiles)
        header = np.zeros((28, strip.shape[1], 3), np.uint8)
        cv2.putText(header, f"{kind} {t:.2f}s frame {centre} {name}", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        path = folder / f"{index:02d}_{kind}_{t:06.2f}s.jpg"
        cv2.imwrite(str(path), np.vstack([header, strip]), [cv2.IMWRITE_JPEG_QUALITY, 88])
        written.append({"kind": kind, "t": t, "frame": centre, "name": name, "path": str(path)})
    return gate("info", f"{len(written)} contact sheets in {folder} ({radius} frames either side); read every one", sheets=written)


def face_region(reel):
    segments = (reel.cues or {}).get("segments", [])
    if segments and segments[0].get("face"):
        face = segments[0]["face"]
        w, h = face["w"] * 1.4, face["h"] * 1.4
        x0, y0 = int(max(0, face["cx"] - w / 2)), int(max(0, face["cy"] - h / 2))
        return x0, y0, int(min(reel.width, x0 + w)), int(min(reel.height, y0 + h)), "cues face box x1.4"
    return reel.width // 4, reel.height // 6, reel.width * 3 // 4, reel.height // 2, "centre upper half (no face box)"


def sharpness(gray, box):
    x0, y0, x1, y1 = box
    crop = gray[y0:y1, x0:x1].astype(np.float32)
    return float(cv2.Laplacian(crop, cv2.CV_32F).var())


def gate_first_frame(reel, args, ctx):
    x0, y0, x1, y1, region = face_region(reel)
    first_end = (reel.cues or {}).get("segments", [{}])[0].get("end", 4.0)
    window_end = min(first_end, 4.0, reel.duration)
    reference_numbers = list(range(int(0.5 * reel.fps), int(window_end * reel.fps), 5))
    first = [0, 1, 2]
    frames = reel.frames_at(reel.path, first + reference_numbers, pix_fmt="yuv420p")
    reference = [sharpness(frames[n], (x0, y0, x1, y1)) for n in reference_numbers if n in frames]
    if not reference:
        return gate("error", "could not decode reference frames")
    median = float(np.median(reference))
    rows, colour = [], reel.frames_at(reel.path, first, 360, 640)
    tiles = []
    for n in first:
        value = sharpness(frames[n], (x0, y0, x1, y1)) if n in frames else 0.0
        ratio = value / median if median else 0.0
        rows.append({"frame": n, "sharpness": round(value, 1), "ratio_to_hook_median": round(ratio, 2)})
        tile = colour.get(n, np.zeros((640, 360, 3), np.uint8)).copy()
        scale = 360 / reel.width
        cv2.rectangle(tile, (int(x0 * scale), int(y0 * scale)), (int(x1 * scale), int(y1 * scale)), (0, 255, 255), 2)
        tiles.append(label(tile, f"f{n} sharp {ratio:.0%} of hook median"))
    path = Path(args.out_dir) / "first_frames.jpg"
    cv2.imwrite(str(path), np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 90])
    weak = [r for r in rows if r["ratio_to_hook_median"] < args.first_frame_ratio]
    status = "fail" if weak else "pass"
    summary = ", ".join(f"f{r['frame']} {r['ratio_to_hook_median']:.0%}" for r in rows) + f" of the hook median (need {args.first_frame_ratio:.0%}); look at {path}"
    return gate(status, summary, frames=rows, region=region, reference_frames=len(reference), image=str(path))


RUNNERS = {
    "spec": gate_spec, "loudness": gate_loudness, "drift": gate_drift, "rhythm": gate_rhythm, "splices": gate_splices,
    "asr": gate_asr, "captions": gate_captions, "levels": gate_levels, "sheets": gate_sheets, "first_frame": gate_first_frame,
}

NOT_COVERED = [
    "Listening: denoise artefacts, de-esser lisp, gate pumping, bed level and masking. Hand the owner 5 timestamps (hook, first slam, loudest SFX, a held pause, end card).",
    "Caption timing against each word onset (0 to 2 frames early) and caption overlap with the mouth: check frames at 5 or 6 onsets.",
    "Graphics content: text size, invented numbers, brand colour meanings, third-party UI. Read the beat sheets.",
    "Taste: hook strength, pacing feel, whether each graphic earns its place. That is the critic pass (references/critic-prompt.md).",
]


def write_report(results, reel, out_dir, started):
    order = {"fail": 0, "error": 1, "warn": 2, "pass": 3, "info": 4, "skip": 5}
    blocking = [name for name, r in results.items() if r["status"] in ("fail", "error")]
    report = {
        "reel": str(reel.path), "work": str(reel.work), "generated": started,
        "video": {"frames": reel.frames, "fps": reel.fps, "duration_s": round(reel.duration, 4)},
        "pass": not blocking, "blocking": blocking, "not_run": [g for g in GATES if g not in results],
        "gates": results, "not_covered": NOT_COVERED,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, default=float) + "\n")
    lines = [
        f"# QA report: {reel.path.name}", "",
        f"Generated {started}. {reel.frames} frames at {reel.fps:g} fps ({reel.duration:.3f} s).", "",
        f"**Overall: {'PASS' if not blocking else 'FAIL'}**" + (f" (blocking: {', '.join(blocking)})" if blocking else ""), "",
        *([f"Partial run: not run {', '.join(g for g in GATES if g not in results)}.", ""] if len(results) < len(GATES) else []),
        "| Gate | Status | Result |", "|---|---|---|",
    ]
    for name, result in sorted(results.items(), key=lambda kv: (order.get(kv[1]["status"], 9), GATES.index(kv[0]))):
        lines.append(f"| {name} | {result['status'].upper()} | {result['summary'].replace('|', '/')} |")
    lines += ["", "## Details", ""]
    rhythm = results.get("rhythm")
    if rhythm and rhythm.get("largest_gaps"):
        lines.append("Largest gaps between visual changes: " + ", ".join(f"{g['from']:.2f}-{g['to']:.2f} ({g['gap']:.2f}s)" for g in rhythm["largest_gaps"]))
    drift = results.get("drift")
    if drift and drift.get("sync_windows"):
        lines.append("Voice sync windows (lag ms / corr): " + ", ".join(f"{w['from']:.0f}-{w['to']:.0f}s {w['lag_ms']:+.0f}/{w['corr']:.2f}" for w in drift["sync_windows"]))
    splices = results.get("splices")
    if splices and splices.get("splices"):
        lines.append("Splices (t: voice HF burst dB / voice step ratio / mix hole dB): " + ", ".join(
            f"{s['t']:.2f}: {s['hf_burst_db']:+.1f}/{s['step_ratio']:.1f}/{s['hole_db']:.1f}" for s in splices["splices"]))
    asr = results.get("asr")
    if asr and asr.get("blocking"):
        lines += ["", "ASR differences:"] + [f"- {line}" for line in asr["blocking"]]
    captions = results.get("captions")
    if captions and captions.get("violations"):
        lines += ["", "Caption pages:"] + [f"- {v['start']:.2f}s {v['text']!r}: {'; '.join(v['problems'])}" for v in captions["violations"]]
    levels = results.get("levels")
    if levels and levels.get("segments"):
        lines += ["", "| Segment | From | To | YMIN | YLOW | YAVG | YHIGH | YMAX | p0.1 | p99.9 | black vs A-roll |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in levels["segments"]:
            lines.append(f"| {s['segment']} | {s['from']} | {s['to']} | {s['YMIN']:.0f} | {s['YLOW']} | {s['YAVG']} | {s['YHIGH']} | {s['YMAX']:.0f} | {s['p0.1']} | {s['p99.9']} | {s.get('black_p1_vs_aroll', '')} |")
    sheets = results.get("sheets")
    if sheets and sheets.get("sheets"):
        lines += ["", "Contact sheets:"] + [f"- {s['kind']} {s['t']:.2f}s {s['name']}: `{s['path']}`" for s in sheets["sheets"]]
    lines += ["", "## Not verified by qa.py", ""] + [f"- {item}" for item in NOT_COVERED]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Run every delivery gate on a rendered reel and write <out-dir>/report.md and report.json. "
                    "Reads edl.json, cues.json, beatmap.json, camera_plan.json, props.json, words.out.json, voice.wav and aroll.mp4 "
                    "from the work folder when present. Exit 1 when any gate fails.")
    parser.add_argument("--reel", required=True, help="delivered MP4 (or any muxed render) to check")
    parser.add_argument("--work", default=".", help="reel work folder (default: current directory)")
    parser.add_argument("--out-dir", help="report folder (default <work>/qa)")
    parser.add_argument("--only", help=f"comma list of gates to run ({','.join(GATES)})")
    parser.add_argument("--skip", default="", help="comma list of gates to skip")
    parser.add_argument("--expected-duration", type=float, help="delivery length in seconds (default: props.json durationSec, else edl + --extra-sec)")
    parser.add_argument("--extra-sec", type=float, help="end card seconds after the A-roll")
    parser.add_argument("--target-lufs", type=float, default=-14.0)
    parser.add_argument("--voice-ref", help="processed voice for the sync check and the splice click check (default <work>/voice.wav, else voice_cut.wav)")
    parser.add_argument("--max-gap", type=float, default=4.0, help="largest allowed gap between visual changes in seconds")
    parser.add_argument("--scene-threshold", type=float, default=4.0, help="mean abs frame difference (0-255, 108x192 grey) that counts as a visual change")
    parser.add_argument("--scene-ratio", type=float, default=2.0, help="and at least this multiple of the local median difference")
    parser.add_argument("--click-db", type=float, default=6.0, help="5 kHz high-pass burst over context that counts as a click")
    parser.add_argument("--hole-db", type=float, default=10.0, help="dip under the local room tone that is reported as a hole")
    parser.add_argument("--asr-model", default="large-v3")
    parser.add_argument("--asr-prompt", default="", help="keyterm prompt for the ASR pass (brand names, acronyms)")
    parser.add_argument("--asr-allow", default="", help="comma list of intended>heard pairs that are deliberate caption edits")
    parser.add_argument("--asr-heard", help="existing transcript JSON [{text,start,end}] instead of running the model")
    parser.add_argument("--dictionary", help="caption dictionary JSON for the ASR diff (single-word entries count as equal)")
    parser.add_argument("--captions-bbox", help="caption page boxes JSON (default <out-dir>/captions_bbox.json)")
    parser.add_argument("--levels-step", type=int, default=5, help="signalstats on every Nth frame")
    parser.add_argument("--sheet-radius", type=int, default=4, help="frames either side of each cut or beat entrance")
    parser.add_argument("--first-frame-ratio", type=float, default=0.6, help="frames 0-2 face sharpness must reach this share of the hook median")
    args = parser.parse_args()

    work = Path(args.work).resolve()
    args.out_dir = str(Path(args.out_dir).resolve() if args.out_dir else work / "qa")
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    selected = [g for g in (args.only.split(",") if args.only else GATES) if g]
    unknown = [g for g in selected + [s for s in args.skip.split(",") if s] if g not in GATES]
    if unknown:
        raise SystemExit(f"unknown gate(s): {unknown}; choose from {GATES}")
    selected = [g for g in selected if g not in args.skip.split(",")]
    reel = Reel(args.reel, work)
    started = datetime.datetime.now().isoformat(timespec="seconds")
    ctx, results = {}, {}
    for name in selected:
        clock = time.monotonic()
        try:
            results[name] = RUNNERS[name](reel, args, ctx)
        except Exception as error:
            results[name] = gate("error", f"{type(error).__name__}: {error}")
        results[name]["seconds"] = round(time.monotonic() - clock, 1)
        print(f"[{name}] {results[name]['status'].upper()} ({results[name]['seconds']}s): {results[name]['summary']}", flush=True)
    report = write_report(results, reel, Path(args.out_dir), started)
    print(f"overall {'PASS' if report['pass'] else 'FAIL'}; {Path(args.out_dir) / 'report.md'}")
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
