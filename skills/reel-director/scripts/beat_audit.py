import argparse
import json
import statistics
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text()) if path and Path(path).is_file() else None


def camera_keys(camera):
    return [{**key, "t": float(key["t"])} for key in (camera or {}).get("keys", [])]


def camera_changes(camera):
    times, previous = [], None
    for key in camera_keys(camera):
        if key.get("ease") == "kick":
            continue
        state = (key.get("scale"), key.get("tx"), key.get("ty"))
        if key.get("ease") not in ("creep", "hold") and previous is not None and state != previous:
            times.append(key["t"])
        previous = state
    return times


def kick_times(camera):
    return sorted(key["t"] for key in camera_keys(camera) if key.get("ease") == "kick")


def is_three(beat):
    return beat.get("component") == "VideoInsert" and isinstance((beat.get("props") or {}).get("three"), dict)


def visual_events(beats, cues, camera, duration, merge):
    raw = set(float(t) for t in (cues or {}).get("cuts", []))
    for b in beats:
        raw.update((b["from"], b["to"]))
    raw.update(camera_changes(camera))
    raw.update(kick_times(camera))
    marks = []
    for t in sorted({0.0, duration, *[t for t in raw if 0 <= t <= duration]}):
        if not marks or t - marks[-1] >= merge or t == duration:
            marks.append(t)
    return marks


def event_count(marks, duration):
    return sum(1 for t in marks if 0 < t < duration)


def talk_end_of(beats, cues, rules):
    ends = [b["from"] for b in beats if b.get("component") in rules["endcard_components"]]
    aroll = float((cues or {}).get("duration") or 0)
    if aroll:
        ends.append(aroll)
    return min(ends) if ends else max((b["to"] for b in beats), default=0.0)


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

    marks = visual_events(beats, cues, camera, duration, rules["event_merge"])
    gaps = sorted(((b - a, a, b) for a, b in zip(marks, marks[1:])), reverse=True)
    for gap, a, b in gaps:
        if gap <= rules["max_gap"]:
            break
        add("FAIL", "rhythm", f"{a:.2f}-{b:.2f}: {gap:.2f}s without a cut, scale change or graphic event (max {rules['max_gap']}s)")
    median_gap = statistics.median([g for g, _, _ in gaps]) if gaps else 0.0
    if median_gap > rules["median_gap_max"]:
        add("WARN", "rhythm", f"median gap between visual events is {median_gap:.2f}s over {event_count(marks, duration)} events (target 1.5 to {rules['median_gap_max']}s)")

    hiders = [b for b in beats if b.get("mode") in ("takeover", "hidden")]
    for window in (cues or {}).get("cover", []):
        start, end = float(window["start"]), float(window["end"])
        if not any(b["from"] <= start + rules["cover_tolerance"] and b["to"] >= end - rules["cover_tolerance"] for b in hiders):
            reason = f" ({window['reason']})" if window.get("reason") else ""
            add("FAIL", "cover", f"cover window {start:.2f}-{end:.2f}{reason} is not inside one takeover or hidden beat")

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

    kicks = kick_times(camera)
    for first, second in zip(kicks, kicks[1:]):
        if second - first < rules["kick_min_gap"]:
            add("WARN", "kick", f"kicks at {first:.2f}s and {second:.2f}s are {second - first:.2f}s apart (want {rules['kick_min_gap']}s)")

    three = sorted((b for b in beats if is_three(b)), key=lambda b: b["from"])
    talk_end = talk_end_of(beats, cues, rules)
    cta_start = talk_end - rules["cta_sec"]
    for b in three:
        if b["from"] < rules["three_min_start"]:
            add("FAIL", "3d", f"{b['id']} starts at {b['from']:.2f}s; no 3D beat before {rules['three_min_start']}s")
        if b["from"] < talk_end - 1e-6 and b["to"] > cta_start:
            add("FAIL", "3d", f"{b['id']} ({b['from']:.2f}-{b['to']:.2f}s) overlaps the CTA window {cta_start:.2f}-{talk_end:.2f}s")
    three_takeovers = [b for b in three if b.get("mode") == "takeover"]
    flagged = set()
    for first in three_takeovers:
        crowd = [b for b in three_takeovers if first["from"] <= b["from"] < first["from"] + rules["three_window"]]
        key = tuple(b["id"] for b in crowd)
        if len(crowd) > 1 and not any(set(key) <= set(f) for f in flagged):
            flagged.add(key)
            listed = ", ".join("{} at {:.2f}s".format(b["id"], b["from"]) for b in crowd)
            add("WARN", "3d", f"{len(crowd)} 3D takeovers within {rules['three_window']:.0f}s ({listed}); at most one per {rules['three_window']:.0f}s")
    for b in three_takeovers:
        if b["to"] - b["from"] > rules["three_takeover_max"] and b not in long_ones:
            add("WARN", "3d", f"3D takeover {b['id']} lasts {b['to'] - b['from']:.2f}s (max {rules['three_takeover_max']}s)")
    if three and talk_end > 0:
        total = sum(b["to"] - b["from"] for b in three)
        low, high = (rules["three_budget"][0] * talk_end / 60, rules["three_budget"][1] * talk_end / 60)
        if not low - 1e-6 <= total <= high + 1e-6:
            add("WARN", "3d", f"3D time {total:.2f}s over {talk_end:.2f}s of talk is {total * 60 / talk_end:.1f}s per 60s (budget {rules['three_budget'][0]:g} to {rules['three_budget'][1]:g}s per 60s, here {low:.2f} to {high:.2f}s)")
    return findings, gaps[:3], median_gap, event_count(marks, duration)


def main():
    parser = argparse.ArgumentParser(
        description="Audit a resolved beat map against the director's planning rules: speech and hook visual at frame 0, no takeover in "
                    "the first second, a visual change at least every 4 s and a median gap under 2.5 s, cover windows inside a takeover "
                    "or hidden beat, takeovers at most 1.5 s with 2 s of face between them, one card at a time, readable hold times, "
                    "kicks at least 3 s apart, and the 3D budget (VideoInsert beats with props.three). Exit 1 on any FAIL.")
    parser.add_argument("--beatmap", required=True, help="beatmap.json (resolved: beats[{id, component, mode, from, to, props}])")
    parser.add_argument("--cues", help="cues.json (cuts, words, cover windows)")
    parser.add_argument("--camera", help="camera_plan.json (keys with scale changes, glides and kicks)")
    parser.add_argument("--duration", type=float, help="reel length in seconds (default: last beat end or cues duration)")
    parser.add_argument("--max-gap", type=float, default=4.0, help="FAIL above this many seconds without a visual event (default 4)")
    parser.add_argument("--median-gap", type=float, default=2.5, help="WARN when the median gap between visual events is above this (default 2.5)")
    parser.add_argument("--takeover-max", type=float, default=1.5)
    parser.add_argument("--cta-sec", type=float, default=3.0, help="seconds before the end card (or the A-roll end) reserved for the CTA; no 3D beat there (default 3)")
    parser.add_argument("--endcard", default="EndCard", help="comma list of components that are end cards (exempt from takeover limits)")
    args = parser.parse_args()

    beatmap = load(args.beatmap)
    if beatmap is None:
        raise SystemExit(f"beat map not found: {args.beatmap}")
    cues = load(args.cues)
    camera = load(args.camera)
    beats = [{**b, "from": float(b["from"]), "to": float(b["to"])} for b in beatmap.get("beats", [])]
    duration = args.duration or max([b["to"] for b in beats] + [float((cues or {}).get("duration", 0))])
    rules = {
        "first_word_max": 0.3, "hook_visual_max": 0.08, "no_takeover_before": 1.0, "max_gap": args.max_gap,
        "median_gap_max": args.median_gap, "event_merge": 0.1, "cover_tolerance": 0.02,
        "takeover_max": args.takeover_max, "takeover_exception_max": 2.5, "face_between_takeovers": 2.0,
        "overlap_tolerance": 0.2, "min_beat": 0.6, "endcard_components": set(args.endcard.split(",")),
        "kick_min_gap": 3.0, "three_min_start": 1.0, "cta_sec": args.cta_sec, "three_window": 15.0,
        "three_takeover_max": 1.5, "three_budget": (4.0, 8.0),
    }
    findings, gaps, median_gap, events = audit(beats, cues, camera, duration, rules)
    for f in findings:
        print(f"{f['level']:4s} {f['rule']:9s} {f['message']}")
    three = [b for b in beats if is_three(b)]
    print(f"{len(beats)} beats ({len(three)} 3D, {sum(b['to'] - b['from'] for b in three):.2f}s) over {duration:.2f}s; "
          f"{events} visual events, median gap {median_gap:.2f}s; largest gaps: " + ", ".join(f"{a:.2f}-{b:.2f} ({g:.2f}s)" for g, a, b in gaps))
    sys.exit(1 if any(f["level"] == "FAIL" for f in findings) else 0)


if __name__ == "__main__":
    main()
