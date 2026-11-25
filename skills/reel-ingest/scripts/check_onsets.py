import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import decode_audio, rms_envelope_db

SAMPLE_RATE = 16000


def bare(text):
    return re.sub(r"[^a-z0-9']", "", text.lower())


def energy_rise(envelope, hop, onset, earliest, floor, silence_db, rise_db):
    def at(t):
        return int(round(t / hop))

    start = at(max(earliest, onset - 0.08))
    before = envelope[start:at(onset + 0.03) + 1]
    if not len(before):
        return None
    low_index = int(np.argmin(before))
    if float(before[low_index]) > floor + silence_db:
        return None
    threshold = float(before[low_index]) + rise_db
    hold = at(0.02)
    for index in range(start + low_index, min(len(envelope) - hold, at(onset + 0.12))):
        if np.all(envelope[index:index + hold] >= threshold):
            return index * hop
    return None


def onset_rows(words, audio, frame, silence_db, rise_db):
    hop = 0.0025
    envelope = rms_envelope_db(audio, SAMPLE_RATE, hop_s=hop, window_s=0.005)
    floor = float(np.percentile(rms_envelope_db(audio, SAMPLE_RATE), 5))
    rows = []
    for index, word in enumerate(words):
        earliest = words[index - 1]["end"] - 0.02 if index else 0.0
        rise = energy_rise(envelope, hop, word["start"], earliest, floor, silence_db, rise_db)
        if rise is None:
            continue
        error = word["start"] - rise
        rows.append({"word": word["word"], "onset": round(word["start"], 3), "rise": round(rise, 3), "error_ms": round(error * 1000), "ok": abs(error) <= frame + 1e-6})
    return rows


def asr_rows(words, audio, model, sample_every, prompt):
    rows = []
    pad = np.zeros(SAMPLE_RATE // 2, np.float32)
    for index in range(1, len(words) - 3, sample_every):
        word = words[index]
        start, end = word["start"], words[index + 3]["start"]
        chunk = np.concatenate([pad, audio[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)], pad])
        segments, _ = model.transcribe(chunk, language="en", beam_size=5, initial_prompt=prompt or None, condition_on_previous_text=False, vad_filter=False)
        heard = [bare(token) for segment in segments for token in segment.text.split() if bare(token)]
        previous, expected = bare(words[index - 1]["word"]), bare(word["word"])
        leaked = bool(heard) and heard[0] == previous and previous != expected
        rows.append({"word": word["word"], "onset": round(start, 3), "heard": " ".join(heard), "ok": not leaked})
    return rows


def load_words(args):
    if args.transcript:
        source = json.loads(Path(args.transcript).read_text())
        for name, clip in source["clips"].items():
            if args.clip and name not in args.clip:
                continue
            words = [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in clip["words"]]
            yield name, clip["file"], words
    else:
        captions = json.loads(Path(args.words).read_text())
        words = [{"word": c["text"].strip(), "start": c["startMs"] / 1000, "end": c["endMs"] / 1000} for c in captions]
        yield Path(args.audio).stem, args.audio, words


def main():
    parser = argparse.ArgumentParser(description="Word onset accuracy gate: onsets against the energy rise, plus optional ASR chunk tests that start at each sampled onset.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--transcript", help="aligned transcript (clips -> words, source time)")
    source.add_argument("--words", help="Caption[] on the output timeline (needs --audio)")
    parser.add_argument("--audio", help="cut audio for --words")
    parser.add_argument("--clip", action="append", help="only these transcript clips")
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--silence-db", type=float, default=10.0, help="only words preceded (within 80 ms) by a frame within this much of the room-tone floor are measured")
    parser.add_argument("--rise-db", type=float, default=12.0, help="the rise is where the envelope (5 ms window) first climbs this far above that quiet frame")
    parser.add_argument("--asr-every", type=int, default=0, help="ASR leak test on every Nth word (0 = off): audio from the onset to three words later must not start with the previous word, which happens when an onset sits early, inside the previous word")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--threads", type=int, default=2, help="CPU threads for faster-whisper in the ASR test (default 2, for a shared machine)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    frame = 1 / args.fps
    model = None
    if args.asr_every:
        from faster_whisper import WhisperModel

        model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads)
    report = {"frame_s": frame, "groups": {}}
    passed = True
    for name, path, words in load_words(args):
        audio = decode_audio(path, sample_rate=SAMPLE_RATE, channels=1)
        rows = onset_rows(words, audio, frame, args.silence_db, args.rise_db)
        group = {"energy": rows, "energy_fail": [r for r in rows if not r["ok"]]}
        if model is not None:
            group["asr"] = asr_rows(words, audio, model, args.asr_every, args.prompt)
            group["asr_fail"] = [r for r in group["asr"] if not r["ok"]]
        errors = [abs(r["error_ms"]) for r in rows]
        group["measured"] = len(rows)
        group["error_ms_median"] = float(np.median(errors)) if errors else None
        group["error_ms_max"] = max(errors) if errors else None
        report["groups"][name] = group
        ok = not group["energy_fail"] and not group.get("asr_fail")
        passed = passed and ok
        print(f"{name}: {len(rows)} onsets after silence, |error| median {group['error_ms_median']} ms max {group['error_ms_max']} ms, {len(group['energy_fail'])} over 1 frame" + (f", ASR chunks {len(group['asr']) - len(group['asr_fail'])}/{len(group['asr'])} ok" if model is not None else ""))
        for row in group["energy_fail"]:
            print(f"  FAIL energy {row['word']} onset {row['onset']} rise {row['rise']} ({row['error_ms']} ms)")
        for row in group.get("asr_fail", []):
            print(f"  FAIL asr {row['word']} onset {row['onset']} heard '{row['heard']}'")
    report["pass"] = passed
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print("PASS" if passed else "FAIL")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
