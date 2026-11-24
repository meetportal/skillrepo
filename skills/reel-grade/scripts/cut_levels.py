import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def read_frames(path, wanted, width, height):
    process = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
        stdout=subprocess.PIPE,
    )
    size = width * height * 3 // 2
    index, last = 0, max(wanted)
    while index <= last:
        data = process.stdout.read(size)
        if len(data) < size:
            break
        if index in wanted:
            yield index, np.frombuffer(data, np.uint8)
        index += 1
    process.stdout.close()
    process.kill()
    process.wait()


def patch_median(plane, cx, cy, half):
    region = plane[max(0, int(cy - half)):int(cy + half), max(0, int(cx - half)):int(cx + half)]
    return float(np.median(region)) if region.size else None


def measure(data, width, height, detector):
    luma = data[:width * height].reshape(height, width)
    bgr = cv2.cvtColor(data.reshape(height * 3 // 2, width), cv2.COLOR_YUV2BGR_I420)
    detector.setInputSize((width // 2, height // 2))
    _, faces = detector.detect(cv2.resize(bgr, (width // 2, height // 2)))
    row = {"y_p01": float(np.percentile(luma, 0.1)), "y_p999": float(np.percentile(luma, 99.9)), "y_min": int(luma.min()), "y_max": int(luma.max()),
           "pct_outside_legal": float(((luma < 16) | (luma > 235)).mean() * 100)}
    if faces is None or not len(faces):
        return row
    best = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = [float(v) * 2 for v in best[:4]]
    marks = [float(v) * 2 for v in best[4:14]]
    right_eye, left_eye, nose = marks[0:2], marks[2:4], marks[4:6]
    half = max(4.0, w / 20)
    cheeks = []
    for eye in (right_eye, left_eye):
        wing_x = nose[0] + (eye[0] - nose[0]) * 0.45
        value = patch_median(luma, (eye[0] + wing_x) / 2, (eye[1] + nose[1]) / 2 + h * 0.03, half)
        if value is not None:
            cheeks.append(value)
    black = luma[int(min(height - 2, y + h * 2.7)):int(min(height - 1, y + h * 3.3)), int(x + w * 0.1):int(x + w * 0.9)]
    row.update({
        "cheek_y": float(np.median(cheeks)) if cheeks else None,
        "black_p10": float(np.percentile(black, 10)) if black.size else None,
        "black_p50": float(np.percentile(black, 50)) if black.size else None,
    })
    return row


def median_of(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return round(float(np.median(values)), 1) if values else None


def main():
    parser = argparse.ArgumentParser(description="Grade gate on a rendered A-roll: landmark cheek patch (between the eye and the nose wing) and a dark-clothing patch on the torso (2.7 to 3.3 face heights below the top of the face box), per shot and on both sides of every cut, plus frame levels.")
    parser.add_argument("video")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--model", required=True, help="face_detection_yunet_2023mar.onnx")
    parser.add_argument("--step", type=float, default=0.2)
    parser.add_argument("--edge-frames", type=int, default=3, help="frames measured on each side of a cut")
    parser.add_argument("--target", type=float, default=150.0)
    parser.add_argument("--tolerance", type=float, default=5.0, help="per-clip median cheek Y must sit within target +/- this")
    parser.add_argument("--max-skin-jump", type=float, default=6.0, help="largest cheek Y change across a cut inside one take")
    parser.add_argument("--max-black-jump", type=float, default=6.0, help="largest change of the shot-median dark-patch p50 across any cut (hands pass through the patch, so single frames are not used)")
    parser.add_argument("--min-p01", type=float, default=14.0, help="encoded 0.1st percentile of Y must be at least this (x264 ringing allowance)")
    parser.add_argument("--max-p999", type=float, default=236.0)
    parser.add_argument("--max-outside-pct", type=float, default=0.1, help="largest share of pixels outside 16-235 on any sampled frame, percent")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cues = json.loads(Path(args.cues).read_text())
    fps = cues["fps"]
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", args.video], capture_output=True, text=True, check=True).stdout)["streams"][0]
    width, height = probe["width"], probe["height"]
    step = max(1, int(round(args.step * fps)))
    wanted = {}
    for shot in cues["segments"]:
        first, last = int(round(shot["start"] * fps)), int(round(shot["end"] * fps))
        for frame in list(range(first, last, step)) + list(range(first, min(last, first + args.edge_frames))) + list(range(max(first, last - args.edge_frames), last)):
            wanted[frame] = shot["index"]
    detector = cv2.FaceDetectorYN.create(args.model, "", (320, 320), 0.7)
    samples = {index: dict(measure(data, width, height, detector), frame=index, shot=wanted[index]) for index, data in read_frames(args.video, set(wanted), width, height)}
    shots, clips = [], {}
    for shot in cues["segments"]:
        rows = [samples[f] for f in sorted(samples) if samples[f]["shot"] == shot["index"]]
        summary = {"index": shot["index"], "clip": shot["clip"], "start": shot["start"], "end": shot["end"], "cheek_y": median_of(rows, "cheek_y"), "black_p50": median_of(rows, "black_p50"), "black_p10": median_of(rows, "black_p10")}
        shots.append(summary)
        clips.setdefault(shot["clip"], []).extend(rows)
    cuts = []
    for left, right in zip(cues["segments"][:-1], cues["segments"][1:]):
        end, start = int(round(left["end"] * fps)), int(round(right["start"] * fps))
        before = [samples[f] for f in range(end - args.edge_frames, end) if f in samples]
        after = [samples[f] for f in range(start, start + args.edge_frames) if f in samples]
        left_rows = [s for s in samples.values() if s["shot"] == left["index"]]
        right_rows = [s for s in samples.values() if s["shot"] == right["index"]]
        row = {"at": right["start"], "same_take": left["clip"] == right["clip"],
               "cheek_before": median_of(before, "cheek_y"), "cheek_after": median_of(after, "cheek_y"),
               "black_before": median_of(left_rows, "black_p50"), "black_after": median_of(right_rows, "black_p50")}
        skin_jump = abs(row["cheek_after"] - row["cheek_before"]) if None not in (row["cheek_after"], row["cheek_before"]) else 0.0
        black_jump = abs(row["black_after"] - row["black_before"]) if None not in (row["black_after"], row["black_before"]) else 0.0
        row["ok"] = (not row["same_take"] or skin_jump <= args.max_skin_jump) and black_jump <= args.max_black_jump
        cuts.append(row)
    clip_rows = []
    for clip, rows in clips.items():
        skin = median_of(rows, "cheek_y")
        clip_rows.append({"clip": clip, "cheek_y": skin, "black_p50": median_of(rows, "black_p50"), "ok": skin is not None and abs(skin - args.target) <= args.tolerance})
    all_rows = list(samples.values())
    levels = {"y_p01_min": round(min(r["y_p01"] for r in all_rows), 1), "y_p999_max": round(max(r["y_p999"] for r in all_rows), 1),
              "y_min": min(r["y_min"] for r in all_rows), "y_max": max(r["y_max"] for r in all_rows),
              "pct_outside_legal_max": round(max(r["pct_outside_legal"] for r in all_rows), 4)}
    levels["ok"] = levels["y_p01_min"] >= args.min_p01 and levels["y_p999_max"] <= args.max_p999 and levels["pct_outside_legal_max"] <= args.max_outside_pct
    report = {"target": args.target, "clips": clip_rows, "shots": shots, "cuts": cuts, "levels": levels,
              "pass": all(c["ok"] for c in clip_rows) and all(c["ok"] for c in cuts) and levels["ok"], "samples": [samples[k] for k in sorted(samples)]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    for row in shots:
        print(f"shot {row['index']:2d} {row['clip']} {row['start']:6.2f}-{row['end']:6.2f} cheek {row['cheek_y']} black p50 {row['black_p50']} p10 {row['black_p10']}")
    for row in cuts:
        print(f"cut {row['at']:6.2f} {'same take' if row['same_take'] else 'new take '} cheek {row['cheek_before']} -> {row['cheek_after']} black {row['black_before']} -> {row['black_after']} {'ok' if row['ok'] else 'FAIL'}")
    for row in clip_rows:
        print(f"{row['clip']}: cheek {row['cheek_y']} black {row['black_p50']} {'ok' if row['ok'] else 'FAIL'}")
    print(f"levels: Y {levels['y_min']}-{levels['y_max']} (p0.1 {levels['y_p01_min']}, p99.9 {levels['y_p999_max']}, outside 16-235 at most {levels['pct_outside_legal_max']} % of a frame) {'ok' if levels['ok'] else 'FAIL'}")
    print("PASS" if report["pass"] else "FAIL")


if __name__ == "__main__":
    main()
