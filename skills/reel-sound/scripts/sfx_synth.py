import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import SAMPLE_RATE

PEAK_DBFS = -1.0
STFT_SIZE = 1024
STFT_HOP = 256
FLATTEN_S = 0.004

PRESETS = {
    "whoosh-move": {"category": "whoosh", "kind": "whoosh", "align": "peak", "variants": 3,
                    "params": {"dur": 0.6, "peak": 0.09, "f_lo": 330.0, "f_hi": 2000.0, "width": 0.8, "tail": 0.18, "air": 0.15}},
    "whoosh-transition": {"category": "transition", "kind": "whoosh", "align": "peak", "variants": 2,
                          "params": {"dur": 0.8, "peak": 0.32, "f_lo": 300.0, "f_hi": 1600.0, "width": 0.8, "tail": 0.25, "air": 0.15}},
    "whoosh-swell": {"category": "swell", "kind": "swell", "align": "peak", "variants": 1,
                     "params": {"dur": 0.9, "peak": 0.12, "f_lo": 500.0, "f_hi": 4200.0, "width": 0.7, "tail": 0.3, "air": 0.2}},
    "impact": {"category": "impact", "kind": "impact", "align": "onset", "variants": 3,
               "params": {"dur": 0.35, "f_start": 120.0, "f_end": 45.0, "sweep_tau": 0.06, "body_tau": 0.09, "click_tau": 0.005, "click": 0.8, "drive": 2.5, "jitter": 0.05}},
    "pop": {"category": "pop", "kind": "pop", "align": "onset", "variants": 3,
            "params": {"dur": 0.08, "burst": 0.03, "band_lo": 2000.0, "band_hi": 6000.0, "blip_hz": 1200.0, "blip_end_hz": 900.0, "blip_tau": 0.012, "blip": 0.6, "jitter": 0.06}},
    "tick": {"category": "tick", "kind": "tick", "align": "onset", "variants": 2,
             "params": {"dur": 0.06, "tone_hz": 3200.0, "tone_tau": 0.006, "noise_tau": 0.0015, "noise": 0.5, "jitter": 0.06}},
    "riser": {"category": "riser", "kind": "riser", "align": "peak", "variants": 1,
              "params": {"dur": 1.5, "f_lo": 300.0, "f_hi": 3500.0, "width": 0.7, "power": 2.5, "end_fade": 0.025}},
    "tone": {"category": "tone", "kind": "tone", "align": "onset", "variants": 1,
             "params": {"dur": 0.3, "hz": 880.0, "harmonic": 0.2, "fade": 0.01}},
}


def samples(seconds):
    return int(round(seconds * SAMPLE_RATE))


def times(seconds):
    return np.arange(samples(seconds)) / SAMPLE_RATE


def highpass(x, cutoff, order=2):
    return signal.sosfilt(signal.butter(order, cutoff, btype="highpass", fs=SAMPLE_RATE, output="sos"), x)


def bandpass(x, low, high, order=2):
    return signal.sosfilt(signal.butter(order, [low, min(high, SAMPLE_RATE * 0.45)], btype="bandpass", fs=SAMPLE_RATE, output="sos"), x)


def coloured_noise(count, rng, slope):
    spectrum = np.fft.rfft(rng.standard_normal(count))
    freqs = np.maximum(np.fft.rfftfreq(count, 1 / SAMPLE_RATE), 20.0)
    noise = np.fft.irfft(spectrum * freqs ** (-slope / 2), count)
    return noise / (np.std(noise) + 1e-12)


def fades(x, fade_in, fade_out):
    x = np.array(x, dtype=np.float64)
    a, b = samples(fade_in), samples(fade_out)
    if a:
        x[:a] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    if b:
        x[-b:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, b))
    return x


def spectral_band(noise, centre_at, width_oct):
    count = len(noise)
    freqs, frame_times, spectrum = signal.stft(noise, fs=SAMPLE_RATE, window="hann", nperseg=STFT_SIZE, noverlap=STFT_SIZE - STFT_HOP, boundary="zeros", padded=True)
    centre = centre_at(frame_times)
    gain = np.exp(-0.5 * (np.log2(np.maximum(freqs[:, None], 20.0) / centre[None, :]) / width_oct) ** 2)
    _, shaped = signal.istft(spectrum * gain, fs=SAMPLE_RATE, window="hann", nperseg=STFT_SIZE, noverlap=STFT_SIZE - STFT_HOP, boundary=True)
    shaped = shaped[:count]
    return np.pad(shaped, (0, count - len(shaped)))


def flattened(x, window_s=FLATTEN_S):
    window = signal.windows.hann(max(3, samples(window_s)))
    power = np.convolve(x ** 2, window / window.sum(), mode="same")
    return x / np.sqrt(np.maximum(power, 1e-12))


def whoosh(rng, dur, peak, f_lo, f_hi, width, tail, air):
    t = times(dur)
    noise = coloured_noise(len(t), rng, 0.6)
    rise = np.where(t < peak, t / peak, np.exp(-(t - peak) / (tail * 1.3)))
    envelope = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / tail))
    band = spectral_band(noise, lambda at: f_lo + (f_hi - f_lo) * np.interp(at, t, rise), width)
    hiss = highpass(noise, 4000.0)
    power = np.mean(band ** 2) * envelope ** 2 + air ** 2 * np.mean(hiss ** 2) * envelope ** 4
    return fades(flattened(band * envelope + air * hiss * envelope ** 2) * np.sqrt(power), 0.005, 0.04), peak


def swell(rng, dur, peak, f_lo, f_hi, width, tail, air):
    forward, anchor = whoosh(rng, dur, peak, f_lo, f_hi, width, tail, air)
    return fades(forward[::-1], 0.02, 0.005), dur - anchor


def impact(rng, dur, f_start, f_end, sweep_tau, body_tau, click_tau, click, drive, jitter):
    t = times(dur)
    scale = 1.0 + rng.uniform(-jitter, jitter)
    freq = (f_end + (f_start - f_end) * np.exp(-t / sweep_tau)) * scale
    body = np.tanh(drive * np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)) / np.tanh(drive) * np.exp(-t / body_tau)
    crack = highpass(rng.standard_normal(len(t)), 1500.0) * np.exp(-t / click_tau) * click
    thump = signal.sosfilt(signal.butter(2, 300.0, fs=SAMPLE_RATE, output="sos"), rng.standard_normal(len(t))) * np.exp(-t / 0.03) * 0.6
    return fades(body + crack + thump, 0.001, 0.03), 0.0


def pop(rng, dur, burst, band_lo, band_hi, blip_hz, blip_end_hz, blip_tau, blip, jitter):
    t = times(dur)
    scale = 1.0 + rng.uniform(-jitter, jitter)
    gate = np.clip(t / 0.001, 0, 1) * np.exp(-t / (burst / 3)) * (t < burst)
    noise = bandpass(rng.standard_normal(len(t)), band_lo * scale, band_hi * scale, order=3) * gate
    freq = (blip_end_hz + (blip_hz - blip_end_hz) * np.exp(-t / blip_tau)) * scale
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE) * np.exp(-t / blip_tau) * blip
    return fades(noise + tone, 0.0005, 0.01), 0.0


def tick(rng, dur, tone_hz, tone_tau, noise_tau, noise, jitter):
    t = times(dur)
    hz = tone_hz * (1.0 + rng.uniform(-jitter, jitter))
    body = np.sin(2 * np.pi * hz * t) * np.exp(-t / tone_tau)
    click = highpass(rng.standard_normal(len(t)), 3000.0) * np.exp(-t / noise_tau) * noise
    return fades(body + click, 0.0003, 0.01), 0.0


def riser(rng, dur, f_lo, f_hi, width, power, end_fade):
    t = times(dur)
    noise = coloured_noise(len(t), rng, 0.4)
    band = flattened(spectral_band(noise, lambda at: f_lo * (f_hi / f_lo) ** np.clip(at / dur, 0, 1), width))
    envelope = (t / dur) ** power
    return fades(band * envelope, 0.01, end_fade), dur - end_fade


def tone(rng, dur, hz, harmonic, fade):
    t = times(dur)
    return fades(np.sin(2 * np.pi * hz * t) + harmonic * np.sin(4 * np.pi * hz * t), fade, fade), 0.0


GENERATORS = {"whoosh": whoosh, "swell": swell, "impact": impact, "pop": pop, "tick": tick, "riser": riser, "tone": tone}


def render(preset_name, seed, variant):
    preset = PRESETS[preset_name]
    index = sorted(PRESETS).index(preset_name)
    rng = np.random.default_rng([seed, index, variant])
    audio, anchor = GENERATORS[preset["kind"]](rng, **preset["params"])
    audio = audio * 10 ** (PEAK_DBFS / 20) / (np.max(np.abs(audio)) + 1e-12)
    return audio.astype(np.float64), anchor


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Generate a seeded, licence-free SFX kit (whooshes, impacts, pops, ticks, risers, tones) as 48 kHz 24-bit WAVs plus a manifest that sfx_cues.py and credits.py read.")
    parser.add_argument("--out-dir", required=True, help="kit folder; files go to <category>/<preset>-NN.wav and the manifest to manifest.json inside it")
    parser.add_argument("--seed", type=int, default=1, help="same seed, same files, byte for byte")
    parser.add_argument("--preset", action="append", choices=sorted(PRESETS), help="only these presets (repeatable, default all)")
    parser.add_argument("--variants", type=int, help="variants per preset (default: the preset's own count)")
    parser.add_argument("--list", action="store_true", help="print the presets and their parameters, then exit")
    args = parser.parse_args()

    if args.list:
        for name in sorted(PRESETS):
            preset = PRESETS[name]
            print(f"{name:18s} {preset['category']:10s} align {preset['align']:5s} x{preset['variants']}  {json.dumps(preset['params'])}")
        return
    out_dir = Path(args.out_dir)
    entries = []
    for name in args.preset or sorted(PRESETS):
        preset = PRESETS[name]
        for variant in range(args.variants or preset["variants"]):
            audio, anchor = render(name, args.seed, variant)
            relative = Path(preset["category"]) / f"{name}-{variant + 1:02d}.wav"
            path = out_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            soundfile.write(str(path), audio, SAMPLE_RATE, subtype="PCM_24", format="WAV")
            entries.append({
                "file": relative.as_posix(),
                "category": preset["category"],
                "title": f"{name} {variant + 1}",
                "creator": "generated",
                "license": "original",
                "attribution_required": False,
                "align": preset["align"],
                "anchor_s": round(anchor, 4),
                "duration_s": round(len(audio) / SAMPLE_RATE, 4),
                "sha256": sha256(path),
                "params": {"preset": name, "seed": args.seed, "variant": variant, **preset["params"]},
            })
            print(f"{relative.as_posix():34s} {len(audio) / SAMPLE_RATE:5.2f}s anchor {anchor:.3f}s")
    manifest = {"kind": "sfx", "root": ".", "generator": "sfx_synth.py", "seed": args.seed, "files": entries}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(entries)} files, manifest {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
