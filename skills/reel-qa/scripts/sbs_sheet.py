import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
GUTTER, ROW_GAP = 8, 16


def parse_times(text):
    return [float(v) for v in text.split(",") if v.strip()] if text else []


def video_frame(path, t):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(path), "-map", "0:v:0", "-frames:v", "1",
         "-f", "image2pipe", "-c:v", "png", "-"],
        check=True, capture_output=True,
    ).stdout
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None
    if image is None:
        raise SystemExit(f"{path}: no frame at {t:.3f}s")
    return image


def sources(path, times):
    path = Path(path)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_TYPES)
        if not files:
            raise SystemExit(f"{path}: no images")
        labels = [f"{t:.2f}s" for t in times] if len(times) == len(files) else [p.stem for p in files]
        return [(cv2.imread(str(p), cv2.IMREAD_COLOR), label) for p, label in zip(files, labels)]
    if path.suffix.lower() in IMAGE_TYPES:
        return [(cv2.imread(str(path), cv2.IMREAD_COLOR), path.stem)]
    if not times:
        raise SystemExit(f"{path} is a video: give its times")
    return [(video_frame(path, t), f"{t:.2f}s") for t in times]


def labelled(image, text, height):
    width = max(1, round(image.shape[1] * height / image.shape[0]))
    tile = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    scale = max(0.4, height / 900)
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    cv2.rectangle(tile, (0, 0), (tw + 10, th + base + 8), (0, 0, 0), -1)
    cv2.putText(tile, text, (5, th + 4), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    return tile


def row(items, height, name):
    tiles = [labelled(image, f"{name} {label}", height) for image, label in items]
    width = sum(t.shape[1] for t in tiles) + GUTTER * (len(tiles) - 1)
    out = np.full((height, width, 3), 255, np.uint8)
    x = 0
    for tile in tiles:
        out[:, x:x + tile.shape[1]] = tile
        x += tile.shape[1] + GUTTER
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Side-by-side review sheet: our frames on the top row, reference frames on the bottom row, equal height, "
                    "white gutters, a time label on every frame. Frames are read straight from the sources; nothing is copied.")
    parser.add_argument("--ours", required=True, help="our render (video), an image, or a folder of images")
    parser.add_argument("--ours-times", default="", help="comma list of seconds to take from --ours when it is a video")
    parser.add_argument("--ref", help="reference video, image, or folder of images (sorted by name)")
    parser.add_argument("--ref-times", default="", help="comma list of seconds for --ref (default: --ours-times for a video, file names for images)")
    parser.add_argument("--height", type=int, default=640, help="row height in px")
    parser.add_argument("--out", required=True, help="output JPEG, e.g. qa/sbs/sbs_01.jpg")
    args = parser.parse_args()
    ours_times = parse_times(args.ours_times)
    rows = [row(sources(args.ours, ours_times), args.height, "ours")]
    if args.ref:
        ref_times = parse_times(args.ref_times)
        if not ref_times and not Path(args.ref).is_dir() and Path(args.ref).suffix.lower() not in IMAGE_TYPES:
            ref_times = ours_times
        rows.append(row(sources(args.ref, ref_times), args.height, "ref"))
    width = max(r.shape[1] for r in rows)
    sheet = np.full((sum(r.shape[0] for r in rows) + ROW_GAP * (len(rows) - 1), width, 3), 255, np.uint8)
    y = 0
    for r in rows:
        sheet[y:y + r.shape[0], :r.shape[1]] = r
        y += r.shape[0] + ROW_GAP
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{out} {sheet.shape[1]}x{sheet.shape[0]}")


if __name__ == "__main__":
    main()
