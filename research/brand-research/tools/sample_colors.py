import argparse
import json
from collections import Counter

import cv2
import numpy as np


def load_rgb(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"cannot read {path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def to_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def quantize(pixels, step):
    return (pixels // step) * step


def ranked(pixels, step, top):
    counts = Counter(map(tuple, quantize(pixels, step)))
    total = sum(counts.values())
    return [{"hex": to_hex(k), "share": round(v / total * 100, 1)} for k, v in counts.most_common(top)]


def dominant(pixels, args):
    return {"colors": ranked(pixels, args.quant, args.top)}


def foreground(pixels, args):
    coarse = Counter(map(tuple, pixels // 8))
    background = np.array(coarse.most_common(1)[0][0]) * 8 + 4
    distance = np.sqrt(((pixels.astype(np.int32) - background) ** 2).sum(axis=1))
    far = pixels[distance > args.thresh]
    if len(far) == 0:
        return {"background": to_hex(background), "colors": []}
    return {"background": to_hex(background), "colors": ranked(far, args.quant, args.top)}


def darkest(pixels, args):
    order = np.argsort(pixels.astype(np.int32).sum(axis=1))
    return {"colors": ranked(pixels[order[: args.darkest]], args.quant, args.top)}


MODES = {"dominant": dominant, "fg": foreground, "darkest": darkest}


def main():
    parser = argparse.ArgumentParser(description="Sample brand colours from boxes of an RGB image.")
    parser.add_argument("image")
    parser.add_argument("--box", nargs=4, type=int, action="append", required=True, metavar=("X0", "Y0", "X1", "Y1"))
    parser.add_argument("--mode", choices=sorted(MODES), default="dominant")
    parser.add_argument("--quant", type=int, default=4)
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--thresh", type=float, default=110.0)
    parser.add_argument("--darkest", type=int, default=200)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    image = load_rgb(args.image)
    results = []
    for x0, y0, x1, y1 in args.box:
        pixels = image[y0:y1, x0:x1].reshape(-1, 3)
        if len(pixels) == 0:
            raise SystemExit(f"empty box {x0} {y0} {x1} {y1}")
        results.append({"box": [x0, y0, x1, y1], "mode": args.mode, **MODES[args.mode](pixels, args)})

    if args.json:
        print(json.dumps(results, indent=2))
        return
    for result in results:
        colors = ", ".join(f"{c['hex']} {c['share']}%" for c in result["colors"])
        background = f" bg {result['background']}" if "background" in result else ""
        print(f"{' '.join(map(str, result['box'])):24s}{background} {colors}")


if __name__ == "__main__":
    main()
