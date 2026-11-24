---
name: reel-cut
description: Transcript-driven jump-cut editing for talking-head vertical reels. Use when turning snapped word timings into an EDL (pause tightening, padding, list-marker breaths, blink-aware J/L cuts), rendering the cut A-roll and cut dialogue in one frame-exact ffmpeg filter_complex, retiming words into Remotion captions and cue files, and gating sync drift and clipped words.
---

# reel-cut

Stage 1b of the reel pipeline. Inputs: the raw clips, `transcript.json` and `frame_metrics.json` from `reel-ingest`, a grade config from `reel-grade`. Outputs, all on one output timeline:

| File | What |
|---|---|
| `edl.json` | `{"fps", "ranges": [{"clip", "v_in", "v_out", "a_in", "a_out", "beat", "quote"}], "duration"}`. `clip` is the absolute path of the video source. A range may carry `a_clip` when its audio comes from another file (cross-clip J/L bridge). Per range `v_out - v_in == a_out - a_in`, all edges on the frame grid. The output is the ranges concatenated. |
| `aroll.mp4` | 1080x1920 CFR, graded, tv range, BT.709 tagged, video only, CRF 14, GOP 25. |
| `voice_cut.wav` | 48 kHz mono 24-bit, cut dialogue with 30 ms fades at every audio splice, otherwise unprocessed. |
| `words.out.json` | Remotion `Caption[]`: `{"text": " word", "startMs", "endMs", "timestampMs" (midpoint), "confidence": null}` with corrected caption text. |
| `cues.json` | `{"duration", "fps", "segments": [{"index", "clip" (basename), "start", "end", "face": {"cx", "cy", "w", "h"}}], "cuts": [...], "words": [{"i", "text", "start", "end"}]}`. A segment is a run of continuous source video; `cuts` are the video cut times. Face box is the median over the segment in A-roll pixels. |

## Cut rules (defaults in `scripts/edl_lib.py`, override per reel in the cutlist `rules`)

1. Cut only between words, on energy-snapped edges. Never inside a word (`plan_cuts.py` refuses to write the EDL).
2. Pauses of 0.25 s or more are always tightened. 0.15 to 0.25 s pauses are tightened only when a blink or soft frame sits in them. Under 0.15 s is never touched.
3. Residual gap left after a cut: about 0.12 s mid-sentence (0.06 tail + 0.06 lead), about 0.18 s after a sentence end or question (0.10 + 0.08), about 0.28 s after a list marker such as "First," "Second," "Third," (0.20 + 0.08) so a title slam can land.
4. Head pad at least 0.05 s before an onset (0.04 s minimum at clip joins), tail at least 0.06 s after the snapped end. The clip's first range starts 0.06 s before the first word, the last range ends 0.10 s after the last word.
5. 30 ms `afade` out and in at every audio discontinuity. No fade where audio stays continuous across a range boundary (a video-only bridge).
6. Video and audio may cut at different times (J/L cut). The joint offset is in whole frames: positive means the picture leaves before the sound (L-cut), negative means the next picture arrives after the next sound starts (J-cut, the previous shot runs over the new line). The EDL expresses it as short bridge ranges whose video and audio come from different source times, so every range still has equal v/a durations.
7. No cut frame within 3 frames of a blink or soft window. `plan_cuts.py` searches joint offsets up to 6 frames, smallest first, to clear them, and warns when it cannot (cover those with a graphic).
8. Everything is rendered in a single `filter_complex`: per range `trim(start_frame, end_frame),setpts` then the grade, and `atrim(start_sample, end_sample),asetpts,afade`, then `concat`. Frame and sample indices, never float seconds.
9. Drift gate: video and audio durations equal within one frame and equal to the EDL total within one frame.
10. No speed change, no atempo.

## Steps

1. **Plan.** Auto mode (rules only):
   ```
   python scripts/plan_cuts.py --transcript ingest/transcript.json --exclusions ingest/frame_metrics.json \
     --config cutlist.json --out edl.json --report plan_report.json
   ```
   `cutlist.json` for auto mode: `{"fps": 25, "order": ["CLIP_A", "CLIP_B"], "clips": {"CLIP_A": "/abs/CLIP_A.MP4"}, "trim": {"CLIP_A": [start, end]}, "exclude": {"CLIP_A": [[s, e]]}, "rules": {...}}`. `trim` keeps one take of a clip, `exclude` adds blemish windows (hand, sway) to the blink/soft windows.

   Manual mode (a decided cut list) uses the same file with `ranges`:
   ```
   {"clip": "CLIP_A", "in": 2.12, "out": 6.88, "video_out": 6.72, "beat": "B0"},
   {"clip": "CLIP_A", "in": 7.12, "video_in": 6.96, "out": 9.60, "beat": "B2"}
   ```
   `in`/`out` are audio edges in source seconds (rounded outward to the frame grid). `video_out`/`video_in` set an explicit joint offset and must agree on both sides of the joint (here 0.16 s: picture leaves before a blink, the next shot starts 4 frames early). Joints without explicit video edges get the automatic blink search (`"auto_offsets": true`). Validation is identical in both modes: cuts inside words are errors; short pads, blink joints and dropped words are listed.

   Read the printed joint table (`tail`, `lead`, `residual`, offset) and the dropped-word list before rendering.

2. **Render** (one ffmpeg pass, both outputs, then the drift gate):
   ```
   python scripts/render_aroll.py --edl edl.json --grade grade.json --out-video aroll.mp4 --out-audio voice_cut.wav
   ```
   Each clip is decoded once and split; each range is trimmed, then graded with `rotate + clip filters + segment filters + look`, with the working format pinned between filters and one explicit full-to-tv range conversion at the end (see `reel-grade`). Encode: `libx264 -preset medium -crf 14 -g 25 -pix_fmt yuv420p`, BT.709 primaries/trc/matrix tags, `-color_range tv`, `-r <fps> -fps_mode cfr`, no audio, no metadata. Audio: mono fold of the first audio stream (`pan` average of L and R), 48 kHz, PCM 24-bit. The filter graph is saved next to the outputs for inspection.

3. **Retime words and cues.**
   ```
   python scripts/retime_words.py --edl edl.json --transcript ingest/transcript.json --corrections corrections.json \
     --frame-metrics ingest/frame_metrics.json --out-words words.out.json --out-cues cues.json
   ```
   A word is kept when its midpoint lies inside a kept audio range; its edges are clamped to that range and shifted to output time. Corrections change caption text only, never timing:
   ```
   {"corrections": [
     {"match": "deliverable", "text": "deliverability"},
     {"match": "DKIM, and", "text": "DKIM and"},
     {"index": 42, "text": "GTM"},
     {"match": "thank you for watching", "text": ""}
   ]}
   ```
   `match` compares lowercase tokens without punctuation and replaces every occurrence (`occurrence: n` for one, `required: true` to fail when absent). Equal token counts keep each word's timing; otherwise the span is divided evenly. Empty `text` deletes. `index` refers to the output word list (`cues.json` `words[].i`) and is applied first.

4. **Verify.**
   ```
   python scripts/drift_gate.py --edl edl.json --video aroll.mp4 --audio voice_cut.wav
   python scripts/cut_frames.py --video aroll.mp4 --cues cues.json --out qa/cuts
   python scripts/verify_asr.py --audio voice_cut.wav --words words.out.json --edl edl.json --corrections corrections.json --out qa/asr_diff.json
   ```
   - `cut_frames.py` writes frames 0 to 2 as PNG and 10 frames either side of every cut, plus one labelled strip per cut (cut frame in red). Read the start frames (sharp, no hand, no blur, mouth state) and every strip (no blink or half-blink on the frames next to a cut, no flash, no duplicate frame).
   - `verify_asr.py` re-transcribes the cut audio with large-v3 and diffs it against the intended words. Missing words mean a clipped edge, extra words mean a ghost. Correction pairs are accepted in either direction, as are contraction spellings. It also measures the 20 ms just outside every 30 ms splice fade: anything above -40 dBFS means speech energy sits at the splice.
   - Iterate the cutlist until all pass. Then recompute every graphic and SFX time from `words.out.json` (never from planning estimates).

## Gotchas

- Seconds such as 2.13 are not on a 25 fps grid. Every edge is converted to whole frames (`in` floor, `out` ceil) before anything else, otherwise video and audio drift by up to a frame per range.
- A blink detected at 6.80 often starts closing 2 frames earlier. Look at the eye strip, then move the video edge, not the audio.
- Never use `-shortest`; the gate catches drift instead of hiding it.
