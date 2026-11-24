import argparse
import difflib
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import audio_segments, bare, load_json, write_json

SAMPLE_RATE = 16000


def decode(path, sample_rate):
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
        check=True, capture_output=True,
    )
    return np.frombuffer(result.stdout, np.float32).copy()


def chunk_bounds(total, splice_times, max_chunk):
    bounds, start = [], 0.0
    candidates = sorted(t for t in splice_times if 0 < t < total)
    while total - start > max_chunk:
        inside = [t for t in candidates if start + 2.0 < t <= start + max_chunk]
        stop = inside[-1] if inside else start + max_chunk
        bounds.append((start, stop))
        start = stop
    bounds.append((start, total))
    return bounds


def transcribe(audio, model_name, prompt, threads, bounds):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    words = []
    pad = np.zeros(SAMPLE_RATE // 2, np.float32)
    for start, end in bounds:
        chunk = np.concatenate([pad, audio[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)], pad])
        segments, _ = model.transcribe(chunk, language="en", beam_size=5, word_timestamps=True, initial_prompt=prompt or None, condition_on_previous_text=False, vad_filter=False)
        for segment in segments:
            for w in segment.words or []:
                words.append({"word": w.word.strip(), "start": round(w.start - 0.5 + start, 3), "end": round(w.end - 0.5 + start, 3)})
    return words


def alias_pairs(corrections):
    pairs = set()
    for correction in corrections:
        if "match" in correction and correction.get("text"):
            left = " ".join(bare(t) for t in correction["match"].split())
            right = " ".join(bare(t) for t in correction["text"].split())
            pairs.add((left, right))
            pairs.add((right, left))
    return pairs


def canonical(text):
    return text.replace("'ll", " will").replace("n't", " not").replace(" ", "")


def splice_report(edl, audio48, threshold_db):
    fps = edl["fps"]
    rows = []
    segments = audio_segments(edl)
    window = int(0.02 * 48000)
    for seg in segments[1:]:
        at = seg["out_start"] / fps
        center = int(round(at * 48000))
        before = audio48[max(0, center - window - int(0.03 * 48000)):center - int(0.03 * 48000)]
        after = audio48[center + int(0.03 * 48000):center + int(0.03 * 48000) + window]
        level = lambda chunk: float(20 * np.log10(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)) + 1e-10)) if len(chunk) else -120.0
        rows.append({"at": round(at, 3), "before_db": round(level(before), 1), "after_db": round(level(after), 1)})
    for row in rows:
        row["ok"] = row["before_db"] < threshold_db and row["after_db"] < threshold_db
    return rows


def main():
    parser = argparse.ArgumentParser(description="Re-transcribe the cut dialogue and diff it against the intended words; check that no splice lands on speech energy.")
    parser.add_argument("--audio", required=True, help="voice_cut.wav (or any render of the cut audio)")
    parser.add_argument("--words", required=True, help="words.out.json (Remotion Caption[])")
    parser.add_argument("--edl", help="edl.json, enables the splice energy check")
    parser.add_argument("--corrections", help="corrections file: replacements are accepted in both directions")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-chunk", type=float, default=20.0, help="transcribe in chunks of at most this many seconds, split at audio splices (whisper invents words at its own 30 s window edges)")
    parser.add_argument("--splice-threshold-db", type=float, default=-40.0, help="RMS of the 20 ms just outside each 30 ms splice fade must stay below this")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    expected = load_json(args.words)
    corrections = load_json(args.corrections) if args.corrections else []
    if isinstance(corrections, dict):
        corrections = corrections.get("corrections", [])
    aliases = alias_pairs(corrections)
    audio = decode(args.audio, SAMPLE_RATE)
    total = len(audio) / SAMPLE_RATE
    splices = []
    if args.edl:
        edl = load_json(args.edl)
        splices = [seg["out_start"] / edl["fps"] for seg in audio_segments(edl)[1:]]
    bounds = chunk_bounds(total, splices, args.max_chunk)
    heard = transcribe(audio, args.model, args.prompt, args.threads, bounds)
    left = [bare(w["text"]) for w in expected]
    right = [bare(w["word"]) for w in heard]
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    problems, accepted, onset_errors = [], [], []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(a1 - a0):
                onset_errors.append(heard[b0 + offset]["start"] - expected[a0 + offset]["startMs"] / 1000)
            continue
        want, got = " ".join(left[a0:a1]), " ".join(right[b0:b1])
        entry = {"type": tag, "expected": want, "heard": got, "at": round(expected[a0]["startMs"] / 1000 if a0 < len(expected) else heard[b0]["start"], 3)}
        if (want, got) in aliases or canonical(want) == canonical(got):
            accepted.append(entry)
        else:
            problems.append(entry)
    report = {
        "expected_words": len(expected),
        "heard_words": len(heard),
        "chunks": [[round(a, 3), round(b, 3)] for a, b in bounds],
        "heard_text": " ".join(w["word"] for w in heard),
        "problems": problems,
        "accepted_variants": accepted,
        "onset_error_median": round(float(np.median(onset_errors)), 3) if onset_errors else None,
        "onset_error_p95_abs": round(float(np.percentile(np.abs(onset_errors), 95)), 3) if onset_errors else None,
    }
    if args.edl:
        report["splices"] = splice_report(load_json(args.edl), decode(args.audio, 48000), args.splice_threshold_db)
    report["pass"] = not problems and all(row["ok"] for row in report.get("splices", []))
    write_json(args.out, report)
    print(f"heard: {report['heard_text']}")
    for entry in accepted:
        print(f"accepted {entry['type']} @{entry['at']}: expected '{entry['expected']}' heard '{entry['heard']}'")
    for entry in problems:
        print(f"PROBLEM {entry['type']} @{entry['at']}: expected '{entry['expected']}' heard '{entry['heard']}'")
    for row in report.get("splices", []):
        print(f"splice {row['at']:7.3f}s before {row['before_db']:6.1f} dB after {row['after_db']:6.1f} dB {'ok' if row['ok'] else 'SPEECH AT SPLICE'}")
    print(f"onset error median {report['onset_error_median']} p95 {report['onset_error_p95_abs']}; {'PASS' if report['pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
