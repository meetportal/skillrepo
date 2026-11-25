import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile
from scipy import signal

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from soundlib import SAMPLE_RATE, load_json, sha256_file

SENTENCES = [
    "Your domain yourbrand.com lands in spam because nobody set up SPF, DKIM and DMARC.",
    "Here is the fix.",
    "First, check your SPF record.",
    "Second, sign every message with DKIM.",
    "Third, publish a DMARC policy.",
]
DURATION = 30.0
FPS = 25


def mock_words(rng):
    words, t, cycle = [], 0.6, 0
    while t < DURATION - 3.0:
        tokens = SENTENCES[cycle % len(SENTENCES)].split()
        for index, token in enumerate(tokens):
            length = 0.12 + 0.045 * len(token.strip(".,"))
            final = index == len(tokens) - 1
            words.append({"text": " " + token, "startMs": round(t * 1000), "endMs": round((t + length) * 1000), "final": final})
            t += length + (0.0 if final else float(rng.choice([0.05, 0.1, 0.22, 0.35], p=[0.4, 0.35, 0.15, 0.1])))
        t += float(rng.uniform(0.5, 0.9))
        cycle += 1
    return words


def mock_voice(rng, words):
    count = int(DURATION * SAMPLE_RATE)
    voice = rng.standard_normal(count) * 10 ** (-62 / 20)
    for word in words:
        a, b = int(word["startMs"] / 1000 * SAMPLE_RATE), int(word["endMs"] / 1000 * SAMPLE_RATE)
        t = np.arange(b - a) / SAMPLE_RATE
        phase = 2 * np.pi * np.cumsum(rng.uniform(105, 140) * (1 + 0.08 * np.sin(4 * np.pi * t))) / SAMPLE_RATE
        voiced = sum(np.sin(k * phase) / k for k in range(1, 30))
        voiced = sum(signal.sosfilt(signal.butter(2, [f * 0.8, f * 1.2], btype="bandpass", fs=SAMPLE_RATE, output="sos"), voiced) * g for f, g in ((600, 1.0), (1500, 0.6), (2600, 0.35)))
        envelope = np.clip(t / 0.015, 0, 1) * np.clip((t[-1] - t) / 0.04, 0, 1) * (1 + 0.6 * np.sin(2 * np.pi * 4.5 * t)) / 1.6
        level = -21.0 - (9.0 if word["final"] else 0.0)
        voice[a:b] += voiced / np.std(voiced) * envelope * 10 ** (level / 20)
    ceiling = 10 ** (-10 / 20)
    return ceiling * np.tanh(voice / ceiling)


def mock_bed(rng):
    count = int(60.0 * SAMPLE_RATE)
    t = np.arange(count) / SAMPLE_RATE
    bar = 240.0 / 110.0
    chords = [[220.0, 277.18, 329.63], [196.0, 246.94, 293.66], [174.61, 220.0, 261.63]]
    chord = np.floor(t / bar).astype(int) % len(chords)
    pad = sum(np.where(chord == i, sum(np.sin(2 * np.pi * f * t) for f in notes), 0.0) for i, notes in enumerate(chords)) * 0.05
    pulse = np.exp(-((t % (bar / 8)) / 0.08)) * np.sin(2 * np.pi * 660 * t) * 0.1
    kick = np.exp(-((t % (bar / 4)) / 0.12)) * np.sin(2 * np.pi * 55 * t) * 0.4
    bed = np.stack([pad + pulse + kick, pad + 0.8 * pulse + kick], axis=1)
    return bed / np.abs(bed).max() * 0.7


def run(args, expect=0):
    result = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    if result.returncode != expect:
        raise SystemExit(f"FAIL {' '.join(map(str, args[:2]))}: exit {result.returncode}, expected {expect}\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return result.stdout + result.stderr


def md5_tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*.wav"))}


def main():
    parser = argparse.ArgumentParser(description="End-to-end self test of the reel-sound scripts on generated mock audio: SFX kit determinism, 3D event cues, LU levelling, both duck modes and the stale-voice guard.")
    parser.add_argument("--keep", help="write the fixtures and outputs here instead of a temporary folder")
    args = parser.parse_args()
    temp = tempfile.TemporaryDirectory()
    work = Path(args.keep or temp.name)
    work.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(5)
    results = {}

    run([SCRIPTS / "sfx_synth.py", "--out-dir", work / "kit_a", "--seed", 7])
    run([SCRIPTS / "sfx_synth.py", "--out-dir", work / "kit_b", "--seed", 7])
    results["kit_identical"] = md5_tree(work / "kit_a") == md5_tree(work / "kit_b")
    inspect = run([SCRIPTS / "sfx_cues.py", "inspect", "--library", work / "kit_a" / "manifest.json"])
    errors = []
    for line in inspect.splitlines():
        if " anchor " in line and line.split()[0] in ("whoosh", "transition"):
            swell = float(line.split(" swell ")[1].split("s")[0])
            anchor = float(line.split(" anchor ")[1].split("s")[0])
            errors.append(abs(swell - anchor))
    results["whoosh_peak_error_ms_max"] = round(1000 * max(errors), 1)

    words = mock_words(rng)
    soundfile.write(work / "voice_cut.wav", mock_voice(rng, words).astype(np.float32), SAMPLE_RATE, subtype="PCM_24")
    soundfile.write(work / "voice.wav", soundfile.read(work / "voice_cut.wav")[0].astype(np.float32), SAMPLE_RATE, subtype="FLOAT")
    soundfile.write(work / "bed.wav", mock_bed(rng).astype(np.float32), SAMPLE_RATE, subtype="PCM_24")
    (work / "words.out.json").write_text(json.dumps([{k: v for k, v in w.items() if k != "final"} for w in words]))
    report = {"input": {"path": str(work / "voice_cut.wav"), "sha256": sha256_file(work / "voice_cut.wav")}, "output": {"path": str(work / "voice.wav"), "sha256": sha256_file(work / "voice.wav")}, "gates": {"length": True, "alignment": True, "floor": True}}
    (work / "voice.report.json").write_text(json.dumps(report))
    land = round(8.0 * FPS) / FPS
    (work / "3d").mkdir(exist_ok=True)
    (work / "3d" / "spam3d.json").write_text(json.dumps({"beat": "spam3d", "composition": "EnvelopeToSpam3D", "from": 7.4, "to": 9.4, "fps": FPS, "frames": 50, "hash": "mock", "gl": "swangle", "renderSec": 0.0,
                                                          "events": [{"id": "land", "t": land, "kind": "impact"}, {"id": "glint", "t": land + 0.6, "kind": "glint"}]}))
    beats = [{"id": "hook", "from": 0.0, "to": 3.0}, {"id": "body", "from": 3.0, "to": 7.4}, {"id": "spam3d", "component": "VideoInsert", "from": 7.4, "to": 9.4}, {"id": "steps", "from": 9.4, "to": 26.0}, {"id": "end", "from": 26.0, "to": DURATION}]
    (work / "beatmap.json").write_text(json.dumps({"beats": beats}))
    cues = [{"id": "c01", "beat": "hook", "category": "impact", "visual": "hook slam", "allow_on_word": True},
            {"id": "c02", "event": "spam3d.land", "category": "impact", "visual": "3D land"},
            {"id": "c03", "event": "spam3d.land", "event_offset": -1 / FPS, "category": "whoosh", "layer_of": "c02", "visual": "3D land"},
            {"id": "c04", "event": "spam3d.glint", "category": "pop", "level_lu": -12, "visual": "3D glint"},
            {"id": "c05", "beat": "end", "offset": -1.45, "category": "riser", "visual": "build"},
            {"id": "c06", "beat": "end", "category": "impact", "visual": "logo", "allow_on_word": True}]
    cues += [{"id": f"p{i:02d}", "beat": "steps", "offset": 1.0 + 1.5 * i, "category": ("pop", "tick", "whoosh", "transition")[i % 4], "visual": "mock card"} for i in range(10)]
    (work / "sfx_cues.json").write_text(json.dumps({"fps": FPS, "beats": {b["id"]: b["from"] for b in beats}, "cues": cues}))
    run([SCRIPTS / "sfx_cues.py", "place", "--cues", work / "sfx_cues.json", "--library", work / "kit_a" / "manifest.json", "--beats", work / "beatmap.json", "--words", work / "words.out.json",
         "--events", str(work / "3d" / "*.json"), "--voice", work / "voice.wav", "--allow-violations", "--out", work / "sfx_placements.json"])
    placements = {p["id"]: p for p in load_json(work / "sfx_placements.json")["placements"]}
    results["event_cue_on_land"] = abs(placements["c02"]["anchor_time"] - land) < 1e-6 and placements["c03"]["anchor_frame"] == round(land * FPS) - 1
    results["glint_capped"] = placements["c04"]["level_lu_target"] == -16.0

    common = ["--voice", work / "voice.wav", "--voice-report", work / "voice.report.json", "--music", work / "bed.wav", "--sfx", work / "sfx_placements.json", "--words", work / "words.out.json",
              "--beats", work / "beatmap.json", "--duration", DURATION, "--bed-lift", "26.0:4", "--dropout", "15.0:15.5"]
    for mode in ("words", "sidechain"):
        out = work / mode
        run([SCRIPTS / "mix.py", *common, "--duck-mode", mode, "--out-pre", out / "mix_pre.wav", "--out", out / "mix.wav", "--report", out / "report.json", "--cue-sheet", out / "cue_sheet.md", "--stems-dir", out / "stems"])
        mix = load_json(out / "report.json")
        results[f"{mode}_gates"] = all(mix["gates"].values())
        results[f"{mode}_span_gain_range_db_max"] = mix["ducking"]["envelope"]["span_gain_range_db_max"]
        results[f"{mode}_lu_delta_max"] = mix["sfx"]["lu_delta_max"]
    mismatch = run([SCRIPTS / "mix.py", "--voice", work / "voice_cut.wav", "--voice-report", work / "voice.report.json", "--music", work / "bed.wav", "--words", work / "words.out.json",
                    "--duration", DURATION, "--out-pre", work / "stale_pre.wav", "--out", work / "stale.wav"], expect=2)
    results["guard_mismatch_exits_2"] = "VOICE GUARD" in mismatch and "sha256" in mismatch
    moved = {**report, "input": {**report["input"], "path": str(work / "moved" / "voice_cut.wav")}}
    (work / "voice.moved.report.json").write_text(json.dumps(moved))
    unchecked = run([SCRIPTS / "mix.py", "--voice", work / "voice.wav", "--voice-report", work / "voice.moved.report.json", "--music", work / "bed.wav", "--words", work / "words.out.json",
                     "--duration", DURATION, "--out-pre", work / "moved_pre.wav", "--out", work / "moved.wav"], expect=2)
    results["guard_unresolved_cut_exits_2"] = "VOICE GUARD" in unchecked and "does not exist" in unchecked
    short = work / "short"
    run([SCRIPTS / "mix.py", "--voice", work / "voice.wav", "--voice-report", work / "voice.report.json", "--music", work / "bed.wav", "--words", work / "words.out.json",
         "--duration", 8.0, "--out-pre", short / "mix_pre.wav", "--out", short / "mix.wav", "--report", short / "report.json"])
    short_report = load_json(short / "report.json")
    results["short_duration_gates"] = all(short_report["gates"].values()) and short_report["word_margins"]["min_db"] is not None

    checks = {
        "kit_identical": results["kit_identical"],
        "whoosh_peak_within_5ms": results["whoosh_peak_error_ms_max"] <= 5.0,
        "event_cue_on_land": results["event_cue_on_land"],
        "glint_capped": results["glint_capped"],
        "words_gates": results["words_gates"],
        "sidechain_gates": results["sidechain_gates"],
        "words_span_range_under_3db": results["words_span_gain_range_db_max"] is not None and results["words_span_gain_range_db_max"] <= 3.0,
        "lu_within_1": results["words_lu_delta_max"] is not None and results["words_lu_delta_max"] <= 1.0,
        "guard_mismatch_exits_2": results["guard_mismatch_exits_2"],
        "guard_unresolved_cut_exits_2": results["guard_unresolved_cut_exits_2"],
        "words_past_duration_ignored": results["short_duration_gates"],
    }
    print(json.dumps(results, indent=1))
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    temp.cleanup()
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
