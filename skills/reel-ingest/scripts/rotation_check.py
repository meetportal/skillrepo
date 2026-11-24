import argparse
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import TRANSPOSE_FILTERS, clip_name, run


def grab(path, time_s, video_filter, height, scratch):
    target = Path(scratch) / f"frame_{abs(hash((str(path), video_filter, time_s)))}.png"
    chain = ",".join(part for part in [video_filter, f"scale=-2:{height}"] if part)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{time_s:.3f}", "-i", str(path), "-frames:v", "1", "-vf", chain, str(target)])
    return cv2.imread(str(target))


def label(image, text):
    canvas = image.copy()
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 44), (0, 0, 0), -1)
    cv2.putText(canvas, text, (10, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Contact sheet of rotation options per clip (one row per clip).")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", required=True, help="output .jpg")
    parser.add_argument("--time", type=float, default=None, help="seconds into each clip (default: middle)")
    parser.add_argument("--options", default="none,1,2,180,hflip", help=f"comma list from {','.join(TRANSPOSE_FILTERS)}")
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()
    options = [option.strip() for option in args.options.split(",")]
    rows = []
    with tempfile.TemporaryDirectory() as scratch:
        for path in args.inputs:
            time_s = args.time
            if time_s is None:
                duration = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout)
                time_s = duration / 2
            tiles = []
            for option in options:
                tiles.append(label(grab(path, time_s, TRANSPOSE_FILTERS[option], args.height, scratch), f"{clip_name(path)} {option}"))
            row_height = max(tile.shape[0] for tile in tiles)
            padded = [cv2.copyMakeBorder(tile, 0, row_height - tile.shape[0], 0, 8, cv2.BORDER_CONSTANT, value=(40, 40, 40)) for tile in tiles]
            rows.append(np.hstack(padded))
    width = max(row.shape[1] for row in rows)
    sheet = np.vstack([cv2.copyMakeBorder(row, 0, 8, 0, width - row.shape[1], cv2.BORDER_CONSTANT, value=(40, 40, 40)) for row in rows])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(args.out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"wrote {args.out}: rows={len(rows)} options={options}. Pick the option where the subject is upright and background text reads left to right.")


if __name__ == "__main__":
    main()
