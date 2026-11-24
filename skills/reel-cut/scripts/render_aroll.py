import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_gate import run_gate
from edl_lib import clip_key, load_json, range_audio_clip, to_frame

SAMPLE_RATE = 48000
DEFAULT_GRADE = {"rotate": [], "look": [], "clips": {}, "segments": []}


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


def gamma_ramp(keys, v_in):
    keys = sorted(keys)
    source_time = f"(t+{v_in:.6f})"
    terms = [f"{keys[0][1]:.4f}"]
    for (t0, g0), (t1, g1) in zip(keys[:-1], keys[1:]):
        terms.append(f"{g1 - g0:+.4f}*clip(({source_time}-{t0:.3f})/{max(t1 - t0, 1e-3):.3f},0,1)")
    return f"eq=gamma='{''.join(terms)}':eval=frame"


def segment_filters(grade, path, v_in, v_out):
    middle = (v_in + v_out) / 2
    filters = []
    for segment in grade["segments"]:
        if segment["clip"] == clip_key(path) and segment["from"] <= middle < segment["to"]:
            filters += as_list(segment.get("filters"))
            if segment.get("gamma_keys"):
                filters.append(gamma_ramp(segment["gamma_keys"], v_in))
    return filters


def video_chain(path, grade, v_in, v_out, full_range):
    working = "yuvj420p" if full_range else "yuv420p"
    filters = as_list(grade.get("rotate")) + as_list(grade["clips"].get(clip_key(path))) + segment_filters(grade, path, v_in, v_out) + as_list(grade.get("look"))
    pinned = [f"format={working}"]
    for item in filters:
        pinned += [item, f"format={working}"]
    if full_range:
        pinned.append("scale=in_range=full:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709")
    pinned.append("format=yuv420p")
    return ",".join(pinned)


def audio_prefix(path):
    channels = int(probe_stream(path, "a:0", "channels").get("channels", "1"))
    downmix = "pan=mono|c0=0.5*c0+0.5*c1" if channels == 2 else "pan=mono|c0=c0"
    return f"aresample={SAMPLE_RATE},{downmix},aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=mono"


def build_graph(edl, grade, fade):
    fps = edl["fps"]
    ranges = edl["ranges"]
    inputs = list(dict.fromkeys([path for entry in ranges for path in (entry["clip"], range_audio_clip(entry))]))
    index_of = {path: index for index, path in enumerate(inputs)}
    video_uses = {path: [i for i, e in enumerate(ranges) if e["clip"] == path] for path in inputs}
    audio_uses = {path: [i for i, e in enumerate(ranges) if range_audio_clip(e) == path] for path in inputs}
    lines = []
    video_pad, audio_pad = {}, {}
    full_range = {}
    for path in inputs:
        stream = probe_stream(path, "v:0", "pix_fmt,color_range")
        full_range[path] = stream.get("color_range") == "pc" or stream.get("pix_fmt", "").startswith("yuvj")
        number = index_of[path]
        uses = video_uses[path]
        if uses:
            labels = "".join(f"[vs{i}]" for i in uses)
            lines.append(f"[{number}:v:0]split={len(uses)}{labels}")
            video_pad.update({i: f"vs{i}" for i in uses})
        uses = audio_uses[path]
        if uses:
            labels = "".join(f"[as{i}]" for i in uses)
            lines.append(f"[{number}:a:0]{audio_prefix(path)},asplit={len(uses)}{labels}")
            audio_pad.update({i: f"as{i}" for i in uses})
    samples_per_frame = SAMPLE_RATE / fps
    for i, entry in enumerate(ranges):
        v_in, v_out = to_frame(entry["v_in"], fps), to_frame(entry["v_out"], fps)
        a_in, a_out = to_frame(entry["a_in"], fps), to_frame(entry["a_out"], fps)
        if v_out - v_in != a_out - a_in:
            raise SystemExit(f"range {i}: video {v_out - v_in} frames != audio {a_out - a_in} frames")
        chain = video_chain(entry["clip"], grade, entry["v_in"], entry["v_out"], full_range[entry["clip"]])
        lines.append(f"[{video_pad[i]}]trim=start_frame={v_in}:end_frame={v_out},setpts=PTS-STARTPTS,{chain}[v{i}]")
        previous = ranges[i - 1] if i else None
        following = ranges[i + 1] if i + 1 < len(ranges) else None
        joined_before = previous is not None and range_audio_clip(previous) == range_audio_clip(entry) and to_frame(previous["a_out"], fps) == a_in
        joined_after = following is not None and range_audio_clip(following) == range_audio_clip(entry) and to_frame(following["a_in"], fps) == a_out
        duration = (a_out - a_in) / fps
        audio = [f"atrim=start_sample={round(a_in * samples_per_frame)}:end_sample={round(a_out * samples_per_frame)}", "asetpts=PTS-STARTPTS"]
        if not joined_before:
            audio.append(f"afade=t=in:st=0:d={fade}")
        if not joined_after:
            audio.append(f"afade=t=out:st={max(0.0, duration - fade):.6f}:d={fade}")
        lines.append(f"[{audio_pad[i]}]{','.join(audio)}[a{i}]")
    video_labels = "".join(f"[v{i}]" for i in range(len(ranges)))
    audio_labels = "".join(f"[a{i}]" for i in range(len(ranges)))
    lines.append(f"{video_labels}concat=n={len(ranges)}:v=1:a=0[vout]")
    lines.append(f"{audio_labels}concat=n={len(ranges)}:v=0:a=1[aout]")
    return inputs, ";\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render the cut A-roll (graded, tv range, video only) and the cut dialogue WAV from an EDL in one filter_complex.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--grade", help="grade JSON: rotate, look, clips{name: filters}, segments[{clip, from, to, filters}] in source seconds")
    parser.add_argument("--out-video", required=True)
    parser.add_argument("--out-audio", required=True)
    parser.add_argument("--fade", type=float, default=0.03, help="afade length at every audio splice")
    parser.add_argument("--crf", type=int, default=14)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--gop", type=int, default=25)
    parser.add_argument("--graph-out", help="where to keep the filter graph script (default next to the video)")
    args = parser.parse_args()
    edl = load_json(args.edl)
    grade = dict(DEFAULT_GRADE, **(load_json(args.grade) if args.grade else {}))
    inputs, graph = build_graph(edl, grade, args.fade)
    graph_path = Path(args.graph_out or Path(args.out_video).with_suffix(".filtergraph.txt"))
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(graph)
    Path(args.out_audio).parent.mkdir(parents=True, exist_ok=True)
    fps = edl["fps"]
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-stats", "-y"]
    for path in inputs:
        command += ["-i", path]
    command += ["-filter_complex_script", str(graph_path)]
    command += [
        "-map", "[vout]", "-an", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-g", str(args.gop),
        "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
        "-r", f"{fps:g}", "-fps_mode", "cfr", "-movflags", "+faststart", args.out_video,
        "-map", "[aout]", "-vn", "-map_metadata", "-1", "-c:a", "pcm_s24le", "-ar", str(SAMPLE_RATE), "-ac", "1", args.out_audio,
    ]
    started = time.time()
    subprocess.run(command, check=True)
    print(f"rendered in {time.time() - started:.1f}s: {args.out_video} {args.out_audio}")
    if not run_gate(args.edl, args.out_video, args.out_audio):
        raise SystemExit("drift gate failed")


if __name__ == "__main__":
    main()
