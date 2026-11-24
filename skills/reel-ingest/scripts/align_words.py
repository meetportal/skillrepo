import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import decode_audio, rms_envelope_db

SAMPLE_RATE = 16000
LETTER_NAMES = {
    "a": "ay", "b": "bee", "c": "see", "d": "dee", "e": "ee", "f": "ef", "g": "gee", "h": "aitch", "i": "eye",
    "j": "jay", "k": "kay", "l": "el", "m": "em", "n": "en", "o": "oh", "p": "pee", "q": "cue", "r": "ar",
    "s": "es", "t": "tee", "u": "you", "v": "vee", "w": "double you", "x": "ex", "y": "why", "z": "zee",
}
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(value):
    if value < 20:
        return ONES[value]
    if value < 100:
        return TENS[value // 10] + ("" if value % 10 == 0 else " " + ONES[value % 10])
    if value < 1000:
        rest = value % 100
        return ONES[value // 100] + " hundred" + ("" if rest == 0 else " " + number_words(rest))
    if 1100 <= value <= 2099 and value % 100 != 0 and not 2000 <= value < 2010:
        return number_words(value // 100) + " " + (number_words(value % 100) if value % 100 >= 10 else "oh " + ONES[value % 100])
    thousands, rest = divmod(value, 1000)
    return number_words(thousands) + " thousand" + ("" if rest == 0 else " " + number_words(rest))


def spoken_form(word, pronunciations):
    core = re.sub(r"^[^\w']+|[^\w']+$", "", word)
    for key in (word, core, core.lower(), core.upper()):
        if key in pronunciations:
            return pronunciations[key]
    parts = []
    for piece in re.findall(r"[A-Za-z']+|\d+", core):
        if piece.isdigit():
            parts.append(number_words(int(piece)))
        elif piece.isupper() and 2 <= len(piece) <= 5:
            parts.append(" ".join(LETTER_NAMES[ch] for ch in piece.lower()))
        else:
            parts.append(piece.lower())
    return " ".join(parts)


def load_aligner():
    import torch
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=True)
    model.eval()
    return torch, torchaudio, model, bundle.get_dict(star="*")


def group_words(words, max_gap, max_span):
    groups, current = [], []
    for index, word in enumerate(words):
        if current and (word["start"] - words[current[-1]]["end"] > max_gap or word["end"] - words[current[0]]["start"] > max_span):
            groups.append(current)
            current = []
        current.append(index)
    if current:
        groups.append(current)
    return groups


def align_window(aligner, audio, start, end, words, indices, pronunciations, star_gap):
    torch, torchaudio, model, dictionary = aligner
    chunk = audio[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
    tokens, owners = [], []
    for position, index in enumerate(indices):
        if position == 0 or words[index]["start"] - words[indices[position - 1]]["end"] > star_gap:
            tokens.append(dictionary["*"])
            owners.append(None)
        letters = [dictionary[ch] for ch in spoken_form(words[index]["word"], pronunciations).replace(" ", "") if ch in dictionary and ch != "*"]
        tokens.extend(letters)
        owners.extend([index] * len(letters))
    tokens.append(dictionary["*"])
    owners.append(None)
    waveform = torch.from_numpy(np.ascontiguousarray(chunk, dtype=np.float32))[None]
    with torch.inference_mode():
        emission, _ = model(waveform)
    emission = torch.log_softmax(emission, dim=-1)
    if emission.shape[1] < len(tokens) * 2:
        return {}
    alignment, scores = torchaudio.functional.forced_align(emission, torch.tensor([tokens], dtype=torch.int32), blank=0)
    spans = torchaudio.functional.merge_tokens(alignment[0], scores[0].exp())
    ratio = len(chunk) / SAMPLE_RATE / emission.shape[1]
    timed = {}
    for owner, span in zip(owners, spans):
        if owner is None:
            continue
        span_start, span_end = start + span.start * ratio, start + span.end * ratio
        entry = timed.setdefault(owner, {"start": span_start, "end": span_end, "scores": []})
        entry["start"] = min(entry["start"], span_start)
        entry["end"] = max(entry["end"], span_end)
        entry["scores"].append(float(span.score))
    return timed


def refine_onset(envelope, hop, ctc_start, earliest, floor, args):
    def at(t):
        return int(round(t / hop))

    search_from = max(earliest, ctc_start - args.max_early)
    for index in range(at(ctc_start + args.max_late), at(search_from) - 1, -1):
        if 0 <= index < len(envelope) and envelope[index] < floor + args.onset_db:
            return (index + 1) * hop, "rise"
    peak = float(np.max(envelope[at(ctc_start):at(ctc_start) + at(0.08) + 1]))
    window_start = at(max(earliest, ctc_start - args.dip_window))
    window = envelope[window_start:at(ctc_start + args.max_late) + 1]
    if len(window):
        low = int(np.argmin(window))
        if peak - float(window[low]) >= args.dip_db:
            return (window_start + low) * hop, "dip"
    return ctc_start, "ctc"


def energy_offset(envelope, hop, ctc_end, latest, floor, close_db):
    index = int(round(ctc_end / hop))
    stop = int(round(latest / hop))
    while index < min(stop, len(envelope)) and envelope[index] > floor + close_db:
        index += 1
    return index * hop


def align_clip(name, clip, aligner, args, pronunciations, overrides):
    audio = decode_audio(clip["file"], sample_rate=SAMPLE_RATE, channels=1)
    duration = len(audio) / SAMPLE_RATE
    hop = 0.005
    envelope = rms_envelope_db(audio, SAMPLE_RATE, hop_s=hop, window_s=0.01)
    floor = float(np.percentile(rms_envelope_db(audio, SAMPLE_RATE), 5))
    words = [dict(word) for word in clip["words"]]
    groups = group_words(words, args.group_gap, args.group_span)
    for number, indices in enumerate(groups):
        previous_end = words[groups[number - 1][-1]]["end"] if number else 0.0
        next_start = words[groups[number + 1][0]]["start"] if number + 1 < len(groups) else duration
        start = max(0.0, (previous_end + words[indices[0]]["start"]) / 2, words[indices[0]]["start"] - args.pad)
        end = min(duration, (words[indices[-1]]["end"] + next_start) / 2, words[indices[-1]]["end"] + args.pad)
        timed = align_window(aligner, audio, start, end, words, indices, pronunciations, args.star_gap)
        for index in indices:
            if index in timed:
                words[index]["ctc_start"] = round(timed[index]["start"], 3)
                words[index]["ctc_end"] = round(timed[index]["end"], 3)
                words[index]["align_score"] = round(float(np.mean(timed[index]["scores"])), 3)
    unaligned = [word["word"] for word in words if "ctc_start" not in word]
    for index, word in enumerate(words):
        if "ctc_start" not in word:
            continue
        earliest = words[index - 1]["start"] + args.min_word if index else 0.0
        onset, how = refine_onset(envelope, hop, word["ctc_start"], earliest, floor, args)
        word["start"], word["onset_method"] = round(onset, 3), how
        word["end"] = word["ctc_end"]
    for override in overrides:
        candidates = [w for w in words if re.sub(r"[^a-z0-9']", "", w["word"].lower()) == re.sub(r"[^a-z0-9']", "", override["word"].lower())]
        candidates = [w for w in candidates if abs(w["start"] - override["near"]) <= 0.3]
        if not candidates:
            raise SystemExit(f"{name}: override for '{override['word']}' near {override['near']} matches no word")
        target = min(candidates, key=lambda w: abs(w["start"] - override["near"]))
        target["start"], target["onset_method"] = round(override["start"], 3), "override"
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else None
        latest = following["start"] if following else duration
        if following is None or following["start"] - word["end"] > args.join_gap:
            word["end"] = round(max(word["end"], energy_offset(envelope, hop, word["end"], min(latest, word["end"] + args.max_decay), floor, args.close_db)), 3)
        if following is not None and 0 <= following["start"] - word["end"] < args.join_gap:
            word["end"] = following["start"]
        if following is not None and word["end"] > following["start"]:
            word["end"] = following["start"]
        word["end"] = round(max(word["end"], word["start"] + 0.02), 3)
    pauses = []
    for index in range(1, len(words)):
        gap = round(words[index]["start"] - words[index - 1]["end"], 3)
        if gap > 0.25:
            pauses.append({"after": words[index - 1]["word"], "before": words[index]["word"], "start": words[index - 1]["end"], "end": words[index]["start"], "dur": gap})
    result = dict(clip)
    result.update({
        "words": words,
        "pauses_gt_250ms": pauses,
        "first_word_start": words[0]["start"] if words else None,
        "last_word_end": words[-1]["end"] if words else None,
        "unaligned_words": unaligned,
    })
    return result


def main():
    parser = argparse.ArgumentParser(description="Forced alignment of transcript words (torchaudio MMS_FA wav2vec2 CTC on CPU), onsets refined to the energy rise.")
    parser.add_argument("transcript", help="snap_words.py output")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pronunciations", help="JSON {word: 'spoken letters'} for acronyms and names said as words, e.g. {\"SQL\": \"sequel\"}")
    parser.add_argument("--overrides", help="JSON list [{clip, word, near, start}] of onsets set by ear and envelope where the aligner is wrong (glides and vowel-to-vowel joins)")
    parser.add_argument("--group-gap", type=float, default=1.2, help="words separated by more than this are aligned in separate windows")
    parser.add_argument("--group-span", type=float, default=25.0, help="longest window in seconds")
    parser.add_argument("--pad", type=float, default=0.6, help="audio kept around each window")
    parser.add_argument("--star-gap", type=float, default=0.2, help="insert a wildcard token (breath, noise, stray speech) at gaps longer than this")
    parser.add_argument("--onset-db", type=float, default=20.0, help="after silence, the onset is where the envelope (10 ms window, 5 ms hop) climbs above the room-tone floor + this; breaths stay under it")
    parser.add_argument("--dip-db", type=float, default=6.0, help="inside continuous speech, use the envelope minimum before the word when it dips this far under the word's first 80 ms peak")
    parser.add_argument("--dip-window", type=float, default=0.12, help="how far before the aligner's start to look for that minimum")
    parser.add_argument("--max-early", type=float, default=0.20, help="largest move of an onset before the aligner's start")
    parser.add_argument("--max-late", type=float, default=0.02, help="largest move of an onset after the aligner's start")
    parser.add_argument("--min-word", type=float, default=0.06, help="an onset never moves closer than this to the previous word's onset (the aligner's word ends are too unreliable to bound the search)")
    parser.add_argument("--join-gap", type=float, default=0.06, help="close gaps between words shorter than this")
    parser.add_argument("--max-decay", type=float, default=0.30, help="longest energy decay added after a phrase-final word")
    parser.add_argument("--close-db", type=float, default=10.0, help="phrase-final words end where the envelope falls to floor + this")
    args = parser.parse_args()
    source = json.loads(Path(args.transcript).read_text())
    pronunciations = json.loads(Path(args.pronunciations).read_text()) if args.pronunciations else {}
    all_overrides = json.loads(Path(args.overrides).read_text()) if args.overrides else []
    aligner = load_aligner()
    clips = {}
    for name, clip in source["clips"].items():
        clips[name] = align_clip(name, clip, aligner, args, pronunciations, [o for o in all_overrides if o["clip"] == name])
        moved = [abs(w["start"] - o["start"]) for w, o in zip(clips[name]["words"], clip["words"])]
        print(f"{name}: {len(clips[name]['words'])} words, onset moved median {np.median(moved) * 1000:.0f} ms max {max(moved) * 1000:.0f} ms, unaligned {clips[name]['unaligned_words']}", flush=True)
        print("  " + " ".join(f"{w['word']}@{w['start']:.2f}" for w in clips[name]["words"]))
    report = dict(source)
    report["version"] = 3
    report["method"] = source.get("method", "") + "; word times from torchaudio MMS_FA forced alignment, onsets refined to the energy rise, phrase-final ends extended through the energy decay"
    report["clips"] = clips
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
