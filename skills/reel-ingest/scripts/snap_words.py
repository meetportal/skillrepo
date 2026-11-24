import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import decode_audio, hysteresis_segments, rms_envelope_db

SAMPLE_RATE = 16000
DEFAULT_HALLUCINATIONS = [
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "subscribe to",
    "like and subscribe",
    "see you in the next",
    "www.",
    ".co.uk",
    "subtitles by",
    "amara.org",
]


def normalise(token):
    return re.sub(r"[^a-z0-9']", "", token.lower())


def is_hallucination(text, phrases):
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_to_segments(words, segments, phantom_margin):
    grouped = [[] for _ in segments]
    phantoms = []
    for word in words:
        best, best_overlap = None, 0.0
        for index, (start, end) in enumerate(segments):
            amount = overlap(word["start"], word["end"], start, end)
            if amount > best_overlap:
                best, best_overlap = index, amount
        if best is None:
            distances = [min(abs(word["start"] - end), abs(word["end"] - start)) for start, end in segments]
            nearest = int(np.argmin(distances)) if distances else None
            if nearest is None or distances[nearest] > phantom_margin:
                phantoms.append(word)
                continue
            best = nearest
        grouped[best].append(dict(word))
    return grouped, phantoms


def resegment(model, audio, segments, prompt, language, beam_size, cache, cache_prefix):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from transcribe import transcribe_array

    grouped = []
    pad = int(0.5 * SAMPLE_RATE)
    for start, end in segments:
        key = f"{cache_prefix}|{start:.2f}|{end:.2f}|{prompt}"
        if key in cache:
            grouped.append([dict(word) for word in cache[key]])
            continue
        chunk_start = max(0.0, start - 0.08)
        chunk_end = min(len(audio) / SAMPLE_RATE, end + 0.08)
        chunk = audio[int(chunk_start * SAMPLE_RATE):int(chunk_end * SAMPLE_RATE)]
        padded = np.concatenate([np.zeros(pad, np.float32), chunk, np.zeros(pad, np.float32)])
        _, words = transcribe_array(model, padded, prompt, language, beam_size)
        for word in words:
            word["start"] = round(word["start"] - 0.5 + chunk_start, 3)
            word["end"] = round(word["end"] - 0.5 + chunk_start, 3)
        cache[key] = [dict(word) for word in words]
        grouped.append(words)
    return grouped


def borrow_context_text(grouped, context_words):
    flat = [word for group in grouped for word in group]
    source = [normalise(word["word"]) for word in flat]
    target = [normalise(word["word"]) for word in context_words]
    matcher = difflib.SequenceMatcher(a=source, b=target, autojunk=False)
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and a_end - a_start == b_end - b_start):
            for offset in range(a_end - a_start):
                flat[a_start + offset]["word"] = context_words[b_start + offset]["word"]
                flat[a_start + offset]["context_prob"] = context_words[b_start + offset]["prob"]
                flat[a_start + offset]["in_context"] = True
    for previous, current in zip(flat[:-1], flat[1:]):
        if normalise(previous["word"]) == normalise(current["word"]):
            for word in (previous, current):
                if not word.get("in_context"):
                    word["duplicate"] = True
                    break
    for group in grouped:
        group[:] = [word for word in group if not word.get("duplicate")]


def snap_group(words, segment, max_lead):
    start, end = segment
    trailing = []
    first_start = words[0]["start"]
    for index, word in enumerate(words):
        word["start"] = max(word["start"], start)
        word["end"] = min(word["end"], end)
    if first_start - start <= max_lead:
        words[0]["start"] = start
    else:
        trailing.append({"start": start, "end": round(words[0]["start"], 3), "note": "voiced energy before the first word (breath or noise)"})
    words[-1]["end"] = end
    for index in range(1, len(words)):
        if words[index]["start"] < words[index - 1]["end"]:
            words[index]["start"] = words[index - 1]["end"]
        if 0 < words[index]["start"] - words[index - 1]["end"] < 0.06:
            words[index - 1]["end"] = words[index]["start"]
    for word in words:
        if word["end"] < word["start"]:
            word["end"] = word["start"]
        word["start"], word["end"] = round(word["start"], 3), round(word["end"], 3)
    return words, trailing


def process_clip(name, clip, args, model, cache):
    audio = decode_audio(clip["file"], sample_rate=SAMPLE_RATE, channels=1)
    envelope = rms_envelope_db(audio, SAMPLE_RATE)
    floor = float(np.percentile(envelope, 5))
    segments = hysteresis_segments(envelope, floor + args.on_db, floor + args.off_db, min_gap_s=args.min_gap, strong_db=floor + args.strong_db)
    if model is not None:
        grouped = resegment(model, audio, segments, args.prompt, args.language, args.beam_size, cache, f"{args.model}|{name}")
        borrow_context_text(grouped, clip["words"])
        phantoms = []
    else:
        grouped, phantoms = assign_to_segments(clip["words"], segments, args.phantom_margin)
    words, non_speech = [], []
    for index, (segment, group) in enumerate(zip(segments, grouped)):
        text = " ".join(word["word"] for word in group)
        if not group:
            non_speech.append({"start": segment[0], "end": segment[1], "note": "voiced energy with no words"})
            continue
        if is_hallucination(text, args.hallucination):
            non_speech.append({"start": segment[0], "end": segment[1], "note": f"hallucination stripped: {text}"})
            continue
        peak = float(np.max(envelope[int(segment[0] * 100):max(int(segment[0] * 100) + 1, int(segment[1] * 100))]))
        if model is not None and peak < floor + args.strong_db:
            confirmed = [word for word in group if word.get("in_context")]
            if not confirmed:
                non_speech.append({"start": segment[0], "end": segment[1], "note": f"weak energy (peak {peak - floor:.0f} dB over floor), words not in the full-clip pass stripped: {text}"})
                continue
            group = confirmed
        snapped, trailing = snap_group(group, segment, args.max_lead)
        non_speech.extend(trailing)
        for word in snapped:
            words.append({"word": word["word"], "start": word["start"], "end": word["end"], "prob": word["prob"], "segment": index})
    pauses = []
    for index in range(1, len(words)):
        gap = round(words[index]["start"] - words[index - 1]["end"], 3)
        if gap > 0.25:
            pauses.append({"after": words[index - 1]["word"], "before": words[index]["word"], "start": words[index - 1]["end"], "end": words[index]["start"], "dur": gap})
    return {
        "file": clip["file"],
        "duration": clip.get("duration"),
        "noise_floor_dbfs": round(floor, 1),
        "text": " ".join(word["word"] for word in words),
        "first_word_start": words[0]["start"] if words else None,
        "last_word_end": words[-1]["end"] if words else None,
        "voiced_segments": segments,
        "pauses_gt_250ms": pauses,
        "non_speech_events": non_speech,
        "phantom_words": phantoms,
        "words": words,
    }


def main():
    parser = argparse.ArgumentParser(description="Snap word edges to the RMS speech envelope and strip phantom or hallucinated words.")
    parser.add_argument("transcript", help="output of transcribe.py")
    parser.add_argument("--out", required=True)
    parser.add_argument("--resegment", action="store_true", help="re-transcribe every voiced segment in isolation (exact segment membership)")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--cache", help="JSON file caching per-segment transcriptions between runs")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--language", default="en")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--prompt", default=None, help="defaults to the prompt stored in the transcript")
    parser.add_argument("--on-db", type=float, default=18.0, help="segment opens at noise floor + this")
    parser.add_argument("--off-db", type=float, default=10.0, help="segment closes at noise floor + this")
    parser.add_argument("--min-gap", type=float, default=0.15, help="merge voiced segments separated by less than this")
    parser.add_argument("--strong-db", type=float, default=24.0, help="runs peaking under noise floor + this (hum, breaths) are never merged into speech")
    parser.add_argument("--max-lead", type=float, default=0.25, help="snap the first word to the segment onset only when whisper's onset is within this")
    parser.add_argument("--phantom-margin", type=float, default=0.10, help="drop words this far from any voiced energy")
    parser.add_argument("--hallucination", action="append", default=list(DEFAULT_HALLUCINATIONS), help="phrase that marks a hallucinated segment (repeatable)")
    parser.add_argument("--frame-metrics", help="frame_metrics.py output; copies blinks and soft windows per clip")
    args = parser.parse_args()
    source = json.loads(Path(args.transcript).read_text())
    if args.prompt is None:
        args.prompt = source.get("initial_prompt", "")
    model = None
    if args.resegment:
        from transcribe import load_model

        model = load_model(args.model, args.compute_type, args.threads)
    metrics = json.loads(Path(args.frame_metrics).read_text())["clips"] if args.frame_metrics else {}
    cache_path = Path(args.cache) if args.cache else None
    cache = json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else {}
    clips = {}
    for name, clip in source["clips"].items():
        clips[name] = process_clip(name, clip, args, model, cache)
        if cache_path:
            cache_path.write_text(json.dumps(cache))
        if name in metrics:
            clips[name]["blinks"] = metrics[name]["blinks"]
            clips[name]["soft"] = metrics[name]["soft"]
        print(f"{name}: {clips[name]['first_word_start']}-{clips[name]['last_word_end']} {clips[name]['text']}", flush=True)
        for event in clips[name]["non_speech_events"]:
            print(f"  non-speech {event['start']}-{event['end']}: {event['note']}")
        for word in clips[name]["phantom_words"]:
            print(f"  phantom {word['word']} {word['start']}-{word['end']}")
    report = {
        "version": 2,
        "method": f"faster-whisper {source.get('model')} words; RMS envelope 10 ms hop, floor p5, on +{args.on_db} dB, off +{args.off_db} dB, gaps < {args.min_gap} s merged; first and last word of each voiced segment snapped to the energy edge{'; segments re-transcribed in isolation' if args.resegment else ''}",
        "clips": clips,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
