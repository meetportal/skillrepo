import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchors import ABSOLUTE_PROP_KEYS, AnchorError, load_json, resolve_document

MODES = {"talk", "card", "takeover", "hidden"}
EASES = {"cut", "push", "creep", "hold", "kick", "glide"}
KICK_KEYS = {"px": (0.0, 12.0), "frames": (2, 12), "rollDeg": (0.0, 1.0), "angleDeg": (-360.0, 360.0)}
GLIDE_FRAMES = (12, 24)
DEFAULT_MAX_SCALE = 1.2
MAX_SCALE_LIMIT = 1.3
RELATIVE_TIME_MIN = -0.5
TIME_KEY = re.compile(r"^(t|at|.*At|.*Times|.*Start|.*End)$")
HISTORY_KEYS = {"events", "railEvents"}
ACCENT_STYLES = ("serif", "serifHeavy", "sansUnderline")
CAPTION_OPTIONS = {
    "hookMaxWords": (int, 1, 6),
    "bodyMinWords": (int, 1, 6),
    "bodyMaxWords": (int, 1, 6),
    "mergeAcrossPauseSec": (float, 0.0, 1.0),
    "localScrim": (float, 0.0, 0.4),
}

CAPTION_CENTER_Y = (220, 1500)
LAYOUT_KEYS = {"mode", "window", "background", "captionY", "cardBeats", "takeoverClip"}
SECTION_BAR_KEYS = {"enabled", "sections", "segments", "railEvents", "ranges", "hideDuring", "centerX", "kickerY", "railY", "enterFrames", "exitFrames", "rollFrames"}


def probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    numerator, denominator = stream["r_frame_rate"].split("/")
    return float(stream["duration"]), float(numerator) / float(denominator)


def relative_media_path(media, public_dir):
    media_path = Path(media).resolve()
    public_path = Path(public_dir).resolve()
    try:
        return media_path.relative_to(public_path).as_posix()
    except ValueError:
        sys.exit(f"{media_path} is not inside the public dir {public_path}")


def camera_keys(plan, duration, max_scale, problems):
    keys = plan["keys"] if isinstance(plan, dict) else plan
    cleaned = []
    for key in keys:
        if key["ease"] not in EASES:
            problems.append(f"camera key at {key['t']}: ease {key['ease']!r} invalid")
        if not 0 <= key["t"] <= duration:
            problems.append(f"camera key at {key['t']}: outside 0..{duration}")
        scale = min(max(float(key["scale"]), 1.0), max_scale)
        entry = {"t": float(key["t"]), "scale": scale, "tx": float(key.get("tx", 0)), "ty": float(key.get("ty", 0)), "ease": key["ease"]}
        if key["ease"] == "kick":
            for name, (low, high) in KICK_KEYS.items():
                if name in key:
                    if not low <= key[name] <= high:
                        problems.append(f"kick at {key['t']}: {name} {key[name]} outside {low}..{high}")
                    entry[name] = int(key[name]) if name == "frames" else float(key[name])
        if key["ease"] == "glide" and "frames" in key:
            if not GLIDE_FRAMES[0] <= key["frames"] <= GLIDE_FRAMES[1]:
                problems.append(f"glide at {key['t']}: frames {key['frames']} outside {GLIDE_FRAMES[0]}..{GLIDE_FRAMES[1]}")
            entry["frames"] = int(key["frames"])
        cleaned.append(entry)
    return sorted(cleaned, key=lambda item: item["t"])


def plan_max_scale(plan, requested):
    value = requested if requested is not None else (plan.get("maxScale") if isinstance(plan, dict) else None)
    return float(value) if value is not None else DEFAULT_MAX_SCALE


def time_values(value, key, path, history):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key not in ABSOLUTE_PROP_KEYS:
                yield from time_values(child, child_key, f"{path}.{child_key}", history or child_key in HISTORY_KEYS)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from time_values(item, key, f"{path}[{index}]", history)
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and key is not None and TIME_KEY.match(key):
        yield path, float(value), history


def check_beat_times(beats, problems):
    for beat in beats:
        if not isinstance(beat.get("from"), (int, float)) or not isinstance(beat.get("to"), (int, float)):
            continue
        length = beat["to"] - beat["from"]
        for path, value, history in time_values(beat.get("props", {}), None, "props", False):
            low = float("-inf") if history else RELATIVE_TIME_MIN
            if value < low - 1e-6 or value > length + 1e-6:
                bounds = f"up to {length:.3f}" if history else f"{RELATIVE_TIME_MIN}..{length:.3f}"
                problems.append(
                    f"beat {beat.get('id')}: {path} = {value} s is outside the beat ({bounds} s from its from); "
                    "times inside props are beat-relative"
                )


def check_caption_options(options, problems):
    if not isinstance(options, dict):
        problems.append("captions options must be an object")
        return {}
    unknown = set(options) - set(CAPTION_OPTIONS) - {"accentStyle", "centerY"}
    if unknown:
        problems.append(f"captions options: unknown keys {sorted(unknown)}")
    cleaned = {}
    for name, (kind, low, high) in CAPTION_OPTIONS.items():
        if name not in options:
            continue
        value = options[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind is int and int(value) != value) or not low <= value <= high:
            problems.append(f"captions.{name} {value!r} must be {'an integer' if kind is int else 'a number'} in {low}..{high}")
            continue
        cleaned[name] = kind(value)
    if "accentStyle" in options:
        if options["accentStyle"] not in ACCENT_STYLES:
            problems.append(f"captions.accentStyle {options['accentStyle']!r} not in {ACCENT_STYLES}")
        else:
            cleaned["accentStyle"] = options["accentStyle"]
    if "centerY" in options:
        center = options["centerY"]
        if not isinstance(center, dict) or set(center) - {"talk", "card"}:
            problems.append("captions.centerY must be an object with talk and/or card")
        else:
            for name, value in center.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not CAPTION_CENTER_Y[0] <= value <= CAPTION_CENTER_Y[1]:
                    problems.append(f"captions.centerY.{name} {value!r} must be a number in {CAPTION_CENTER_Y[0]}..{CAPTION_CENTER_Y[1]}")
            cleaned["centerY"] = center
    body_min, body_max = cleaned.get("bodyMinWords", 2), cleaned.get("bodyMaxWords", 4)
    if body_min > body_max:
        problems.append(f"captions.bodyMinWords {body_min} is above bodyMaxWords {body_max}")
    return cleaned


def check_beats(beats, duration, problems):
    seen = set()
    for beat in beats:
        for field in ("id", "component", "from", "to"):
            if field not in beat:
                problems.append(f"beat {beat.get('id', '?')}: missing {field}")
        if beat.get("id") in seen:
            problems.append(f"beat id {beat['id']} duplicated")
        seen.add(beat.get("id"))
        if not 0 <= beat.get("from", -1) < beat.get("to", -1) <= duration + 1e-6:
            problems.append(f"beat {beat.get('id')}: from/to {beat.get('from')}..{beat.get('to')} invalid for duration {duration}")
        beat.setdefault("props", {})
        layer = beat.get("layer", 0)
        if isinstance(layer, bool) or not isinstance(layer, int) or not -10 <= layer <= 10:
            problems.append(f"beat {beat.get('id')}: layer {layer!r} must be an integer in -10..10")
    check_beat_times(beats, problems)


def check_modes(modes, problems):
    for mode in modes:
        if mode["mode"] not in MODES:
            problems.append(f"caption mode {mode['mode']!r} invalid")
        if mode["from"] >= mode["to"]:
            problems.append(f"caption mode {mode['mode']} {mode['from']}..{mode['to']} empty")


def check_words(words, duration, problems):
    previous_start = -1
    for word in words:
        if word["startMs"] < previous_start:
            problems.append(f"word {word['text']!r} at {word['startMs']} ms is out of order")
        if word["endMs"] < word["startMs"]:
            problems.append(f"word {word['text']!r} ends before it starts")
        if word["endMs"] > duration * 1000 + 40:
            problems.append(f"word {word['text']!r} ends after the reel")
        previous_start = word["startMs"]


def normalize_accents(accents, problems):
    normalized = []
    for accent in accents:
        if isinstance(accent, str):
            normalized.append({"text": accent})
        elif isinstance(accent, dict) and isinstance(accent.get("text"), str):
            entry = {"text": accent["text"]}
            if "n" in accent:
                if not isinstance(accent["n"], int) or accent["n"] < 1:
                    problems.append(f"accent {accent!r}: n must be a positive integer")
                    continue
                entry["n"] = accent["n"]
            normalized.append(entry)
        else:
            problems.append(f"accent {accent!r} must be a string or {{text, n?}}")
    return normalized


TOP_LOGO_KEYS = {"enabled", "logo", "widthPx", "centerY", "ranges", "hideDuring", "enterFrames", "exitFrames", "slidePx", "shadow", "scrim"}


def check_top_logo(top_logo, duration, fps, problems):
    if not isinstance(top_logo, dict):
        problems.append("topLogo must be an object")
        return
    unknown = set(top_logo) - TOP_LOGO_KEYS
    if unknown:
        problems.append(f"topLogo: unknown keys {sorted(unknown)}")
    for item in top_logo.get("ranges", []):
        if not 0 <= item.get("from", -1) < item.get("to", -1) <= duration + 1e-6:
            problems.append(f"topLogo range {item.get('from')}..{item.get('to')} invalid for duration {duration}")
    ranges = top_logo.get("ranges", [])
    latest_start = 1.0 - top_logo.get("enterFrames", 8) / fps
    if top_logo.get("enabled") and ranges and min(item.get("from", 0) for item in ranges) > latest_start + 1e-6:
        problems.append(f"topLogo: the first range starts after {latest_start:.2f} s; the logo must be fully in by 1.0 s")


LOOK_KEYS = {"vignette": (0.0, 1.0), "grain": (0.0, 1.0), "grainSizePx": (1.0, 4.0), "seed": (0, 100000)}


def check_look(look, problems):
    if not isinstance(look, dict):
        problems.append("look must be an object")
        return
    unknown = set(look) - set(LOOK_KEYS)
    if unknown:
        problems.append(f"look: unknown keys {sorted(unknown)}")
    for name, (low, high) in LOOK_KEYS.items():
        value = look.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            problems.append(f"look.{name} {value!r} must be a number in {low}..{high}")
    if "seed" in look and isinstance(look["seed"], float) and not look["seed"].is_integer():
        problems.append("look.seed must be an integer")


def check_layout(layout, problems):
    if not isinstance(layout, dict):
        problems.append("layout must be an object")
        return
    unknown = set(layout) - LAYOUT_KEYS
    if unknown:
        problems.append(f"layout: unknown keys {sorted(unknown)}")
    if layout.get("mode", "full") not in ("full", "framed"):
        problems.append(f"layout.mode {layout.get('mode')!r} must be full or framed")
    if layout.get("takeoverClip", "frame") not in ("frame", "window"):
        problems.append(f"layout.takeoverClip {layout.get('takeoverClip')!r} must be frame or window")
    window = layout.get("window", {})
    y0, y1 = window.get("y0", 356), window.get("y1", 1330)
    if not y0 < y1:
        problems.append(f"layout.window y0 {y0} must be above y1 {y1}")
    caption_y = layout.get("captionY", {})
    for name, value in caption_y.items():
        if not y1 < value <= CAPTION_CENTER_Y[1]:
            problems.append(f"layout.captionY.{name} {value} must be below the window (y1 {y1}) and at most {CAPTION_CENTER_Y[1]}")


def check_section_bar(section_bar, duration, problems):
    if not isinstance(section_bar, dict):
        problems.append("sectionBar must be an object")
        return
    unknown = set(section_bar) - SECTION_BAR_KEYS
    if unknown:
        problems.append(f"sectionBar: unknown keys {sorted(unknown)}")
    for item in section_bar.get("sections", []):
        if not isinstance(item, dict) or not isinstance(item.get("label"), str) or not 0 <= item.get("from", -1) <= duration:
            problems.append(f"sectionBar section {item!r} needs from (0..{duration}) and a label string")
        elif "\u2014" in item["label"]:
            problems.append(f"sectionBar label {item['label']!r} contains an em-dash")
    segments = section_bar.get("segments", 3)
    for event in section_bar.get("railEvents", []):
        if not 0 <= event.get("segment", -1) < max(1, segments) or event.get("state") not in ("empty", "active", "marked", "fixed"):
            problems.append(f"sectionBar rail event {event!r} invalid")


def main():
    parser = argparse.ArgumentParser(description="Merge cues, words, beatmap and camera plan into Remotion props for the Reel composition.")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--words", required=True, help="Remotion Caption[] on the output timeline")
    parser.add_argument("--beatmap", required=True, help="{beats, captionModes, accents, captions?, topLogo?, look?, layout?, sectionBar?}; anchors allowed (beat-relative inside beats[].props)")
    parser.add_argument("--camera", required=True, help="camera plan {keys:[{t,scale,tx,ty,ease}]}")
    parser.add_argument("--aroll", required=True, help="A-roll video file inside --public-dir")
    parser.add_argument("--public-dir", required=True, help="directory passed to remotion as --public-dir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-scale", type=float, default=None, help="camera scale ceiling (default: the camera plan's maxScale, else 1.20; at most 1.30)")
    parser.add_argument("--captions-config", help="JSON caption options {hookMaxWords, bodyMinWords, bodyMaxWords, mergeAcrossPauseSec, accentStyle, localScrim}; overrides the beat map's captions block")
    parser.add_argument("--extra-sec", type=float, default=0.0, help="seconds appended after the A-roll (for example an end card)")
    args = parser.parse_args()

    cues = load_json(args.cues)
    try:
        beatmap = resolve_document(load_json(args.beatmap), cues)
    except AnchorError as error:
        sys.exit(f"anchor error: {error}")
    words = load_json(args.words)
    fps = int(cues.get("fps", 25))
    duration = float(cues["duration"]) + args.extra_sec
    problems = []

    aroll_duration, aroll_fps = probe_duration(args.aroll)
    if abs(aroll_fps - fps) > 0.01:
        problems.append(f"A-roll fps {aroll_fps} differs from cues fps {fps}")
    if abs(aroll_duration - float(cues["duration"])) > 1.0 / fps + 1e-6:
        print(f"warning: A-roll duration {aroll_duration:.3f} differs from cues duration {cues['duration']:.3f} by more than one frame")

    plan = load_json(args.camera)
    max_scale = plan_max_scale(plan, args.max_scale)
    if not 1.0 < max_scale <= MAX_SCALE_LIMIT + 1e-9:
        problems.append(f"max scale {max_scale} must be above 1.0 and at most {MAX_SCALE_LIMIT}")
    if max_scale > DEFAULT_MAX_SCALE + 1e-9:
        print(f"warning: max scale {max_scale} is above {DEFAULT_MAX_SCALE}: the upscale softens, check stills at the ceiling")
    camera = camera_keys(plan, duration, max_scale, problems)
    caption_source = beatmap.get("captions", {})
    if args.captions_config:
        caption_source = {**(caption_source if isinstance(caption_source, dict) else {}), **load_json(args.captions_config)}
    caption_options = check_caption_options(caption_source, problems)
    beats = beatmap.get("beats", [])
    modes = beatmap.get("captionModes", [])
    check_beats(beats, duration, problems)
    check_modes(modes, problems)
    check_words(words, duration, problems)
    accents = normalize_accents(beatmap.get("accents", []), problems)
    top_logo = beatmap.get("topLogo")
    if top_logo is not None:
        check_top_logo(top_logo, duration, fps, problems)
    layout = beatmap.get("layout")
    if layout is not None:
        check_layout(layout, problems)
    section_bar = beatmap.get("sectionBar")
    if section_bar is not None:
        check_section_bar(section_bar, duration, problems)
    look = beatmap.get("look")
    if look is not None:
        check_look(look, problems)
    if problems:
        sys.exit("props invalid:\n  " + "\n  ".join(problems))

    props = {
        "aroll": relative_media_path(args.aroll, args.public_dir),
        "durationSec": round(duration, 3),
        "fps": fps,
        "cues": {
            "segments": [
                {"index": s["index"], "clip": s["clip"], "start": s["start"], "end": s["end"], "face": s.get("face")}
                for s in cues["segments"]
            ],
            "cuts": cues["cuts"],
        },
        "camera": camera,
        "cameraLimits": {"maxScale": round(max_scale, 4)},
        "captions": [
            {"text": w["text"], "startMs": w["startMs"], "endMs": w["endMs"], "timestampMs": w.get("timestampMs"), "confidence": w.get("confidence")}
            for w in words
        ],
        "captionModes": modes,
        "beats": beats,
        "accents": accents,
    }
    if caption_options:
        props["captionOptions"] = caption_options
    if top_logo is not None:
        props["topLogo"] = top_logo
    if look is not None:
        props["look"] = look
    if layout is not None:
        props["layout"] = layout
    if section_bar is not None:
        props["sectionBar"] = section_bar
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(props, indent=1) + "\n")
    print(f"wrote {os.path.abspath(args.out)}: {len(words)} words, {len(beats)} beats, {len(camera)} camera keys, {duration:.2f} s")


if __name__ == "__main__":
    main()
