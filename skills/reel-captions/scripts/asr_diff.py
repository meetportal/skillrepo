import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

SAMPLE_RATE = 16000


def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def decode_audio(media):
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(media), "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(media, model_name, prompt):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        decode_audio(media), language="en", word_timestamps=True, initial_prompt=prompt or None, vad_filter=False, beam_size=5,
    )
    return [{"text": word.word.strip(), "start": round(word.start, 3), "end": round(word.end, 3)} for segment in segments for word in segment.words]


def expand(words, text_key, start_key, scale):
    tokens = []
    for word in words:
        for part in word[text_key].split():
            if normalize(part):
                tokens.append({"norm": normalize(part), "text": part, "start": word[start_key] * scale})
    return tokens


def equivalent_forms(dictionary_path):
    if not dictionary_path:
        return {}
    phrases = json.loads(Path(dictionary_path).read_text()).get("phrases", {})
    return {normalize(source): normalize(target) for source, target in phrases.items() if len(source.split()) == 1 and len(target.split()) == 1}


def diff(intended, heard, equivalents):
    heard_norm = [equivalents.get(token["norm"], token["norm"]) for token in heard]
    intended_norm = [token["norm"] for token in intended]
    matcher = difflib.SequenceMatcher(a=intended_norm, b=heard_norm, autojunk=False)
    problems = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        problems.append({
            "type": {"delete": "missing", "insert": "extra", "replace": "changed"}[tag],
            "intended": " ".join(t["text"] for t in intended[i1:i2]),
            "heard": " ".join(t["text"] for t in heard[j1:j2]),
            "at": round((intended[i1]["start"] if i1 < len(intended) else heard[j1]["start"]), 2),
        })
    return problems, matcher.ratio()


def main():
    parser = argparse.ArgumentParser(description="Re-transcribe delivered audio and diff it against the intended caption words (missing = clipped, extra = ghost).")
    parser.add_argument("--intended", required=True, help="Caption[] JSON (words.out.json)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--media", help="audio or video file to transcribe")
    source.add_argument("--heard", help="existing transcript JSON list [{text,start,end}] in seconds")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--prompt", default="", help="initial prompt with brand terms")
    parser.add_argument("--dictionary", help="caption dictionary; single-word entries count as equal")
    parser.add_argument("--allow", default="", help="comma list of 'intended>heard' pairs that are intentional text edits")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    intended = expand(json.loads(Path(args.intended).read_text()), "text", "startMs", 0.001)
    heard_words = json.loads(Path(args.heard).read_text()) if args.heard else transcribe(args.media, args.model, args.prompt)
    heard = expand(heard_words, "text", "start", 1.0)
    problems, ratio = diff(intended, heard, equivalent_forms(args.dictionary))
    allowed = {tuple(normalize(side) for side in pair.split(">")) for pair in args.allow.split(",") if ">" in pair}
    for problem in problems:
        problem["allowed"] = (normalize(problem["intended"]), normalize(problem["heard"])) in allowed
    blocking = [problem for problem in problems if not problem["allowed"]]
    report = {"similarity": round(ratio, 4), "problems": problems, "blocking": len(blocking), "heard": heard_words}
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    for problem in problems:
        flag = "ok " if problem["allowed"] else "FIX"
        print(f"{flag} {problem['at']:7.2f}s {problem['type']:8s} intended={problem['intended']!r} heard={problem['heard']!r}")
    print(f"similarity {ratio:.3f}, {len(blocking)} blocking differences, report {args.out}")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
