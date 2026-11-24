import json
import math
import re
import subprocess
from pathlib import Path

DEFAULT_RULES = {
    "tighten_min": 0.25,
    "optional_min": 0.15,
    "head_pad": 0.06,
    "tail_pad": 0.06,
    "sentence_tail": 0.10,
    "sentence_lead": 0.08,
    "list_marker_tail": 0.20,
    "list_marker_lead": 0.08,
    "clip_head_pad": 0.06,
    "clip_tail_pad": 0.10,
    "min_head_pad": 0.04,
    "min_tail_pad": 0.05,
    "fade": 0.03,
    "edge_energy_margin_db": 15.0,
    "guard_frames": 3,
    "max_offset_frames": 6,
    "exclude_kinds": ["blinks", "soft"],
    "list_markers": ["first", "second", "third", "fourth", "fifth", "next", "finally", "one", "two", "three"],
}


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data, indent=1):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=indent))


def clip_key(path):
    return Path(path).stem


def bare(token):
    return re.sub(r"[^a-z0-9']", "", token.lower())


def ends_sentence(token):
    return token.rstrip().endswith((".", "?", "!"))


def is_list_marker(token, markers):
    return token.rstrip().endswith((",", ":", ".")) and bare(token) in markers


def to_frame_floor(seconds, fps):
    return int(math.floor(seconds * fps + 1e-6))


def to_frame_ceil(seconds, fps):
    return int(math.ceil(seconds * fps - 1e-6))


def to_frame(seconds, fps):
    return int(round(seconds * fps))


def seconds(frames, fps):
    return round(frames / fps, 6)


def media_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    streams = json.loads(result.stdout)["streams"]
    durations = {s["codec_type"]: float(s["duration"]) for s in streams if s.get("duration")}
    return min(durations.get("video", math.inf), durations.get("audio", math.inf))


def windows_hit(frame_start, frame_end, windows, fps):
    for start, end in windows:
        window_start, window_end = to_frame_floor(start, fps), to_frame_ceil(end, fps)
        if frame_start < window_end and window_start < frame_end:
            return True
    return False


def expand_to_edl(ranges, clip_paths, fps):
    audio_spans, video_spans = [], []
    cursor = 0
    offsets = [0] + [r["joint_offset"] for r in ranges[:-1]] + [0]
    for index, item in enumerate(ranges):
        length = item["out"] - item["in"]
        audio_spans.append((cursor, cursor + length, item["clip"], item["in"], index))
        video_start = cursor - offsets[index]
        video_end = cursor + length - offsets[index + 1]
        video_spans.append((video_start, video_end, item["clip"], item["in"] - offsets[index], index))
        cursor += length
    starts = {0} | {s[0] for s in audio_spans} | {s[0] for s in video_spans}
    breakpoints = sorted(point for point in starts if 0 <= point < cursor) + [cursor]
    pieces = []
    for start, end in zip(breakpoints[:-1], breakpoints[1:]):
        audio = next(s for s in audio_spans if s[0] <= start < s[1])
        video = next(s for s in video_spans if s[0] <= start < s[1])
        pieces.append({
            "v_clip": video[2], "v_in": video[3] + start - video[0], "v_out": video[3] + end - video[0],
            "a_clip": audio[2], "a_in": audio[3] + start - audio[0], "a_out": audio[3] + end - audio[0],
            "source": audio[4], "out_start": start, "out_end": end,
        })
    edl_ranges = []
    for piece in pieces:
        source = ranges[piece["source"]]
        entry = {
            "clip": clip_paths[piece["v_clip"]],
            "v_in": seconds(piece["v_in"], fps), "v_out": seconds(piece["v_out"], fps),
            "a_in": seconds(piece["a_in"], fps), "a_out": seconds(piece["a_out"], fps),
            "beat": source.get("beat", ""),
            "quote": "",
        }
        if piece["a_clip"] != piece["v_clip"]:
            entry["a_clip"] = clip_paths[piece["a_clip"]]
        edl_ranges.append(entry)
    return {"fps": fps, "ranges": edl_ranges, "duration": seconds(cursor, fps)}


def range_audio_clip(entry):
    return entry.get("a_clip", entry["clip"])


def video_segments(edl):
    fps = edl["fps"]
    segments, cursor = [], 0
    for entry in edl["ranges"]:
        frames_in, frames_out = to_frame(entry["v_in"], fps), to_frame(entry["v_out"], fps)
        length = frames_out - frames_in
        if segments and segments[-1]["clip"] == entry["clip"] and segments[-1]["src_out"] == frames_in:
            segments[-1]["src_out"] = frames_out
            segments[-1]["out_end"] = cursor + length
        else:
            segments.append({"clip": entry["clip"], "src_in": frames_in, "src_out": frames_out, "out_start": cursor, "out_end": cursor + length})
        cursor += length
    return segments


def audio_segments(edl):
    fps = edl["fps"]
    segments, cursor = [], 0
    for entry in edl["ranges"]:
        frames_in, frames_out = to_frame(entry["a_in"], fps), to_frame(entry["a_out"], fps)
        length = frames_out - frames_in
        clip = range_audio_clip(entry)
        if segments and segments[-1]["clip"] == clip and segments[-1]["src_out"] == frames_in:
            segments[-1]["src_out"] = frames_out
            segments[-1]["out_end"] = cursor + length
        else:
            segments.append({"clip": clip, "src_in": frames_in, "src_out": frames_out, "out_start": cursor, "out_end": cursor + length})
        cursor += length
    return segments


def source_to_output(audio_segs, clip_path, time_s, fps):
    for seg in audio_segs:
        if seg["clip"] != clip_path:
            continue
        src_start, src_end = seg["src_in"] / fps, seg["src_out"] / fps
        if src_start - 1e-6 <= time_s <= src_end + 1e-6:
            return seg["out_start"] / fps + (time_s - src_start)
    return None
