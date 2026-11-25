import json
import math
import re
import sys
from pathlib import Path

ANCHOR_KEYS = ("@word", "@keyword", "@cutBefore", "@cutAfter", "@cut", "@end")
REL_KEY = "@rel"
ABSOLUTE_PROP_KEYS = ("three",)
CUT_SNAP_SEC = 0.12


class AnchorError(ValueError):
    pass


def frame_of(seconds, fps):
    return math.floor(seconds * fps + 0.5)


def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_json(path):
    return json.loads(Path(path).read_text())


def warn(message):
    print(f"warning: {message}", file=sys.stderr)


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


def find_keyword(words, keyword, occurrence):
    stem = normalize(keyword)
    if not stem:
        raise AnchorError(f"empty keyword {keyword!r}")
    matches = [word for word in words if normalize(word["text"]).startswith(stem)]
    if len(matches) < occurrence:
        raise AnchorError(f"keyword {keyword!r} occurrence {occurrence} not found ({len(matches)} found)")
    return matches[occurrence - 1]


def cut_before(cuts, time, snap):
    candidates = [cut for cut in cuts if cut <= time + snap]
    if not candidates:
        raise AnchorError(f"no cut at or before {time:.3f}")
    return max(candidates)


def cut_after(cuts, time, snap):
    candidates = [cut for cut in cuts if cut >= time - snap]
    if not candidates:
        raise AnchorError(f"no cut at or after {time:.3f}")
    return min(candidates)


def resolve_anchor(anchor, cues):
    offset = float(anchor.get("offset", 0.0))
    occurrence = int(anchor.get("n", 1))
    snap = float(anchor.get("snap", CUT_SNAP_SEC))
    words = cues["words"]
    if "@word" in anchor:
        first, last = find_phrase(words, anchor["@word"], occurrence)
        edge = anchor.get("edge", "start")
        if edge not in ("start", "end"):
            raise AnchorError(f"edge must be start or end, got {edge!r}")
        base = first["start"] if edge == "start" else last["end"]
    elif "@keyword" in anchor:
        word = find_keyword(words, anchor["@keyword"], occurrence)
        base = word["start"] if anchor.get("edge", "start") == "start" else word["end"]
    elif "@cutBefore" in anchor:
        first, _ = find_phrase(words, anchor["@cutBefore"], occurrence)
        base = cut_before(cues["cuts"], first["start"], snap)
    elif "@cutAfter" in anchor:
        _, last = find_phrase(words, anchor["@cutAfter"], occurrence)
        base = cut_after(cues["cuts"], last["end"], snap)
    elif "@cut" in anchor:
        index = int(anchor["@cut"])
        cuts = cues["cuts"]
        if not 1 <= index <= len(cuts):
            raise AnchorError(f"cut {index} out of range 1..{len(cuts)}")
        warn(f"raw cut index {{'@cut': {index}}} breaks after a re-cut; use {{'@cutBefore': '<word>'}} or {{'@cutAfter': '<word>'}}")
        base = cuts[index - 1]
    elif "@end" in anchor:
        base = cues["duration"]
    else:
        raise AnchorError(f"unknown anchor {anchor!r}")
    return round(max(0.0, base + offset), 3)


def is_anchor(value):
    return isinstance(value, dict) and any(key in value for key in ANCHOR_KEYS)


def is_relative(value):
    return isinstance(value, dict) and REL_KEY in value


def resolve_tree(value, cues, base=None):
    if is_relative(value):
        if base is None:
            raise AnchorError(f"{REL_KEY} is only allowed inside beats[].props: {value!r}")
        inner = value[REL_KEY]
        absolute = resolve_anchor(inner, cues) if is_anchor(inner) else inner
        if not isinstance(absolute, (int, float)):
            raise AnchorError(f"{REL_KEY} needs an anchor or a number of output seconds, got {inner!r}")
        return round(absolute - base, 3)
    if is_anchor(value):
        absolute = resolve_anchor(value, cues)
        return absolute if base is None else round(absolute - base, 3)
    if isinstance(value, dict):
        return {key: resolve_tree(item, cues, base) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_tree(item, cues, base) for item in value]
    return value


def resolve_beat(beat, cues):
    if not isinstance(beat, dict):
        return resolve_tree(beat, cues)
    resolved = {key: resolve_tree(item, cues) for key, item in beat.items() if key != "props"}
    props = beat.get("props")
    if isinstance(props, dict):
        start = resolved.get("from")
        if not isinstance(start, (int, float)):
            raise AnchorError(f"beat {beat.get('id', '?')}: from must resolve to seconds before its props can be made beat-relative")
        resolved["props"] = {
            key: resolve_tree(item, cues) if key in ABSOLUTE_PROP_KEYS else resolve_tree(item, cues, float(start))
            for key, item in props.items()
        }
    elif props is not None:
        resolved["props"] = props
    return resolved


def resolve_document(document, cues):
    if not isinstance(document, dict) or not isinstance(document.get("beats"), list):
        return resolve_tree(document, cues)
    resolved = {key: resolve_tree(item, cues) for key, item in document.items() if key != "beats"}
    resolved["beats"] = [resolve_beat(beat, cues) for beat in document["beats"]]
    return resolved


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve time anchors (@word, @keyword, @cutBefore, @cutAfter, @cut, @end) in any JSON file against cues.json. "
        "Inside beats[].props they resolve to seconds relative to that beat's from ({'@rel': anchor} is the explicit form), "
        "except under props.three, which stays in absolute output seconds."
    )
    parser.add_argument("--cues", required=True, help="cues.json on the output timeline")
    parser.add_argument("--input", required=True, help="JSON with anchors")
    parser.add_argument("--out", required=True, help="resolved JSON output path")
    args = parser.parse_args()
    try:
        resolved = resolve_document(load_json(args.input), load_json(args.cues))
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    Path(args.out).write_text(json.dumps(resolved, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
