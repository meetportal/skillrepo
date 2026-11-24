import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import clip_name, decode_audio, ffprobe, frame_rate


def rotation_of(stream):
    for side_data in stream.get("side_data_list") or []:
        if "rotation" in side_data:
            return int(side_data["rotation"])
    rotate_tag = (stream.get("tags") or {}).get("rotate")
    return int(rotate_tag) if rotate_tag else 0


def dual_mono_report(path, seconds):
    stereo = decode_audio(path, sample_rate=48000, channels=2, end=seconds)
    if stereo.ndim != 2 or stereo.shape[1] < 2 or len(stereo) == 0:
        return {"channels_identical": None}
    left, right = stereo[:, 0].astype(np.float64), stereo[:, 1].astype(np.float64)
    left_db = 20 * np.log10(np.sqrt(np.mean(left ** 2)) + 1e-12)
    diff_db = 20 * np.log10(np.sqrt(np.mean((left - right) ** 2)) + 1e-12)
    return {
        "left_rms_dbfs": round(float(left_db), 1),
        "difference_rms_dbfs": round(float(diff_db), 1),
        "difference_below_left_db": round(float(left_db - diff_db), 1),
        "channels_identical": bool(left_db - diff_db >= 30),
    }


def summarise(path, dual_mono_seconds):
    info = ffprobe(path)
    streams = info["streams"]
    videos = [s for s in streams if s["codec_type"] == "video" and not (s.get("disposition") or {}).get("attached_pic")]
    audios = [s for s in streams if s["codec_type"] == "audio"]
    others = [s for s in streams if s["codec_type"] not in ("video", "audio")]
    summary = {"file": str(Path(path).resolve()), "clip": clip_name(path), "duration": round(float(info["format"]["duration"]), 3)}
    if videos:
        video = videos[0]
        full_range = video.get("color_range") == "pc" or video.get("pix_fmt", "").startswith("yuvj")
        summary["video"] = {
            "index": video["index"],
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": round(frame_rate(video), 3),
            "frames": int(video["nb_frames"]) if video.get("nb_frames") else None,
            "pix_fmt": video.get("pix_fmt"),
            "range": "full" if full_range else "tv",
            "color_space": video.get("color_space"),
            "color_primaries": video.get("color_primaries"),
            "color_transfer": video.get("color_transfer"),
            "start_time": float(video.get("start_time", 0)),
            "duration": float(video.get("duration", 0)),
            "rotation_metadata": rotation_of(video),
            "landscape_pixels": (video.get("width") or 0) > (video.get("height") or 0),
        }
    if audios:
        audio = audios[0]
        summary["audio"] = {
            "index": audio["index"],
            "codec": audio.get("codec_name"),
            "sample_rate": int(audio.get("sample_rate", 0)),
            "channels": audio.get("channels"),
            "start_time": float(audio.get("start_time", 0)),
            "duration": float(audio.get("duration", 0)),
        }
        if audio.get("channels", 1) >= 2:
            summary["audio"]["dual_mono"] = dual_mono_report(path, dual_mono_seconds)
    summary["extra_streams"] = [
        {"index": s["index"], "type": s["codec_type"], "codec": s.get("codec_name"), "timecode": (s.get("tags") or {}).get("timecode")}
        for s in others
    ]
    flags = ["-map 0:v:0", "-map 0:a:0", "-map_metadata -1"]
    if any(s["type"] == "data" or s["timecode"] for s in summary["extra_streams"]):
        flags.append("-write_tmcd 0")
    notes = []
    if summary.get("video", {}).get("range") == "full":
        notes.append("full range source: convert to tv range exactly once (scale=in_range=full:out_range=tv)")
    dual = summary.get("audio", {}).get("dual_mono", {})
    if dual.get("channels_identical"):
        flags.append("-ac 1")
        notes.append("dual-mono audio: treat as one channel")
    if summary.get("video", {}).get("rotation_metadata"):
        notes.append("rotation metadata present: check that the decoder auto-rotates before adding transpose")
    elif summary.get("video", {}).get("landscape_pixels"):
        notes.append("landscape pixels with no rotation tag: run rotation_check.py if the shoot was vertical")
    summary["recommended_flags"] = " ".join(flags)
    summary["notes"] = notes
    return summary


def main():
    parser = argparse.ArgumentParser(description="Probe raw clips: streams, data/timecode tracks, range, rotation, dual-mono.")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--dual-mono-seconds", type=float, default=30.0)
    args = parser.parse_args()
    report = {"clips": [summarise(path, args.dual_mono_seconds) for path in args.inputs]}
    for clip in report["clips"]:
        video, audio = clip.get("video", {}), clip.get("audio", {})
        print(f"{clip['clip']}: {clip['duration']}s video {video.get('width')}x{video.get('height')} {video.get('fps')}fps {video.get('pix_fmt')} range={video.get('range')} rot={video.get('rotation_metadata')} audio {audio.get('channels')}ch {audio.get('sample_rate')}Hz dual_mono={audio.get('dual_mono', {}).get('channels_identical')} extra={len(clip['extra_streams'])}")
        for note in clip["notes"]:
            print(f"  - {note}")
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
