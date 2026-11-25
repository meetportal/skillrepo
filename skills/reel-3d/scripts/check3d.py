import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from PIL import Image

from render3d import BUNDLED_BRAND, PROJECT_DIR, SKILL_DIR, brand_dir, bundle, code_hash, ensure_project, fail, load_json, locked, run

MOCKS = [
    ("EnvelopeToSpam3D", "full", 34, {}),
    ("DomainBurn3D", "card", 45, {}),
    ("AuthShield3D", "card", 56, {}),
    ("AuthShield3D", "full", 36, {"lockFrame": 21}),
    ("LogoExtrude3D", "full", 24, {}),
]

FROZEN_DIFF = 0.25
FROZEN_RUN = 12
MESH_IOU_MIN = 0.95


def size_for(fit, brand):
    if fit == "full":
        return brand["layout"]["width"], brand["layout"]["height"]
    box = brand["layout"]["cardBox"]
    return box["x1"] - box["x0"], box["y1"] - box["y0"]


def props_file(work, composition, fit, frames, brand, beat_props=None):
    width, height = size_for(fit, brand)
    path = work / f"{composition}_{fit}.props.json"
    path.write_text(
        json.dumps(
            {"fps": 25, "durationInFrames": frames, "width": width, "height": height, "fit": fit, "brand": brand, "assetBase": ".reel-3d-brand", "beatProps": beat_props or {}}
        )
    )
    return path


def render(serve_url, composition, props, extra):
    started = time.monotonic()
    result = run(locked(["node", "render.mjs", "--serve-url", str(serve_url), "--composition", composition, "--props", str(props), *extra]), cwd=PROJECT_DIR, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if not lines:
        fail(f"{composition}: renderer printed no result\n{result.stderr[-1500:]}")
    report = json.loads(lines[-1])
    report["wallSec"] = report["renderSec"]
    report["lockedWallSec"] = round(elapsed, 2)
    return report


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def grey(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def frozen_runs(frames):
    diffs = [float(np.abs(grey(b) - grey(a)).mean()) for a, b in zip(frames, frames[1:])]
    runs, start = [], None
    for i, d in enumerate(diffs + [99.0]):
        if d < FROZEN_DIFF and start is None:
            start = i
        elif d >= FROZEN_DIFF and start is not None:
            if i - start + 1 >= FROZEN_RUN:
                runs.append((start, i))
            start = None
    return diffs, runs


def check_sequences(serve_url, work, brand, only):
    rows = []
    for composition, fit, frames, beat_props in MOCKS:
        if only and composition not in only:
            continue
        props = props_file(work, composition, fit, frames, brand, beat_props)
        tag = f"{composition}_{fit}"
        render(serve_url, composition, props, ["--sequence", str(work / tag / "a")])
        render(serve_url, composition, props, ["--sequence", str(work / tag / "b")])
        mid = frames // 2
        still = render(serve_url, composition, props, ["--stills", str(mid), "--stills-dir", str(work / tag / "still")])
        a = sorted((work / tag / "a").glob("*.png"))
        b = sorted((work / tag / "b").glob("*.png"))
        same = sum(1 for x, y in zip(a, b) if md5(x) == md5(y))
        still_png = next((work / tag / "still").glob("*.png"))
        still_same = md5(still_png) == md5(a[mid])
        diffs, runs = frozen_runs(a)
        mov = work / tag / "insert.mov"
        timed = render(serve_url, composition, props, ["--out", str(mov)])
        per_frame = (timed["wallSec"] - still["wallSec"]) / max(1, frames - 1)
        rows.append(
            {
                "composition": composition,
                "fit": fit,
                "frames": frames,
                "identical": f"{same}/{len(a)}" if len(a) == len(b) else f"{len(a)} vs {len(b)} frames",
                "stillEqualsSequence": still_same,
                "minDiff": round(min(diffs), 3),
                "frozenRuns": runs,
                "movSec": timed["wallSec"],
                "oneFrameSec": still["wallSec"],
                "secPerFrame": round(per_frame, 3),
            }
        )
        if composition == "LogoExtrude3D":
            rows[-1]["meshVsFlatIoU"] = logo_iou(a[-1], a[-5])
        print(json.dumps(rows[-1]))
    return rows


def mask(path, threshold=90):
    return grey(path) > threshold


def iou(a, b):
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 1.0


def logo_iou(final_frame, solid_frame):
    return round(iou(mask(final_frame), mask(solid_frame)), 4)


def check_patch(serve_url, work, brand):
    tokens = ["brandBlueOnDark", "navyPanel", "danger", "success", "accent", "cream"]
    props = props_file(work, "BrandPatch3D", "full", 1, brand, {"tokens": tokens})
    render(serve_url, "BrandPatch3D", props, ["--stills", "0", "--stills-dir", str(work / "patch"), "--out", str(work / "patch" / "patch.mov")])
    png = np.asarray(Image.open(next((work / "patch").glob("*.png"))).convert("RGB")).astype(int)
    decoded_path = work / "patch" / "decoded.png"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(work / "patch" / "patch.mov"), "-frames:v", "1", str(decoded_path)])
    decoded = np.asarray(Image.open(decoded_path).convert("RGB")).astype(int)
    width = png.shape[1]
    rows = []
    for i, token in enumerate(tokens):
        cx = int((i % 2) * 300 + width / 2 - 150)
        cy = int((i // 2) * 300 + 300)
        hexv = brand["colors"][token]
        want = np.array([int(hexv[k : k + 2], 16) for k in (1, 3, 5)])
        got_png = np.median(png[cy - 40 : cy + 40, cx - 40 : cx + 40].reshape(-1, 3), axis=0).astype(int)
        got_mov = np.median(decoded[cy - 40 : cy + 40, cx - 40 : cx + 40].reshape(-1, 3), axis=0).astype(int)
        rows.append({"token": token, "hex": hexv, "png": got_png.tolist(), "pngMaxErr": int(np.abs(got_png - want).max()), "prores": got_mov.tolist(), "proresMaxErr": int(np.abs(got_mov - want).max())})
        print(json.dumps(rows[-1]))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Acceptance checks for the reel-3d compositions on mock props: determinism, still vs sequence, frozen runs, cost per frame, logo hand-off IoU and brand patches.")
    parser.add_argument("--work", help="scratch folder for the renders (default: a new temp folder)")
    parser.add_argument("--only", help="comma-separated composition ids")
    parser.add_argument("--skip-sequences", action="store_true")
    parser.add_argument("--skip-patch", action="store_true")
    parser.add_argument("--report", help="write the results as JSON here")
    args = parser.parse_args()

    work = Path(args.work or tempfile.mkdtemp(prefix="reel3d-check-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    brand_path = brand_dir()
    brand = load_json(brand_path / "brand.json")
    ensure_project()
    run(["bash", str(SKILL_DIR / "scripts" / "prepare_public.sh"), str(brand_path)], stdout=subprocess.DEVNULL)
    serve_url = bundle(code_hash())
    only = set(args.only.split(",")) if args.only else None
    report = {"work": str(work), "brand": "bundled" if brand_path == BUNDLED_BRAND.resolve() else "REEL_BRAND"}
    if not args.skip_sequences:
        report["sequences"] = check_sequences(serve_url, work, brand, only)
    if not args.skip_patch:
        report["patch"] = check_patch(serve_url, work, brand)
    problems = []
    for row in report.get("sequences", []):
        frames = row["frames"]
        if row["identical"] != f"{frames}/{frames}":
            problems.append(f"{row['composition']} {row['fit']}: runs differ ({row['identical']})")
        if not row["stillEqualsSequence"]:
            problems.append(f"{row['composition']} {row['fit']}: still differs from the sequence frame")
        if row["frozenRuns"]:
            problems.append(f"{row['composition']} {row['fit']}: frozen runs {row['frozenRuns']}")
        if row["secPerFrame"] > 0.35:
            problems.append(f"{row['composition']} {row['fit']}: {row['secPerFrame']} s per frame is over 0.35")
        if row.get("meshVsFlatIoU", 1) < MESH_IOU_MIN:
            problems.append(f"LogoExtrude3D: front-on mesh vs flat mark IoU {row['meshVsFlatIoU']} under {MESH_IOU_MIN}")
    for row in report.get("patch", []):
        if row["pngMaxErr"] > 1:
            problems.append(f"patch {row['token']}: PNG off by {row['pngMaxErr']}")
        if row["proresMaxErr"] > 1:
            problems.append(f"patch {row['token']}: ProRes decode off by {row['proresMaxErr']}")
    report["problems"] = problems
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    print("\n".join(problems) if problems else "all checks passed")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
