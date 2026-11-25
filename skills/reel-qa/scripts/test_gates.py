import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

QA = Path(__file__).resolve().parent / "qa.py"
W, H, FPS = 1080, 1920, 25
BG = np.array([0x5A, 0x60, 0x70], np.uint8)
SKIN = np.array([0xC8, 0x90, 0x70], np.uint8)
NAVY = np.array([0x10, 0x1C, 0x34], np.uint8)
CREAM = np.array([0xF4, 0xF0, 0xE8], np.uint8)
WHITE = np.array([0xF8, 0xFC, 0xFC], np.uint8)


def aroll(rng, box_x):
    frame = np.empty((H, W, 3), np.uint8)
    frame[:] = BG
    frame[530:990, box_x:box_x + 360] = SKIN
    noise = rng.integers(-6, 7, (H, W, 1), dtype=np.int16)
    return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def encode(frames, out, audio_filter, seconds):
    audio = out.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.1:sample_rate=48000:duration={seconds}",
                    "-af", audio_filter, "-ac", "2", str(audio)], check=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio), "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
           "-threads", "2", "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in frames:
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait():
        raise SystemExit(f"ffmpeg failed for {out}")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))


def page(text, first, end, box=(200, 1040, 880, 1110)):
    return {"text": text, "start": first / FPS, "end": end / FPS, "firstFrame": first, "endFrame": end, "bbox": list(box)}


def faults_fixture(work):
    rng = np.random.default_rng(7)
    segments = [(0, 80, 360), (80, 130, 480), (130, 225, 240), (225, 250, 420)]
    frames = []
    for n in range(250):
        box_x = next(x for lo, hi, x in segments if lo <= n < hi)
        frames.append(aroll(rng, box_x))
    frames[50] = np.zeros((H, W, 3), np.uint8)
    frames[100] = np.full((H, W, 3), 255, np.uint8)
    for n in range(151, 170):
        frames[n] = frames[150]
    frames[175] = np.clip(frames[175].astype(np.int16) + 60, 0, 255).astype(np.uint8)
    encode(frames, work / "reel.mp4", "volume=0:enable='between(t,5.0,5.5)',volume=0:enable='gte(t,9.6)'", 10)
    face = {"cx": 540, "cy": 760, "w": 360, "h": 460}
    write(work / "cues.json", {"duration": 10.0, "fps": FPS, "cuts": [3.2, 5.2, 9.0],
                               "segments": [{"index": i, "start": lo / FPS, "end": hi / FPS, "face": face} for i, (lo, hi, _) in enumerate(segments)],
                               "cover": [{"start": 8.0, "end": 9.0, "reason": "mock cover window with no takeover"}]})
    write(work / "qa" / "captions_bbox.json", {"fps": FPS, "pages": [
        page("Your domain", 0, 40), page("yourbrand.com", 40, 80), page("lands in spam", 80, 130),
        page("because nobody set up", 130, 185), page("SPF, DKIM and DMARC.", 185, 225), page("Here is the fix.", 225, 250)]})
    write(work / "qa" / "mix_report.json", {"bed": {"dropouts": [{"start": 5.0, "end": 5.5}]}})
    return {
        "frames": {"status": "fail", "black": [[50, 50]], "white": [[100, 100]], "frozen": [[150, 169]], "pops": [175],
                   "frozen_three": [], "flat_three": [], "empty": []},
        "cover": {"status": "fail", "uncovered": list(range(200, 225))},
        "silence": {"status": "pass"},
        "captions": {"status": "pass", "across": [], "low": []},
    }


def card(frame, n, start):
    frame[1150:1480, 70:950] = NAVY
    grow = min(1.0, (n - start + 1) / 8)
    for row, width in enumerate((620, 480, 540)):
        y = 1210 + row * 90
        frame[y:y + 40, 130:130 + int(width * grow)] = WHITE


def takeover(n, x):
    frame = np.empty((H, W, 3), np.uint8)
    frame[:] = NAVY
    frame[800:1080, x:x + 400] = CREAM
    frame[930:950, x + 40:x + 360] = NAVY
    return frame


def graphics_fixture(work):
    rng = np.random.default_rng(11)
    frames = []
    for n in range(200):
        frame = aroll(rng, 360 if n < 50 else 480)
        if n < 50:
            frame[1000:1150] = CREAM
        if 26 <= n < 65:
            card(frame, n, 26)
        if 66 <= n < 100:
            card(frame, n, 66)
        if 100 <= n < 120:
            card(frame, n, 100)
        if 125 <= n < 175:
            frame = takeover(n, 60 + (min(n, 140) - 125) * 16 + max(0, n - 154) * 16)
        if n == 165:
            frame[:] = NAVY
        frames.append(frame)
    encode(frames, work / "reel.mp4", "anull", 8)
    face = {"cx": 540, "cy": 760, "w": 360, "h": 460}
    write(work / "cues.json", {"duration": 8.0, "fps": FPS, "cuts": [2.0],
                               "segments": [{"index": 0, "start": 0.0, "end": 2.0, "face": face}, {"index": 1, "start": 2.0, "end": 8.0, "face": face}],
                               "cover": []})
    beats = [
        {"id": "C1", "component": "StatCard", "mode": "card", "from": 1.0, "to": 2.6, "props": {}},
        {"id": "C2", "component": "StatCard", "mode": "card", "from": 2.6, "to": 4.0, "props": {}},
        {"id": "C3", "component": "StatCard", "mode": "card", "from": 4.0, "to": 4.8, "props": {}},
        {"id": "T1", "component": "VideoInsert", "mode": "takeover", "from": 5.0, "to": 7.0,
         "props": {"src": "3d/T1.mov", "fit": "full", "three": {"composition": "EnvelopeToSpam3D", "props": {}}}},
    ]
    write(work / "props.json", {"fps": FPS, "durationSec": 8.0, "beats": beats, "accents": [{"text": "yourbrand.com"}, {"text": "spam"}]})
    write(work / "qa" / "captions_bbox.json", {"fps": FPS, "pages": [
        page("Your domain yourbrand.com", 5, 51), page("is fine", 51, 120), page("lands in spam", 130, 160, (260, 1200, 820, 1270)), page("Here is the fix.", 175, 200)]})
    return {
        "frames": {"status": "fail", "black": [], "white": [], "frozen": [], "pops": [165],
                   "frozen_three": [[140, 154]], "flat_three": [165], "empty": [25, 65]},
        "cover": {"status": "pass", "uncovered": []},
        "silence": {"status": "pass"},
        "captions": {"status": "warn", "across": [0], "low": [0]},
    }


def spans(rows):
    return [[row["from"], row["to"]] for row in rows]


def compare(name, report, expected):
    gates = report["gates"]
    frames, cover, captions = gates["frames"], gates["cover"], gates["captions"]
    want_frames = expected["frames"]
    actual = {
        "frames.status": frames["status"],
        "frames.black": spans(frames["black"]), "frames.white": spans(frames["white"]),
        "frames.frozen": spans(frames["frozen"]), "frames.frozen_three": spans(frames["frozen_three"]),
        "frames.pops": frames["pops"], "frames.flat_three": frames["flat_three"],
        "frames.empty": [row["frame"] for row in frames["entrances"] if row["empty"]],
        "cover.status": cover["status"],
        "cover.uncovered": [n for window in cover.get("windows", []) for n in window["uncovered"]],
        "silence.status": gates["silence"]["status"],
        "captions.status": captions["status"],
        "captions.across": [row["page"] for row in captions.get("across_cuts", [])],
        "captions.low": [row["page"] for row in captions.get("accent_contrast", []) if row["low"]],
    }
    wanted = {
        "frames.status": want_frames["status"], "frames.black": want_frames["black"], "frames.white": want_frames["white"],
        "frames.frozen": want_frames["frozen"], "frames.frozen_three": want_frames["frozen_three"], "frames.pops": want_frames["pops"],
        "frames.flat_three": want_frames["flat_three"], "frames.empty": want_frames["empty"],
        "cover.status": expected["cover"]["status"], "cover.uncovered": expected["cover"]["uncovered"],
        "silence.status": expected["silence"]["status"], "captions.status": expected["captions"]["status"],
        "captions.across": expected["captions"]["across"], "captions.low": expected["captions"]["low"],
    }
    failures = 0
    for key, value in wanted.items():
        ok = actual[key] == value
        failures += not ok
        shown = actual[key] if len(str(actual[key])) < 90 else str(actual[key])[:87] + "..."
        print(f"{'ok  ' if ok else 'FAIL'} {name} {key}: {shown}" + ("" if ok else f" (want {value})"))
    return failures


def main():
    parser = argparse.ArgumentParser(description="Build two synthetic reels with known faults and check that the frames, cover, silence and captions gates report exactly those faults.")
    parser.add_argument("--scratch", required=True, help="empty folder for the fixtures and reports")
    parser.add_argument("--keep", action="store_true", help="reuse fixtures already built in --scratch")
    args = parser.parse_args()
    root = Path(args.scratch).resolve()
    failures = 0
    for name, build in (("faults", faults_fixture), ("graphics", graphics_fixture)):
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        expected_path = work / "expected.json"
        if args.keep and expected_path.is_file() and (work / "reel.mp4").is_file():
            expected = json.loads(expected_path.read_text())
        else:
            expected = build(work)
            expected_path.write_text(json.dumps(expected))
        subprocess.run([sys.executable, "-I", str(QA), "--reel", str(work / "reel.mp4"), "--work", str(work),
                        "--only", "frames,silence,cover,captions", "--threads", "2"], check=False)
        failures += compare(name, json.loads((work / "qa" / "report.json").read_text()), expected)
    print("all checks pass" if not failures else f"{failures} checks failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
