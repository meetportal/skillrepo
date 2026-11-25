import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAMPLE_RATE = 16000
GAP_MIN_SEC = 0.12
QUIET_RUN_FRAMES = 8
QUIET_PERCENTILE = 15


def bare(text):
    return re.sub(r"[^a-z0-9']", "", text.lower())


def canonical(text):
    return text.replace("'ll", " will").replace("n't", " not").replace("'re", " are").replace(" ", "")


def decode(media):
    channels = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", str(media)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    fold = "pan=mono|c0=c0" if channels in ("", "1") else "pan=mono|c0=0.5*c0+0.5*c1"
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(media), "-map", "0:a:0", "-af", fold, "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def splice_times(edl_path):
    edl = json.loads(Path(edl_path).read_text())
    fps = edl["fps"]
    times, cursor, previous = [], 0, None
    for entry in edl["ranges"]:
        clip = entry.get("a_clip", entry["clip"])
        a_in, a_out = round(entry["a_in"] * fps), round(entry["a_out"] * fps)
        if previous is not None and (previous[0] != clip or previous[1] != a_in):
            times.append(cursor / fps)
        previous = (clip, a_out)
        cursor += a_out - a_in
    return times


def word_spans(words):
    return sorted((word["startMs"] / 1000, word["endMs"] / 1000) for word in words)


def inside_word(time, spans):
    return any(start < time < end for start, end in spans)


def gap_points(spans, min_gap=GAP_MIN_SEC):
    points = []
    latest_end = None
    for start, end in spans:
        if latest_end is not None and start - latest_end >= min_gap:
            points.append(round((latest_end + start) / 2, 3))
        latest_end = end if latest_end is None else max(latest_end, end)
    return points


def quiet_points(audio, min_run=QUIET_RUN_FRAMES):
    hop = SAMPLE_RATE // 100
    frames = len(audio) // hop
    if frames == 0:
        return []
    energy = np.sqrt(np.mean(audio[:frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
    quiet = np.append(energy <= np.percentile(energy, QUIET_PERCENTILE), False)
    points, run_start = [], None
    for index, flag in enumerate(quiet):
        if flag and run_start is None:
            run_start = index
        elif not flag and run_start is not None:
            if index - run_start >= min_run:
                points.append(round((run_start + index) / 2 / 100, 3))
            run_start = None
    return points


def chunk_bounds(total, tiers, max_chunk, spans=()):
    usable = [sorted(t for t in tier if 0 < t < total and not inside_word(t, spans)) for tier in tiers]
    word_ends = sorted(end for _, end in spans if not inside_word(end, spans))
    bounds, start = [], 0.0
    while total - start > max_chunk:
        stop = None
        for tier in usable + [word_ends]:
            inside = [t for t in tier if start + 2.0 < t <= start + max_chunk]
            if inside:
                stop = inside[-1]
                break
        stop = start + max_chunk if stop is None else stop
        bounds.append((start, stop))
        start = stop
    bounds.append((start, total))
    return bounds


def transcribe(audio, model_name, prompt, bounds, threads):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    words = []
    pad = np.zeros(SAMPLE_RATE // 2, np.float32)
    for start, end in bounds:
        chunk = np.concatenate([pad, audio[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)], pad])
        segments, _ = model.transcribe(chunk, language="en", beam_size=5, word_timestamps=True, initial_prompt=prompt or None, condition_on_previous_text=False, vad_filter=False)
        for segment in segments:
            for word in segment.words or []:
                words.append({"text": word.word.strip(), "start": round(word.start - 0.5 + start, 3), "end": round(word.end - 0.5 + start, 3)})
    return words


def alias_pairs(corrections_path, dictionary_path, allow):
    pairs = set()
    sources = []
    if corrections_path:
        data = json.loads(Path(corrections_path).read_text())
        rules = data.get("corrections", []) if isinstance(data, dict) else data
        sources += [(r["match"], r["text"]) for r in rules if "match" in r and r.get("text")]
    if dictionary_path:
        sources += list(json.loads(Path(dictionary_path).read_text()).get("phrases", {}).items())
    sources += [tuple(pair.split(">", 1)) for pair in allow.split(",") if ">" in pair]
    for left, right in sources:
        a = " ".join(bare(t) for t in left.split() if bare(t))
        b = " ".join(bare(t) for t in right.split() if bare(t))
        pairs |= {(a, b), (b, a)}
    return pairs


def tokens_of(words, text_key, start_key, scale):
    tokens = []
    for word in words:
        for part in word[text_key].split():
            if bare(part):
                tokens.append({"norm": bare(part), "text": part, "start": word[start_key] * scale})
    return tokens


def main():
    parser = argparse.ArgumentParser(description="One ASR diff for every stage: re-transcribe audio and diff it against the intended caption words (missing = clipped edge, extra = ghost or uncut retake, changed = slip or ASR variant).")
    parser.add_argument("--mode", choices=["cut", "final"], default="final", help="cut: Stage 1 voice_cut.wav, chunked at the EDL audio splices (needs --edl); final (default): the delivered file, chunked in the middle of word gaps of 120 ms or more, else in runs of 8+ quiet 10 ms frames; never inside a word")
    parser.add_argument("--words", "--intended", dest="words", required=True, help="words.out.json (Caption[])")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--media", help="audio or video file to transcribe")
    source.add_argument("--heard", help="existing transcript JSON list [{text, start, end}] instead of running a model")
    parser.add_argument("--edl", help="edl.json (cut mode)")
    parser.add_argument("--corrections", help="reel corrections file: each match/text pair is accepted in both directions")
    parser.add_argument("--dictionary", help="brand caption dictionary: phrase pairs accepted in both directions")
    parser.add_argument("--allow", default="", help="extra comma list of 'intended>heard' pairs")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--max-chunk", type=float, default=20.0, help="whisper invents words at its own 30 s window edges, so audio is cut into chunks of at most this many seconds")
    parser.add_argument("--threads", type=int, default=2, help="CPU threads for faster-whisper (0 lets it pick; keep 2 on a shared machine)")
    parser.add_argument("--chunks-only", action="store_true", help="print the chunk bounds and exit without transcribing")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.mode == "cut" and not args.edl and not args.heard:
        parser.error("--mode cut needs --edl")
    expected = json.loads(Path(args.words).read_text())
    if args.heard:
        heard_words = json.loads(Path(args.heard).read_text())
        bounds = []
    else:
        audio = decode(args.media)
        total = len(audio) / SAMPLE_RATE
        spans = word_spans(expected)
        tiers = [gap_points(spans), quiet_points(audio)]
        if args.mode == "cut":
            tiers.insert(0, splice_times(args.edl))
        bounds = chunk_bounds(total, tiers, args.max_chunk, spans)
        if args.chunks_only:
            print(json.dumps([[round(a, 3), round(b, 3)] for a, b in bounds]))
            return
        heard_words = transcribe(audio, args.model, args.prompt, bounds, args.threads)
    intended = tokens_of(expected, "text", "startMs", 0.001)
    heard = tokens_of(heard_words, "text", "start", 1.0)
    aliases = alias_pairs(args.corrections, args.dictionary, args.allow)
    matcher = difflib.SequenceMatcher(a=[t["norm"] for t in intended], b=[t["norm"] for t in heard], autojunk=False)
    problems, accepted, onset_errors = [], [], []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            onset_errors += [heard[b0 + k]["start"] - intended[a0 + k]["start"] for k in range(a1 - a0)]
            continue
        want = " ".join(t["norm"] for t in intended[a0:a1])
        got = " ".join(t["norm"] for t in heard[b0:b1])
        entry = {"type": {"delete": "missing", "insert": "extra", "replace": "changed"}[tag], "intended": want, "heard": got,
                 "at": round(intended[a0]["start"] if a0 < len(intended) else heard[b0]["start"], 3)}
        (accepted if (want, got) in aliases or canonical(want) == canonical(got) else problems).append(entry)
    report = {
        "mode": args.mode,
        "intended_words": len(intended),
        "heard_words": len(heard),
        "similarity": round(matcher.ratio(), 4),
        "chunks": [[round(a, 3), round(b, 3)] for a, b in bounds],
        "heard_text": " ".join(t["text"] for t in heard),
        "problems": problems,
        "accepted_variants": accepted,
        "asr_onset_offset_median_s": round(float(np.median(onset_errors)), 3) if onset_errors else None,
        "pass": not problems,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    print(f"heard: {report['heard_text']}")
    for entry in accepted:
        print(f"accepted {entry['type']} @{entry['at']}: intended '{entry['intended']}' heard '{entry['heard']}'")
    for entry in problems:
        print(f"PROBLEM {entry['type']} @{entry['at']}: intended '{entry['intended']}' heard '{entry['heard']}'")
    print(f"{len(intended)} intended, {len(heard)} heard, similarity {matcher.ratio():.3f}: {'PASS' if report['pass'] else 'FAIL'}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
