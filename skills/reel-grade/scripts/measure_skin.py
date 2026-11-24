import argparse
import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROTATE_FILTERS = {"none": "", "1": "transpose=1", "2": "transpose=2", "180": "transpose=1,transpose=1"}


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,pix_fmt,color_range,duration,r_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(result.stdout)["streams"][0]
    numerator, denominator = info["r_frame_rate"].split("/")
    info["fps"] = float(numerator) / float(denominator)
    info["full_range"] = info.get("color_range") == "pc" or info["pix_fmt"].startswith("yuvj")
    return info


def frames_yuv(path, rotate, width, height, pix_fmt):
    chain = ",".join(item for item in [ROTATE_FILTERS[rotate], f"format={pix_fmt}"] if item)
    process = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vf", chain, "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"],
        stdout=subprocess.PIPE,
    )
    size = width * height * 3 // 2
    index = 0
    while True:
        data = process.stdout.read(size)
        if len(data) < size:
            break
        yield index, np.frombuffer(data, np.uint8)
        index += 1
    process.stdout.close()
    process.wait()


def split_planes(data, width, height):
    luma = data[:width * height].reshape(height, width)
    quarter = (width // 2) * (height // 2)
    cb = data[width * height:width * height + quarter].reshape(height // 2, width // 2)
    cr = data[width * height + quarter:width * height + 2 * quarter].reshape(height // 2, width // 2)
    return luma, cb, cr


def patch_boxes(landmarks, face):
    _, _, w, h = face
    right_eye, left_eye = landmarks[0:2], landmarks[2:4]
    mouth_y = (landmarks[7] + landmarks[9]) / 2
    eye_y = (right_eye[1] + left_eye[1]) / 2
    cheek_y = (eye_y + mouth_y) / 2
    size = max(8, int(w / 8))
    eye_gap = abs(left_eye[0] - right_eye[0])
    cheeks = [
        (int(right_eye[0] - w / 14 - size / 2), int(cheek_y - size / 2), size, size),
        (int(left_eye[0] + w / 14 - size / 2), int(cheek_y - size / 2), size, size),
    ]
    forehead = (int((right_eye[0] + left_eye[0]) / 2 - eye_gap / 4), int(eye_y - h / 4), max(8, int(eye_gap / 2)), max(6, int(h / 12)))
    return cheeks, forehead


def crop(plane, box, scale=1):
    x, y, w, h = [int(v / scale) for v in box]
    return plane[max(0, y):y + h, max(0, x):x + w]


def skin_patch(luma, cb, cr, box, highlight, min_share=0.6):
    region_y = crop(luma, box)[::2, ::2].astype(np.float64)
    region_cb = crop(cb, box, 2).astype(np.float64)
    region_cr = crop(cr, box, 2).astype(np.float64)
    rows, cols = min(region_y.shape[0], region_cb.shape[0]), min(region_y.shape[1], region_cb.shape[1])
    if rows == 0 or cols == 0:
        return None
    region_y, region_cb, region_cr = region_y[:rows, :cols], region_cb[:rows, :cols], region_cr[:rows, :cols]
    hue = np.degrees(np.arctan2(region_cr - 128, region_cb - 128))
    chroma = np.hypot(region_cr - 128, region_cb - 128)
    skin = (hue > 95) & (hue < 160) & (chroma > 6) & (region_y > 40)
    mask = skin | (region_y >= highlight)
    if mask.mean() < min_share or not skin.any():
        return None
    return {"y": float(np.mean(region_y[mask])), "cb": float(np.median(region_cb[skin])), "cr": float(np.median(region_cr[skin]))}


def normalised(value, full_range):
    return value / 255.0 if full_range else (value - 16.0) / 219.0


def to_native(target_tv, full_range):
    return (target_tv - 16) * 255 / 219 if full_range else target_tv


def suggest_gamma(measured, target_tv, full_range):
    current, wanted = normalised(measured, full_range), normalised(to_native(target_tv, full_range), full_range)
    if not (0 < current < 1 and 0 < wanted < 1):
        return None
    return round(math.log(current) / math.log(wanted), 3)


def sample_frame(data, width, height, full_range, detector, debug_path):
    luma, cb, cr = split_planes(data, width, height)
    bgr = cv2.cvtColor(data[:width * height * 3 // 2].reshape(height * 3 // 2, width), cv2.COLOR_YUV2BGR_I420)
    detector.setInputSize((width // 2, height // 2))
    _, faces = detector.detect(cv2.resize(bgr, (width // 2, height // 2)))
    white = 250 if full_range else 233
    levels = {"y_min": int(luma.min()), "y_max": int(luma.max()), "y_p01": float(np.percentile(luma, 0.1)), "y_p999": float(np.percentile(luma, 99.9)),
              "pct_outside_legal": round(float(((luma < 16) | (luma > 235)).mean() * 100), 3)}
    if faces is None or not len(faces):
        return dict(levels, skin_y=None)
    best = max(faces, key=lambda row: row[2] * row[3])
    face = [int(v * 2) for v in best[:4]]
    landmarks = [int(v * 2) for v in best[4:14]]
    cheeks, forehead = patch_boxes(landmarks, face)
    highlight = 215 if full_range else 200
    cheek_values = [skin_patch(luma, cb, cr, box, highlight) for box in cheeks]
    forehead_value = skin_patch(luma, cb, cr, forehead, highlight)
    usable = [value for value in cheek_values if value] or ([forehead_value] if forehead_value else [])
    if debug_path:
        for box, value in zip(cheeks + [forehead], cheek_values + [forehead_value]):
            cv2.rectangle(bgr, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), (0, 255, 0) if value else (0, 0, 255), 3)
        cv2.imwrite(str(debug_path), cv2.resize(bgr, (width // 3, height // 3)))
    if not usable:
        return dict(levels, skin_y=None, face=face)
    top = bgr[: int(height * 0.15)].reshape(-1, 3).astype(np.float64)
    top = top[(top.mean(1) > 120) & (top.mean(1) < 245)]
    x, y, w, h = face
    face_luma = luma[max(0, y):y + h, max(0, x):x + w]
    skin_cb = float(np.median([value["cb"] for value in usable]))
    skin_cr = float(np.median([value["cr"] for value in usable]))
    return dict(
        levels,
        face=face,
        skin_y=round(float(np.median([value["y"] for value in usable])), 1),
        source="cheeks" if any(cheek_values) else "forehead",
        forehead_y=round(forehead_value["y"], 1) if forehead_value else None,
        skin_hue_deg=round(math.degrees(math.atan2(skin_cr - 128, skin_cb - 128)), 1),
        wall_r_minus_b=round(float(top[:, 2].mean() - top[:, 0].mean()), 1) if len(top) else None,
        pct_face_clipped=round(float((face_luma >= white - 5).mean() * 100), 2) if face_luma.size else None,
        pct_frame_clipped=round(float((luma >= white).mean() * 100), 2),
    )


def summarise(name, samples, full_range, target):
    usable = [s for s in samples if s.get("skin_y") is not None]
    result = {"group": name, "samples": len(samples), "measured": len(usable)}
    if usable:
        skin = float(np.median([s["skin_y"] for s in usable]))
        result.update({
            "skin_y": round(skin, 1),
            "skin_y_p25": round(float(np.percentile([s["skin_y"] for s in usable], 25)), 1),
            "skin_y_p75": round(float(np.percentile([s["skin_y"] for s in usable], 75)), 1),
            "skin_y_full_scale": round(skin if full_range else (skin - 16) * 255 / 219, 1),
            "skin_hue_deg": round(float(np.median([s["skin_hue_deg"] for s in usable])), 1),
            "wall_r_minus_b": round(float(np.median([s["wall_r_minus_b"] for s in usable if s["wall_r_minus_b"] is not None] or [math.nan])), 1),
            "pct_face_clipped": round(float(np.median([s["pct_face_clipped"] for s in usable])), 2),
            "suggested_extra_eq_gamma": suggest_gamma(skin, target, full_range),
        })
    result.update({
        "y_min": min(s["y_min"] for s in samples),
        "y_max": max(s["y_max"] for s in samples),
        "y_p01_min": round(min(s["y_p01"] for s in samples), 1),
        "y_p999_max": round(max(s["y_p999"] for s in samples), 1),
        "pct_outside_legal_max": max(s["pct_outside_legal"] for s in samples),
    })
    return result


def main():
    parser = argparse.ArgumentParser(description="Skin Y (mean over skin and specular pixels, like signalstats YAVG on a clean patch) from cheek patches (YuNet landmarks), hue, wall WB proxy, clipping and levels, in the stream's own code values.")
    parser.add_argument("input")
    parser.add_argument("--model", required=True, help="face_detection_yunet_2023mar.onnx")
    parser.add_argument("--rotate", default="none", choices=list(ROTATE_FILTERS))
    parser.add_argument("--cues", help="cues.json of a rendered A-roll: groups samples per segment and per source clip")
    parser.add_argument("--step", type=float, default=0.2, help="seconds between samples")
    parser.add_argument("--target", type=float, default=150.0, help="target skin Y in tv-range code values")
    parser.add_argument("--tolerance", type=float, default=5.0)
    parser.add_argument("--debug-dir", help="write sampled frames with patches drawn (green used, red rejected)")
    parser.add_argument("--out")
    args = parser.parse_args()
    info = probe(args.input)
    fps, full_range = info["fps"], info["full_range"]
    width, height = (info["height"], info["width"]) if args.rotate in ("1", "2") else (info["width"], info["height"])
    pix_fmt = "yuvj420p" if full_range else "yuv420p"
    step = max(1, int(round(args.step * fps)))
    groups = []
    if args.cues:
        cues = json.loads(Path(args.cues).read_text())
        for segment in cues["segments"]:
            first, last = int(round(segment["start"] * fps)), int(round(segment["end"] * fps))
            frames = list(range(first + 2, last - 2, step)) or [int((first + last) / 2)]
            groups.append({"segment": segment["index"], "clip": segment["clip"], "start": segment["start"], "end": segment["end"], "frames": frames})
    else:
        total = int(float(info.get("duration", 0)) * fps)
        groups.append({"segment": 0, "clip": Path(args.input).name, "start": 0.0, "end": total / fps, "frames": list(range(0, total, step))})
    wanted = {frame: group for group in groups for frame in group["frames"]}
    detector = cv2.FaceDetectorYN.create(args.model, "", (320, 320), 0.7)
    if args.debug_dir:
        Path(args.debug_dir).mkdir(parents=True, exist_ok=True)
    samples = {}
    for index, data in frames_yuv(args.input, args.rotate, width, height, pix_fmt):
        if index in wanted:
            debug_path = Path(args.debug_dir) / f"f{index:05d}.jpg" if args.debug_dir else None
            samples[index] = dict(sample_frame(data, width, height, full_range, detector, debug_path), frame=index, t=round(index / fps, 3))
    report = {"file": str(Path(args.input).resolve()), "range": "full" if full_range else "tv", "target_skin_y_tv": args.target, "segments": [], "clips": []}
    by_clip = {}
    for group in groups:
        group_samples = [samples[f] for f in group["frames"] if f in samples]
        summary = summarise(f"segment {group['segment']}", group_samples, full_range, args.target)
        summary.update({"clip": group["clip"], "start": group["start"], "end": group["end"]})
        report["segments"].append(summary)
        by_clip.setdefault(group["clip"], []).extend(group_samples)
    for clip, clip_samples in by_clip.items():
        summary = summarise(clip, clip_samples, full_range, args.target)
        summary["clip"] = clip
        summary["pass"] = bool(not full_range and "skin_y" in summary and abs(summary["skin_y"] - args.target) <= args.tolerance and summary["y_p01_min"] >= 12 and summary["y_p999_max"] <= 238)
        report["clips"].append(summary)
    report["samples"] = [samples[k] for k in sorted(samples)]
    if args.cues:
        for row in report["segments"]:
            print(f"  seg {row['group'][8:]:>2} {row['clip']} {row['start']:6.2f}-{row['end']:6.2f} skin_y={row.get('skin_y')} (p25 {row.get('skin_y_p25')} p75 {row.get('skin_y_p75')}) n={row['measured']}")
    for row in report["clips"]:
        print(f"{row['clip']}: range={report['range']} skin_y={row.get('skin_y')} (full-scale {row.get('skin_y_full_scale')}) hue={row.get('skin_hue_deg')} wall_R-B={row.get('wall_r_minus_b')} face_clip%={row.get('pct_face_clipped')} Y min/max={row['y_min']}/{row['y_max']} p0.1/p99.9={row['y_p01_min']}/{row['y_p999_max']} outside16-235%={row['pct_outside_legal_max']} gamma_x={row.get('suggested_extra_eq_gamma')} {'PASS' if row['pass'] else 'CHECK'}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
