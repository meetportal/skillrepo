import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

SENTENCE = "Your domain yourbrand.com lands in spam because nobody set up SPF, DKIM and DMARC. Here is the fix."
PAUSE_AFTER = {"spam": 0.35, "DMARC.": 0.45}
FACE = {"cx": 540, "cy": 760, "w": 360, "h": 460}
CLIPS = ["CLIP_A.MP4", "CLIP_B.MP4"]


def low_priority():
    prefix = []
    if shutil.which("nice"):
        prefix += ["nice", "-n", "19"]
    if shutil.which("ionice"):
        prefix += ["ionice", "-c", "3"]
    return prefix


def mock_words(start, word_sec, gap):
    words, t = [], start
    for text in SENTENCE.split():
        words.append({"text": text, "start": round(t, 3), "end": round(t + word_sec, 3)})
        t += word_sec + gap + PAUSE_AFTER.get(text, 0.0)
    return words


def captions(words):
    out = []
    for w in words:
        start_ms, end_ms = int(round(w["start"] * 1000)), int(round(w["end"] * 1000))
        out.append({"text": " " + w["text"], "startMs": start_ms, "endMs": end_ms, "timestampMs": (start_ms + end_ms) // 2, "confidence": None})
    return out


def mock_voice(words, duration, rate=48000, seed=7):
    rng = np.random.default_rng(seed)
    total = int(round(duration * rate))
    audio = rng.normal(0, 10 ** (-62 / 20), total)
    spectrum = np.fft.rfft(rng.normal(0, 1, total))
    freqs = np.fft.rfftfreq(total, 1 / rate)
    shaped = np.where((freqs > 120) & (freqs < 5000), 1 / np.sqrt(np.maximum(freqs, 1)), 0)
    speech = np.fft.irfft(spectrum * shaped, total)
    speech /= np.sqrt(np.mean(speech ** 2))
    for w in words:
        a, b = int(w["start"] * rate), min(total, int(w["end"] * rate))
        t = np.arange(b - a) / rate
        envelope = np.sin(np.pi * np.clip(t / max(t[-1], 1e-3), 0, 1)) ** 0.6 * (0.75 + 0.25 * np.sin(2 * np.pi * 5 * t))
        audio[a:b] += speech[a:b] * envelope * 10 ** (-20 / 20)
    return audio.astype(np.float32), rate


def frames(t, fps):
    return int(round(t * fps))


def main():
    parser = argparse.ArgumentParser(
        description="Build the synthetic mock reel used to smoke-test the pipeline without footage: a grey 1080x1920 A-roll with a "
                    "skin-tone face box and moving grain, edl.json, a synthetic voice_cut.wav (shaped noise on the word times over room tone), "
                    "words.retimed.json and words.out.json for one mock sentence, and "
                    "cues.json with cuts, face boxes, keywords and optional cover windows. Never overwrites unless --force.")
    parser.add_argument("work", help="reel work folder (created when missing)")
    parser.add_argument("--seconds", type=float, default=12.0, help="A-roll length (default 12)")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--cuts", default="3.2,6.4,9.0", help="comma list of cut times in seconds (default 3.2,6.4,9.0)")
    parser.add_argument("--cover", action="append", default=[], help="start:end cover window to add to cues.json (repeatable)")
    parser.add_argument("--first-word", type=float, default=0.2, help="first word onset (default 0.2)")
    parser.add_argument("--word-sec", type=float, default=0.24, help="length of each mock word (default 0.24)")
    parser.add_argument("--word-gap", type=float, default=0.06, help="gap between words inside a phrase (default 0.06; with the two phrase pauses about 3 words/s)")
    parser.add_argument("--force", action="store_true", help="replace existing mock files")
    args = parser.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    names = ["edl.json", "aroll.mp4", "voice_cut.wav", "words.retimed.json", "words.out.json", "cues.json"]
    existing = [n for n in names if (work / n).exists()]
    if existing and not args.force:
        raise SystemExit(f"{work} already has {existing}; pass --force to replace them")

    fps = args.fps
    total = frames(args.seconds, fps)
    cut_frames = sorted({frames(float(t), fps) for t in args.cuts.split(",") if t.strip() and 0 < frames(float(t), fps) < total})
    bounds = [0, *cut_frames, total]
    segments, ranges = [], []
    for index, (a, b) in enumerate(zip(bounds, bounds[1:])):
        clip = CLIPS[index % len(CLIPS)]
        src_in = 1.0 + a / fps
        segments.append({"index": index, "clip": clip, "start": round(a / fps, 3), "end": round(b / fps, 3),
                         "src_in": round(src_in, 3), "src_out": round(src_in + (b - a) / fps, 3), "face": dict(FACE)})
        ranges.append({"clip": f"/path/to/raw/{clip}", "v_in": round(src_in, 3), "v_out": round(src_in + (b - a) / fps, 3),
                       "a_in": round(src_in, 3), "a_out": round(src_in + (b - a) / fps, 3), "beat": f"mock-{index}", "quote": ""})
    duration = round(total / fps, 3)
    (work / "edl.json").write_text(json.dumps({"fps": fps, "ranges": ranges, "duration": duration}, indent=1) + "\n")

    video = f"color=c=0x5a6070:s=1080x1920:r={fps}:d={args.seconds}"
    command = [*low_priority(), "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", video,
               "-vf", "drawbox=x=360:y=530:w=360:h=460:color=0xC89070@1:t=fill,noise=alls=6:allf=t",
               "-frames:v", str(total), "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
               "-color_primaries", "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", "-crf", "14", "-g", str(fps),
               str(work / "aroll.mp4")]
    subprocess.run(command, check=True)

    words = [w for w in mock_words(args.first_word, args.word_sec, args.word_gap) if w["end"] <= duration]
    for name in ("words.retimed.json", "words.out.json"):
        (work / name).write_text(json.dumps(captions(words), indent=1) + "\n")

    audio, rate = mock_voice(words, duration)
    subprocess.run([*low_priority(), "ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s24le", str(work / "voice_cut.wav")], input=audio.tobytes(), check=True)

    covers = []
    for entry in args.cover:
        start, end = (float(x) for x in entry.split(":"))
        covers.append({"start": start, "end": end, "reason": "mock cover window"})
    keywords = {w["text"].strip(".,"): w["start"] for w in words if w["text"].strip(".,") in ("SPF", "DMARC")}
    cues = {
        "duration": duration,
        "fps": fps,
        "segments": segments,
        "cuts": [round(f / fps, 3) for f in cut_frames],
        "audio_splices": [round(f / fps, 3) for f in cut_frames],
        "words": [{"i": i, "text": w["text"], "start": w["start"], "end": w["end"]} for i, w in enumerate(words)],
        "keywords": keywords,
        "cover": covers,
        "needs_punch": [],
    }
    (work / "cues.json").write_text(json.dumps(cues, indent=1) + "\n")
    rate = len(words) / (words[-1]["end"] - words[0]["start"])
    print(f"mock reel in {work}: {duration:.2f}s at {fps} fps, cuts {cues['cuts']}, {len(words)} words "
          f"{words[0]['start']:.2f}-{words[-1]['end']:.2f}s ({rate:.2f} words/s), cover {covers}")


if __name__ == "__main__":
    main()
