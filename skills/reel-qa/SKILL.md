---
name: reel-qa
description: Delivery gates and critic loop for vertical short-form reels (Reels, TikTok, Shorts). Use after a reel is rendered or exported, before anything is handed over, when asked to check, verify or QA a reel, when a render might be stale against the current cut, when comparing a render with a reference video, or when running the independent scored critic pass. Measures spec, loudness, silences, A/V drift and voice sync, rhythm, every frame (pops, black, white, frozen, empty entrances, 3D inserts), cover windows, splice clicks, missing or ghost words, caption safe zone, captions across cuts and accent contrast, colour levels and first-frame sharpness, and writes full-reel contact sheets, sheets around every cut and graphic entrance, and side-by-side reference sheets.
---

# reel-qa

Last stage of the reel pipeline. Input: a muxed render (normally `out/reel_vN.mp4` from `reel-export`) plus whatever the reel work folder holds. Output: `qa/report.md`, `qa/report.json`, `qa/frames.npz`, `qa/first_frames.jpg`, `qa/sheets/full_NN.jpg` (every frame), `qa/sheets/NN_<kind>_<t>s.jpg` (around events), `qa/asr_diff_delivered.json`. A failing gate blocks delivery.

Run from the reel work folder, with `SKILLS` pointing at the repo's `skills/` folder:

```bash
python $SKILLS/reel-qa/scripts/qa.py --reel out/reel_v1.mp4 \
  --asr-prompt "Brand Name. ACRONYM, ACRONYM." --asr-allow "intended>heard" \
  --dictionary $SKILLS/<brand-skill>/caption-dictionary.json
```

Exit code 0 means every gate that ran passed; 1 means at least one FAIL or ERROR. `--only frames,silence,cover,captions` or `--skip asr` runs a subset (the report then says "Partial run"). `--threads` (default 4) sets the CPU threads of every faster-whisper call and of the frames decode; use 2 on a shared machine. Everything has `--help`.

## What it reads from the work folder

| File | Used by | Without it |
|---|---|---|
| `edl.json` | splices, expected duration | splices skipped |
| `cues.json` | rhythm (planned cuts), levels (segments), sheets, first-frame face box | whole-reel levels, centre crop for sharpness |
| `beatmap.json` | rhythm (beat events), sheets (beat entrances), takeover cover for hidden cuts | fewer events |
| `camera_plan.json` | rhythm (scale changes) | fewer events |
| `props.json` | expected duration (`durationSec`) | EDL duration (+ `--extra-sec`) |
| `words.out.json` | ASR diff | asr skipped |
| `voice.wav` (else `voice_cut.wav`, or `--voice-ref`) | voice sync, stale-voice check, splice clicks | durations only; clicks measured on the delivered audio |
| `aroll.mp4` | black level comparison (double range conversion) | no comparison |
| `qa/captions_bbox.json` (or `--captions-bbox`), from `reel-motion/scripts/render.sh --caption-boxes` | caption safe zone, captions across cuts, accent contrast, frames (page starts and ends are planned events) | captions skipped |
| `props.json` `beats`, `camera`, `accents` (else `beatmap.json` and `camera_plan.json`) | frames (planned events, entrance zones, 3D windows), captions (accent pages) | fewer planned events, no contrast check |
| `3d/*.json` from `reel-3d/scripts/render3d.py` | frames (3D events are planned) | none |
| `qa/mix_report.json` (or `--mix-report`), its `dropouts` list | silence and frames (planned dropouts) | every silence is reported |
| `brand.json` from `--brand`, else `$REEL_BRAND`, else the bundled `mailinfra-brand` | frames (`layout.cardBox` is the card zone), captions (`colors.accent`) | card zone x 70-950, y 1150-1480; accent `#F09C48` |

## Gates

| Gate | Method | Pass |
|---|---|---|
| `spec` | ffprobe via `reel-export/scripts/delivery_spec.py` | H.264 High level 4.2, 1080x1920, SAR 1:1, 25/1 CFR, yuv420p, tv range, BT.709 primaries/transfer/matrix, exactly 1 video + 1 audio stream, AAC-LC 48 kHz stereo, v/a within 40 ms, duration within 40 ms of the expected length, `moov` before `mdat` (faststart) |
| `loudness` | `ebur128=peak=true` on the delivered audio | I = -14 +/- 1 LUFS (`--target-lufs`), true peak at or below -1.5 dBTP, LRA at or below 7 LU |
| `silence` | `silencedetect=n=-45dB:d=0.3` (`--silence-db`, `--silence-min`) on the delivered audio | WARN for every silence that overlaps no planned dropout from `qa/mix_report.json` and lies before the last 0.3 s |
| `drift` | video frames / fps vs audio stream duration; then the delivered audio's 2.5 ms RMS envelope cross-correlated against the processed voice in 6 s windows (lag search +/-400 ms) | v/a within 40 ms; voice file length equals the EDL within 40 ms; no window with correlation 0.5+ lagging more than 40 ms |
| `rhythm` | frame difference on a 108x192 grey decode (peak at least `--scene-threshold` 4.0 and 2x the local median), plus beat in/out times and camera scale changes from the plan | largest gap between visual changes at most 4.0 s (`--max-gap`); every `cues.json` cut visible in the render unless a takeover beat covers it. WARN when scene detection alone leaves a gap over 4 s (the plan closes it; confirm on the sheets) |
| `frames` | `scripts/framecheck.py`: the reel decoded once at 180x320 rgb24. Per frame: mean Rec.709 luma (0 to 1), std, p2, p98, mean saturation (pixels with max channel under 0.06 left out), `diff` = mean abs grey difference to the previous frame (0 to 255). Planned events (each +-1 frame): `cues.cuts`, cue segment `holds`, EDL `v_hold` ranges, every beat `from` and `to`, beat prop times (`*At`, `*Start`, `*End`, `*Times`, `events[].t`, beat-relative), every camera key (kick windows `t` to `t + frames/fps`, glide windows centred on `t`), caption page starts and ends, `3d/*.json` events, mix dropouts | FAIL: black (mean luma under 0.04, outside the last 0.2 s); unplanned white (over 0.93, outside planned events and the end card); a frozen span inside a 3D beat (`VideoInsert` with `props.three`); a 3D frame with luma std under 0.01. WARN: pops (`diff` over 3 x the median of the 8 frames either side, self excluded, + 1.0, a spike of 1 or 2 frames that peaks above its neighbours; runs of 3 or more are transitions, listed in `report.json` only, and a spike on the 3 frames after an empty entrance belongs to that entrance); frozen spans (12+ frames, `--frozen-frames`, with `diff` under 0.25, `--frozen-diff`, outside holds and the end card from its `from` + 1 s); empty entrance frame (see below). Writes `qa/frames.npz`, per-segment medians of luma, std, p2, p98 and saturation, and `qa/sheets/full_NN.jpg`: 60 frames per sheet (10 x 6 thumbs of 108x192, 2.4 s at 25 fps), frame number and time on every thumb, flagged frames outlined red |
| `cover` | for each `cues.cover` window, every frame's share of pixels with R - B over 20 (`--cover-rb`) at 180x320 | FAIL when any frame of the window is over 0.05 (`--cover-max-skin`): the A-roll shows where a full-frame graphic must hide it |
| `splices` | audio discontinuities from the EDL (source change or `a_out` != next `a_in`). Clicks are measured on the voice stem (`voice.wav`, else `voice_cut.wav`, or `--voice-ref`) so music and SFX transients near a splice do not count: 5 kHz high-pass burst in +/-10 ms vs the median of 16 to 50 ms either side, and max sample step in +/-10 ms vs the 99th percentile of 15 to 50 ms either side. The room-tone hole (dip under the local level, 10 ms RMS) is measured on the delivered audio, where the bed can fill it. Without a voice stem both run on the delivered audio | click = burst over 6 dB (`--click-db`) and step ratio over 2 and peak above -60 dBFS. A dip over 10 dB (`--hole-db`) is a WARN: cut 1 s around it from the delivered audio, `voice.wav` and the bed stem and compare 10 ms RMS and spectrograms. If the bed stays well above the voice's room tone through the dip (15 dB or more), the hole is masked; otherwise lay room tone under the splice |
| `asr` | `reel-captions/scripts/asr_diff.py` (faster-whisper large-v3 int8 on the delivered audio, difflib against `words.out.json`) | no blocking missing, extra or changed words. Deliberate caption edits go in `--asr-allow "intended>heard"`; brand spellings in `--dictionary`. `--asr-heard` reuses a transcript |
| `captions` | page boxes from the caption renderer; for pages with an accent word (`props.json` `accents`, `n` picks one occurrence), the frame at the page middle at full size | FAIL: a page outside x 70-950, y 220-1500 or on screen under 0.35 s. WARN: a page whose `endFrame` lands 1 to 3 frames after a `cues.cuts` frame (the old page shows on the new shot; end it on the cut frame). WARN: WCAG contrast of the brand accent (`--accent-color`) against the 75th percentile relative luminance of a 24 px ring (`--accent-ring`) outside the page box under 3:1 (`--accent-contrast`); never a FAIL |
| `levels` | `signalstats` on every 5th frame (`--levels-step`), grouped by `cues.json` segment plus the end card; raw Y-plane percentiles on 3 frames per segment; 1st-percentile black compared with the same frame of `aroll.mp4` | p0.1 at least 15 and p99.9 at most 236 per segment. A black-level shift of 6+ codes against the A-roll is a WARN (graphics over the frame, or a second range conversion) |
| `sheets` | one strip per cut and per beat entrance, `--sheet-radius` 4 frames either side, 180x320 thumbnails, event frame outlined red | INFO: read every sheet |
| `first_frame` | Laplacian variance of the face box (from `cues.json` segment 0, x1.4) on frames 0, 1, 2 vs the median of every 5th frame from 0.5 s to the end of the first shot (max 4 s) | all three at least 60 % of that median (`--first-frame-ratio`). Writes `qa/first_frames.jpg` |

### Empty entrance frames

For every beat, the zone is the full frame for `takeover` and `hidden` beats and for a full-fit `VideoInsert`, `props.box` when the beat has one, else the brand card box. The first frame of the beat (`from` rounded the way the renderer rounds, half up) is an **empty entrance frame** (WARN) when any of these holds:

| Test | Rule | Catches |
|---|---|---|
| unchanged | zone `diff` on the first frame under 0.5 (`--entrance-min-diff`) | nothing drawn over a still background |
| late | zone `diff` on the second frame over 4 x (`--entrance-lag-ratio`) the first frame's + 2 | the graphic first shows one frame after `from` |
| blank | inner zone (10 % inset) mean abs luma gradient under 0.004 (`--entrance-blank`) on the first or second frame | an empty panel or an empty navy takeover |
| handoff | a beat in the same zone ends within 1 frame of this `from`, and the first frame's A-roll share (R - B over 20) is 0.2 (`--handoff-uncovered`) above both neighbours | a frame of bare A-roll between two cards |

A graphic whose first frame lands on a cut is only caught by the blank and handoff tests: the cut hides the lag.

### Side-by-side reference sheets

```bash
python $SKILLS/reel-qa/scripts/sbs_sheet.py --ours out/reel_v3.mp4 --ours-times 0.4,3.2,7.3,21.7 \
  --ref refs/reference.mp4 --ref-times 0.5,2.9,6.8,20.1 --height 640 --out qa/sbs/sbs_01.jpg
```

Our frames on the top row, the reference on the bottom row, both scaled to `--height`, white gutters, a time label on every frame (file name for image folders). `--ref` takes a video, one image or a folder of images (sorted by name); `--ref-times` defaults to `--ours-times` for a video. Frames are read straight from the sources and only the sheet is written: reference media stays where it is, never copy it into the work folder, the repo or anywhere else. Pick moments that match in purpose (hook, first graphic, a takeover, the end card), not in time.

### `captions_bbox.json` format (one entry per caption page, output seconds or ms; `reel-motion`'s exporter writes `start`/`end` of the page's visible frames and `bbox`, plus extra keys the gate ignores):

```json
{"pages": [{"text": "first page", "start": 0.04, "end": 0.90, "bbox": [180, 1130, 900, 1230]},
           {"text": "next page", "startMs": 900, "endMs": 1600, "x": 200, "y": 1120, "w": 600, "h": 96}]}
```

## Reading the report

- Fix FAILs at the stage that owns them: spec and loudness in `reel-export`/`reel-sound`, drift in `reel-cut`/`voice-clean` (a stale `voice.wav` shows as "voice.wav is X s but the EDL is Y s" and lag steps of 120 to 240 ms), rhythm in the beat map or camera plan, splice clicks in the EDL fades, ASR differences in the cut (missing = clipped edge, extra = ghost word) or in the caption text, levels in `reel-grade`, first frame by moving the first cut or covering frames 0 to 7 with the hook graphic.
- "cuts from cues.json not visible in the render" means the graphics pass was rendered from an older A-roll or cue file. Re-render it before anything else; every other visual number is suspect until then.
- Look at every sheet: blink or half-blink next to a cut frame, flash frames, a graphic covering the face, captions on the chin, text cut by the frame edge. Numbers do not catch these. Read the full sheets (`full_NN.jpg`) start to end once per version; every red outline needs a reason.
- frames: an empty entrance frame or a handoff hole is fixed in `reel-motion` (the entrance must draw on its first frame; at a handoff the next beat starts on the frame the last one ends). A pop at a hold release is fixed in the EDL (`reel-cut`). Black, white and frozen FAILs are render problems: re-render the graphics pass.
- cover: put a `takeover` or `hidden` beat over the whole window (`reel-director` beat map), then re-render.
- captions across a cut and low accent contrast are `reel-captions` and `reel-motion` fixes (end the page on the cut frame; `accentStyle` or `localScrim`).
- silence: a gap the mix did not plan is a `reel-sound` fix (room tone or bed); list deliberate dropouts in the mix so the gate skips them.
- `report.json` has every measurement (per-window sync lags, per-splice metrics, per-segment levels, scene-change times) for scripts and for the critic.

## Not covered by qa.py (say so in the hand-over)

- Listening: denoiser artefacts, de-esser lisp, gate pumping, bed level, SFX masking. Hand the owner 5 timestamps: the hook (0.0), the first title slam, the loudest SFX, the longest held pause, the end card.
- Caption timing against each onset (0 to 2 frames early) and mouth overlap: extract frames at 5 or 6 onsets and look.
- Graphics content: text size, invented numbers, colour meanings, third-party UI.
- Taste. That is the critic.

## Critic loop

After the gates pass (or with known FAILs listed), run an independent critic sub-agent with `references/critic-prompt.md`: it has not seen the plan, it roasts and does not praise, it scores 8 areas from 1 to 10 (`hook, rhythm, cuts, captions, graphics, layout, grade, end`) and returns a severity-ranked table with timecodes, frame numbers, the owning stage and one concrete fix per row. Log every pass as `| pass | hook | rhythm | cuts | captions | graphics | layout | grade | end | mean |` in `project.md`. Fix BLOCKER and MAJOR rows, export a new version, re-run `qa.py`, and spawn a fresh critic. Stop when a pass has no BLOCKER or MAJOR and the mean did not rise over the previous pass, or after 3 passes.

## Calibration

Measured on three delivered talking-head reels of 49.5 s (1201 to 1238 frames, 25 fps), rendered before entrances were fixed:

| Check | Measured | Chosen |
|---|---|---|
| planned events | 210 to 332 exempt frames per reel | +-1 frame per event |
| pops | 0, 0 and 1 unplanned WARNs (the 1 is a real jump when motion resumes after a 5-frame hold); 0 to 1 transition runs (a takeover dissolve) | 3 x local median + 1.0, spikes of 1 or 2 frames |
| black and white | mean luma 0.093 to 0.905 per frame; the cream end card is the 0.905 | 0.04 and 0.93; 0 FAILs |
| frozen | talking head never 12 frames under `diff` 1.0; mean `diff` 4.0 to 4.1; 4.8 to 7.2 % of frames under 0.25; 0.25 and 0.5 flag the same spans | 0.25 over 12 frames; 0 FAILs, 1 WARN in one reel (a still takeover title for 16 frames with only the caption changing) |
| empty entrances | 9 of 17, 10 of 17 and 4 of 5 beats flagged, every one confirmed on the sheets; late ratios 6.8 to 31 on flagged beats, at most 3.6 on good ones; blank panels 0.0016 to 0.0028, drawn frames 0.0055 or more; handoff holes 0.25 to 0.30 above both neighbours, good handoffs at most 0.09 | 4.0, 0.004, 0.2 |
| captions across cuts | 7, 10 and 8 pages ending 1 to 3 frames after a cut | WARN at 1 to 3 frames |
| accent contrast | 1.01 to 2.8:1 over the bright wall, 7.8 to 8.9:1 over navy; 14 of 15, 7 of 9 and 12 of 15 accent pages under 3:1 | WARN under 3:1 |
| cover | A-roll frames: median share 0.62 to 0.67, 10th percentile 0.27 to 0.48; a navy takeover window 0.0011 | R - B over 20, at most 0.05 |
| silence | 0 WARNs | -45 dB for 0.3 s |

`scripts/test_gates.py --scratch DIR` builds two synthetic 1080x1920 25 fps reels with known faults (a black frame, a white frame, a 20-frame freeze, a 1-frame pop, an uncovered cover window, an empty entrance, a handoff hole, a frozen and a uniform 3D insert, a caption page across a cut, an accent page on a bright band) and checks that the gates report exactly those faults at the right frames and nothing else. Run it after any change to the gates.

## Performance

On an 8-core CPU, a 49 s reel takes about 2 to 2.5 minutes for all gates: ASR about 55 s with 8 threads (about 100 s with `--threads 2`), levels about 20 s, sheets about 11 s (31 sheets), frames 8.5 to 11 s (decode 5 to 8 s, measurements about 2.5 s, about 550 MB of memory, 21 full sheets), rhythm about 7 s, captions 3 to 5 s, the rest under 2 s each. Run under `nice -n 19 ionice -c 3` on a shared machine.

## Licence

`scripts/framecheck.py`, the silence gate in `scripts/qa.py` and `scripts/sbs_sheet.py` adapt MIT-licensed code. The project name, copyright line and the permission text are in `NOTICE`; keep that file with the skill.
