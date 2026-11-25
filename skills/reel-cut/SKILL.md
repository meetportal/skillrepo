---
name: reel-cut
description: Transcript-driven jump-cut editing for talking-head vertical reels. Use when turning force-aligned word timings into an EDL (pause tightening, padding, list-marker breaths, blink-aware J/L cuts, held frames over soft footage), rendering the cut A-roll in one frame-exact ffmpeg filter_complex and the cut dialogue sample-exactly with equal-power crossfades, retiming words onto the output timeline, writing cues.json for the graphics stage, and gating sync drift, splices and cut frames.
---

# reel-cut

Stage 1b of the reel pipeline. Inputs: the raw clips, `ingest/transcript.json` (force-aligned) and `ingest/frame_metrics.json` from `reel-ingest`, the grade config from `reel-grade`. reel-cut only places and retimes words; caption text belongs to `reel-captions`.

## Conventions

Run from the reel work folder with `SKILLS` set to this repo's `skills/` folder; call scripts as `python $SKILLS/reel-cut/scripts/<script>.py`. Reel-specific inputs live in `config/`.

## Outputs (all on one output timeline)

| File | What |
|---|---|
| `edl.json` | `{"fps", "ranges": [{"clip", "v_in", "v_out", "a_in", "a_out", "beat", "quote", "a_clip"?, "v_hold"?}], "duration"}`. `clip` is the absolute path of the video source; `a_clip` is set when the audio comes from another file (cross-clip J/L bridge). `v_hold` (source seconds) means the range shows that one frame for its whole length. Per range `v_out - v_in == a_out - a_in`, all edges on the frame grid. |
| `aroll.mp4` | 1080x1920 CFR, graded, tv range held inside 16-235 before encoding by a soft toe and shoulder, BT.709 tagged, video only, CRF 14, GOP 25. |
| `voice_cut.wav` | 48 kHz mono 24-bit, cut dialogue, an equal-power crossfade centred on every audio splice, otherwise unprocessed. |
| `words.retimed.json` | Remotion `Caption[]` with the spoken (transcribed) text: `{"text": " word", "startMs", "endMs", "timestampMs", "confidence": null}`. Input to `reel-captions`. |
| `cues.json` | Written after `reel-captions` produced `words.out.json`; schema below. |
| `plan_report.json` | Joint table, warnings, dropped words. |

### cues.json

```
{
 "duration": 30.0, "fps": 25,
 "segments": [{"index", "clip" (basename), "start", "end", "src_in", "src_out",
               "face": {"cx", "cy", "w", "h"} (median face box over the shot, A-roll pixels),
               "holds": [[start, end]] (only when the shot contains frozen frames)}],
 "cuts": [t, ...],                      visual cut times (a shot boundary where the picture jumps)
 "audio_splices": [t, ...],
 "words": [{"i", "text", "start", "end"}],   corrected caption words (from words.out.json)
 "keywords": {"<word or phrase>": onset},    onsets of the key words listed in the cue config
 "cover": [{"start", "end", "reason"}],      MANDATORY full-frame graphic windows
 "needs_punch": [{"t", "reason"}]            times that must get a camera scale change
}
```

- A segment is a shot: a run of continuously advancing (or held) source frames from one take. A freeze that continues from the last live frame, or a held frame that the live video then continues from, is not a cut.
- `cover`: frozen frames of 5 or more frames under speech (used to hide soft or blurred source frames) and any window from the cue config. Stage 2 must place a full-frame graphic (takeover) that spans each window completely; QA fails if one is uncovered.
- `needs_punch`: every cut inside one take that skips 6 source frames or fewer (a micro jump cut that reads as a stutter without a scale change), plus config entries. The camera plan must change scale exactly on these frames.
- `keywords` come from the cue config `{"keywords": ["word", "two words", {"text": "word", "n": 2}], "cover": [...], "needs_punch": [...]}`; `n` picks the nth occurrence. A keyword that is not found stops the script. Recompute every graphic and SFX time from `keywords` and `words`, never from planning notes.

## Cut rules (defaults in `scripts/edl_lib.py`, override per reel in the cutlist `rules`)

1. Cut only between words, on force-aligned edges. Never inside a word (`plan_cuts.py` refuses to write the EDL).
2. Pauses of 0.25 s or more are always tightened. 0.15 to 0.25 s pauses only when a blink or soft frame sits in them. Under 0.15 s never.
3. Residual gap after a cut: about 0.12 to 0.15 s mid-sentence, 0.16 to 0.20 s after a sentence end or question (also when the next take starts a new section), about 0.28 s after a list marker ("First,", "Second,", "Third,") so a title slam can land. A list marker keeps at least 50 ms of head before its onset. When a pause holds a breath, take the cut out of the silence on either side of the breath, never through it.
4. Head pad at least 0.05 s before an onset (0.04 s minimum at clip joins), tail at least 0.06 s after the end (the end already includes the decay).
5. Every audio discontinuity gets an equal-power (sine/cosine) crossfade of 16 ms centred on the splice, using 8 ms of source handle on each side, so room tone never drops. No 30 ms fade-out/fade-in pairs: they leave 40 to 60 ms holes 15 to 25 dB under room tone. Where audio stays continuous (a video-only bridge) nothing is applied.
6. J/L cuts: the joint offset is in whole frames. Positive: the picture leaves before the sound (L-cut). Negative: the previous picture runs over the start of the next line (J-cut). The EDL expresses it as bridge ranges, so every range keeps equal v/a durations.
7. No cut frame within 3 frames of a blink or soft window (`guard_frames`). `plan_cuts.py` searches offsets up to 6 frames to clear them and warns when it cannot.
8. Held frames: when the frames at a cut are soft (focus hunt, sway blur) on a side, freeze the nearest sharp frame with `holds` (video only, the audio keeps running). Use 2 to 4 frames to fix a cut frame or the first frame of the reel; longer holds under speech become mandatory `cover` windows.
9. Frame 0 is the thumbnail and loop frame: it must be a sharp frame with the eyes open. If the take opens soft, hold the first sharp frame over the first frames (at most about 4) and let the live video continue from that same frame.
10. Video is rendered in a single `filter_complex`: per range `trim(start_frame, end_frame)` (or one frame plus `tpad` for a hold), `setpts`, then the grade, then `concat`. Audio is cut in sample indices from the same frame grid.
11. Drift gate: video and audio durations equal within one frame and equal to the EDL total. No speed change, no atempo, never `-shortest`.

## Steps (exact order and files)

1. **Plan.**
   ```
   python $SKILLS/reel-cut/scripts/plan_cuts.py --transcript ingest/transcript.json --exclusions ingest/frame_metrics.json \
     --config config/cutlist.json --out edl.json --report plan_report.json
   ```
   Auto mode: `{"fps": 25, "order": ["CLIP_A", "CLIP_B"], "clips": {"CLIP_A": "/abs/CLIP_A.MP4"}, "trim": {"CLIP_A": [start, end]}, "exclude": {"CLIP_A": [[s, e]]}, "rules": {...}}`.

   Manual mode (a decided cut list) adds `ranges`:
   ```
   {"clip": "CLIP_A", "in": 1.00, "out": 5.00, "video_out": 4.92, "beat": "intro",
    "holds": [{"from": 1.00, "to": 1.16, "frame": 1.16}, {"from": 4.80, "to": 4.92, "frame": 4.76}]},
   {"clip": "CLIP_A", "in": 5.40, "video_in": 5.32, "out": 8.00, "beat": "point-1"}
   ```
   `in`/`out` are audio edges in source seconds (rounded outward to the frame grid). `video_out`/`video_in` set an explicit joint offset and must agree on both sides of the joint. `holds` are in the range's source video time: from `from` to `to` the picture shows the frame at `frame`. Validation is identical in both modes. Read the printed joint table (`tail`, `lead`, `residual`, offset), the warnings and the dropped-word list.

2. **Render.**
   ```
   python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video aroll.mp4 --out-audio voice_cut.wav
   ```
   Video: each clip decoded once and split; per range the grade from `reel-grade` (rotate, clip filters, tone curve, segment filters, look), working format pinned between filters, one explicit full-to-tv conversion, then the legal stage (`lutyuv` soft toe and shoulder on Y into 17-233, chroma clipped to 16-240; see `reel-grade`). Time-varying tone curves are driven per frame with `sendcmd` into `lutyuv` (command files next to the saved filter graph). Encode `libx264 -preset medium -crf 14 -g 25` (`--threads N` caps decoder, filter and encoder threads on a shared machine), BT.709 tags, `-color_range tv`, CFR. Audio: decoded per clip (mono fold with `pan`, 48 kHz), cut and crossfaded in numpy, written as PCM 24-bit. The drift gate runs at the end.

3. **Retime words** (timing only).
   ```
   python $SKILLS/reel-cut/scripts/retime_words.py --edl edl.json --transcript ingest/transcript.json --out words.retimed.json
   ```
   A word is kept when its midpoint lies inside a kept audio range; its edges are clamped to that range and shifted to output time.

4. **Caption text** (owned by `reel-captions`, run here so cues carry the final text).
   ```
   python $SKILLS/reel-captions/scripts/apply_corrections.py --words words.retimed.json --corrections config/corrections.json \
     --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --out words.out.json
   ```

5. **Cues.**
   ```
   python $SKILLS/reel-cut/scripts/build_cues.py --edl edl.json --words words.out.json --frame-metrics ingest/frame_metrics.json \
     --config config/cues_config.json --out cues.json
   ```

6. **Verify.**
   ```
   python $SKILLS/reel-cut/scripts/drift_gate.py --edl edl.json --video aroll.mp4 --audio voice_cut.wav
   python $SKILLS/reel-cut/scripts/splice_check.py --edl edl.json --audio voice_cut.wav --out qa/stage1/splices.json
   python $SKILLS/reel-cut/scripts/cut_frames.py --video aroll.mp4 --cues cues.json --out qa/stage1/cuts
   python $SKILLS/reel-captions/scripts/asr_diff.py --mode cut --media voice_cut.wav --words words.out.json --edl edl.json \
     --corrections config/corrections.json --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --out qa/stage1/asr_diff.json
   python $SKILLS/reel-ingest/scripts/check_onsets.py --words words.out.json --audio voice_cut.wav --out qa/stage1/onsets_out.json
   ```
   - `splice_check.py`: at every audio splice the 10 ms RMS never drops more than 3 dB under the quieter take's room-tone floor (5th percentile of its 10 ms RMS), no 4 kHz+ burst over 6 dB above its surroundings, no sample step over 1.5x the local 99.9th percentile.
   - `cut_frames.py` writes frames 0 to 2 as PNG and 10 frames either side of every cut, plus one labelled strip per cut. Read the start frames (sharp face, eyes open, no hand, no blur) and every strip (no blink or half-blink next to a cut, no blur on the cut frame unless the cut sits inside a `cover` window, no flash, no duplicate frame).
   - Iterate the cutlist until everything passes.

## Gotchas

- Seconds such as 2.13 are not on a 25 fps grid. Every edge is converted to whole frames (`in` floor, `out` ceil) first.
- A blink detected at a time often starts closing 1 to 2 frames earlier, and the eyes stay heavy for 2 to 3 frames after it. Frame-step the eye crop, then move the video edge or hold a frame; never move the audio for a blink.
- A J-cut that pulls the incoming video earlier can land on the soft frames at the start of a take. Check the incoming frames' face sharpness, not only the blink list.
