import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beat_audit import event_count, load, visual_events
from packed_transcript import phrases, words_from

EVENT_MERGE = 0.1


def planned_events(beatmap, camera, cues, last_word_end):
    beats = [{"from": float(b["from"]), "to": float(b["to"])} for b in (beatmap or {}).get("beats", [])
             if isinstance(b.get("from"), (int, float)) and isinstance(b.get("to"), (int, float))]
    duration = max([b["to"] for b in beats] + [float((cues or {}).get("duration") or 0), last_word_end])
    marks = visual_events(beats, cues, camera, duration, EVENT_MERGE)
    return [t for t in marks if t < duration], event_count(marks, duration)


def last_event(events, t):
    before = [e for e in events if e <= t + 1e-6]
    return before[-1] if before else 0.0


def longest_quiet(events, start, end):
    inside = [e for e in events if start < e < end]
    marks = [last_event(events, start), *inside]
    stops = [*inside, end]
    return max(stop - mark for mark, stop in zip(marks, stops))


def main():
    parser = argparse.ArgumentParser(
        description="Beat sheet for planning: one row per spoken phrase with start, end, words/s, the pause after it, the seconds "
                    "since the last planned visual event (cut, scale change, glide, kick, beat in or out) and a GAP marker where "
                    "the picture would stay unchanged for more than --max-gap seconds. The header gives total words/s and the sum "
                    "of pauses over 0.25 s.")
    parser.add_argument("words", help="words.out.json (Caption[]), ingest transcript.json or cues.json")
    parser.add_argument("--beatmap", help="resolved beatmap.json")
    parser.add_argument("--camera", help="camera_plan.json")
    parser.add_argument("--cues", help="cues.json (adds its cuts as visual events)")
    parser.add_argument("--gap", type=float, default=0.25, help="a pause of at least this many seconds ends a phrase (default 0.25)")
    parser.add_argument("--max-words", type=int, default=12, help="longest phrase in words (default 12)")
    parser.add_argument("--max-gap", type=float, default=2.5, help="mark a phrase when the picture stays unchanged longer than this (default 2.5)")
    parser.add_argument("--pause-min", type=float, default=0.25, help="pauses at least this long count in the pause total (default 0.25)")
    args = parser.parse_args()

    groups = words_from(json.loads(Path(args.words).read_text()))
    last_word_end = max((w["end"] for words in groups.values() for w in words), default=0.0)
    events, count = planned_events(load(args.beatmap), load(args.camera), load(args.cues), last_word_end)
    lines = []
    for name, words in groups.items():
        words = [w for w in words if w["text"]]
        if not words:
            continue
        span = words[-1]["end"] - words[0]["start"]
        pauses = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
        long_pauses = [p for p in pauses if p >= args.pause_min]
        per15 = sum(long_pauses) * 15 / span if span > 0 else 0.0
        head = f"## {name}  " if len(groups) > 1 else ""
        lines.append(f"{head}{len(words)} words over {span:.2f}s = {len(words) / span if span else 0:.2f} words/s; "
                     f"pauses >= {args.pause_min:.2f}s: {len(long_pauses)}, {sum(long_pauses):.2f}s total ({per15:.2f}s per 15s); "
                     f"{count} planned visual events (counted as beat_audit.py does)")
        lines.append(f"{'start':>6} {'end':>6} {'w':>3} {'w/s':>5} {'pause':>6} {'since':>6}  text")
        for chunk, pause in phrases(words, args.gap, args.max_words):
            start, end = chunk[0]["start"], chunk[-1]["end"]
            rate = len(chunk) / (end - start) if end > start else 0.0
            since = start - last_event(events, start)
            quiet = longest_quiet(events, start, end + (pause or 0.0))
            mark = f"  GAP {quiet:.1f}s" if quiet > args.max_gap else ""
            pause_text = f"{pause:6.2f}" if pause is not None else f"{'-':>6}"
            text = " ".join(w["text"] for w in chunk)
            lines.append(f"{start:6.2f} {end:6.2f} {len(chunk):3d} {rate:5.2f} {pause_text} {since:6.2f}  {text}{mark}")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
