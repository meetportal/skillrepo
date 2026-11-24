---
name: reel-qa
description: Delivery gates and critic loop for vertical short-form reels (Reels, TikTok, Shorts). Use after a reel is rendered or exported, before anything is handed over, when asked to check, verify or QA a reel, when a render might be stale against the current cut, or when running the independent critic pass. Measures spec, loudness, A/V drift and voice sync, rhythm, splice clicks, missing or ghost words, caption safe zone, colour levels and first-frame sharpness, and writes contact sheets around every cut and graphic entrance.
---

# reel-qa

Last stage of the reel pipeline. Input: a muxed render (normally `out/reel_vN.mp4` from `reel-export`) plus whatever the reel work folder holds. Output: `qa/report.md`, `qa/report.json`, `qa/first_frames.jpg`, `qa/sheets/*.jpg`, `qa/asr_diff_delivered.json`. A failing gate blocks delivery.

Run from the reel work folder, with `SKILLS` pointing at the repo's `skills/` folder:

```bash
python $SKILLS/reel-qa/scripts/qa.py --reel out/reel_v1.mp4 \
  --asr-prompt "Brand Name. ACRONYM, ACRONYM." --asr-allow "intended>heard" \
  --dictionary $SKILLS/<brand-skill>/caption-dictionary.json
```

Exit code 0 means every gate that ran passed; 1 means at least one FAIL or ERROR. `--only spec,loudness` or `--skip asr` runs a subset (the report then says "Partial run"). Everything has `--help`.

## What it reads from the work folder

| File | Used by | Without it |
|---|---|---|
| `edl.json` | splices, expected duration | splices skipped |
| `cues.json` | rhythm (planned cuts), levels (segments), sheets, first-frame face box | whole-reel levels, centre crop for sharpness |
| `beatmap.json` | rhythm (beat events), sheets (beat entrances), takeover cover for hidden cuts | fewer events |
| `camera_plan.json` | rhythm (scale changes) | fewer events |
| `props.json` | expected duration (`durationSec`) | EDL duration (+ `--extra-sec`) |
| `words.out.json` | ASR diff | asr skipped |
| `voice.wav` (else `voice_cut.wav`, or `--voice-ref`) | voice sync and stale-voice check | durations only |
| `aroll.mp4` | black level comparison (double range conversion) | no comparison |
| `qa/captions_bbox.json` (or `--captions-bbox`) | caption safe zone | captions skipped |

## Gates

| Gate | Method | Pass |
|---|---|---|
| `spec` | ffprobe via `reel-export/scripts/delivery_spec.py` | H.264 High level 4.2, 1080x1920, SAR 1:1, 25/1 CFR, yuv420p, tv range, BT.709 primaries/transfer/matrix, exactly 1 video + 1 audio stream, AAC-LC 48 kHz stereo, v/a within 40 ms, duration within 40 ms of the expected length, `moov` before `mdat` (faststart) |
| `loudness` | `ebur128=peak=true` on the delivered audio | I = -14 +/- 1 LUFS (`--target-lufs`), true peak at or below -1.5 dBTP, LRA at or below 7 LU |
| `drift` | video frames / fps vs audio stream duration; then the delivered audio's 2.5 ms RMS envelope cross-correlated against the processed voice in 6 s windows (lag search +/-400 ms) | v/a within 40 ms; voice file length equals the EDL within 40 ms; no window with correlation 0.5+ lagging more than 40 ms |
| `rhythm` | frame difference on a 108x192 grey decode (peak at least `--scene-threshold` 4.0 and 2x the local median), plus beat in/out times and camera scale changes from the plan | largest gap between visual changes at most 4.0 s (`--max-gap`); every `cues.json` cut visible in the render unless a takeover beat covers it. WARN when scene detection alone leaves a gap over 4 s (the plan closes it; confirm on the sheets) |
| `splices` | audio discontinuities from the EDL (source change or `a_out` != next `a_in`), on the delivered audio: 5 kHz high-pass burst in +/-10 ms vs the median of 16 to 50 ms either side, max sample step in +/-10 ms vs the 99th percentile of 15 to 50 ms either side, and the dip under local room tone | click = burst over 6 dB (`--click-db`) and step ratio over 2 and peak above -60 dBFS. A dip over 10 dB (`--hole-db`) is a WARN (room-tone hole; lay a bed or room tone under it) |
| `asr` | `reel-captions/scripts/asr_diff.py` (faster-whisper large-v3 int8 on the delivered audio, difflib against `words.out.json`) | no blocking missing, extra or changed words. Deliberate caption edits go in `--asr-allow "intended>heard"`; brand spellings in `--dictionary`. `--asr-heard` reuses a transcript |
| `captions` | page boxes from the caption renderer | every page inside x 70-950, y 220-1500 and on screen at least 0.35 s |
| `levels` | `signalstats` on every 5th frame (`--levels-step`), grouped by `cues.json` segment plus the end card; raw Y-plane percentiles on 3 frames per segment; 1st-percentile black compared with the same frame of `aroll.mp4` | p0.1 at least 15 and p99.9 at most 236 per segment. A black-level shift of 6+ codes against the A-roll is a WARN (graphics over the frame, or a second range conversion) |
| `sheets` | one strip per cut and per beat entrance, `--sheet-radius` 4 frames either side, 180x320 thumbnails, event frame outlined red | INFO: read every sheet |
| `first_frame` | Laplacian variance of the face box (from `cues.json` segment 0, x1.4) on frames 0, 1, 2 vs the median of every 5th frame from 0.5 s to the end of the first shot (max 4 s) | all three at least 60 % of that median (`--first-frame-ratio`). Writes `qa/first_frames.jpg` |

`captions_bbox.json` format (one entry per caption page, output seconds or ms):

```json
{"pages": [{"text": "first page", "start": 0.04, "end": 0.90, "bbox": [180, 1130, 900, 1230]},
           {"text": "next page", "startMs": 900, "endMs": 1600, "x": 200, "y": 1120, "w": 600, "h": 96}]}
```

## Reading the report

- Fix FAILs at the stage that owns them: spec and loudness in `reel-export`/`reel-sound`, drift in `reel-cut`/`voice-clean` (a stale `voice.wav` shows as "voice.wav is X s but the EDL is Y s" and lag steps of 120 to 240 ms), rhythm in the beat map or camera plan, splice clicks in the EDL fades, ASR differences in the cut (missing = clipped edge, extra = ghost word) or in the caption text, levels in `reel-grade`, first frame by moving the first cut or covering frames 0 to 7 with the hook graphic.
- "cuts from cues.json not visible in the render" means the graphics pass was rendered from an older A-roll or cue file. Re-render it before anything else; every other visual number is suspect until then.
- Look at every sheet: blink or half-blink next to a cut frame, flash frames, a graphic covering the face, captions on the chin, text cut by the frame edge. Numbers do not catch these.
- `report.json` has every measurement (per-window sync lags, per-splice metrics, per-segment levels, scene-change times) for scripts and for the critic.

## Not covered by qa.py (say so in the hand-over)

- Listening: denoiser artefacts, de-esser lisp, gate pumping, bed level, SFX masking. Hand the owner 5 timestamps: the hook (0.0), the first title slam, the loudest SFX, the longest held pause, the end card.
- Caption timing against each onset (0 to 2 frames early) and mouth overlap: extract frames at 5 or 6 onsets and look.
- Graphics content: text size, invented numbers, colour meanings, third-party UI.
- Taste. That is the critic.

## Critic loop

After the gates pass (or with known FAILs listed), run an independent critic sub-agent with `references/critic-prompt.md`: it has not seen the plan, it roasts and does not praise, and it returns a severity-ranked table with timecodes and one concrete fix per row. Fix BLOCKER and MAJOR rows, export a new version, re-run `qa.py`, and spawn a fresh critic. At most 3 passes.

## Performance

On an 8-core CPU, a 49 s reel takes about 1.5 to 2 minutes for all gates: ASR about 55 s, levels about 20 s, sheets about 11 s (31 sheets), rhythm about 7 s, the rest under 2 s each.
