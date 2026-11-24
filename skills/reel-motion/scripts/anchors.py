import json
import re
import sys
from pathlib import Path


class AnchorError(ValueError):
    pass


def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_json(path):
    return json.loads(Path(path).read_text())


def find_phrase(words, phrase, occurrence):
    target = normalize(phrase)
    if not target:
        raise AnchorError(f"empty anchor phrase {phrase!r}")
    tokens = [normalize(word["text"]) for word in words]
    seen = 0
    for index, token in enumerate(tokens):
        if not token or not target.startswith(token):
            continue
        joined = ""
        for last in range(index, len(tokens)):
            joined += tokens[last]
            if joined == target:
                seen += 1
                if seen == occurrence:
                    return words[index], words[last]
                break
            if not target.startswith(joined):
                break
    raise AnchorError(f"phrase {phrase!r} occurrence {occurrence} not found ({seen} found)")


def resolve_anchor(anchor, cues):
    offset = float(anchor.get("offset", 0.0))
    if "@word" in anchor:
        first, last = find_phrase(cues["words"], anchor["@word"], int(anchor.get("n", 1)))
        edge = anchor.get("edge", "start")
        if edge not in ("start", "end"):
            raise AnchorError(f"edge must be start or end, got {edge!r}")
        base = first["start"] if edge == "start" else last["end"]
    elif "@cut" in anchor:
        index = int(anchor["@cut"])
        cuts = cues["cuts"]
        if not 1 <= index <= len(cuts):
            raise AnchorError(f"cut {index} out of range 1..{len(cuts)}")
        base = cuts[index - 1]
    elif "@end" in anchor:
        base = cues["duration"]
    else:
        raise AnchorError(f"unknown anchor {anchor!r}")
    return round(max(0.0, base + offset), 3)


def is_anchor(value):
    return isinstance(value, dict) and any(key in value for key in ("@word", "@cut", "@end"))


def resolve_tree(value, cues):
    if is_anchor(value):
        return resolve_anchor(value, cues)
    if isinstance(value, dict):
        return {key: resolve_tree(item, cues) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_tree(item, cues) for item in value]
    return value


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Resolve @word/@cut/@end time anchors in any JSON file against cues.json.")
    parser.add_argument("--cues", required=True, help="cues.json on the output timeline")
    parser.add_argument("--input", required=True, help="JSON with anchors")
    parser.add_argument("--out", required=True, help="resolved JSON output path")
    args = parser.parse_args()
    try:
        resolved = resolve_tree(load_json(args.input), load_json(args.cues))
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    Path(args.out).write_text(json.dumps(resolved, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
