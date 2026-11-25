import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2]
RAW = "@raw"

STAGES = [
    {"id": "probe", "stage": "1", "inputs": [RAW], "outputs": ["ingest/probe.json"],
     "command": 'python $SKILLS/reel-ingest/scripts/probe.py "$RAW"/*.MP4 --out ingest/probe.json'},
    {"id": "rotation", "stage": "1", "inputs": [RAW], "outputs": ["qa/stage1/rotation_check.jpg"],
     "command": 'python $SKILLS/reel-ingest/scripts/rotation_check.py "$RAW"/*.MP4 --out qa/stage1/rotation_check.jpg'},
    {"id": "frame_metrics", "stage": "1", "inputs": [RAW], "outputs": ["ingest/frame_metrics.json"],
     "command": 'python $SKILLS/reel-ingest/scripts/frame_metrics.py "$RAW"/*.MP4 --model "$MODELS"/face_detection_yunet_2023mar.onnx --rotate 2 --out ingest/frame_metrics.json'},
    {"id": "transcribe", "stage": "1", "inputs": [RAW], "outputs": ["ingest/words_raw.json"],
     "command": 'python $SKILLS/reel-ingest/scripts/transcribe.py "$RAW"/*.MP4 --prompt "Brand. Acronyms." --threads 2 --out ingest/words_raw.json'},
    {"id": "snap", "stage": "1", "inputs": ["ingest/words_raw.json", "ingest/frame_metrics.json"], "outputs": ["ingest/words_snapped.json"],
     "command": "python $SKILLS/reel-ingest/scripts/snap_words.py ingest/words_raw.json --resegment --cache ingest/segment_cache.json --threads 2 --frame-metrics ingest/frame_metrics.json --out ingest/words_snapped.json"},
    {"id": "align", "stage": "1", "inputs": ["ingest/words_snapped.json"], "optional": ["config/pronunciations.json", "config/word_overrides.json"], "outputs": ["ingest/transcript.json"],
     "command": "python $SKILLS/reel-ingest/scripts/align_words.py ingest/words_snapped.json --pronunciations config/pronunciations.json --overrides config/word_overrides.json --out ingest/transcript.json"},
    {"id": "plan_cuts", "stage": "3", "inputs": ["ingest/transcript.json", "ingest/frame_metrics.json", "config/cutlist.json"], "outputs": ["edl.json", "plan_report.json"],
     "command": "python $SKILLS/reel-cut/scripts/plan_cuts.py --transcript ingest/transcript.json --exclusions ingest/frame_metrics.json --config config/cutlist.json --out edl.json --report plan_report.json"},
    {"id": "render_aroll", "stage": "5", "inputs": ["edl.json", "config/grade.json"], "outputs": ["aroll.mp4", "voice_cut.wav"],
     "command": "python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video aroll.mp4 --out-audio voice_cut.wav --threads 4"},
    {"id": "retime", "stage": "5", "inputs": ["edl.json", "ingest/transcript.json"], "outputs": ["words.retimed.json"],
     "command": "python $SKILLS/reel-cut/scripts/retime_words.py --edl edl.json --transcript ingest/transcript.json --out words.retimed.json"},
    {"id": "captions", "stage": "7", "inputs": ["words.retimed.json"], "optional": ["config/corrections.json"], "outputs": ["words.out.json"],
     "command": "python $SKILLS/reel-captions/scripts/apply_corrections.py --words words.retimed.json --corrections config/corrections.json --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json --out words.out.json"},
    {"id": "cues", "stage": "5", "inputs": ["edl.json", "words.out.json"], "optional": ["ingest/frame_metrics.json", "config/cues_config.json"], "outputs": ["cues.json"],
     "command": "python $SKILLS/reel-cut/scripts/build_cues.py --edl edl.json --words words.out.json --frame-metrics ingest/frame_metrics.json --config config/cues_config.json --out cues.json"},
    {"id": "voice", "stage": "6", "inputs": ["voice_cut.wav", "edl.json"], "optional": ["voice_lab/clip_params.json"], "outputs": ["voice.wav", "voice_lab/voice.report.json"],
     "command": "python $SKILLS/voice-clean/scripts/process_voice.py --input voice_cut.wav --output voice.wav --preset dialogue --edl edl.json --words words.out.json --report voice_lab/voice.report.json"},
    {"id": "camera", "stage": "8", "inputs": ["cues.json", "config/shots.json"], "outputs": ["camera_plan.json"],
     "command": "python $SKILLS/reel-motion/scripts/plan_camera.py --cues cues.json --shots config/shots.json --out camera_plan.json"},
    {"id": "beatmap", "stage": "8", "inputs": ["cues.json", "config/beatmap.src.json"], "outputs": ["beatmap.json"],
     "command": "python $SKILLS/reel-motion/scripts/resolve_beatmap.py --cues cues.json --input config/beatmap.src.json --out beatmap.json --extra-sec {extra}"},
    {"id": "props", "stage": "8", "inputs": ["cues.json", "words.out.json", "beatmap.json", "camera_plan.json", "aroll.mp4"], "outputs": ["props.json"],
     "command": 'python $SKILLS/reel-motion/scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll "$PWD/aroll.mp4" --public-dir "$PWD" --extra-sec {extra} --out props.json'},
    {"id": "render3d", "stage": "8b", "inputs": ["beatmap.json", "props.json"], "outputs": ["@3d"],
     "command": "python $SKILLS/reel-3d/scripts/render3d.py --beatmap beatmap.json --props props.json --public-dir . --out-dir 3d"},
    {"id": "gfx", "stage": "8", "inputs": ["props.json", "aroll.mp4", "3d/*.mov"], "outputs": ["out/gfx.mp4"],
     "command": 'bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --out out/gfx.mp4'},
    {"id": "caption_boxes", "stage": "8", "inputs": ["props.json"], "outputs": ["qa/captions_bbox.json"],
     "command": 'bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --caption-boxes --out qa/captions_bbox.json'},
    {"id": "downbeats", "stage": "9", "inputs": ["@music"], "optional": ["beatmap.json"], "outputs": ["music/downbeats.json"],
     "command": "python $SKILLS/reel-sound/scripts/find_downbeats.py {music} --targets 0:3 --duration {duration} --allow-edits --out music/downbeats.json"},
    {"id": "sfx", "stage": "9", "inputs": ["config/sfx_cues.json", "sfx/manifest.json", "beatmap.json", "words.out.json", "voice.wav"], "optional": ["3d/*.json"], "outputs": ["sfx_placements.json"],
     "command": 'python $SKILLS/reel-sound/scripts/sfx_cues.py place --cues config/sfx_cues.json --library sfx/manifest.json --beats beatmap.json --words words.out.json --voice voice.wav --events "3d/*.json" --out sfx_placements.json'},
    {"id": "mix", "stage": "9", "inputs": ["voice.wav", "@music", "music/downbeats.json", "sfx_placements.json", "words.out.json"], "optional": ["voice_lab/voice.report.json", "beatmap.json"], "outputs": ["mix.wav", "mix_pre.wav"],
     "command": "python $SKILLS/reel-sound/scripts/mix.py --voice voice.wav --voice-report voice_lab/voice.report.json --music {music} --music-plan music/downbeats.json --sfx sfx_placements.json --duck-mode words --words words.out.json --beats beatmap.json --duration {duration} --bed-lift {talk_end}:4 --out-pre mix_pre.wav --out mix.wav --report qa/mix_report.json --cue-sheet qa/cue_sheet.md"},
    {"id": "credits", "stage": "9", "inputs": ["sfx/manifest.json", "music/manifest.json", "sfx_placements.json"], "outputs": ["CREDITS.txt"],
     "command": "python $SKILLS/reel-sound/scripts/credits.py --manifest sfx/manifest.json --manifest music/manifest.json --placements sfx_placements.json --used {music} --out CREDITS.txt"},
    {"id": "export", "stage": "10", "inputs": ["out/gfx.mp4", "mix.wav", "edl.json"], "outputs": ["@reel"],
     "command": "python $SKILLS/reel-export/scripts/export.py --video out/gfx.mp4 --audio mix.wav --out-dir out --name {name} --edl edl.json --extra-sec {extra} --cover-time 0.4 --srt words.out.json"},
    {"id": "qa", "stage": "11", "inputs": ["@reel", "qa/captions_bbox.json"], "outputs": ["qa/report.json"],
     "command": 'python $SKILLS/reel-qa/scripts/qa.py --reel {reel} --asr-prompt "Brand. Acronyms." --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json'},
]


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def file_hash(path, algorithm):
    digest = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Work:
    def __init__(self, root, raw, name):
        self.root = Path(root).resolve()
        self.raw = raw
        self.name = name
        self.beatmap = read_json(self.root / "beatmap.json") or {}
        self.props = read_json(self.root / "props.json") or {}
        self.three_hasher = ThreeHasher(self)

    def path(self, *parts):
        return self.root.joinpath(*parts)

    def music(self):
        manifest = read_json(self.path("music/manifest.json")) or {}
        for track in manifest.get("tracks", []):
            if track.get("file") and self.path("music", track["file"]).is_file():
                return f"music/{track['file']}"
        found = sorted(glob.glob(str(self.path("music/bed.*"))))
        return str(Path(found[0]).relative_to(self.root)) if found else None

    def reel(self):
        pattern = re.compile(rf"^{re.escape(self.name)}_v(\d+)\.mp4$")
        versions = [(int(m.group(1)), p) for p in self.path("out").glob(f"{self.name}_v*.mp4") if (m := pattern.match(p.name))]
        return str(max(versions)[1].relative_to(self.root)) if versions else None

    def three_beats(self):
        return [b for b in self.beatmap.get("beats", []) if b.get("component") == "VideoInsert" and isinstance((b.get("props") or {}).get("three"), dict)]

    def expand(self, entry):
        if entry == "@music":
            found = self.music()
            return [found] if found else []
        if entry == "@reel":
            found = self.reel()
            return [found] if found else []
        if entry == "@3d":
            return [f"3d/{b['id']}{ext}" for b in self.three_beats() for ext in (".mov", ".json")]
        if any(ch in entry for ch in "*?["):
            return sorted(str(Path(p).relative_to(self.root)) for p in glob.glob(str(self.path(entry))))
        return [entry]

    def upstream(self, stage):
        files = []
        for entry in stage["inputs"] + stage.get("optional", []):
            if entry != RAW:
                files += self.expand(entry)
        return files

    def mtime(self, rel):
        path = self.path(rel)
        if path.is_dir():
            times = [p.stat().st_mtime for p in path.rglob("*") if p.is_file()]
            return min(times) if times else None
        return path.stat().st_mtime if path.exists() else None

    def exists(self, rel):
        path = self.path(rel)
        return path.is_file() or (path.is_dir() and any(p.is_file() for p in path.rglob("*")))

    def inputs_present(self, stage):
        missing = []
        for entry in stage["inputs"]:
            if entry == RAW:
                if not self.raw:
                    missing.append("raw clips (--raw)")
                continue
            if any(ch in entry for ch in "*?[") and entry.startswith("3d/"):
                continue
            files = self.expand(entry)
            if not files or not all(self.exists(f) for f in files):
                missing.append(entry if entry[0] != "@" else {"@music": "music bed (music/manifest.json or music/bed.*)", "@reel": "out/<name>_vN.mp4"}.get(entry, entry))
        return missing

    def input_files(self, stage):
        files = []
        for entry in stage["inputs"] + stage.get("optional", []):
            if entry == RAW:
                if self.raw:
                    files += sorted(glob.glob(os.path.join(self.raw, "*")))
                continue
            files += [str(self.path(f)) for f in self.expand(entry) if self.exists(f)]
        return files


def load_render3d():
    path = SKILLS_DIR / "reel-3d" / "scripts" / "render3d.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("reel3d_render3d", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (Exception, SystemExit):
        return None
    needed = ("brand_dir", "load_json", "brand_hash", "code_hash", "insert_size", "local_props")
    return module if all(hasattr(module, name) for name in needed) else None


class ThreeHasher:
    def __init__(self, work):
        self.work = work
        self.module = load_render3d()
        self.shared = None

    def expected(self, beat):
        render3d = self.module
        if render3d is None:
            raise ValueError("reel-3d/scripts/render3d.py cannot be loaded to recompute the hash")
        fps = self.work.props.get("fps")
        if not fps:
            raise ValueError("props.json has no fps")
        try:
            if self.shared is None:
                brand_path = render3d.brand_dir()
                brand = render3d.load_json(brand_path / "brand.json")
                self.shared = (brand, render3d.brand_hash(brand_path, brand), render3d.code_hash())
            brand, tokens, code = self.shared
            start = round(beat["from"] * fps)
            frames = round(beat["to"] * fps) - start
            fit, width, height = render3d.insert_size(beat, brand)
            props = render3d.local_props(beat, fps, frames)
        except SystemExit as error:
            raise ValueError(str(error)) from None
        key = {"composition": beat["props"]["three"]["composition"], "props": props, "width": width, "height": height,
               "fps": fps, "frames": frames, "fit": fit, "brand": tokens, "code": code}
        return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def three_state(work, beat):
    meta = read_json(work.path(f"3d/{beat['id']}.json"))
    if meta is None:
        return "STALE", "no 3d json next to the clip"
    three = beat["props"]["three"]
    reasons = []
    if meta.get("composition") != three.get("composition"):
        reasons.append(f"composition {meta.get('composition')} != {three.get('composition')}")
    for key in ("from", "to"):
        if meta.get(key) is None or abs(float(meta[key]) - float(beat[key])) > 1e-3:
            reasons.append(f"{key} {meta.get(key)} != {beat[key]}")
    if beat.get("props", {}).get("src") not in (None, f"3d/{beat['id']}.mov"):
        reasons.append(f"props.src is {beat['props']['src']}, not 3d/{beat['id']}.mov")
    try:
        expected = work.three_hasher.expected(beat)
    except ValueError as error:
        if reasons:
            return "STALE", "; ".join(reasons)
        return "UNKNOWN", f"cannot verify props, brand and code: {error}"
    if meta.get("hash") != expected:
        reasons.append(f"hash {str(meta.get('hash'))[:12]} != {expected[:12]} (three.props, size, fps, brand or reel-3d code changed)")
    return ("STALE", "; ".join(reasons)) if reasons else ("FRESH", f"hash {expected[:12]}")


def output_state(work, stage, rel):
    if not work.exists(rel):
        return "MISSING", ""
    if stage["id"] == "render3d":
        beat = next(b for b in work.three_beats() if rel.startswith(f"3d/{b['id']}."))
        state, reason = three_state(work, beat)
        if rel.endswith(".json") or state != "FRESH":
            return state, reason
        meta_stamp = work.mtime(f"3d/{beat['id']}.json")
        if meta_stamp and work.mtime(rel) + 2 < meta_stamp:
            return "STALE", "clip older than its 3d json"
        return "FRESH", ""
    stamp = work.mtime(rel)
    newer = [f for f in work.input_files(stage) if os.path.getmtime(f) > stamp + 1e-3]
    if newer:
        names = ", ".join(str(Path(f).relative_to(work.root)) if f.startswith(str(work.root)) else Path(f).name for f in newer[:3])
        return "STALE", f"input newer: {names}"
    if rel == "out/gfx.mp4" and work.exists("aroll.mp4"):
        record = work.path("out/gfx.mp4.aroll.md5")
        if not record.is_file():
            return "STALE", "no out/gfx.mp4.aroll.md5 to prove which A-roll it used"
        recorded = record.read_text().split()[0] if record.read_text().split() else ""
        if recorded != file_hash(work.path("aroll.mp4"), "md5"):
            return "STALE", "out/gfx.mp4.aroll.md5 does not match aroll.mp4"
    if rel == "voice.wav" and work.exists("voice_cut.wav"):
        report = read_json(work.path("voice_lab/voice.report.json")) or {}
        expected = (report.get("input") or {}).get("sha256")
        if expected and expected != file_hash(work.path("voice_cut.wav"), "sha256"):
            return "STALE", "voice report input sha256 does not match voice_cut.wav"
    return "FRESH", ""


def fill(command, work):
    duration = work.props.get("durationSec")
    talk_end = None
    ends = [float(b["from"]) for b in work.beatmap.get("beats", []) if b.get("component") == "EndCard"]
    if ends:
        talk_end = min(ends)
    extra = round(duration - talk_end, 3) if duration and talk_end else None
    values = {
        "duration": f"{duration:g}" if duration else "<video seconds>",
        "talk_end": f"{talk_end:g}" if talk_end is not None else "<end card start>",
        "extra": f"{extra:g}" if extra is not None else "<end card seconds>",
        "music": work.music() or "music/bed.mp3",
        "name": work.name,
        "reel": work.reel() or f"out/{work.name}_v1.mp4",
    }
    return command.format(**values)


def downstream_exists(work, index):
    for stage in STAGES[index + 1:]:
        for entry in stage["outputs"]:
            if any(work.exists(f) for f in work.expand(entry)):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline status of a reel work folder: walks the stage graph of reel-director/references/runbook.md and prints "
                    "FRESH, STALE (an input is newer, an input is itself stale, out/gfx.mp4.aroll.md5 does not match aroll.mp4, "
                    "a 3d/<id>.json hash differs from the one render3d.py computes now from the beat, brand and reel-3d code, or the "
                    "voice report hash does not match voice_cut.wav), UNKNOWN (a 3D clip whose hash cannot be recomputed) or MISSING "
                    "for every output, then the next command.")
    parser.add_argument("--work", default=".", help="reel work folder (default: current directory)")
    parser.add_argument("--raw", help="folder of raw camera clips (enables the ingest stages)")
    parser.add_argument("--name", default="reel", help="delivery name stem, out/<name>_vN.mp4 (default reel)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    work = Work(args.work, args.raw, args.name)
    if not work.root.is_dir():
        raise SystemExit(f"work folder not found: {work.root}")
    rows, next_step, states_by_output = [], None, {}
    for index, stage in enumerate(STAGES):
        outputs = [f for entry in stage["outputs"] for f in work.expand(entry)]
        if stage["id"] == "render3d" and not outputs:
            continue
        if not outputs:
            outputs = [{"@reel": f"out/{args.name}_vN.mp4", "@3d": "3d/<id>.mov"}.get(stage["outputs"][0], stage["outputs"][0])]
        states = []
        upstream = work.upstream(stage)
        stale_inputs = [f for f in upstream if states_by_output.get(f) == "STALE"]
        unknown_inputs = [f for f in upstream if states_by_output.get(f) == "UNKNOWN"]
        for rel in outputs:
            state, reason = output_state(work, stage, rel) if "<" not in rel and "vN" not in rel else ("MISSING", "")
            if state == "FRESH" and stale_inputs:
                state, reason = "STALE", f"upstream stale: {', '.join(stale_inputs[:3])}"
            elif state == "FRESH" and unknown_inputs:
                state, reason = "UNKNOWN", f"upstream unknown: {', '.join(unknown_inputs[:3])}"
            states_by_output[rel] = state
            states.append(state)
            rows.append({"stage": stage["stage"], "step": stage["id"], "output": rel, "state": state, "reason": reason})
        if next_step is None and any(s in ("STALE", "MISSING") for s in states):
            missing = work.inputs_present(stage)
            fresh_folder = RAW in stage["inputs"] and not args.raw and not downstream_exists(work, index)
            if not missing or fresh_folder:
                next_step = {"stage": stage["stage"], "step": stage["id"], "command": fill(stage["command"], work),
                             "missing_inputs": missing}
    if args.json:
        print(json.dumps({"work": str(work.root), "outputs": rows, "next": next_step}, indent=1))
        return
    width = max(len(r["output"]) for r in rows)
    for r in rows:
        print(f"{r['stage']:>3} {r['step']:14s} {r['output']:{width}s}  {r['state']:7s} {r['reason']}")
    counts = {s: sum(r["state"] == s for r in rows) for s in ("FRESH", "STALE", "UNKNOWN", "MISSING")}
    print(f"\n{counts['FRESH']} fresh, {counts['STALE']} stale, {counts['UNKNOWN']} unknown, {counts['MISSING']} missing")
    if next_step:
        need = f"  (needs: {', '.join(next_step['missing_inputs'])})" if next_step["missing_inputs"] else ""
        print(f"next ({next_step['stage']} {next_step['step']}): {next_step['command']}{need}")
    else:
        print("next: nothing runnable; every output is fresh or waits on a missing input")
    sys.exit(0)


if __name__ == "__main__":
    main()
