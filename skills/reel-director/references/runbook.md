# Runbook: raw clips to a gated reel

One command per step, in order. Every command runs from the reel work folder; data paths are relative to it, script paths go through `$SKILLS`. The stage numbers match the stage table in `../SKILL.md`. Read what each script prints, and look at every image it writes, before the next step. `status.py` tells you at any time which outputs are missing or stale and which command comes next.

Numbers in the examples (`--duration`, `--extra-sec`, `--bed-lift`, downbeat targets, still times) are placeholders: take them from your own `cues.json`, `beatmap.json` and `props.json`.

## Setup (once per shell)

```bash
export SKILLS=/path/to/repo/skills
export MODELS=/path/to/models
export RAW=/path/to/raw/clips
export REEL_CONCURRENCY=2
export REEL_RENDER_LOCK=/path/to/locks/remotion.lock
cd work/<series>/<reel>
```

- `REEL_CONCURRENCY` (default 2) is the Remotion concurrency of every render entry point (`reel-motion/scripts/render.sh`, `reel-3d/scripts/render3d.py`).
- `REEL_RENDER_LOCK`, when set, makes every Remotion render or still run under `flock "$REEL_RENDER_LOCK"`, so two agents never render at the same time on one machine. With `REEL_RENDER_LOCK` set, do not also wrap a command in `flock` on the same file: `render.sh` takes the lock again and waits on itself forever.
- On a shared machine prefix the heavy steps (transcription, alignment, A-roll render, voice, Remotion, mix, export, QA) with `nice -n 19 ionice -c 3` and give faster-whisper `--threads 2`.

## 0. New reel

```bash
bash $SKILLS/reel-director/scripts/new_reel.sh .
python $SKILLS/reel-director/scripts/status.py --raw "$RAW"
```

`new_reel.sh` creates `config/`, `ingest/`, `voice_lab/`, `music/`, `sfx/`, `3d/`, `out/`, `qa/` and copies the templates (mock values: replace every one). It never overwrites. The series style bible lands next to the reel folder the first time; read it now. Fill `config/cutlist.json` with the clip paths and `project.md` with the brief.

Smoke test without footage: `python $SKILLS/reel-director/scripts/make_mock_reel.py mock` builds a 12 s synthetic A-roll, `edl.json`, `words.out.json` and `cues.json` for the mock sentence, then run `new_reel.sh mock` and continue at stage 8.

## 1. Ingest (`reel-ingest`)

```bash
python $SKILLS/reel-ingest/scripts/probe.py "$RAW"/*.MP4 --out ingest/probe.json
python $SKILLS/reel-ingest/scripts/rotation_check.py "$RAW"/*.MP4 --out qa/stage1/rotation_check.jpg
python $SKILLS/reel-ingest/scripts/frame_metrics.py "$RAW"/*.MP4 --model "$MODELS"/face_detection_yunet_2023mar.onnx --rotate 2 --out ingest/frame_metrics.json
python $SKILLS/reel-ingest/scripts/transcribe.py "$RAW"/*.MP4 --prompt "Brand. Acronyms." --threads 2 --out ingest/words_raw.json
python $SKILLS/reel-ingest/scripts/snap_words.py ingest/words_raw.json --resegment --cache ingest/segment_cache.json --threads 2 --frame-metrics ingest/frame_metrics.json --out ingest/words_snapped.json
python $SKILLS/reel-ingest/scripts/align_words.py ingest/words_snapped.json --pronunciations config/pronunciations.json --overrides config/word_overrides.json --out ingest/transcript.json
python $SKILLS/reel-ingest/scripts/check_onsets.py --transcript ingest/transcript.json --out ingest/onsets_energy.json
python $SKILLS/reel-ingest/scripts/check_onsets.py --transcript ingest/transcript.json --asr-every 1 --model medium.en --out ingest/onsets_asr.json
```

`snap_words.py` cleans the text; `align_words.py` sets the force-aligned times every later stage uses. `--pronunciations` and `--overrides` are optional files. Both onset gates pass before cutting.

## 2. Read the script, plan beats (`reel-director`)

```bash
python $SKILLS/reel-director/scripts/packed_transcript.py ingest/transcript.json
python $SKILLS/reel-director/scripts/beat_sheet.py ingest/transcript.json
```

Paste both into `project.md`. The beat sheet marks every phrase where the picture would sit still for more than 2.5 s: plan a cut, scale change, kick or beat there. Write three hook variants (`script-brief.md`), pick the 3D moments (`../../reel-3d/references/when-3d.md`), fill the "Beat map" and "3D moments" tables.

## 3. Cut list and EDL (`reel-cut`)

```bash
python $SKILLS/reel-cut/scripts/plan_cuts.py --transcript ingest/transcript.json --exclusions ingest/frame_metrics.json --config config/cutlist.json --out edl.json --report plan_report.json
```

## 4 and 5. A-roll, words, cues, grade (`reel-cut`, `reel-captions`, `reel-grade`)

```bash
python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video aroll.mp4 --out-audio voice_cut.wav --threads 4
python $SKILLS/reel-cut/scripts/retime_words.py --edl edl.json --transcript ingest/transcript.json --out words.retimed.json
python $SKILLS/reel-captions/scripts/apply_corrections.py --words words.retimed.json --corrections config/corrections.json --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json --out words.out.json
python $SKILLS/reel-cut/scripts/build_cues.py --edl edl.json --words words.out.json --frame-metrics ingest/frame_metrics.json --config config/cues_config.json --out cues.json
```

Verify the cut (iterate `config/cutlist.json` until all pass):

```bash
python $SKILLS/reel-cut/scripts/drift_gate.py --edl edl.json --video aroll.mp4 --audio voice_cut.wav
python $SKILLS/reel-cut/scripts/splice_check.py --edl edl.json --audio voice_cut.wav --out qa/stage1/splices.json
python $SKILLS/reel-cut/scripts/cut_frames.py --video aroll.mp4 --cues cues.json --out qa/stage1/cuts
python $SKILLS/reel-captions/scripts/asr_diff.py --mode cut --media voice_cut.wav --words words.out.json --edl edl.json --corrections config/corrections.json --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json --prompt "Brand. Acronyms." --out qa/stage1/asr_diff.json
python $SKILLS/reel-ingest/scripts/check_onsets.py --words words.out.json --audio voice_cut.wav --out qa/stage1/onsets_out.json
```

Grade loop (stage 4): draft render, measure the cheek patch per shot and across cuts, fit the exposure curve, render again.

```bash
python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video qa/stage1/grade_try.mp4 --out-audio qa/stage1/grade_try.wav --preset veryfast --threads 4
python $SKILLS/reel-grade/scripts/cut_levels.py qa/stage1/grade_try.mp4 --cues cues.json --model "$MODELS"/face_detection_yunet_2023mar.onnx --edge-frames 5 --out qa/stage1/levels_try.json
python $SKILLS/reel-grade/scripts/match_exposure.py --levels qa/stage1/levels_try.json --cues cues.json --grade config/grade.json --out config/grade.json
python $SKILLS/reel-grade/scripts/tone.py --mid 1.1 --high -6
```

When the levels pass, re-run the first command of this stage (the final `aroll.mp4`).

## 6. Voice (`voice-clean`)

```bash
python $SKILLS/voice-clean/scripts/diagnose.py "$RAW"/*.MP4 --out-dir voice_lab/diagnosis
python $SKILLS/voice-clean/scripts/ab_render.py --input voice_cut.wav --presets tone-only dialogue dialogue-df --reference tone-only --gate-pair dialogue:tone-only --words words.out.json --spectrograms --listen-copies --out-dir voice_lab/cut_ab
python $SKILLS/voice-clean/scripts/process_voice.py --input voice_cut.wav --output voice.wav --preset dialogue --edl edl.json --clip-params voice_lab/clip_params.json --words words.out.json --report voice_lab/voice.report.json
python $SKILLS/voice-clean/scripts/check_splices.py --edl edl.json --audio voice_cut.wav --audio voice.wav --out voice_lab/splices.json
python $SKILLS/voice-clean/scripts/asr_diff.py --reference voice_cut.wav --candidate voice.wav --prompt "Brand. Acronyms." --out voice_lab/asr_diff.json
```

The preset comes from the A/B (`dialogue` is the usual pick). `--clip-params` is optional.

## 7. Caption text (`reel-captions`)

Already done in stage 5 (`apply_corrections.py`, the only caption text layer). Re-run it, then `build_cues.py`, after every change to `config/corrections.json`, and re-run everything in stage 8 after that.

## 8. Camera, beat map, props, graphics (`reel-motion`)

```bash
python $SKILLS/reel-motion/scripts/plan_camera.py --cues cues.json --shots config/shots.json --out camera_plan.json
python $SKILLS/reel-motion/scripts/resolve_beatmap.py --cues cues.json --input config/beatmap.src.json --out beatmap.json --extra-sec 2.5
python $SKILLS/reel-director/scripts/beat_audit.py --beatmap beatmap.json --cues cues.json --camera camera_plan.json
python $SKILLS/reel-director/scripts/beat_sheet.py words.out.json --beatmap beatmap.json --camera camera_plan.json --cues cues.json
python $SKILLS/reel-motion/scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll "$PWD/aroll.mp4" --public-dir "$PWD" --extra-sec 2.5 --out props.json
```

Fix every `beat_audit.py` FAIL in the beat map source or the shot config before rendering. Anchors inside `beats[].props` resolve to seconds relative to the beat's `from`; anchors inside `props.three.props` stay absolute output seconds.

### 8b. 3D inserts (`reel-3d`), only when the beat map has a `VideoInsert` beat with `props.three`

```bash
python $SKILLS/reel-3d/scripts/render3d.py --beatmap beatmap.json --props props.json --public-dir . --out-dir 3d --stills
```

Renders each 3D beat once to `3d/<beatId>.mov` (ProRes 4444, opaque, `--gl=swangle`) with `3d/<beatId>.json` (hash, events), and skips beats whose hash did not change. Look at `3d/stills/` before the full pass.

### Stills, full pass, caption boxes

```bash
bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --still 0.0,1.0,7.3 --out out/stills
bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --out out/gfx.mp4
bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --caption-boxes --out qa/captions_bbox.json
```

The full pass records the A-roll md5 in `out/gfx.mp4.aroll.md5`; `status.py` marks the pass STALE when it no longer matches `aroll.mp4`.

## 9. Sound (`reel-sound`)

```bash
python $SKILLS/reel-sound/scripts/sfx_synth.py --out-dir sfx --seed 1
python $SKILLS/reel-sound/scripts/analyze_music.py music/candidates/*.mp3 --out music/analysis.json
python $SKILLS/reel-sound/scripts/find_downbeats.py music/bed.mp3 --targets 0:3,8.0,16.0 --duration 49 --allow-edits --out music/downbeats.json
python $SKILLS/reel-sound/scripts/sfx_cues.py place --cues config/sfx_cues.json --library sfx/manifest.json --beats beatmap.json --words words.out.json --voice voice.wav --level-mode lu --events "3d/*.json" --out sfx_placements.json
python $SKILLS/reel-sound/scripts/mix.py --voice voice.wav --voice-report voice_lab/voice.report.json --music music/bed.mp3 --music-plan music/downbeats.json --sfx sfx_placements.json --duck-mode words --words words.out.json --beats beatmap.json --duration 49.0 --bed-lift 46.5:4 --out-pre mix_pre.wav --out mix.wav --report qa/mix_report.json --cue-sheet qa/cue_sheet.md
python $SKILLS/reel-sound/scripts/credits.py --manifest sfx/manifest.json --manifest music/manifest.json --placements sfx_placements.json --used music/bed.mp3 --out CREDITS.txt
```

- `sfx_synth.py` writes an original, licence-free kit and its manifest (skip it when a vetted CC0 kit is in `sfx/`). The music bed needs the licence check of `reel-sound` before it touches the timeline.
- `--events "3d/*.json"` lets a cue name a 3D event (`"event": "spam3d.land"`); the whoosh peaks one frame before the land, one impact on the land frame.
- `mix.py` exits 2 when `voice.wav` does not come from the current `voice_cut.wav` (`--voice-report`). `--duck-mode sidechain` keeps the older sidechain path; `--dropout s:e`, `--voice-gain s:e:dB`, `--room-tone-src FILE:s:e` with `--room-tone-at s:e` and `--auto-ride-min-margin 10` are per-reel fixes. Read `qa/cue_sheet.md`.

## 10. Export (`reel-export`)

```bash
python $SKILLS/reel-export/scripts/export.py --video out/gfx.mp4 --audio mix.wav --out-dir out --name reel --edl edl.json --extra-sec 2.5 --cover-time 0.4 --srt words.out.json --threads 4
```

Never overwrites: writes `out/reel_vN.mp4` with the next free N.

## 11. Gates and the critic loop (`reel-qa`)

```bash
python $SKILLS/reel-qa/scripts/qa.py --reel out/reel_v1.mp4 --asr-prompt "Brand. Acronyms." --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json
python $SKILLS/reel-qa/scripts/sbs_sheet.py --ours out/reel_v1.mp4 --ours-times 0.4,3.2,7.3 --ref research/ref.mp4 --ref-times 0.4,3.0,7.0 --height 640 --out qa/sbs/sbs_01.jpg
python $SKILLS/craft-research/scripts/measure_reference.py out/reel_v1.mp4 --words words.out.json --out qa/ours_measure.json
```

Fix every FAIL, then run the critic loop of `../SKILL.md` (fresh critic per pass, the critic score table in `project.md` with `hook, rhythm, cuts, captions, graphics, layout, grade, end` scored 1 to 10, at most 3 passes). The side-by-side sheet and the measurement compare our reel with a reference measured the same way (`craft-research`); the reference media stays outside the repo.

## Re-run rules

| You changed | Re-run from |
|---|---|
| `config/cutlist.json` or the transcript | stage 3, then everything after it, in order |
| `config/grade.json` | `render_aroll.py`, then stage 8 full pass and everything after |
| `config/corrections.json` | `apply_corrections.py`, `build_cues.py`, stage 8 onward |
| `config/shots.json` or `config/beatmap.src.json` | stage 8 (`render3d.py` re-renders only beats whose hash changed), then 9 to 11 |
| a beat component or the brand | stills, full pass, then 10 and 11 |
| `config/sfx_cues.json`, music, mix flags | stage 9, then 10 and 11 |

Never mix outputs of two cuts. After any change, `python $SKILLS/reel-director/scripts/status.py` lists every STALE output (an output whose input is itself stale is stale too, so the whole chain shows) and the next command. A 3D clip shows UNKNOWN when its hash cannot be recomputed (no `props.json` fps, or `reel-3d` not installed).
