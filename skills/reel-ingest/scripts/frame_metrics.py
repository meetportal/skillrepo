import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import median_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import clip_name, windows_from_mask

ROTATIONS = {
    "none": None,
    "1": cv2.ROTATE_90_CLOCKWISE,
    "2": cv2.ROTATE_90_COUNTERCLOCKWISE,
    "180": cv2.ROTATE_180,
}


def eye_darkness(gray, landmarks, face_width):
    half = max(6, face_width // 14)
    patches = []
    for eye_x, eye_y in (landmarks[0:2], landmarks[2:4]):
        patch = gray[max(0, eye_y - half // 2):eye_y + half // 2, max(0, eye_x - half):eye_x + half]
        if patch.size:
            patches.append(np.percentile(patch, 15))
    return float(np.mean(patches)) if patches else np.nan


def analyse(path, detector, rotation, detect_scale, fps_hint):
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or fps_hint
    rows, previous, eye_values = [], None, []
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if ROTATIONS[rotation] is not None:
            frame = cv2.rotate(frame, ROTATIONS[rotation])
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (width // 4, height // 4))
        sharpness = float(cv2.Laplacian(small, cv2.CV_64F).var())
        motion = float(np.mean(cv2.absdiff(small, previous))) if previous is not None else 0.0
        previous = small
        detect_size = (int(width * detect_scale), int(height * detect_scale))
        detector.setInputSize(detect_size)
        _, faces = detector.detect(cv2.resize(frame, detect_size))
        face, landmarks, eyes = None, None, np.nan
        if faces is not None and len(faces):
            best = max(faces, key=lambda row: row[2] * row[3])
            face = [int(round(value / detect_scale)) for value in best[:4]] + [round(float(best[-1]), 3)]
            landmarks = [int(round(value / detect_scale)) for value in best[4:14]]
            eyes = eye_darkness(gray, landmarks, face[2])
        eye_values.append(eyes)
        rows.append({
            "n": index,
            "t": round(index / fps, 3),
            "luma": round(float(small.mean()), 1),
            "sharp": round(sharpness, 1),
            "motion": round(motion, 2),
            "face": face,
            "landmarks": landmarks,
        })
        index += 1
    capture.release()
    return fps, width, height, rows, np.array(eye_values, dtype=np.float64)


def detect_blinks(eye_values, sharpness, fps, min_sharp_ratio):
    usable = ~np.isnan(eye_values) & (sharpness > np.median(sharpness) * min_sharp_ratio)
    if usable.sum() < 10:
        return []
    filled = np.where(usable, eye_values, np.nanmedian(eye_values[usable]))
    deviation = filled - median_filter(filled, 15)
    spread = 1.4826 * float(np.median(np.abs(deviation[usable] - np.median(deviation[usable]))))
    threshold = max(12.0, 5.0 * spread)
    return windows_from_mask((deviation > threshold) & usable, fps, min_frames=1, join_frames=1)


def face_summary(rows, width, height):
    boxes = np.array([row["face"][:4] for row in rows if row["face"]], dtype=np.float64)
    if not len(boxes):
        return None
    centers_x = boxes[:, 0] + boxes[:, 2] / 2
    return {
        "cx_median": round(float(np.median(centers_x)), 1),
        "cx_p5": round(float(np.percentile(centers_x, 5)), 1),
        "cx_p95": round(float(np.percentile(centers_x, 95)), 1),
        "cy_median": round(float(np.median(boxes[:, 1] + boxes[:, 3] / 2)), 1),
        "w_median": round(float(np.median(boxes[:, 2])), 1),
        "top_median": round(float(np.median(boxes[:, 1])), 1),
        "chin_median": round(float(np.median(boxes[:, 1] + boxes[:, 3])), 1),
        "frame_width": width,
        "frame_height": height,
        "detected_ratio": round(len(boxes) / len(rows), 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Per-frame sharpness, motion, YuNet face box/landmarks, blinks, soft and sway windows.")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--model", required=True, help="path to face_detection_yunet_2023mar.onnx")
    parser.add_argument("--rotate", default="none", choices=list(ROTATIONS), help="same rotation as the edit (transpose=2 is '2')")
    parser.add_argument("--out", required=True)
    parser.add_argument("--detect-scale", type=float, default=0.5)
    parser.add_argument("--score", type=float, default=0.7)
    parser.add_argument("--soft-ratio", type=float, default=0.45, help="frames below this share of the clip median sharpness are soft")
    parser.add_argument("--motion-threshold", type=float, default=8.0, help="mean abs frame difference (quarter-res luma) that counts as sway")
    args = parser.parse_args()
    detector = cv2.FaceDetectorYN.create(args.model, "", (320, 320), args.score)
    report = {"rotate": args.rotate, "clips": {}}
    for path in args.inputs:
        fps, width, height, rows, eye_values = analyse(path, detector, args.rotate, args.detect_scale, 25.0)
        sharpness = np.array([row["sharp"] for row in rows])
        motion = np.array([row["motion"] for row in rows])
        median_sharp = float(np.median(sharpness))
        clip = {
            "file": str(Path(path).resolve()),
            "fps": fps,
            "width": width,
            "height": height,
            "frames": len(rows),
            "sharp_median": round(median_sharp, 1),
            "blinks": detect_blinks(eye_values, sharpness, fps, 0.25),
            "soft": windows_from_mask(sharpness < median_sharp * args.soft_ratio, fps, min_frames=2, join_frames=2),
            "motion": windows_from_mask(motion > args.motion_threshold, fps, min_frames=2, join_frames=3),
            "no_face": windows_from_mask(np.array([row["face"] is None for row in rows]), fps, min_frames=1, join_frames=1),
            "face": face_summary(rows, width, height),
            "per_frame": rows,
        }
        report["clips"][clip_name(path)] = clip
        print(f"{clip_name(path)}: {len(rows)} frames {width}x{height} sharp_median={clip['sharp_median']} blinks={clip['blinks']} soft={clip['soft']} motion={clip['motion']} no_face={clip['no_face']}", flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report))


if __name__ == "__main__":
    main()
