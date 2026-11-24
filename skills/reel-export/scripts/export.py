import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delivery_spec import SPEC, check, frame_rate, loudness, print_result, probe, video_seconds

CROP_4X5 = (1080, 1350)


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def next_version(out_dir, name):
    pattern = re.compile(rf"^{re.escape(name)}_v(\d+)\.mp4$")
    found = [int(m.group(1)) for p in Path(out_dir).glob(f"{name}_v*.mp4") if (m := pattern.match(p.name))]
    return Path(out_dir) / f"{name}_v{max(found, default=0) + 1}.mp4"


def run(cmd):
    print("$ " + " ".join(shlex.quote(str(c)) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def input_video_facts(path):
    info = probe(path)
    videos = [s for s in info["streams"] if s.get("codec_type") == "video"]
    if not videos:
        raise SystemExit(f"{path}: no video stream")
    v = videos[0]
    fps = frame_rate(v.get("r_frame_rate", "0/1"))
    return v, fps, video_seconds(v, fps)


def encode_command(video, audio, out, duration, preset, crf):
    audio_chain = f"[1:a]apad,atrim=end={duration:.6f},aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]"
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats", "-nostdin", "-n", "-i", video, "-i", audio,
        "-filter_complex", audio_chain,
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "libx264", "-preset", preset, "-profile:v", "high", "-level:v", "4.2", "-crf", str(crf),
        "-maxrate", "16M", "-bufsize", "32M", "-g", str(2 * SPEC["fps"]), "-keyint_min", str(SPEC["fps"]), "-bf", "2",
        "-pix_fmt", "yuv420p", "-r", str(SPEC["fps"]), "-fps_mode", "cfr",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "256k", "-ar", "48000", "-ac", "2",
        "-map_metadata", "-1", "-map_chapters", "-1", "-movflags", "+faststart", out,
    ]


def parse_box(text):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return parts


def export_cover(reel, stem, time_s, keep_box):
    cover = stem.with_name(stem.name + "_cover.jpg")
    grid = stem.with_name(stem.name + "_cover_4x5.jpg")
    sheet = stem.with_name(stem.name + "_cover_check.jpg")
    crop_w, crop_h = CROP_4X5
    top = (SPEC["height"] - crop_h) // 2
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-ss", f"{time_s:.3f}", "-i", reel, "-frames:v", "1", "-q:v", "2"]
    run(base + [cover])
    run(base + ["-vf", f"crop={crop_w}:{crop_h}:0:{top}", grid])
    top_34 = (SPEC["height"] - 1440) // 2
    boxes = [f"drawbox=x=0:y={top}:w={crop_w}:h={crop_h}:color=yellow@0.9:t=6", f"drawbox=x=0:y={top_34}:w=1080:h=1440:color=cyan@0.8:t=4"]
    if keep_box:
        x0, y0, x1, y1 = keep_box
        boxes.append(f"drawbox=x={x0:.0f}:y={y0:.0f}:w={x1 - x0:.0f}:h={y1 - y0:.0f}:color=red@0.9:t=4")
    run(base + ["-vf", ",".join(boxes) + ",scale=540:960", sheet])
    result = {"cover": str(cover), "cover_4x5": str(grid), "check_sheet": str(sheet), "time_s": time_s, "crop_4x5_y": [top, top + crop_h]}
    if keep_box:
        inside = keep_box[1] >= top and keep_box[3] <= top + crop_h and keep_box[0] >= 0 and keep_box[2] <= crop_w
        result["keep_box"] = keep_box
        result["keep_box_inside_4x5"] = inside
    return result


def srt_time(seconds):
    ms = max(0, int(round(seconds * 1000)))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_srt_cues(words, max_chars, max_gap, max_dur, min_dur, tail):
    cues, current = [], []
    for word in words:
        text = word["text"].strip()
        if not text:
            continue
        start, end = word["startMs"] / 1000, word["endMs"] / 1000
        if current:
            joined = " ".join(w[0] for w in current + [(text, start, end)])
            gap = start - current[-1][2]
            sentence_end = current[-1][0][-1:] in ".?!"
            too_long = len(joined) > max_chars or end - current[0][1] > max_dur
            if gap >= max_gap or sentence_end or too_long:
                cues.append(current)
                current = []
        current.append((text, start, end))
    if current:
        cues.append(current)
    out = []
    for index, cue in enumerate(cues):
        start = cue[0][1]
        end = cue[-1][2] + tail
        if end - start < min_dur:
            end = start + min_dur
        if index + 1 < len(cues):
            end = min(end, cues[index + 1][0][1])
        out.append((start, end, " ".join(w[0] for w in cue)))
    return out


def write_srt(words_path, out_path, max_chars):
    words = json.loads(Path(words_path).read_text())
    cues = build_srt_cues(words, max_chars=max_chars, max_gap=0.5, max_dur=4.0, min_dur=0.7, tail=0.2)
    lines = []
    for number, (start, end, text) in enumerate(cues, 1):
        lines += [str(number), f"{srt_time(start)} --> {srt_time(end)}", text, ""]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return len(cues)


def main():
    parser = argparse.ArgumentParser(
        description="Encode the delivery MP4 from the graphics pass and the mastered mix (H.264 High 4.2 CRF 18, AAC 256k 48 kHz stereo, "
                    "BT.709 tv range, faststart), pad or trim audio to the video length (never -shortest), run the ffprobe spec gate, "
                    "and optionally export a cover image and an SRT. Never overwrites: picks <name>_vN.mp4.")
    parser.add_argument("--video", required=True, help="graphics pass, e.g. out/gfx.mp4 (1080x1920, 25 fps, tv range)")
    parser.add_argument("--audio", required=True, help="mastered mix, e.g. mix.wav")
    parser.add_argument("--out-dir", default="out", help="folder for versioned outputs (default out)")
    parser.add_argument("--name", default="reel", help="file stem; output is <name>_vN.mp4 with N one above the highest existing")
    parser.add_argument("--out", help="explicit output path (must not exist) instead of auto versioning")
    parser.add_argument("--expected-duration", type=float, help="seconds the delivery must last (+/- 40 ms)")
    parser.add_argument("--edl", help="edl.json; expected duration = its duration + --extra-sec")
    parser.add_argument("--extra-sec", type=float, default=0.0, help="end card seconds after the A-roll (with --edl)")
    parser.add_argument("--cover-time", type=float, help="seconds of the frame to export as the cover (1080x1920 jpg + 1080x1350 centre crop)")
    parser.add_argument("--keep-box", type=parse_box, help="x0,y0,x1,y1 that must survive the 1080x1350 centre crop (e.g. the hook headline)")
    parser.add_argument("--srt", metavar="WORDS_JSON", help="words.out.json (Remotion Caption[]) to export as <name>_vN.srt")
    parser.add_argument("--srt-max-chars", type=int, default=32, help="max characters per SRT cue (default 32)")
    parser.add_argument("--preset", default="slow", help="x264 preset (slow for delivery; faster presets only for drafts)")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--dry-run", action="store_true", help="print the command and the output name only")
    args = parser.parse_args()

    for path in (args.video, args.audio):
        if not Path(path).is_file():
            raise SystemExit(f"missing input: {path}")
    v, fps, duration = input_video_facts(args.video)
    problems = []
    if (v.get("width"), v.get("height")) != (SPEC["width"], SPEC["height"]):
        problems.append(f"video is {v.get('width')}x{v.get('height')}, expected 1080x1920 (scale in the graphics stage, not here)")
    if abs(fps - SPEC["fps"]) > 1e-6:
        problems.append(f"video is {v.get('r_frame_rate')} fps, expected {SPEC['fps']}")
    if v.get("color_range") not in ("tv", None):
        problems.append(f"video color_range is {v.get('color_range')}; this step never converts range")
    if problems:
        raise SystemExit("input rejected:\n  " + "\n  ".join(problems))

    expected = args.expected_duration
    if expected is None and args.edl:
        expected = json.loads(Path(args.edl).read_text())["duration"] + args.extra_sec
    if expected is not None and abs(expected - duration) > SPEC["duration_tolerance_s"]:
        print(f"WARNING: graphics pass is {duration:.3f}s but the expected duration is {expected:.3f}s (stale render?)")

    if args.out:
        out = Path(args.out)
        if out.exists():
            raise SystemExit(f"{out} exists; never overwrite a delivery, choose a new version")
    else:
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        out = next_version(args.out_dir, args.name)
    cmd = encode_command(args.video, args.audio, out, duration, args.preset, args.crf)
    print(f"output {out} ({duration:.3f}s, {round(duration * fps)} frames)")
    if args.dry_run:
        print(" ".join(shlex.quote(str(c)) for c in cmd))
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    run(cmd)

    result = check(out, expected_duration=expected if expected is not None else duration)
    print(f"spec gate: {'PASS' if result['pass'] else 'FAIL'}")
    print_result(result)
    level = loudness(out)
    print(f"loudness: I {level['I']} LUFS, TP {level['TP']} dBTP, LRA {level['LRA']} LU (target -14 +/- 1, <= -1.5, <= 7)")
    stem = out.with_suffix("")
    sidecar = {
        "output": str(out),
        "inputs": {"video": {"path": str(args.video), "md5": md5(args.video)}, "audio": {"path": str(args.audio), "md5": md5(args.audio)}},
        "duration_s": round(duration, 4),
        "spec_gate": result,
        "loudness": level,
        "command": [str(c) for c in cmd],
    }
    if args.cover_time is not None:
        sidecar["cover"] = export_cover(out, stem, args.cover_time, args.keep_box)
        if sidecar["cover"].get("keep_box_inside_4x5") is False:
            print("FAIL keep box falls outside the 1080x1350 centre crop: move the headline or pick another frame")
            result["pass"] = False
        print(f"cover: {sidecar['cover']['cover']} and {sidecar['cover']['cover_4x5']}; look at {sidecar['cover']['check_sheet']}")
    if args.srt:
        srt = stem.with_suffix(".srt")
        count = write_srt(args.srt, srt, args.srt_max_chars)
        sidecar["srt"] = {"path": str(srt), "cues": count}
        print(f"srt: {srt} ({count} cues)")
    Path(str(stem) + ".json").write_text(json.dumps(sidecar, indent=1) + "\n")
    print(f"sidecar {stem}.json")
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
