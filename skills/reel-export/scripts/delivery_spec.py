import json
import re
import struct
import subprocess
from fractions import Fraction
from pathlib import Path

SPEC = {
    "width": 1080,
    "height": 1920,
    "fps": 25,
    "video_codec": "h264",
    "video_profile": "High",
    "video_level": 42,
    "pix_fmt": "yuv420p",
    "color_range": "tv",
    "color_space": "bt709",
    "color_transfer": "bt709",
    "color_primaries": "bt709",
    "audio_codec": "aac",
    "audio_profile": "LC",
    "sample_rate": 48000,
    "channels": 2,
    "av_tolerance_s": 0.040,
    "duration_tolerance_s": 0.040,
}


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_packets", "-show_entries",
         "stream=index,codec_type,codec_name,codec_tag_string,profile,level,width,height,sample_aspect_ratio,"
         "r_frame_rate,avg_frame_rate,pix_fmt,color_range,color_space,color_transfer,color_primaries,"
         "sample_rate,channels,duration,nb_read_packets:format=duration,format_name",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def top_level_atoms(path, limit=64):
    atoms = []
    size_total = Path(path).stat().st_size
    with open(path, "rb") as handle:
        offset = 0
        while offset < size_total and len(atoms) < limit:
            handle.seek(offset)
            header = handle.read(16)
            if len(header) < 8:
                break
            size, kind = struct.unpack(">I4s", header[:8])
            if size == 1:
                size = struct.unpack(">Q", header[8:16])[0]
            elif size == 0:
                size = size_total - offset
            atoms.append(kind.decode("latin-1"))
            if size < 8:
                break
            offset += size
    return atoms


def frame_rate(text):
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return float(value) if value else 0.0


def video_seconds(stream, fps):
    packets = int(stream.get("nb_read_packets") or 0)
    if packets and fps:
        return packets / fps
    return float(stream.get("duration") or 0.0)


def check(path, expected_duration=None, spec=None):
    spec = {**SPEC, **(spec or {})}
    info = probe(path)
    streams = info.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    others = [s for s in streams if s.get("codec_type") not in ("video", "audio")]
    checks = []

    def add(name, passed, actual, expected):
        checks.append({"check": name, "pass": bool(passed), "actual": actual, "expected": expected})

    add("streams", len(videos) == 1 and len(audios) == 1 and not others,
        {"video": len(videos), "audio": len(audios), "other": [s.get("codec_tag_string") or s.get("codec_name") for s in others]},
        "1 video + 1 audio, no data/tmcd")
    metrics = {}
    if videos:
        v = videos[0]
        fps = frame_rate(v.get("r_frame_rate", "0/1"))
        add("video_codec", v.get("codec_name") == spec["video_codec"], v.get("codec_name"), spec["video_codec"])
        add("video_profile", v.get("profile") == spec["video_profile"], v.get("profile"), spec["video_profile"])
        add("video_level", v.get("level") == spec["video_level"], v.get("level"), spec["video_level"])
        add("size", (v.get("width"), v.get("height")) == (spec["width"], spec["height"]),
            f"{v.get('width')}x{v.get('height')}", f"{spec['width']}x{spec['height']}")
        add("sar", v.get("sample_aspect_ratio") in ("1:1", None, "0:1"), v.get("sample_aspect_ratio"), "1:1")
        add("fps", abs(fps - spec["fps"]) < 1e-6, v.get("r_frame_rate"), f"{spec['fps']}/1")
        add("cfr", v.get("avg_frame_rate") == v.get("r_frame_rate"), v.get("avg_frame_rate"), v.get("r_frame_rate"))
        add("pix_fmt", v.get("pix_fmt") == spec["pix_fmt"], v.get("pix_fmt"), spec["pix_fmt"])
        for key in ("color_range", "color_space", "color_transfer", "color_primaries"):
            add(key, v.get(key) == spec[key], v.get(key), spec[key])
        metrics["video_s"] = round(video_seconds(v, fps or spec["fps"]), 4)
        metrics["video_frames"] = int(v.get("nb_read_packets") or 0)
    if audios:
        a = audios[0]
        add("audio_codec", a.get("codec_name") == spec["audio_codec"], a.get("codec_name"), spec["audio_codec"])
        add("audio_profile", a.get("profile") == spec["audio_profile"], a.get("profile"), spec["audio_profile"])
        add("sample_rate", int(a.get("sample_rate") or 0) == spec["sample_rate"], a.get("sample_rate"), spec["sample_rate"])
        add("channels", a.get("channels") == spec["channels"], a.get("channels"), spec["channels"])
        metrics["audio_s"] = round(float(a.get("duration") or 0.0), 4)
    if "video_s" in metrics and "audio_s" in metrics:
        gap = abs(metrics["video_s"] - metrics["audio_s"])
        add("av_duration", gap <= spec["av_tolerance_s"], round(gap, 4), f"<= {spec['av_tolerance_s']}")
    if expected_duration is not None and "video_s" in metrics:
        gap = abs(metrics["video_s"] - expected_duration)
        add("expected_duration", gap <= spec["duration_tolerance_s"],
            metrics["video_s"], f"{expected_duration:.3f} +/- {spec['duration_tolerance_s']}")
    atoms = top_level_atoms(path)
    faststart = "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat")
    add("faststart", faststart, " ".join(atoms[:6]), "moov before mdat")
    return {"pass": all(c["pass"] for c in checks), "checks": checks, "metrics": metrics}


def print_result(result, out=print):
    for item in result["checks"]:
        out(f"  {'PASS' if item['pass'] else 'FAIL'} {item['check']:18s} actual={item['actual']} expected={item['expected']}")


def loudness(path):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    summary = result.stderr.split("Summary:")[-1]
    values = {}
    for key, pattern in (("I", r"I:\s+(-?[\d.]+|-inf) LUFS"), ("LRA", r"LRA:\s+(-?[\d.]+) LU"), ("TP", r"Peak:\s+(-?[\d.]+|-inf) dBFS")):
        match = re.search(pattern, summary)
        values[key] = float(match.group(1)) if match and match.group(1) != "-inf" else None
    return values
