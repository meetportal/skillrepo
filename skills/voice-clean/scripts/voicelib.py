import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

SAMPLE_RATE = 48000
FRAME_WINDOW_S = 0.03
FRAME_HOP_S = 0.01
SKILL_DIR = Path(__file__).resolve().parent.parent
PRESETS_DIR = SKILL_DIR / "presets"
SPEECH_BANDS = [(80, 250), (250, 800), (800, 2500), (2500, 5000), (5000, 10000), (10000, 16000)]
EPSILON = 1e-12


def band_label(low, high):
    def short(hz):
        return f"{hz / 1000:g}k" if hz >= 1000 else str(hz)
    return f"{short(low)}-{short(high)}"


def run_ffmpeg(args, capture=True):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], check=True, capture_output=capture, text=True)


def probe_channels(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return int(result.stdout.strip().split(",")[0])


def decode(path, sample_rate=SAMPLE_RATE, keep_channels=False):
    channels = probe_channels(path)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:a:0",
         "-ar", str(sample_rate), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    samples = np.frombuffer(raw, dtype=np.float32).astype(np.float64).reshape(-1, channels)
    if keep_channels:
        return samples
    return samples.mean(axis=1)


def write_wav(path, samples, sample_rate=SAMPLE_RATE, subtype="FLOAT"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.asarray(samples, dtype=np.float32 if subtype == "FLOAT" else np.float64), sample_rate, subtype=subtype)


def fit_length(samples, length):
    if len(samples) >= length:
        return samples[:length]
    return np.concatenate([samples, np.zeros(length - len(samples))])


def to_db(power_or_amplitude, power=False):
    factor = 10 if power else 20
    return factor * np.log10(np.maximum(power_or_amplitude, EPSILON))


def frame_db(samples, sample_rate=SAMPLE_RATE, window_s=FRAME_WINDOW_S, hop_s=FRAME_HOP_S):
    window = int(sample_rate * window_s)
    hop = int(sample_rate * hop_s)
    padded = np.pad(samples, (window // 2, window // 2))
    frames = np.lib.stride_tricks.sliding_window_view(padded, window)[::hop]
    return to_db(np.mean(frames ** 2, axis=1), power=True)


def mean_db(frame_levels, mask):
    if not np.any(mask):
        return None
    return float(to_db(np.mean(10 ** (frame_levels[mask] / 10)), power=True))


DIGITAL_SILENCE_DBFS = -90.0


def level_masks(frame_levels, pause_margin_db=6.0, speech_margin_db=20.0):
    live = frame_levels[frame_levels > DIGITAL_SILENCE_DBFS]
    live = live if len(live) else frame_levels
    floor = float(np.percentile(live, 5))
    speech_level = float(np.percentile(live, 90))
    return {
        "floor_p5_dbfs": floor,
        "speech_p90_dbfs": speech_level,
        "pause": (frame_levels < floor + pause_margin_db) & (frame_levels > DIGITAL_SILENCE_DBFS),
        "speech": frame_levels > speech_level - speech_margin_db,
    }


def window_mask(frame_count, windows, hop_s=FRAME_HOP_S):
    mask = np.zeros(frame_count, dtype=bool)
    for start, end in windows:
        mask[int(round(start / hop_s)):int(round(end / hop_s))] = True
    return mask


def parse_window(text):
    start, end = text.split(":")
    return float(start), float(end)


def stft_power(samples, sample_rate=SAMPLE_RATE, n_fft=2048, hop_s=FRAME_HOP_S):
    hop = int(sample_rate * hop_s)
    freqs, _, spectrum = signal.stft(samples, sample_rate, nperseg=n_fft, noverlap=n_fft - hop, boundary="zeros", padded=True)
    return freqs, np.abs(spectrum) ** 2


def band_balance(freqs, power, frame_mask):
    count = min(power.shape[1], len(frame_mask))
    selected = power[:, :count][:, frame_mask[:count]]
    if selected.size == 0:
        return {}
    total = selected[(freqs >= 80) & (freqs < 16000)].sum()
    return {
        band_label(low, high): round(float(to_db(selected[(freqs >= low) & (freqs < high)].sum() / total, power=True)), 1)
        for low, high in SPEECH_BANDS
    }


def band_ratio_db(freqs, power, frame_mask, numerator, denominator):
    count = min(power.shape[1], len(frame_mask))
    selected = power[:, :count][:, frame_mask[:count]]
    top = selected[(freqs >= numerator[0]) & (freqs < numerator[1])].sum()
    bottom = selected[(freqs >= denominator[0]) & (freqs < denominator[1])].sum()
    return round(float(to_db(top / max(bottom, EPSILON), power=True)), 1)


def log_spectral_distance(freqs, power_a, power_b, frame_mask):
    count = min(power_a.shape[1], power_b.shape[1], len(frame_mask))
    band = (freqs >= 80) & (freqs < 16000)
    a = to_db(power_a[band, :count][:, frame_mask[:count]], power=True)
    b = to_db(power_b[band, :count][:, frame_mask[:count]], power=True)
    if a.size == 0:
        return None
    b = b + (np.mean(a) - np.mean(b))
    floor = np.max(a) - 80
    a = np.maximum(a, floor)
    b = np.maximum(b, floor)
    return round(float(np.mean(np.sqrt(np.mean((a - b) ** 2, axis=0)))), 2)


def runs(mask, min_frames):
    edges = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= min_frames]


def hum_peaks(samples, sample_rate, frame_mask, fundamentals=(50, 60), harmonics=4):
    hop = int(sample_rate * FRAME_HOP_S)
    pieces = [samples[i * hop:(i + 1) * hop] for i in np.where(frame_mask)[0]]
    quiet = np.concatenate(pieces) if pieces else samples
    if len(quiet) < 8192:
        quiet = samples
    freqs, power = signal.welch(quiet, sample_rate, nperseg=8192)
    power_db = to_db(power, power=True)
    peaks = {}
    for fundamental in fundamentals:
        for order in range(1, harmonics + 1):
            target = fundamental * order
            index = int(np.argmin(np.abs(freqs - target)))
            local = np.median(power_db[max(0, index - 20):index + 20])
            peaks[str(target)] = round(float(power_db[max(0, index - 2):index + 3].max() - local), 1)
    noise_bands = {
        band_label(low, high): round(float(np.mean(power_db[(freqs >= low) & (freqs < high)])), 1)
        for low, high in [(20, 80), (80, 300), (300, 2000), (2000, 6000), (6000, 12000), (12000, 20000)]
    }
    return peaks, noise_bands


def transient_events(freqs, power, frame_levels, floor, hop_s=FRAME_HOP_S):
    count = min(power.shape[1], len(frame_levels))
    levels = frame_levels[:count]
    sib = to_db(power[(freqs >= 5000) & (freqs < 10000), :count].sum(0), power=True)
    body = to_db(power[(freqs >= 300) & (freqs < 3000), :count].sum(0), power=True)
    low = to_db(power[(freqs >= 20) & (freqs < 120), :count].sum(0), power=True)
    sib_ratio = sib - body
    low_ratio = low - body
    low_gate = np.percentile(low, 97)

    def local_maxima(values, condition):
        return [
            i for i in range(1, count - 1)
            if condition[i] and values[i] >= values[i - 1] and values[i] >= values[i + 1]
        ]

    sibilants = local_maxima(sib_ratio, (sib_ratio > 3) & (levels > floor + 15))
    plosives = local_maxima(low_ratio, (low_ratio > 6) & (low > low_gate))
    sibilant_events = sorted(
        ({"t": round(i * hop_s, 2), "ratio_db": round(float(sib_ratio[i]), 1), "level_dbfs": round(float(levels[i]), 1)} for i in sibilants),
        key=lambda event: -event["ratio_db"],
    )
    plosive_events = sorted(
        ({"t": round(i * hop_s, 2), "low_vs_body_db": round(float(low_ratio[i]), 1), "low_dbfs": round(float(low[i]), 1)} for i in plosives),
        key=lambda event: -event["low_vs_body_db"],
    )
    return sibilant_events, plosive_events


def parse_ebur128(stderr):
    summary = stderr[stderr.rfind("Summary:"):]

    def grab(pattern):
        found = re.search(pattern, summary)
        return float(found.group(1)) if found else None

    return {
        "lufs_i": grab(r"I:\s+(-?[\d.]+|-inf) LUFS"),
        "lra_lu": grab(r"LRA:\s+(-?[\d.]+) LU"),
        "true_peak_dbtp": grab(r"Peak:\s+(-?[\d.]+|-inf) dBFS"),
    }


def ebur128(path):
    result = run_ffmpeg(["-nostats", "-i", str(path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
    return parse_ebur128(result.stderr)


def astats(path, start=None, end=None):
    filters = []
    if start is not None:
        filters.append(f"atrim=start={max(0.0, start):.6f}:end={end:.6f}")
    filters.append("astats=measure_perchannel=none")
    result = run_ffmpeg(["-nostats", "-i", str(path), "-af", ",".join(filters), "-f", "null", "-"])
    overall = result.stderr[result.stderr.rfind("] Overall"):]
    values = {}
    for key, value in re.findall(r"\] ([A-Za-z ]+): (-?[\d.]+|-?inf)", overall):
        values[key.strip().lower().replace(" ", "_")] = float(value)
    return values


def spectrum_png(audio_path, png_path, width=1600, height=700):
    Path(png_path).parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-v", "error", "-y", "-i", str(audio_path),
        "-lavfi", f"showspectrumpic=s={width}x{height}:mode=combined:color=magma:scale=log:fscale=log:drange=100:legend=1",
        "-frames:v", "1", "-update", "1", str(png_path),
    ])
    return str(png_path)


def listen_points(samples, sample_rate=SAMPLE_RATE, count=5):
    levels = frame_db(samples, sample_rate)
    masks = level_masks(levels)
    freqs, power = stft_power(samples, sample_rate)
    sibilants, plosives = transient_events(freqs, power, levels, masks["floor_p5_dbfs"])
    speech_frames = np.where(masks["speech"])[0]
    points = []
    if len(speech_frames):
        onset = max(0.0, speech_frames[0] * FRAME_HOP_S - 0.3)
        points.append({"t": round(onset, 2), "why": "first speech onset: denoiser and gate attack"})
    if sibilants:
        points.append({"t": max(0.0, sibilants[0]["t"] - 0.5), "why": f"strongest sibilant at {sibilants[0]['t']} s: de-esser"})
    if plosives:
        points.append({"t": max(0.0, plosives[0]["t"] - 0.5), "why": f"strongest low-frequency burst at {plosives[0]['t']} s: high-pass"})
    inner = masks["pause"].copy()
    if len(speech_frames):
        inner[:speech_frames[0]] = False
        inner[speech_frames[-1]:] = False
    pause_runs = sorted(runs(inner, 15), key=lambda run: run[0] - run[1])
    if pause_runs:
        start, end = pause_runs[0]
        points.append({"t": round(max(0.0, start * FRAME_HOP_S - 1.0), 2), "why": f"longest inner pause {start * FRAME_HOP_S:.2f}-{end * FRAME_HOP_S:.2f} s: gate pumping, floor"})
    if len(speech_frames):
        points.append({"t": round(max(0.0, speech_frames[-1] * FRAME_HOP_S - 1.0), 2), "why": "last phrase tail: gate release on decay"})
    return points[:count]


def load_preset(reference):
    path = Path(reference)
    if not path.exists():
        candidates = [PRESETS_DIR / f"{reference}{suffix}" for suffix in (".json", ".yaml", ".yml")]
        found = [candidate for candidate in candidates if candidate.exists()]
        if not found:
            available = sorted(p.stem for p in PRESETS_DIR.glob("*") if p.suffix in (".json", ".yaml", ".yml"))
            raise SystemExit(f"preset not found: {reference}. Available: {', '.join(available)}")
        path = found[0]
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        import yaml
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    data.setdefault("name", path.stem)
    data.setdefault("params", {})
    data.setdefault("stages", [])
    return data


def parse_assignments(assignments):
    values = {}
    for item in assignments or []:
        key, value = item.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def fill_template(value, params):
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, dict):
        return {key: fill_template(item, params) for key, item in value.items()}
    if isinstance(value, list):
        return [fill_template(item, params) for item in value]
    return value


def hum_notch_filters(options):
    fundamental = float(options.get("fundamental_hz", 50))
    harmonics = int(options.get("harmonics", 4))
    q = float(options.get("q", 20))
    gain = float(options.get("gain_db", -30))
    return [f"equalizer=f={fundamental * order:g}:t=q:w={q:g}:g={gain:g}" for order in range(1, harmonics + 1)]


def resolve_stages(preset, overrides=None):
    params = {**preset.get("params", {}), **(overrides or {})}
    missing = [match for stage in preset["stages"] for match in re.findall(r"\{(\w+)\}", json.dumps(stage)) if match not in params]
    if missing:
        raise SystemExit(f"preset {preset['name']} needs params: {', '.join(sorted(set(missing)))} (pass --set name=value)")
    resolved = []
    for stage in fill_template(preset["stages"], params):
        if isinstance(stage, dict) and "hum_notch" in stage:
            resolved.extend(hum_notch_filters(stage["hum_notch"]))
        else:
            resolved.append(stage)
    return resolved, params


def group_stages(stages):
    groups = []
    for stage in stages:
        if isinstance(stage, str):
            if groups and groups[-1][0] == "ffmpeg":
                groups[-1][1].append(stage)
            else:
                groups.append(("ffmpeg", [stage]))
        elif isinstance(stage, dict) and "deepfilter" in stage:
            groups.append(("deepfilter", stage["deepfilter"] or {}))
        else:
            raise SystemExit(f"unknown stage: {stage}")
    return groups


def find_deep_filter(explicit=None):
    candidate = explicit or os.environ.get("DEEP_FILTER_BIN") or shutil.which("deep-filter")
    if not candidate or not Path(candidate).exists():
        raise SystemExit(
            "deep-filter binary not found. Download the release binary for your platform from "
            "https://github.com/Rikorose/DeepFilterNet/releases, chmod +x it, and pass --deep-filter PATH "
            "or set DEEP_FILTER_BIN."
        )
    return candidate


DEEP_FILTER_FLAGS = {
    "atten_lim_db": "--atten-lim-db",
    "pf_beta": "--pf-beta",
    "min_db_thresh": "--min-db-thresh",
    "max_db_erb_thresh": "--max-db-erb-thresh",
    "max_db_df_thresh": "--max-db-df-thresh",
    "model": "--model",
}


def run_deep_filter(input_wav, output_wav, options, binary, workdir):
    out_dir = Path(workdir) / f"deepfilter_{Path(output_wav).stem}"
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [binary, "--compensate-delay", "--output-dir", str(out_dir)]
    for key, flag in DEEP_FILTER_FLAGS.items():
        if key in options and str(options[key]) != "":
            command += [flag, str(options[key])]
    if str(options.get("post_filter", "false")).lower() in ("1", "true", "yes"):
        command.append("--pf")
    command.append(str(input_wav))
    subprocess.run(command, check=True, capture_output=True, text=True)
    source_length = len(decode(input_wav))
    enhanced = fit_length(decode(out_dir / Path(input_wav).name), source_length)
    write_wav(output_wav, enhanced)


LATENCY_PAD_S = 0.25
MAX_LATENCY_S = 0.1


def apply_chain(input_path, output_path, stages, deep_filter_bin=None, subtype="FLOAT", latencies=None):
    source = decode(input_path)
    pad = int(SAMPLE_RATE * LATENCY_PAD_S)
    current_samples = source
    with tempfile.TemporaryDirectory() as workdir:
        for index, (kind, payload) in enumerate(group_stages(stages), start=1):
            stage_input = Path(workdir) / f"stage_{index}_in.wav"
            stage_output = Path(workdir) / f"stage_{index}_out.wav"
            write_wav(stage_input, np.concatenate([current_samples, np.zeros(pad)]))
            if kind == "ffmpeg":
                run_ffmpeg(["-v", "error", "-y", "-i", str(stage_input), "-af", ",".join(payload),
                            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", str(stage_output)])
            else:
                run_deep_filter(stage_input, stage_output, payload, find_deep_filter(deep_filter_bin), workdir)
            processed = decode(stage_output)
            delay = -alignment_lag_samples(current_samples, processed, int(SAMPLE_RATE * MAX_LATENCY_S))
            if latencies is not None:
                latencies.append({"stage": payload if kind == "ffmpeg" else {"deepfilter": payload}, "latency_samples": delay})
            current_samples = fit_length(processed[max(delay, 0):], len(source))
    write_wav(output_path, current_samples, subtype=subtype)
    return current_samples


def alignment_lag_samples(reference, candidate, max_lag=4800):
    length = min(len(reference), len(candidate))
    correlation = signal.correlate(reference[:length], candidate[:length], mode="full", method="fft")
    center = length - 1
    window = correlation[center - max_lag:center + max_lag + 1]
    return int(np.argmax(np.abs(window)) - max_lag)
