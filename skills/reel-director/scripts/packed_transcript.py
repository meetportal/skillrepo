import argparse
import json
import sys
from pathlib import Path

SENTENCE_END = (".", "?", "!")


def words_from(data):
    if isinstance(data, list):
        return {"reel": [{"text": w["text"].strip(), "start": w["startMs"] / 1000, "end": w["endMs"] / 1000} for w in data]}
    if "clips" in data:
        return {
            name: [{"text": w.get("word", w.get("text", "")).strip(), "start": float(w["start"]), "end": float(w["end"])} for w in clip.get("words", [])]
            for name, clip in data["clips"].items()
        }
    if "words" in data:
        return {"reel": [{"text": w["text"].strip(), "start": float(w["start"]), "end": float(w["end"])} for w in data["words"]]}
    raise SystemExit("unknown format: expected Caption[] (words.out.json), {clips: {...}} (transcript.json) or {words: [...]} (cues.json)")


def phrases(words, gap, max_words):
    out, current = [], []
    for word in words:
        if not word["text"]:
            continue
        if current:
            pause = word["start"] - current[-1]["end"]
            if pause >= gap or current[-1]["text"].endswith(SENTENCE_END) or len(current) >= max_words:
                out.append((current, pause))
                current = []
        current.append(word)
    if current:
        out.append((current, None))
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Print a packed transcript: one line per phrase as [start-end] text, with the pause that follows. "
                    "About a tenth of the tokens of the word JSON, and enough to plan beats and cuts.")
    parser.add_argument("words", help="words.out.json (Caption[]), ingest transcript.json or cues.json")
    parser.add_argument("--gap", type=float, default=0.5, help="start a new line at a pause of at least this many seconds (default 0.5)")
    parser.add_argument("--max-words", type=int, default=20, help="start a new line after this many words (default 20)")
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args()

    groups = words_from(json.loads(Path(args.words).read_text()))
    lines = []
    for name, words in groups.items():
        if len(groups) > 1:
            lines.append(f"## {name}")
        for chunk, pause in phrases(words, args.gap, args.max_words):
            text = " ".join(w["text"] for w in chunk)
            tail = f"  (+{pause:.2f}s)" if pause is not None and pause >= 0.15 else ""
            lines.append(f"[{chunk[0]['start']:.2f}-{chunk[-1]['end']:.2f}] {text}{tail}")
    output = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(output)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
