import json
import subprocess
from pathlib import Path

import numpy as np

TRANSPOSE_FILTERS = {
    "none": "",
    "0": "transpose=0",
    "1": "transpose=1",
    "2": "transpose=2",
    "3": "transpose=3",
    "180": "transpose=1,transpose=1",
    "hflip": "hflip",
}


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


def ffprobe(path):
    result = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    return json.loads(result.stdout)


def clip_name(path):
    return Path(path).stem


def audio_channels(path):
    result = run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", str(path)])
    return int(result.stdout.decode().strip() or 1)


def mono_fold(channel_count):
    if channel_count == 1:
        return "pan=mono|c0=c0"
    weight = 1.0 / channel_count
    return "pan=mono|c0=" + "+".join(f"{weight:.6g}*c{index}" for index in range(channel_count))


def decode_audio(path, sample_rate=16000, channels=1, start=None, end=None):
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    layout = ["-af", mono_fold(audio_channels(path))] if channels == 1 else ["-ac", str(channels)]
    cmd += ["-i", str(path), "-map", "0:a:0", "-vn", *layout, "-ar", str(sample_rate), "-f", "f32le", "-"]
    samples = np.frombuffer(run(cmd).stdout, dtype=np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels)
    return samples.copy()


def rms_envelope_db(samples, sample_rate, hop_s=0.01, window_s=0.03):
    hop = int(round(sample_rate * hop_s))
    window = int(round(sample_rate * window_s))
    padded = np.pad(samples.astype(np.float64), (window // 2, window // 2))
    count = max(1, 1 + (len(padded) - window) // hop)
    squares = np.concatenate([[0.0], np.cumsum(padded ** 2)])
    starts = np.arange(count) * hop
    energy = (squares[starts + window] - squares[starts]) / window
    return 20 * np.log10(np.sqrt(energy) + 1e-10)


def hysteresis_segments(envelope_db, on_db, off_db, hop_s=0.01, min_gap_s=0.15, min_len_s=0.06, strong_db=None):
    active = np.zeros(len(envelope_db), bool)
    state = False
    for index, value in enumerate(envelope_db):
        if not state and value > on_db:
            state = True
        elif state and value < off_db:
            state = False
        active[index] = state
    segments = []
    index = 0
    while index < len(active):
        if active[index]:
            stop = index
            while stop < len(active) and active[stop]:
                stop += 1
            peak = float(np.max(envelope_db[index:stop]))
            segments.append([index * hop_s, stop * hop_s, strong_db is None or peak >= strong_db])
            index = stop
        else:
            index += 1
    merged = []
    for segment in segments:
        if merged and segment[0] - merged[-1][1] < min_gap_s and segment[2] and merged[-1][2]:
            merged[-1][1] = segment[1]
        else:
            merged.append(segment)
    return [[round(a, 2), round(b, 2)] for a, b, _ in merged if b - a >= min_len_s]


def frame_rate(stream):
    numerator, denominator = stream.get("avg_frame_rate", stream.get("r_frame_rate", "0/1")).split("/")
    return float(numerator) / float(denominator) if float(denominator) else 0.0


def windows_from_mask(mask, fps, min_frames=1, join_frames=1):
    windows = []
    index = 0
    while index < len(mask):
        if mask[index]:
            stop = index
            while stop < len(mask) and mask[stop]:
                stop += 1
            if windows and index - windows[-1][1] <= join_frames:
                windows[-1][1] = stop
            else:
                windows.append([index, stop])
            index = stop
        else:
            index += 1
    return [[round(a / fps, 3), round(b / fps, 3)] for a, b in windows if b - a >= min_frames]
