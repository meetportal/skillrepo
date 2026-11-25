import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asr_diff import SAMPLE_RATE, chunk_bounds, gap_points, inside_word, quiet_points, word_spans


def synthetic_reel(seed, seconds, long_gap_every):
    rng = random.Random(seed)
    words, t, index = [], 0.4, 0
    while t < seconds - 1.0:
        length = rng.uniform(0.18, 0.42)
        words.append({"text": f"word{index}", "startMs": round(t * 1000), "endMs": round((t + length) * 1000)})
        index += 1
        gap = rng.uniform(0.13, 0.3) if long_gap_every and index % long_gap_every == 0 else rng.uniform(0.02, 0.09)
        t += length + gap
    audio = np.random.default_rng(seed).normal(0, 0.002, int(seconds * SAMPLE_RATE)).astype(np.float32)
    for word in words:
        a, b = int(word["startMs"] * SAMPLE_RATE / 1000), int(word["endMs"] * SAMPLE_RATE / 1000)
        envelope = np.ones(b - a, np.float32)
        soft = slice(len(envelope) // 3, len(envelope) // 3 + int(0.09 * SAMPLE_RATE))
        envelope[soft] = 0.01
        audio[a:b] += 0.2 * envelope * np.sin(np.arange(b - a) * 0.3).astype(np.float32)
    return words, audio


def check(seed, seconds, long_gap_every, max_chunk=20.0):
    words, audio = synthetic_reel(seed, seconds, long_gap_every)
    spans = word_spans(words)
    total = len(audio) / SAMPLE_RATE
    bounds = chunk_bounds(total, [gap_points(spans), quiet_points(audio)], max_chunk, spans)
    for start, end in bounds:
        assert end - start <= max_chunk + 1e-6, f"seed {seed}: chunk {start:.2f}-{end:.2f} is longer than {max_chunk} s"
        assert not inside_word(start, spans) and not inside_word(end, spans), f"seed {seed}: bound {start:.3f}/{end:.3f} splits a word"
    assert bounds[0][0] == 0.0 and abs(bounds[-1][1] - total) < 1e-9
    return bounds


def main():
    cases = 0
    for seed in range(12):
        check(seed, 75.0, 9)
        check(seed, 75.0, 0)
        cases += 2
    gap_bounds = check(3, 75.0, 9)
    words, _ = synthetic_reel(3, 75.0, 9)
    gaps = gap_points(word_spans(words))
    assert all(any(abs(end - point) < 1e-6 for point in gaps) for _, end in gap_bounds[:-1]), "word gaps of 120 ms or more are used first"
    print(f"asr chunk tests passed ({cases} synthetic reels, no bound inside a word)")


if __name__ == "__main__":
    main()
