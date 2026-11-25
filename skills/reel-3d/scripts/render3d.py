import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SKILL_DIR / "remotion"
BUNDLED_BRAND = SKILL_DIR.parent / "mailinfra-brand"
ASSET_FOLDER = ".reel-3d-brand"
COMPOSITIONS = {"EnvelopeToSpam3D", "DomainBurn3D", "AuthShield3D", "LogoExtrude3D"}
CODE_FILES = ("render.mjs", "package-lock.json", "remotion.config.ts")


def fail(message):
    sys.exit(f"render3d: {message}")


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")


def tree_hash(paths):
    digest = hashlib.sha256()
    for root in paths:
        files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root]
        for file in files:
            digest.update(str(file.relative_to(root.parent if root.is_dir() else root.parent)).encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def code_hash():
    return tree_hash([PROJECT_DIR / "src", *[PROJECT_DIR / name for name in CODE_FILES if (PROJECT_DIR / name).exists()]])


def brand_dir():
    path = Path(os.environ.get("REEL_BRAND") or BUNDLED_BRAND).resolve()
    if not (path / "brand.json").is_file():
        fail(f"no brand.json in {path}")
    return path


def brand_hash(brand_path, brand):
    digest = hashlib.sha256(json.dumps({"colors": brand.get("colors"), "three": brand.get("three"), "logos": brand.get("logos"), "fonts": brand.get("fonts")}, sort_keys=True).encode())
    for sub in ("assets/logos", "assets/fonts"):
        folder = brand_path / sub
        for file in sorted(folder.glob("*")) if folder.is_dir() else []:
            if file.is_file():
                digest.update(file.name.encode())
                digest.update(file.read_bytes())
    return digest.hexdigest()


def is_3d(beat):
    return beat.get("component") == "VideoInsert" and isinstance(beat.get("props", {}).get("three"), dict)


def local_props(beat, fps, frames):
    three = beat["props"]["three"]
    start = round(beat["from"] * fps)
    out = {}
    for key, value in (three.get("props") or {}).items():
        if key.endswith("At") and isinstance(value, (int, float)) and not isinstance(value, bool):
            local = round(value * fps) - start
            if not 0 <= local < frames:
                fail(f"beat {beat['id']}: {key} {value} s is outside the beat ({beat['from']} to {beat['to']} s)")
            out[key[:-2] + "Frame"] = local
        elif key.endswith("At"):
            fail(f"beat {beat['id']}: {key} must be absolute output seconds (resolve anchors first), got {value!r}")
        else:
            out[key] = value
    return out


def insert_size(beat, brand):
    fit = beat["props"].get("fit", "full")
    if fit == "full":
        return fit, brand["layout"]["width"], brand["layout"]["height"]
    if fit != "card":
        fail(f"beat {beat['id']}: fit {fit!r} must be full or card")
    box = beat["props"].get("box") or brand["layout"]["cardBox"]
    return fit, int(round(box["x1"] - box["x0"])), int(round(box["y1"] - box["y0"]))


def ffprobe_frames(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return -1


def ancestors():
    pids = set()
    pid = os.getpid()
    while pid > 1 and pid not in pids:
        pids.add(pid)
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            pid = int(fields[1])
        except (OSError, IndexError, ValueError):
            break
    return pids


def lock_held_by_ancestor(lock):
    try:
        inode = os.stat(lock).st_ino
        rows = Path("/proc/locks").read_text().splitlines()
    except OSError:
        return False
    mine = ancestors()
    for row in rows:
        parts = row.replace("->", "").split()
        if len(parts) >= 6 and parts[1] == "FLOCK" and parts[5].endswith(f":{inode}") and int(parts[4]) in mine and "->" not in row:
            return True
    return False


def locked(command):
    lock = os.environ.get("REEL_RENDER_LOCK")
    if not lock or lock_held_by_ancestor(lock):
        return command
    return ["flock", lock, *command]


def run(command, **kwargs):
    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        fail(f"command failed ({result.returncode}): {' '.join(map(str, command[:6]))} ...")
    return result


def ensure_project():
    if not (PROJECT_DIR / "node_modules").is_dir():
        run(["npm", "ci", "--no-audit", "--no-fund"], cwd=PROJECT_DIR)


def bundle_key(code):
    return hashlib.sha256((code + tree_hash([PROJECT_DIR / "public"])).encode()).hexdigest()


def bundle(code):
    target = PROJECT_DIR / "out" / f"bundle-{bundle_key(code)[:16]}"
    if (target / "index.html").is_file():
        return target
    others = sorted((PROJECT_DIR / "out").glob("bundle-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in others[3:]:
        shutil.rmtree(old, ignore_errors=True)
    print("bundling the reel-3d project")
    run(["npx", "remotion", "bundle", "src/index.ts", f"--out-dir={target}", "--log=error"], cwd=PROJECT_DIR, stdout=subprocess.DEVNULL)
    return target


def stills_frames(frames):
    return sorted({min(frames - 1, 4), frames // 2, max(0, frames - 2)})


def extract_stills(mov, frames, out_dir, beat_id):
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for frame in stills_frames(frames):
        target = out_dir / f"{beat_id}_f{frame:03d}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(mov), "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", str(target)])
        written.append(target)
    return written


def main():
    parser = argparse.ArgumentParser(description="Render every 3D beat (VideoInsert with props.three) of a beat map to <out-dir>/<id>.mov, cached by hash.")
    parser.add_argument("--beatmap", required=True, help="resolved beatmap.json (absolute seconds)")
    parser.add_argument("--props", help="props.json of the reel (for fps)")
    parser.add_argument("--fps", type=float, help="frame rate when no props.json exists yet")
    parser.add_argument("--public-dir", required=True, help="public dir of the reel render; props.src is relative to it")
    parser.add_argument("--out-dir", required=True, help="folder for <id>.mov and <id>.json, usually <public-dir>/3d")
    parser.add_argument("--only", help="comma-separated beat ids")
    parser.add_argument("--stills", action="store_true", help="also write entry+4, mid and exit-2 PNGs to <out-dir>/stills/")
    parser.add_argument("--force", action="store_true", help="render even when the hash is unchanged")
    args = parser.parse_args()

    if args.props:
        fps = load_json(args.props)["fps"]
    elif args.fps:
        fps = args.fps
    else:
        fail("give --props props.json or --fps")
    if isinstance(fps, float) and fps.is_integer():
        fps = int(fps)
    beatmap = load_json(args.beatmap)
    public_dir = Path(args.public_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    only = set(args.only.split(",")) if args.only else None
    beats = [b for b in beatmap.get("beats", []) if is_3d(b) and (only is None or b["id"] in only)]
    if only and len(beats) != len(only):
        fail(f"--only names beats that are not 3D beats: {sorted(only - {b['id'] for b in beats})}")
    if not beats:
        print("no 3D beats (VideoInsert with props.three) in the beat map")
        return

    errors = []
    for beat in beats:
        expected = os.path.relpath(out_dir / f"{beat['id']}.mov", public_dir)
        if beat["props"].get("src") != expected:
            errors.append(f"beat {beat['id']}: props.src is {beat['props'].get('src')!r}, expected {expected!r}")
        composition = beat["props"]["three"].get("composition")
        if composition not in COMPOSITIONS:
            errors.append(f"beat {beat['id']}: three.composition {composition!r} not in {sorted(COMPOSITIONS)}")
    if errors:
        fail("\n".join(errors))

    brand_path = brand_dir()
    brand = load_json(brand_path / "brand.json")
    if "three" not in brand:
        fail(f"{brand_path / 'brand.json'} has no three block")
    tokens = brand_hash(brand_path, brand)
    code = code_hash()
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = []
    for beat in beats:
        start = round(beat["from"] * fps)
        frames = round(beat["to"] * fps) - start
        if frames < 2:
            fail(f"beat {beat['id']} is shorter than 2 frames")
        fit, width, height = insert_size(beat, brand)
        composition = beat["props"]["three"]["composition"]
        props = local_props(beat, fps, frames)
        key = {"composition": composition, "props": props, "width": width, "height": height, "fps": fps, "frames": frames, "fit": fit, "brand": tokens, "code": code}
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        mov = out_dir / f"{beat['id']}.mov"
        meta_path = out_dir / f"{beat['id']}.json"
        meta = load_json(meta_path) if meta_path.is_file() else {}
        cached = not args.force and meta.get("hash") == digest and mov.is_file() and ffprobe_frames(mov) == frames
        jobs.append({"beat": beat, "start": start, "frames": frames, "fit": fit, "width": width, "height": height, "composition": composition, "props": props, "hash": digest, "mov": mov, "meta_path": meta_path, "meta": meta, "cached": cached})

    todo = [job for job in jobs if not job["cached"]]
    if todo:
        ensure_project()
        run(["bash", str(SKILL_DIR / "scripts" / "prepare_public.sh"), str(brand_path)], stdout=subprocess.DEVNULL)
        serve_url = bundle(code)
    concurrency = os.environ.get("REEL_CONCURRENCY", "2")

    for job in jobs:
        beat = job["beat"]
        if job["cached"]:
            print(f"{beat['id']:10s} {job['composition']:18s} cached ({job['frames']} frames, hash {job['hash'][:12]})")
        else:
            input_props = {
                "fps": fps,
                "durationInFrames": job["frames"],
                "width": job["width"],
                "height": job["height"],
                "fit": job["fit"],
                "brand": brand,
                "assetBase": ASSET_FOLDER,
                "beatProps": job["props"],
            }
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                json.dump(input_props, handle)
                props_file = handle.name
            started = time.monotonic()
            try:
                command = locked(["node", "render.mjs", "--serve-url", str(serve_url), "--composition", job["composition"], "--props", props_file, "--out", str(job["mov"]), "--concurrency", concurrency])
                result = run(command, cwd=PROJECT_DIR, capture_output=True, text=True)
            finally:
                os.unlink(props_file)
            lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
            if not lines:
                fail(f"beat {beat['id']}: the renderer printed no result\n{result.stderr[-2000:]}")
            report = json.loads(lines[-1])
            wall_sec = round(time.monotonic() - started, 2)
            render_sec = report["renderSec"]
            count = ffprobe_frames(job["mov"])
            if count != job["frames"]:
                fail(f"beat {beat['id']}: {job['mov'].name} has {count} frames, expected {job['frames']}")
            events = [
                {"id": event["id"], "t": round((job["start"] + event["frame"]) / fps, 4), "kind": event["kind"]}
                for event in report["events"]
            ]
            meta = {
                "beat": beat["id"],
                "composition": job["composition"],
                "from": beat["from"],
                "to": beat["to"],
                "fps": fps,
                "frames": job["frames"],
                "hash": job["hash"],
                "gl": report["gl"],
                "renderSec": render_sec,
                "events": events,
            }
            job["meta_path"].write_text(json.dumps(meta, indent=2) + "\n")
            print(f"{beat['id']:10s} {job['composition']:18s} rendered {job['frames']} frames in {render_sec} s ({render_sec / job['frames']:.3f} s/frame including browser start; {wall_sec} s with lock wait)")
        if args.stills:
            for path in extract_stills(job["mov"], job["frames"], out_dir / "stills", beat["id"]):
                print(f"  still {path}")


if __name__ == "__main__":
    main()
