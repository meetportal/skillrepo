---
name: reel-grade
description: Exposure, white balance and range handling for talking-head reels cut from several takes. Use when building or checking the grade of an A-roll, matching skin brightness across jump cuts without lifting blacks, following light drift inside a take, converting full-range camera files to broadcast range exactly once with a legal clamp, or verifying cheek, black and signal levels on both sides of every cut.
---

# reel-grade

The grade is a JSON config read by `reel-cut/scripts/render_aroll.py`. Run from the reel work folder with `SKILLS` set to this repo's `skills/` folder.

Per EDL range the renderer builds:

```
rotate -> clip filters -> tone curve -> segment filters -> look -> one explicit range conversion -> yuv420p -> legal toe/shoulder
```

with `format=<working format>` pinned between every filter.

```json
{
 "rotate": ["transpose=2", "setsar=1"],
 "look": ["colortemperature=temperature=6000:mix=0.3", "eq=contrast=1.06:saturation=1.10", "unsharp=5:5:0.4:5:5:0"],
 "legal_clamp": true,
 "clips": {"CLIP_B": {"tone": {"high": -8}, "filters": ["colorbalance=rm=-0.03"]}},
 "segments": [
  {"clip": "CLIP_A", "from": 0, "to": 1000000, "mid_keys": [[2.3, 1.08], [2.7, 1.0], [4.1, 0.96]]},
  {"clip": "CLIP_C", "from": 0.0, "to": 2.3, "tone": {"black": -6}}
 ]
}
```

- Every segment whose `[from, to)` holds a range's source-video midpoint applies; tones combine (mids multiply, highs and blacks add) and filters chain.
- `mid_keys` is a curve over **source time** of the take, interpolated per frame (`sendcmd` into `lutyuv`). One curve per take means a jump cut inside the take reads the curve at its own source times, so exposure follows the light continuously instead of stepping at the cut.

## Tone curve (shadow-neutral exposure)

`scripts/tone.py` defines the only exposure control. On normalised luma `x`:

- `mid`: `x + (x^(1/mid) - x) * smoothstep(0.03, 0.25, x)`. It behaves like `eq` gamma in the mid-tones and highlights but fades to nothing at the toe, so black clothing and hair stay where they are. `eq=gamma` lifts a Y 20 black to about 30 at gamma 1.6 and makes jump cuts look milky; do not use it for exposure.
- `high` (tv code values): added to the upper mids and highlights (smoothstep 0.40 to 0.70), faded out again above 90 % so pure white is untouched. Use a negative value to pull hot skin and specular cheeks down.
- `black` (tv code values): added at black, fading out by 30 % grey. Use to match black levels between takes.

```
python $SKILLS/reel-grade/scripts/tone.py --mid 1.3 --high -8
```
prints the `lutyuv` expression and a code-value table (for example 20 stays 20, 140 goes to 150).

## Range: convert once, explicitly, pin the working format, clamp

Camera files are often `yuvj420p` (full range). Measured on ffmpeg 6.1:

- An unpinned chain lets format negotiation insert an automatic `yuvj420p -> yuv420p` conversion at the input; the final `scale=in_range=full` then compresses the signal a second time.
- Converting to tv range first and grading after it pushes tv data outside 16 to 235.
- Correct: keep the source's own format between every filter, then one `scale=in_range=full:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709,format=yuv420p`, then the legal stage: a soft toe and shoulder on Y (0 to 20 maps to 17 to 20, 226 to 255 maps to 226 to 233) and chroma clipped to 16 to 240. A hard clip to exactly 16 leaves dark clothing as a flat plane of 16 that the encoder dithers to 14 and 15 over whole areas (measured: up to 1.2 % of a frame outside legal range); with the soft toe the darkest blacks sit at 17 to 20 and encoder noise stays inside 16 to 235. The graded signal measures YMIN 17, YMAX 233 or tighter (check with a lossless render, below).
- Never convert range again later (Remotion render, final encode).

## Matching exposure (iterate on fast renders)

```
python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video qa/stage1/grade_try.mp4 --out-audio qa/stage1/grade_try.wav --preset veryfast
python $SKILLS/reel-grade/scripts/cut_levels.py qa/stage1/grade_try.mp4 --cues cues.json --model "$MODELS"/face_detection_yunet_2023mar.onnx --edge-frames 5 --out qa/stage1/levels_try.json
python $SKILLS/reel-grade/scripts/match_exposure.py --levels qa/stage1/levels_try.json --cues cues.json --grade config/grade.json --out config/grade.json
```

Start from a grade with no `mid_keys` and repeat until `cut_levels.py` passes (usually 3 to 6 passes; the look changes what a curve does, so measure again instead of computing a final value).

- `cut_levels.py` reads the encoded Y plane. Cheek patch: a square of 1/10 of the face width between each eye and the nose wing (YuNet landmarks), median Y, the two sides averaged. Dark patch: 2.7 to 3.3 face heights below the top of the face box (dark clothing on the torso), p50. It reports per shot, per take and on both sides of every cut (the last and first `--edge-frames` frames).
- `match_exposure.py` fits one `mid_keys` curve per take: per 0.4 s bin of source time the extra mid that brings the cheek to the target (150), smoothed with a moving median and mean, multiplied into the current curve and clamped to 0.8 to 1.7. Then the first and last frame of every shot get their own key from the frames next to the cut, so both sides of every cut (inside a take and between takes) land on the target. Inside one take, when one side is clamped, the other side is matched to what the clamped side can reach. Mids are kept within 0.8 to 1.7: below 0.8 the whole frame (wall included) sinks into murk, so a take that still reads hot gets a negative `high` instead.
- Hot or redder takes: a negative `high` and `colorbalance=rm=-0.03` on that clip. Warm room on every clip: a uniform `colortemperature` in `look`, never per clip.
- Patches are noisy on single frames (head turns, the hand or mic crossing the cheek) and read high on a rim-lit or specular cheek. Look at a few frames with the patches drawn before trusting a surprising number, and always look at whole frames on both sides of every cut after a fit: a fit that passes the numbers can still darken a whole shot.

## Gates

1. Skin: every take's median cheek Y within 145 to 155.
2. Cuts: across every cut inside a take the cheek Y changes by 6 codes or less; across every cut the shot-median dark patch changes by 6 codes or less.
3. Levels of the graded signal before encoding sit inside 16 to 235 (17 to 233 with the soft toe and shoulder). Check by rendering the saved filter graph losslessly:
   `ffmpeg -i RAW... -filter_complex_script aroll.filtergraph.txt -map "[vout]" -frames:v 60 -c:v ffv1 ll.mkv`, then `signalstats` on every frame.
4. Levels of the encoded file: x264 ringing around hard edges (dark hair against a bright wall) still produces a few stray code values outside 16 to 235. Gate the encode on the 0.1/99.9 percentiles (14 or more and 236 or less) and on at most 0.1 % of pixels outside 16 to 235 on any sampled frame.
5. Same frame, raw against A-roll, side by side: no hue shift, no crushed blacks, wall not lifted to grey.
6. Downstream (Remotion and the final encode) must keep the A-roll's levels on the same frame. A shift of 5 or more codes means a second range conversion.
