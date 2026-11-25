import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile

SKILLS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(SKILLS_DIR / "reel-grade" / "scripts"))
sys.path.insert(2, str(SKILLS_DIR / "reel-ingest" / "scripts"))
from drift_gate import run_gate
from edl_lib import DEFAULT_RULES, clip_key, load_json, range_audio_clip, to_frame
from media import decode_audio
from tone import tone_expression

SAMPLE_RATE = 48000
LEGAL_CLAMP = "lutyuv=y='if(lt(val,20),17+val*3/20,if(gt(val,226),226+(val-226)*7/29,val))':u='clip(val,16,240)':v='clip(val,16,240)'"
DEFAULT_GRADE = {"rotate": [], "look": [], "clips": {}, "segments": [], "legal_clamp": True}


def probe_stream(path, selector, entries):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", selector, "-show_entries", f"stream={entries}", "-of", "default=nw=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line)


def as_list(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def clip_grade(grade, path):
    entry = grade["clips"].get(clip_key(path)) or {}
    return entry if isinstance(entry, dict) else {"filters": as_list(entry)}


def matching_segments(grade, path, source_time):
    return [segment for segment in grade["segments"] if segment["clip"] == clip_key(path) and segment["from"] <= source_time < segment["to"]]


def tone_at(clip_entry, segments, source_time):
    base = dict(mid=1.0, high=0.0, black=0.0)
    for layer in [clip_entry.get("tone") or {}] + [segment.get("tone") or {} for segment in segments]:
        base["mid"] *= layer.get("mid", 1.0)
        base["high"] += layer.get("high", 0.0)
        base["black"] += layer.get("black", 0.0)
    for segment in segments:
        keys = sorted(segment.get("mid_keys") or [])
        if keys:
            base["mid"] *= float(np.interp(source_time, [k[0] for k in keys], [k[1] for k in keys]))
    return base


def escape_path(path):
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def video_chain(index, entry, grade, full_range, fps, command_dir):
    path = entry["clip"]
    working = "yuvj420p" if full_range else "yuv420p"
    clip_entry = clip_grade(grade, path)
    held = "v_hold" in entry
    v_in = entry["v_hold"] if held else entry["v_in"]
    frames = to_frame(entry["v_out"], fps) - to_frame(entry["v_in"], fps)
    segments = matching_segments(grade, path, v_in if held else (entry["v_in"] + entry["v_out"]) / 2)
    filters = as_list(grade.get("rotate")) + as_list(clip_entry.get("filters"))
    tones = [tone_at(clip_entry, segments, v_in + (0 if held else k / fps)) for k in range(1 if held else frames)]
    label = f"tone{index}"
    if any(tone != tones[0] for tone in tones):
        lines = [f"{k / fps:.4f} lutyuv@{label} y '{tone_expression(full_range=full_range, **tone)}';" for k, tone in enumerate(tones)]
        command_file = Path(command_dir) / f"{label}.cmd"
        command_file.write_text("\n".join(lines) + "\n")
        filters += [f"sendcmd=f='{escape_path(command_file)}'", f"lutyuv@{label}=y='{tone_expression(full_range=full_range, **tones[0])}'"]
    elif tones[0] != dict(mid=1.0, high=0.0, black=0.0):
        filters.append(f"lutyuv=y='{tone_expression(full_range=full_range, **tones[0])}'")
    filters += [item for segment in segments for item in as_list(segment.get("filters"))] + as_list(grade.get("look"))
    pinned = [f"format={working}"]
    for item in filters:
        pinned += [item, f"format={working}"]
    if full_range:
        pinned.append("scale=in_range=full:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709")
    pinned.append("format=yuv420p")
    if grade.get("legal_clamp", True):
        pinned.append(LEGAL_CLAMP)
    if held:
        pinned.append(f"tpad=stop_mode=clone:stop={frames - 1}")
    return ",".join(pinned)


def build_video_graph(edl, grade, command_dir):
    fps = edl["fps"]
    ranges = edl["ranges"]
    inputs = list(dict.fromkeys(entry["clip"] for entry in ranges))
    index_of = {path: number for number, path in enumerate(inputs)}
    lines = []
    full_range = {}
    for path in inputs:
        stream = probe_stream(path, "v:0", "pix_fmt,color_range")
        full_range[path] = stream.get("color_range") == "pc" or stream.get("pix_fmt", "").startswith("yuvj")
        uses = [i for i, entry in enumerate(ranges) if entry["clip"] == path]
        lines.append(f"[{index_of[path]}:v:0]split={len(uses)}" + "".join(f"[vs{i}]" for i in uses))
    for i, entry in enumerate(ranges):
        v_in, v_out = to_frame(entry["v_in"], fps), to_frame(entry["v_out"], fps)
        a_in, a_out = to_frame(entry["a_in"], fps), to_frame(entry["a_out"], fps)
        if v_out - v_in != a_out - a_in:
            raise SystemExit(f"range {i}: video {v_out - v_in} frames != audio {a_out - a_in} frames")
        if "v_hold" in entry:
            held = to_frame(entry["v_hold"], fps)
            trim = f"trim=start_frame={held}:end_frame={held + 1}"
        else:
            trim = f"trim=start_frame={v_in}:end_frame={v_out}"
        chain = video_chain(i, entry, grade, full_range[entry["clip"]], fps, command_dir)
        lines.append(f"[vs{i}]{trim},setpts=PTS-STARTPTS,{chain}[v{i}]")
    lines.append("".join(f"[v{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=1:a=0[vout]")
    return inputs, ";\n".join(lines)


def decode_mono(path):
    return decode_audio(path, sample_rate=SAMPLE_RATE, channels=1).astype(np.float64)


def audio_pieces(edl):
    fps = edl["fps"]
    per_frame = SAMPLE_RATE / fps
    pieces = []
    for entry in edl["ranges"]:
        clip = range_audio_clip(entry)
        start = int(round(to_frame(entry["a_in"], fps) * per_frame))
        end = int(round(to_frame(entry["a_out"], fps) * per_frame))
        if pieces and pieces[-1]["clip"] == clip and pieces[-1]["end"] == start:
            pieces[-1]["end"] = end
        else:
            pieces.append({"clip": clip, "start": start, "end": end})
    return pieces


def equal_power(length):
    theta = (np.arange(length) + 0.5) / length * np.pi / 2
    return np.sin(theta), np.cos(theta)


def render_audio(edl, crossfade, edge_fade):
    pieces = audio_pieces(edl)
    sources = {piece["clip"]: decode_mono(piece["clip"]) for piece in pieces}
    total = sum(piece["end"] - piece["start"] for piece in pieces)
    half = int(round(crossfade * SAMPLE_RATE / 2))
    handles = [0]
    for left, right in zip(pieces[:-1], pieces[1:]):
        handles.append(max(0, min(half, len(sources[left["clip"]]) - left["end"], right["start"])))
    handles.append(0)
    output = np.zeros(total)
    splices = []
    cursor = 0
    for number, piece in enumerate(pieces):
        source = sources[piece["clip"]]
        lead, tail = handles[number], handles[number + 1]
        length = piece["end"] - piece["start"]
        chunk = source[piece["start"] - lead:piece["end"] + tail].copy()
        if len(chunk) < length + lead + tail:
            chunk = np.pad(chunk, (0, length + lead + tail - len(chunk)))
        if lead:
            chunk[:2 * lead] *= equal_power(2 * lead)[0]
        if tail:
            chunk[len(chunk) - 2 * tail:] *= equal_power(2 * tail)[1]
        begin = cursor - lead
        output[begin:begin + len(chunk)] += chunk[:total - begin]
        if number:
            splices.append({"at": round(cursor / SAMPLE_RATE, 4), "crossfade_ms": round(2 * lead * 1000 / SAMPLE_RATE, 1)})
        cursor += length
    fade = int(round(edge_fade * SAMPLE_RATE))
    if fade:
        output[:fade] *= np.linspace(0, 1, fade)
        output[-fade:] *= np.linspace(1, 0, fade)
    return output, splices


def main():
    parser = argparse.ArgumentParser(description="Render the cut A-roll (graded, tv range, video only) in one ffmpeg filter_complex and the cut dialogue WAV sample-exactly with equal-power crossfades at every audio splice.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--grade", help="grade JSON: rotate, look, clips{name: {tone, filters}}, segments[{clip, from, to, tone, mid_keys, filters}] in source seconds")
    parser.add_argument("--out-video", required=True)
    parser.add_argument("--out-audio", required=True)
    parser.add_argument("--crossfade", type=float, default=DEFAULT_RULES["crossfade"], help="equal-power crossfade length at every audio splice, centred on the splice, using source handles")
    parser.add_argument("--edge-fade", type=float, default=0.005, help="fade at the very start and end of the reel")
    parser.add_argument("--crf", type=int, default=14)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--gop", type=int, default=25)
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--graph-out", help="where to keep the filter graph script (default next to the video)")
    parser.add_argument("--threads", type=int, help="cap the ffmpeg encoder and filter threads (for a shared machine); default uses every core")
    args = parser.parse_args()
    edl = load_json(args.edl)
    grade = dict(DEFAULT_GRADE, **(load_json(args.grade) if args.grade else {}))
    fps = edl["fps"]
    started = time.time()
    audio, splices = render_audio(edl, args.crossfade, args.edge_fade)
    Path(args.out_audio).parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(args.out_audio, audio.astype(np.float32), SAMPLE_RATE, subtype="PCM_24")
    print(f"audio: {len(audio) / SAMPLE_RATE:.4f}s, {len(splices)} crossfaded splices at {[s['at'] for s in splices]}")
    if not args.audio_only:
        graph_path = Path(args.graph_out or Path(args.out_video).with_suffix(".filtergraph.txt"))
        command_dir = graph_path.parent / (graph_path.stem + ".cmd")
        command_dir.mkdir(parents=True, exist_ok=True)
        for stale in command_dir.glob("*.cmd"):
            stale.unlink()
        inputs, graph = build_video_graph(edl, grade, command_dir)
        graph_path.write_text(graph)
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-nostats", "-y"]
        if args.threads:
            command += ["-filter_complex_threads", str(args.threads)]
        for path in inputs:
            command += [*(["-threads", str(args.threads)] if args.threads else []), "-i", path]
        command += [
            "-filter_complex_script", str(graph_path),
            "-map", "[vout]", "-an", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
            "-c:v", "libx264", *(["-threads", str(args.threads)] if args.threads else []), "-preset", args.preset, "-crf", str(args.crf), "-g", str(args.gop),
            "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            "-r", f"{fps:g}", "-fps_mode", "cfr", "-movflags", "+faststart", args.out_video,
        ]
        subprocess.run(command, check=True)
    print(f"rendered in {time.time() - started:.1f}s: {args.out_video} {args.out_audio}")
    if not args.audio_only and not run_gate(args.edl, args.out_video, args.out_audio):
        raise SystemExit("drift gate failed")


if __name__ == "__main__":
    main()
