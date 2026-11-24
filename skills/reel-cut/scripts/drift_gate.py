import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edl_lib import load_json, to_frame


def stream_facts(path, selector):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_packets", "-select_streams", selector,
         "-show_entries", "stream=codec_type,duration,nb_read_packets,nb_frames,sample_rate,r_frame_rate,duration_ts,time_base", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    streams = json.loads(result.stdout)["streams"]
    return streams[0] if streams else None


def video_duration(path):
    facts = stream_facts(path, "v:0")
    numerator, denominator = facts["r_frame_rate"].split("/")
    fps = float(numerator) / float(denominator)
    frames = int(facts["nb_read_packets"])
    return frames / fps, frames, fps


def audio_duration(path):
    import soundfile

    info = soundfile.info(str(path))
    return info.frames / info.samplerate


def run_gate(edl_path, video_path, audio_path):
    edl = load_json(edl_path)
    fps = edl["fps"]
    frame = 1 / fps
    ranges = edl["ranges"]
    range_errors = [i for i, r in enumerate(ranges) if to_frame(r["v_out"], fps) - to_frame(r["v_in"], fps) != to_frame(r["a_out"], fps) - to_frame(r["a_in"], fps)]
    edl_total = sum(to_frame(r["v_out"], fps) - to_frame(r["v_in"], fps) for r in ranges) / fps
    video_s, frames, video_fps = video_duration(video_path)
    audio_s = audio_duration(audio_path)
    checks = {
        "ranges_equal_v_a": not range_errors,
        "edl_duration_field": abs(edl_total - edl["duration"]) < frame / 2,
        "video_fps": abs(video_fps - fps) < 1e-3,
        "video_vs_audio": abs(video_s - audio_s) <= frame,
        "video_vs_edl": abs(video_s - edl_total) <= frame,
        "audio_vs_edl": abs(audio_s - edl_total) <= frame,
    }
    print(f"drift gate: edl {edl_total:.3f}s ({round(edl_total * fps)} frames) video {video_s:.3f}s ({frames} frames @ {video_fps:g}) audio {audio_s:.4f}s")
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'} {name}")
    if range_errors:
        print(f"  ranges with unequal v/a durations: {range_errors}")
    return all(checks.values())


def main():
    parser = argparse.ArgumentParser(description="Drift gate: video and audio durations equal within one frame and equal to the EDL total.")
    parser.add_argument("--edl", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--audio", required=True)
    args = parser.parse_args()
    if not run_gate(args.edl, args.video, args.audio):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
