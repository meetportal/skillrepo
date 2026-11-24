---
name: reel-grade
description: Exposure, white balance and range handling for talking-head reels cut from several takes. Use when building or checking the per-clip and per-segment grade of an A-roll, matching skin brightness across jump cuts, converting full-range camera files to broadcast range exactly once, or verifying levels with signalstats.
---

# reel-grade

The grade is a JSON config read by `reel-cut/scripts/render_aroll.py`. The renderer builds, per EDL range:

```
rotate -> clip filters -> segment filters -> look -> one explicit range conversion -> yuv420p
```

with `format=<working format>` pinned between every filter.

```json
{
 "rotate": ["transpose=2", "setsar=1"],
 "look": ["colortemperature=temperature=6000:mix=0.3", "eq=contrast=1.06:saturation=1.10", "unsharp=5:5:0.4:5:5:0"],
 "clips": {"CLIP_A": ["eq=gamma=0.85"], "CLIP_B": ["curves=all='0/0 0.75/0.72 1/0.96'", "colorbalance=rm=-0.03"]},
 "segments": [{"clip": "CLIP_A", "from": 2.12, "to": 6.72, "filters": ["eq=gamma=0.96"]}]
}
```

`segments` match an EDL range when the range's source-video midpoint lies in `[from, to)`. They exist because the light on a moving speaker changes within one take: a single clip gamma leaves jump cuts inside the take visibly brighter or darker than each other.

A segment may also carry `"gamma_keys": [[source_seconds, gamma], ...]` for a speaker who walks out of the key light during one continuous shot. The renderer turns it into `eq=gamma='<piecewise linear ramp of source time>':eval=frame` (source time = output-range time + `v_in`, so the ramp stays continuous across bridge ranges).

## Range: convert once, explicitly, and pin the working format

Camera files are often `yuvj420p` (full range, 0 to 255). Measured on ffmpeg 6.1:

- With an unpinned chain (`transpose,eq,colortemperature,...,scale=in_range=full:out_range=tv`), format negotiation inserts an automatic `yuvj420p -> yuv420p` conversion at the input. The final `scale=in_range=full` then compresses an already-limited signal a second time: blacks lift and whites drop.
- Converting to tv range first and grading after it is also wrong: `eq` works on raw code values, so contrast and gamma push tv-range data outside 16 to 235 (measured YMIN 4, YMAX 255).
- Correct: keep the source's own format (`format=yuvj420p`) between every filter (RGB-only filters such as `colortemperature` and `curves` convert to RGB and back correctly when both ends are pinned), then a single `scale=in_range=full:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709,format=yuv420p`. Graded output measures exactly YMIN 16, YMAX 235.
- Never convert range again later (Remotion render, final encode).

## Measuring skin

```
python scripts/measure_skin.py aroll.mp4 --cues cues.json --model MODELS/face_detection_yunet_2023mar.onnx --step 0.12 --out qa/skin.json
python scripts/measure_skin.py RAW/CLIP.MP4 --rotate 2 --model MODELS/face_detection_yunet_2023mar.onnx
```

- Reads the stream's own Y/Cb/Cr code values (raw decode in the native pixel format, the same numbers `signalstats` reports), so tv-range files give tv-range numbers.
- Patches come from YuNet landmarks: one square per cheek (between eye and mouth level, just outside the eye line, a side of 1/8 of the face width) and a forehead strip.
- Inside each patch only skin pixels (YCbCr hue 95 to 160 degrees, chroma above 6) and specular highlights count. That rejects the hand-held mic, hair and fingers that often cover a cheek. Skin Y is the mean of those pixels (what `signalstats` YAVG reports on a clean cheek crop); hue uses skin pixels only.
- Also reported: wall white-balance proxy (mean RGB of the top 15 % of the frame, mid-tones only, as R minus B), face and frame clipping, Y min/max, the 0.1/99.9 percentiles and the share of pixels outside 16 to 235.
- With `--cues` it groups by output segment and by source clip and suggests an extra `eq` gamma per group. `--debug-dir` writes every sampled frame with the patches drawn (green used, red rejected). Look at a few before trusting the numbers.
- Single frames are noisy (head turns, gestures): sample every 0.1 to 0.2 s and use medians.

## Rule table (skin Y in tv-range code values, target 150, pass 145 to 155)

| Measured skin Y (segment median) | Action |
|---|---|
| 148 to 152 | nothing |
| 135 to 147 or 153 to 165 | `eq=gamma=g` with `g = ln(n_measured) / ln(n_target)`, where `n = (Y - 16) / 219`. `match_exposure.py` does this per segment, multiplying any existing segment gamma. |
| under 135 | the same gamma (cap 1.6) and check the shadows: if black clothing or hair lifts visibly, use `curves` with a pinned black point instead (`curves=all='0/0 0.4/0.47 1/1'`). |
| over 165, or face clipping (Y 245+ full range) above 2 % | a highlight roll-off first (`curves=all='0/0 0.75/0.72 1/0.96'`), then a gamma. Clipped skin cannot be recovered. |
| skin hue more than 4 degrees off the others (redder) | `colorbalance=rm=-0.03` (or `hue=h=2`) on that clip only |
| wall R minus B above 30 on every clip (warm room) | uniform light cool-down in `look` (`colortemperature=temperature=6000:mix=0.3`); never per clip |

A gamma between 0.6 and 1.6 is the safe envelope; outside it, change the light or the take.

## Iterating

```
python scripts/measure_skin.py aroll.mp4 --cues cues.json --model YUNET --out qa/skin_v1.json
python scripts/match_exposure.py --measure qa/skin_v1.json --edl edl.json --grade grade.json --out grade.json
python ../reel-cut/scripts/render_aroll.py --edl edl.json --grade grade.json --out-video aroll.mp4 --out-audio voice_cut.wav
python scripts/measure_skin.py aroll.mp4 --cues cues.json --model YUNET --out qa/skin_v2.json
```

Usually two passes. The look (contrast, saturation) slightly changes what a gamma does, so measure again instead of computing a final value.

`match_exposure.py` writes one constant gamma per segment, unless the segment's skin Y interquartile range is over 18 code values (real light drift, not head-turn noise). Then it writes `gamma_keys` every 0.5 s from the binned medians, smoothed over 3 keys and clamped to 0.6 to 1.6. Keep ramps for genuine drift: on noisy segments they make the exposure breathe.

## Verification procedure

1. Skin: every clip's median skin Y in 145 to 155 on the rendered A-roll (`measure_skin.py ... --cues`). Also look at the segment table: neighbouring segments of one take within about 8 code values.
2. Levels of the graded signal, before encoding: run the same chain to `-f null` with `signalstats`:
   `ffmpeg -ss T -i RAW -frames:v 5 -vf "<chain from the saved filtergraph>,signalstats,metadata=print:file=-" -f null -` gives YMIN 16 and YMAX 235.
3. Levels of the encoded file: `ffmpeg -i aroll.mp4 -vf signalstats,metadata=print:file=ss.txt -f null -`. x264 ringing around clipped plateaus (black hair at 16, blown walls at 235) produces stray code values outside 16 to 235 in under about 1 % of pixels; that is encoding, not grading. Gate on the 0.1/99.9 percentiles (`measure_skin.py` reports them; 15 or more and 236 or less) and on YLOW/YHIGH. Re-encoding with a different encoder or CRF shows the same thing.
4. Same frame, raw against A-roll, side by side (`hstack`): no hue shift, no crushed blacks, wall not lifted to grey.
5. Downstream (Remotion and the final encode) must keep the A-roll's levels on the same frame. A shift of 5 or more code values in YAVG means a second range conversion.
