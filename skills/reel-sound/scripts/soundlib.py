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
