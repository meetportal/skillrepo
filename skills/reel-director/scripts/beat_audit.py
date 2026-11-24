import argparse
import json
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text()) if path and Path(path).is_file() else None


def camera_changes(camera):
    times, previous = [], None
    for key in (camera or {}).get("keys", []):
        state = (key.get("scale"), key.get("tx"), key.get("ty"))
        if key.get("ease") not in ("creep", "hold") and previous is not None and state != previous:
            times.append(float(key["t"]))
        previous = state
    return times


def audit(beats, cues, camera, duration, rules):
    findings = []

    def add(level, rule, message):
        findings.append({"level": level, "rule": rule, "message": message})

    words = (cues or {}).get("words", [])
    if words and words[0]["start"] > rules["first_word_max"]:
        add("FAIL", "hook", f"first word starts at {words[0]['start']:.2f}s; speech should start within {rules['first_word_max']}s")
    opening = [b for b in beats if b["from"] <= rules["hook_visual_max"]]
    if not opening:
        add("FAIL", "hook", f"no beat on screen by {rules['hook_visual_max']}s; frame 0 needs the hook visual (headline or treatment)")
    early_takeovers = [b["id"] for b in beats if b.get("mode") == "takeover" and b["from"] < rules["no_takeover_before"]]
    if early_takeovers:
        add("FAIL", "hook", f"takeover {early_takeovers} inside the first {rules['no_takeover_before']}s hides the face during the hook")

    events = set((cues or {}).get("cuts", []))
    for b in beats:
        events.update((b["from"], b["to"]))
    events.update(camera_changes(camera))
    marks = sorted({0.0, duration, *[round(t, 2) for t in events if 0 <= t <= duration]})
    gaps = sorted(((b - a, a, b) for a, b in zip(marks, marks[1:])), reverse=True)
    for gap, a, b in gaps:
        if gap <= rules["max_gap"]:
            break
        add("FAIL", "rhythm", f"{a:.2f}-{b:.2f}: {gap:.2f}s without a cut, scale change or graphic event (max {rules['max_gap']}s)")

    takeovers = sorted((b for b in beats if b.get("mode") == "takeover" and b.get("component") not in rules["endcard_components"]), key=lambda b: b["from"])
    long_ones = [b for b in takeovers if b["to"] - b["from"] > rules["takeover_max"]]
    for b in long_ones:
        level = "WARN" if b["to"] - b["from"] <= rules["takeover_exception_max"] and len(long_ones) == 1 else "FAIL"
        add(level, "takeover", f"{b['id']} hides the speaker for {b['to'] - b['from']:.2f}s (max {rules['takeover_max']}s; one exception up to {rules['takeover_exception_max']}s only to cover a defect)")
    for first, second in zip(takeovers, takeovers[1:]):
        face = second["from"] - first["to"]
        if face < rules["face_between_takeovers"]:
            add("WARN", "takeover", f"only {face:.2f}s of face between {first['id']} and {second['id']} (want {rules['face_between_takeovers']}s)")

    cards = sorted((b for b in beats if b.get("mode") == "card"), key=lambda b: b["from"])
    for first, second in zip(cards, cards[1:]):
        if second["from"] < first["to"] - rules["overlap_tolerance"]:
            add("WARN", "one idea", f"{first['id']} and {second['id']} overlap {first['to'] - second['from']:.2f}s in the card zone (one idea per beat)")
    for b in beats:
        length = b["to"] - b["from"]
        if b.get("mode") in ("card", "takeover") and length < rules["min_beat"]:
            add("WARN", "hold", f"{b['id']} is on screen {length:.2f}s; under {rules['min_beat']}s it cannot be read")
    return findings, gaps[:3]


def main():
    parser = argparse.ArgumentParser(
        description="Audit a resolved beat map against the director's planning rules: speech and hook visual at frame 0, no takeover in "
                    "the first second, a visual change at least every 4 s, takeovers at most 1.5 s with 2 s of face between them, "
                    "one card at a time, readable hold times. Exit 1 on any FAIL.")
    parser.add_argument("--beatmap", required=True, help="beatmap.json (resolved: beats[{id, component, mode, from, to}])")
    parser.add_argument("--cues", help="cues.json (cuts and words)")
    parser.add_argument("--camera", help="camera_plan.json (keys with scale changes)")
    parser.add_argument("--duration", type=float, help="reel length in seconds (default: last beat end or cues duration)")
    parser.add_argument("--max-gap", type=float, default=4.0)
    parser.add_argument("--takeover-max", type=float, default=1.5)
    parser.add_argument("--endcard", default="EndCard", help="comma list of components that are end cards (exempt from takeover limits)")
    args = parser.parse_args()

    beatmap = load(args.beatmap)
    cues = load(args.cues)
    camera = load(args.camera)
    beats = [{**b, "from": float(b["from"]), "to": float(b["to"])} for b in beatmap.get("beats", [])]
    duration = args.duration or max([b["to"] for b in beats] + [float((cues or {}).get("duration", 0))])
    rules = {
        "first_word_max": 0.3, "hook_visual_max": 0.08, "no_takeover_before": 1.0, "max_gap": args.max_gap,
        "takeover_max": args.takeover_max, "takeover_exception_max": 2.5, "face_between_takeovers": 2.0,
        "overlap_tolerance": 0.2, "min_beat": 0.6, "endcard_components": set(args.endcard.split(",")),
    }
    findings, gaps = audit(beats, cues, camera, duration, rules)
    for f in findings:
        print(f"{f['level']:4s} {f['rule']:9s} {f['message']}")
    print(f"{len(beats)} beats over {duration:.2f}s; largest gaps: " + ", ".join(f"{a:.2f}-{b:.2f} ({g:.2f}s)" for g, a, b in gaps))
    sys.exit(1 if any(f["level"] == "FAIL" for f in findings) else 0)


if __name__ == "__main__":
    main()
