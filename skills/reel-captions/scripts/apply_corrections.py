import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

EDGE = re.compile(r"^([^\w']*)(.*?)([^\w']*)$", re.S)


def bare(text):
    return re.sub(r"[^a-z0-9']", "", text.lower())


def edges(text):
    match = EDGE.match(text.strip())
    return match.group(1), match.group(3)


def load_rules(path):
    data = json.loads(Path(path).read_text())
    return data.get("corrections", []) if isinstance(data, dict) else data


def replace_span(words, index, size, text):
    span = words[index:index + size]
    lead, _ = edges(span[0]["text"])
    _, trail = edges(span[-1]["text"])
    tokens = text.split()
    if not tokens:
        del words[index:index + size]
        return
    if not edges(tokens[0])[0]:
        tokens[0] = lead + tokens[0]
    if not edges(tokens[-1])[1]:
        tokens[-1] = tokens[-1] + trail
    if len(tokens) == size:
        for word, token in zip(span, tokens):
            word["text"] = " " + token
        return
    start, end = span[0]["startMs"], span[-1]["endMs"]
    step = (end - start) / len(tokens)
    replacement = []
    for number, token in enumerate(tokens):
        a, b = int(round(start + number * step)), int(round(start + (number + 1) * step))
        replacement.append({**span[0], "text": " " + token, "startMs": a, "endMs": b, "timestampMs": int(round((a + b) / 2))})
    words[index:index + size] = replacement


def find_matches(words, tokens):
    size = len(tokens)
    return [i for i in range(len(words) - size + 1) if [bare(w["text"]) for w in words[i:i + size]] == tokens]


def apply_rules(words, rules, source, log):
    for rule in sorted([r for r in rules if "index" in r], key=lambda r: -r["index"]):
        size = rule.get("count", 1)
        before = " ".join(w["text"].strip() for w in words[rule["index"]:rule["index"] + size])
        replace_span(words, rule["index"], size, rule["text"])
        log.append(f"{source} [{rule['index']}] {before!r} -> {rule['text']!r}")
    for rule in [r for r in rules if "match" in r]:
        tokens = [bare(t) for t in rule["match"].split() if bare(t)]
        hits = find_matches(words, tokens)
        if "occurrence" in rule:
            hits = hits[rule["occurrence"] - 1:rule["occurrence"]] if len(hits) >= rule["occurrence"] else []
        if not hits and rule.get("required", False):
            raise SystemExit(f"{source}: required correction did not match: {rule['match']!r}")
        for index in reversed(hits):
            before = " ".join(w["text"].strip() for w in words[index:index + len(tokens)])
            replace_span(words, index, len(tokens), rule["text"])
            after = " ".join(w["text"].strip() for w in words[index:index + len(rule["text"].split())])
            if before != after:
                log.append(f"{source} @{words[index]['startMs'] / 1000 if index < len(words) else -1:.2f}s {before!r} -> {after!r}")


def never_show_hits(words, never_show):
    joined = " " + " ".join(bare(w["text"]) for w in words) + " "
    return [phrase for phrase in never_show if " " + " ".join(bare(p) for p in phrase.split() if bare(p)) + " " in joined]


def main():
    parser = argparse.ArgumentParser(description="The one caption text layer: apply reel corrections, then the brand dictionary, to a Remotion Caption[] file. Timings never change (a span that changes word count is divided evenly).")
    parser.add_argument("--words", required=True, help="words.retimed.json from reel-cut (Caption[] with the spoken text)")
    parser.add_argument("--corrections", help="reel corrections JSON {corrections: [{index, text, count?} | {match, text, occurrence?, required?}]}")
    parser.add_argument("--dictionary", help="brand caption dictionary {phrases: {spoken: caption}, neverShow: [...]}")
    parser.add_argument("--out", required=True, help="words.out.json")
    args = parser.parse_args()
    words = [dict(w) for w in json.loads(Path(args.words).read_text())]
    log = []
    if args.corrections:
        apply_rules(words, load_rules(args.corrections), "correction", log)
    never_show = []
    if args.dictionary:
        dictionary = json.loads(Path(args.dictionary).read_text())
        apply_rules(words, [{"match": k, "text": v} for k, v in sorted(dictionary.get("phrases", {}).items(), key=lambda item: -len(item[0].split()))], "dictionary", log)
        never_show = dictionary.get("neverShow", [])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(words, indent=1) + "\n")
    for line in log:
        print(line)
    hits = never_show_hits(words, never_show)
    if hits:
        raise SystemExit(f"never-show phrases present: {hits}")
    print(f"wrote {args.out} ({len(words)} words, {len(log)} changes)")
    print(" ".join(w["text"].strip() for w in words))


if __name__ == "__main__":
    main()
