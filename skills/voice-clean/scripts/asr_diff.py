import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicelib import decode

ASR_RATE = 16000


def normalise(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())


def transcribe(model, path, language, prompt):
    audio = decode(path, sample_rate=ASR_RATE).astype("float32")
    segments, _ = model.transcribe(
        audio, language=language, beam_size=5, temperature=0.0, word_timestamps=True,
        condition_on_previous_text=False, vad_filter=False, initial_prompt=prompt,
    )
    words = []
    for segment in segments:
        for word in segment.words or []:
            token = normalise(word.word)
            if token:
                words.append({"word": token, "start": round(word.start, 2), "end": round(word.end, 2), "p": round(word.probability, 3)})
    return words


def main():
    parser = argparse.ArgumentParser(description="Transcribe two versions of the same dialogue and list words missing from or added to the second.")
    parser.add_argument("--reference", required=True, help="unprocessed audio, for example the raw cut")
    parser.add_argument("--candidate", required=True, help="processed audio on the same timeline")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="en")
    parser.add_argument("--prompt", help="initial prompt with names and jargon, used for both passes")
    parser.add_argument("--drop-limit", type=float, default=0.15, help="list matched words whose confidence falls by more than this in the candidate")
    parser.add_argument("--threads", type=int, default=2, help="CPU threads for faster-whisper (default 2, for a shared machine)")
    parser.add_argument("--out", help="write the json report here")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type=args.compute_type, cpu_threads=args.threads)
    reference = transcribe(model, args.reference, args.language, args.prompt)
    candidate = transcribe(model, args.candidate, args.language, args.prompt)
    matcher = difflib.SequenceMatcher(a=[w["word"] for w in reference], b=[w["word"] for w in candidate], autojunk=False)
    changes = []
    confidence = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            for ref_word, cand_word in zip(reference[a0:a1], candidate[b0:b1]):
                confidence.append({"word": ref_word["word"], "t": ref_word["start"], "reference_p": ref_word["p"], "candidate_p": cand_word["p"], "drop": round(ref_word["p"] - cand_word["p"], 3)})
            continue
        changes.append({
            "type": tag,
            "reference": [w["word"] for w in reference[a0:a1]],
            "candidate": [w["word"] for w in candidate[b0:b1]],
            "t": (reference[a0] if a0 < len(reference) else candidate[b0])["start"] if (a0 < len(reference) or b0 < len(candidate)) else None,
        })
    missing = sum(len(c["reference"]) for c in changes if c["type"] in ("delete", "replace"))
    extra = sum(len(c["candidate"]) for c in changes if c["type"] in ("insert", "replace"))
    report = {
        "model": args.model,
        "reference_words": len(reference),
        "candidate_words": len(candidate),
        "match_ratio": round(matcher.ratio(), 4),
        "missing_or_changed": missing,
        "extra_or_changed": extra,
        "changes": changes,
        "mean_p": {"reference": round(sum(w["p"] for w in reference) / max(len(reference), 1), 3), "candidate": round(sum(w["p"] for w in candidate) / max(len(candidate), 1), 3)},
        "matched_confidence": confidence,
        "confidence_drops": sorted((item for item in confidence if item["drop"] > args.drop_limit), key=lambda item: -item["drop"]),
        "reference_text": " ".join(w["word"] for w in reference),
        "candidate_text": " ".join(w["word"] for w in candidate),
    }
    print(f"reference {len(reference)} words, candidate {len(candidate)} words, match {report['match_ratio']}")
    print(f"mean word confidence: reference {report['mean_p']['reference']}, candidate {report['mean_p']['candidate']}; drops over {args.drop_limit}: {len(report['confidence_drops'])}")
    for item in report["confidence_drops"]:
        print(f"  confidence {item['word']} at {item['t']} s: {item['reference_p']} -> {item['candidate_p']}")
    for change in changes:
        print(f"  {change['type']:<7} at {change['t']} s: {' '.join(change['reference']) or '-'} -> {' '.join(change['candidate']) or '-'}")
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
