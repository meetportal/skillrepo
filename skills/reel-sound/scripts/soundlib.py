import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

SAMPLE_RATE = 48000
FPS_DEFAULT = 25


def run_ffmpeg(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], check=True, capture_output=True, text=True)


def probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def decode_mono(path, sample_rate=SAMPLE_RATE, start=None, duration=None):
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error"]
    if start is not None:
        args += ["-ss", f"{start:.6f}"]
    if duration is not None:
        args += ["-t", f"{duration:.6f}"]
    args += ["-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"]
    raw = subprocess.run(args, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def db(value, floor=1e-12):
    return 20.0 * np.log10(np.maximum(np.abs(value), floor))


K_PRE_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
K_PRE_A = [1.0, -1.69065929318241, 0.73248077421585]
K_RLB_B = [1.0, -2.0, 1.0]
K_RLB_A = [1.0, -1.99004745483398, 0.99007225036621]
MOMENTARY_S = 0.4


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def k_weighted(samples):
    from scipy.signal import lfilter

    stage = lfilter(K_PRE_B, K_PRE_A, samples, axis=0)
    return lfilter(K_RLB_B, K_RLB_A, stage, axis=0)


def weighted_power(samples, dual_mono=True):
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    channels = 2.0 if dual_mono and x.shape[1] == 1 else 1.0
    return (k_weighted(x) ** 2).sum(axis=1) * channels


def momentary_curve(samples, hop_s=0.01, dual_mono=True, pad=True):
    window = int(MOMENTARY_S * SAMPLE_RATE)
    x = np.asarray(samples, dtype=np.float64)
    if pad:
        x = np.pad(x, [(window, window)] + [(0, 0)] * (x.ndim - 1))
    power = weighted_power(x, dual_mono)
    if len(power) < window:
        power = np.pad(power, (0, window - len(power)))
    hop = max(1, int(hop_s * SAMPLE_RATE))
    cumulative = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, len(power) - window + 1, hop)
    mean = (cumulative[starts + window] - cumulative[starts]) / window
    loudness = -0.691 + 10.0 * np.log10(np.maximum(mean, 1e-20))
    centres = (starts + window / 2) / SAMPLE_RATE - (MOMENTARY_S if pad else 0.0)
    return centres, loudness


def momentary_max(samples, dual_mono=True):
    if not len(samples) or not np.any(samples):
        return float("-inf")
    _, loudness = momentary_curve(samples, dual_mono=dual_mono)
    return float(loudness.max())


def gated_mean(loudness):
    return -0.691 + 10.0 * np.log10(np.mean(10.0 ** ((loudness + 0.691) / 10.0)))


def integrated_lufs(samples, dual_mono=True):
    if len(samples) < int(MOMENTARY_S * SAMPLE_RATE) or not np.any(samples):
        return float("-inf")
    _, loudness = momentary_curve(samples, hop_s=0.1, dual_mono=dual_mono, pad=False)
    gated = loudness[loudness > -70.0]
    if not len(gated):
        return float("-inf")
    gated = gated[gated > gated_mean(gated) - 10.0]
    return float(gated_mean(gated)) if len(gated) else float("-inf")


def power_track(samples, dual_mono=True):
    return np.concatenate([[0.0], np.cumsum(weighted_power(samples, dual_mono))])


def track_lufs(track, centre_s, width_s=MOMENTARY_S):
    last = len(track) - 1
    start = min(last, max(0, int(round((centre_s - width_s / 2) * SAMPLE_RATE))))
    end = min(last, max(start, int(round((centre_s + width_s / 2) * SAMPLE_RATE))))
    width = max(1, int(round(width_s * SAMPLE_RATE)))
    power = (track[end] - track[start]) / width
    return float(-0.691 + 10.0 * np.log10(max(power, 1e-20)))


def played_portion(samples, trim_start=0.0, max_dur=None, fade_out=0.0):
    start = int(round(trim_start * SAMPLE_RATE))
    portion = np.asarray(samples[start:], dtype=np.float64)
    if max_dur:
        portion = portion[:int(round(max_dur * SAMPLE_RATE))]
    portion = portion.copy()
    fade = min(len(portion), int(round((fade_out or 0.0) * SAMPLE_RATE)))
    if fade > 0:
        portion[len(portion) - fade:] *= np.linspace(1.0, 0.0, fade)
    return portion


def load_words(path):
    data = load_json(path)
    items = data["words"] if isinstance(data, dict) else data
    words = []
    for item in items:
        if "startMs" in item:
            start, end = item["startMs"] / 1000.0, item["endMs"] / 1000.0
        else:
            start, end = float(item["start"]), float(item["end"])
        words.append({"text": str(item.get("text", item.get("word", ""))).strip(), "start": start, "end": max(end, start)})
    return sorted(words, key=lambda w: w["start"])


def read_stereo(path):
    import soundfile

    data, rate = soundfile.read(str(path), dtype="float64", always_2d=True)
    if rate != SAMPLE_RATE:
        raise SystemExit(f"{path}: {rate} Hz, expected {SAMPLE_RATE}")
    return data if data.shape[1] == 2 else np.repeat(data[:, :1], 2, axis=1)


def write_float_wav(path, data):
    import soundfile

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(path), np.asarray(data, dtype=np.float32), SAMPLE_RATE, subtype="FLOAT")


def ebur128(path, filter_prefix=None):
    chain = "ebur128=peak=true:framelog=verbose"
    if filter_prefix:
        chain = f"{filter_prefix},{chain}"
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-v", "verbose", "-i", str(path), "-map", "0:a:0", "-af", chain, "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    log = result.stderr
    frames = []
    pattern = re.compile(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)\s+S:\s*(-?[\d.]+|-inf)")
    for match in pattern.finditer(log):
        t, momentary, short_term = match.groups()
        frames.append((float(t), parse_level(momentary), parse_level(short_term)))
    summary = log[log.rfind("Summary:"):]
    integrated = parse_level(re.search(r"I:\s*(-?[\d.]+|-inf)\s+LUFS", summary).group(1))
    threshold = parse_level(re.search(r"I:.*?Threshold:\s*(-?[\d.]+|-inf)\s+LUFS", summary, re.S).group(1))
    lra = float(re.search(r"LRA:\s*(-?[\d.]+)\s+LU", summary).group(1))
    true_peak_match = re.search(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf)", summary)
    true_peak = parse_level(true_peak_match.group(1)) if true_peak_match else None
    return {"integrated": integrated, "threshold": threshold, "lra": lra, "true_peak": true_peak, "frames": frames}


def parse_level(text):
    return float("-inf") if text == "-inf" else float(text)


def short_term_at(frames, start, end):
    values = [s for t, _, s in frames if start <= t <= end and s != float("-inf")]
    if not values:
        return None
    return float(np.median(values))


def last_json_block(text):
    start = text.rfind("{")
    end = text.rfind("}")
    return json.loads(text[start:end + 1])


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2) + "\n")
