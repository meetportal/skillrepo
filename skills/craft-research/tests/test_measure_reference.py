import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_reference.py"
W, H, FPS = 540, 960, 25


def low_priority():
    return (["nice", "-n", "19"] if shutil.which("nice") else []) + (["ionice", "-c", "3"] if shutil.which("ionice") else [])


def texture(seed):
    rng = np.random.default_rng(seed)
    base = rng.random((H // 8 + 40, W // 8 + 40)).astype(np.float32)
    image = cv2.GaussianBlur(cv2.resize(base, (W + 320, H + 320), interpolation=cv2.INTER_CUBIC), (0, 0), 2)
    return np.clip(image * 255, 0, 255).astype(np.uint8)


def view(tex, dx=0.0, scale=1.0):
    cx, cy = (W + 320) / 2, (H + 320) / 2
    matrix = np.array([[scale, 0, W / 2 - scale * (cx + dx)], [0, scale, H / 2 - scale * cy]], np.float32)
    return cv2.warpAffine(tex, matrix, (W, H), flags=cv2.INTER_LINEAR)


def smootherstep(u):
    return u ** 3 * (u * (6 * u - 15) + 10)


def encode(frames, path):
    command = [*low_priority(), "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-vf", "noise=alls=3:allf=t,format=yuv420p", "-c:v", "libx264", "-threads", "2", "-crf", "16", str(path)]
    subprocess.run(command, input=b"".join(f.tobytes() for f in frames), check=True)


def build(path):
    a, b = texture(1), texture(2)
    frames = [view(a) for _ in range(50)]
    frames += [view(a, dx=120 * smootherstep((i + 1) / 25)) for i in range(25)]
    frames += [view(b, scale=1.002 ** i) for i in range(75)]
    frames += [view(a, dx=120) for _ in range(50)]
    encode(frames, path)


def blend(x, y, weight):
    return np.clip(x.astype(np.float32) * (1 - weight) + y.astype(np.float32) * weight, 0, 255).astype(np.uint8)


def build_transitions(path):
    a, b, c = view(texture(1)), view(texture(2)), view(texture(3))
    frames = [a] * 50 + [blend(a, b, 1 / 3), blend(a, b, 2 / 3)] + [b] * 50
    frames += [view(texture(seed)) for seed in (4, 5, 6)] + [c] * 50
    encode(frames, path)


def measure(folder, name, builder):
    video, out = Path(folder) / f"{name}.mp4", Path(folder) / f"{name}.json"
    builder(video)
    done = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), str(video), "--out", str(out)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(out.read_text())


def main():
    with tempfile.TemporaryDirectory() as folder:
        result = measure(folder, "synth", build)
        transitions = measure(folder, "transitions", build_transitions)
    expected_peak = 1.875 * 120 * (720 / W) / 25
    checks = {
        "cuts at 3.0 and 6.0 s": result["cut_times"] == [3.0, 6.0],
        "one camera move": result["moves"] == 1,
        f"move peak near {expected_peak:.1f} px/frame": abs(result["move_peak_px_per_frame_720p_median"] - expected_peak) < 1.0,
        "push near 0.2 %/frame on the zoom hold": 0.15 < result["push_pct_per_frame_on_holds_p75"] < 0.25,
        "static holds read as still": result["push_pct_per_frame_on_holds_median"] < 0.02,
        "a 3-frame dissolve and a 3-frame flash count as one cut each": transitions["cut_times"] == [2.0, 4.08],
    }
    for name, ok in checks.items():
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    print(json.dumps({k: v for k, v in result.items() if not isinstance(v, list)}))
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
