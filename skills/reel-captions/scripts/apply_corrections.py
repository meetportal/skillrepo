import argparse
import json
import re
import sys
from pathlib import Path

WORD_CORE = re.compile(r"^(\W*)(.*?)(\W*)$", re.S)


def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def split_affixes(text):
    match = WORD_CORE.match(text.strip())
    return match.group(1), match.group(2), match.group(3)


def keep_spacing(original, new_text):
    return (" " if original.startswith(" ") else "") + new_text


def apply_edits(words, edits, log):
    by_index = {int(edit["i"]): edit for edit in edits}
    result = []
    for index, word in enumerate(words):
        edit = by_index.get(index)
        if edit is None:
            result.append(dict(word))
        elif edit.get("drop"):
            log.append(f"[{index}] dropped {word['text'].strip()!r}")
        else:
            result.append({**word, "text": keep_spacing(word["text"], edit["text"])})
            log.append(f"[{index}] {word['text'].strip()!r} -> {edit['text']!r}")
    return result


def apply_dictionary(words, phrases, log):
    entries = sorted(
        ((key.split(), value) for key, value in phrases.items()),
        key=lambda item: -len(item[0]),
    )
    result = []
    index = 0
    while index < len(words):
        replaced = False
        for key_words, value in entries:
            span = words[index:index + len(key_words)]
            if len(span) == len(key_words) and all(normalize(w["text"]) == normalize(k) for w, k in zip(span, key_words)):
                lead, _, _ = split_affixes(span[0]["text"])
                _, _, trail = split_affixes(span[-1]["text"])
                value_words = value.split()
                if len(value_words) == len(span):
                    for word, value_word in zip(span, value_words):
                        word_lead, _, word_trail = split_affixes(word["text"])
                        new_text = keep_spacing(word["text"], f"{word_lead}{value_word}{word_trail}")
                        if new_text != word["text"]:
                            log.append(f"{word['text'].strip()!r} -> {new_text.strip()!r}")
                        result.append({**word, "text": new_text})
                else:
                    merged = {**span[0], "endMs": span[-1]["endMs"], "text": keep_spacing(span[0]["text"], f"{lead}{value}{trail}")}
                    log.append(f"{' '.join(w['text'].strip() for w in span)!r} -> {merged['text'].strip()!r}")
                    result.append(merged)
                index += len(span)
                replaced = True
                break
        if not replaced:
            result.append(dict(words[index]))
            index += 1
    return result


def never_show_hits(words, never_show):
    joined = " ".join(normalize(w["text"]) for w in words)
    return [phrase for phrase in never_show if " ".join(normalize(p) for p in phrase.split()) in joined]


def main():
    parser = argparse.ArgumentParser(description="Apply text-only caption corrections (index edits, then a brand dictionary) to a Remotion Caption[] file. Timings never change.")
    parser.add_argument("--words", required=True, help="Caption[] JSON")
    parser.add_argument("--dictionary", help="brand caption dictionary JSON {phrases:{asr:caption}, neverShow:[...]}")
    parser.add_argument("--edits", help="JSON list [{i, text} | {i, drop:true}] keyed by input word index")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    words = json.loads(Path(args.words).read_text())
    log = []
    if args.edits:
        words = apply_edits(words, json.loads(Path(args.edits).read_text()), log)
    never_show = []
    if args.dictionary:
        dictionary = json.loads(Path(args.dictionary).read_text())
        words = apply_dictionary(words, dictionary.get("phrases", {}), log)
        never_show = dictionary.get("neverShow", [])
    Path(args.out).write_text(json.dumps(words, indent=1) + "\n")
    for line in log:
        print(line)
    hits = never_show_hits(words, never_show)
    if hits:
        sys.exit(f"never-show phrases present: {hits}")
    print(f"wrote {args.out} ({len(words)} words, {len(log)} changes)")


if __name__ == "__main__":
    main()
