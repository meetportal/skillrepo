import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def label(image, text, highlight):
    canvas = image.copy()
    color = (0, 0, 255) if highlight else (0, 0, 0)
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 30), color, -1)
    cv2.putText(canvas, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Extract the first frames and N frames either side of every cut, plus one labelled strip per cut.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--cues", required=True, help="cues.json (uses fps and cuts)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--radius", type=int, default=10)
    parser.add_argument("--first", type=int, default=3)
    parser.add_argument("--tile-width", type=int, default=216)
    parser.add_argument("--columns", type=int, default=10)
    args = parser.parse_args()
    cues = json.loads(Path(args.cues).read_text())
    fps = cues["fps"]
    cut_frames = [int(round(cut * fps)) for cut in cues["cuts"]]
    wanted = {}
    for index in range(args.first):
        wanted.setdefault(index, []).append(("start", index))
    for number, cut in enumerate(cut_frames):
        for frame in range(cut - args.radius, cut + args.radius):
            wanted.setdefault(frame, []).append((f"cut{number:02d}", frame))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tiles = {}
    capture = cv2.VideoCapture(args.video)
    frame_index = 0
    last = max(wanted)
    while frame_index <= last:
        ok, image = capture.read()
        if not ok:
            break
        for group, frame in wanted.get(frame_index, []):
            if group == "start":
                cv2.imwrite(str(out / f"start_f{frame:04d}.png"), image)
            else:
                cv2.imwrite(str(out / f"{group}_f{frame:04d}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
                small = cv2.resize(image, (args.tile_width, int(image.shape[0] * args.tile_width / image.shape[1])))
                cut = cut_frames[int(group[3:])]
                tiles.setdefault(group, []).append(label(small, f"{frame} ({frame - cut:+d}) {frame / fps:.2f}s", frame == cut))
        frame_index += 1
    capture.release()
    for group, images in tiles.items():
        rows = []
        for start in range(0, len(images), args.columns):
            row = images[start:start + args.columns]
            row += [np.zeros_like(images[0])] * (args.columns - len(row))
            rows.append(np.hstack(row))
        cv2.imwrite(str(out / f"{group}_strip.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"wrote {sum(len(v) for v in tiles.values())} cut frames for {len(tiles)} cuts and {args.first} start frames to {out}")
    for number, cut in enumerate(cut_frames):
        print(f"  cut{number:02d} at frame {cut} ({cut / fps:.2f}s)")


if __name__ == "__main__":
    main()
