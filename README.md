# Reel editing skills

Agent skills and scripts that edit vertical talking-head reels (1080x1920, Instagram Reels, TikTok, YouTube Shorts) from raw camera clips to a delivered, gated MP4: transcript-driven jump cuts, per-segment grade, cleaned dialogue, Remotion camera moves, graphics and burned-in captions, music and SFX mixed to -14 LUFS, a fixed upload spec, and QA gates with an independent critic pass.

Each skill is a folder under `skills/` with a `SKILL.md` (when to use it, rules with numbers, commands), `scripts/` (Python 3.10+, ffmpeg, node) and sometimes `references/`. Start with `skills/reel-director/SKILL.md`: it is the entry point for "edit this reel" and routes every stage to the right skill.

## Skills, in stage order

| # | Skill | One line |
|---|---|---|
| 0 | [`reel-director`](skills/reel-director/SKILL.md) | Entry point: stage order, hard rules, `project.md`, beat-map planning, parallel builders, critic loop, source precedence, owner questions |
| 1 | [`reel-ingest`](skills/reel-ingest/SKILL.md) | Probe clips (range, rotation, tmcd, dual-mono), rotation sheet, per-frame sharpness, blinks and face boxes, faster-whisper transcript with energy-snapped words |
| 2 | [`reel-cut`](skills/reel-cut/SKILL.md) | EDL from snapped words (pause tightening, pads, J/L cuts around blinks), single-pass A-roll and cut-voice render, retimed words and `cues.json`, drift gate |
| 3 | [`reel-grade`](skills/reel-grade/SKILL.md) | Skin measurement, per-clip and per-segment exposure, one explicit full-to-tv range conversion, signalstats checks |
| 4 | [`voice-clean`](skills/voice-clean/SKILL.md) | Diagnose noise, A/B denoise chains, process the cut voice with latency compensation, splice and word-loss checks |
| 5 | [`reel-captions`](skills/reel-captions/SKILL.md) | Caption text corrections (index edits + brand dictionary), page and accent rules, delivered-audio ASR diff |
| 6 | [`mailinfra-brand`](skills/mailinfra-brand/SKILL.md) | Example brand kit: tokens, colour meanings, fonts, logos, CTA rules, claims policy (swap in your own brand folder) |
| 7 | [`reel-motion`](skills/reel-motion/SKILL.md) | Remotion 4 project: camera punch-ins and pushes, beat graphics in Talk / Card / Takeover layouts, captions last, stills and the `gfx.mp4` pass |
| 8 | [`reel-sound`](skills/reel-sound/SKILL.md) | Music licence check, downbeat sync, SFX cues on visible events, sidechain mix, two-pass linear loudnorm, `CREDITS.txt` |
| 9 | [`reel-export`](skills/reel-export/SKILL.md) | Delivery encode (H.264 High 4.2, AAC 256k, BT.709 tv, faststart), never `-shortest`, ffprobe spec gate, cover image, SRT, versioning |
| 10 | [`reel-qa`](skills/reel-qa/SKILL.md) | `qa.py`: spec, loudness, drift and voice sync, rhythm, splice clicks, ASR diff, caption safe zone, levels, contact sheets, first-frame sharpness; critic prompt |
| - | [`craft-research`](skills/craft-research/SKILL.md) | yt-dlp and gh research recipes, turning tutorials and owner notes into tested rules, untrusted-content handling, vetted sources |

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

- **Python 3.10+** with `requirements.txt` (faster-whisper, librosa, numpy, opencv-python, pyyaml, scipy, soundfile, yt-dlp). The first transcription downloads the faster-whisper `large-v3` model (about 3 GB); it runs int8 on CPU, about 1 minute per minute of audio on 8 cores.
- **ffmpeg and ffprobe 6.1 or newer** on `PATH`, built with libx264 (and libzimg if you use `zscale`). Check: `ffmpeg -hide_banner -filters | grep -E "loudnorm|ebur128|afftdn|deesser|signalstats"`.
- **Node 20 or newer** (tested on 24) for the Remotion stage: `cd skills/reel-motion/remotion && npm ci && npx remotion browser ensure`. All `@remotion/*` packages are pinned to one exact version.
- **Face model** (not bundled): YuNet `face_detection_yunet_2023mar.onnx` from the OpenCV model zoo (MIT), see `reel-ingest`.
- **Remotion licence**: Remotion is free for individuals and for companies of up to 3 people. A larger for-profit company needs a Remotion company licence before rendering its videos with `reel-motion` (see remotion.dev/license). Everything else here is MIT.
- Optional: the `deep-filter` binary (DeepFilterNet) for hard noise, see `voice-clean`.

## Folder convention

- One **work folder per reel** (for example `work/<reel>/`). Every command runs from it and writes into it. Raw clips stay where they are and are only read.
- `SKILLS` points at this repo's `skills/` folder. Scripts are always called as `python $SKILLS/<skill>/scripts/<script>.py` from the work folder, so data paths are relative to the work folder and script paths never are.
- Reel-specific settings (cut list, grade, shot config, beat map source, SFX cue list, caption edits) live in the work folder, usually `config/`. Nothing reel-specific goes into this repo.
- A different brand: copy `skills/mailinfra-brand` to your own folder, change `brand.json`, fonts and logos, and set `REEL_BRAND=/path/to/brand-folder` for the Remotion stage.

```
work/<reel>/
  project.md            plan, decisions, QA and critic log (reel-director)
  config/               cutlist.json, grade.json, shots.json, beatmap.src.json, caption edits ...
  ingest/               probe.json, frame_metrics.json, words_raw.json, transcript.json
  edl.json  aroll.mp4  voice_cut.wav  words.retimed.json  cues.json
  voice.wav  words.out.json
  camera_plan.json  beatmap.json  props.json
  music/  sfx/  sfx_cues.json  sfx_placements.json  mix.wav  CREDITS.txt
  out/                  stills/, gfx.mp4, reel_vN.mp4 (+ .json, cover, .srt)
  qa/                   report.md, report.json, first_frames.jpg, sheets/, cuts/
```

## End to end

```bash
export SKILLS=/path/to/repo/skills
cd work/<reel>
RAW="/path/to/raw/clips"

# 1. ingest
python $SKILLS/reel-ingest/scripts/probe.py "$RAW"/*.MP4 --out ingest/probe.json
python $SKILLS/reel-ingest/scripts/rotation_check.py "$RAW"/*.MP4 --out qa/rotation_check.jpg
python $SKILLS/reel-ingest/scripts/frame_metrics.py "$RAW"/*.MP4 --model models/face_detection_yunet_2023mar.onnx --rotate 2 --out ingest/frame_metrics.json
python $SKILLS/reel-ingest/scripts/transcribe.py "$RAW"/*.MP4 --prompt "Brand. Acronyms." --out ingest/words_raw.json
python $SKILLS/reel-ingest/scripts/snap_words.py ingest/words_raw.json --resegment --frame-metrics ingest/frame_metrics.json --out ingest/transcript.json

# 2. read the script, plan beats and the hook in project.md
python $SKILLS/reel-director/scripts/packed_transcript.py ingest/transcript.json

# 3-5. cut, grade, render, retime (iterate the grade with measure_skin + match_exposure)
python $SKILLS/reel-cut/scripts/plan_cuts.py --transcript ingest/transcript.json --exclusions ingest/frame_metrics.json --config config/cutlist.json --out edl.json --report plan_report.json
python $SKILLS/reel-cut/scripts/render_aroll.py --edl edl.json --grade config/grade.json --out-video aroll.mp4 --out-audio voice_cut.wav
python $SKILLS/reel-cut/scripts/drift_gate.py --edl edl.json --video aroll.mp4 --audio voice_cut.wav
python $SKILLS/reel-cut/scripts/retime_words.py --edl edl.json --transcript ingest/transcript.json --frame-metrics ingest/frame_metrics.json --out-words words.retimed.json --out-cues cues.json
python $SKILLS/reel-cut/scripts/cut_frames.py --video aroll.mp4 --cues cues.json --out qa/cuts
python $SKILLS/reel-grade/scripts/measure_skin.py aroll.mp4 --cues cues.json --model models/face_detection_yunet_2023mar.onnx --out qa/skin.json

# 6. voice
python $SKILLS/voice-clean/scripts/process_voice.py --input voice_cut.wav --output voice.wav --preset chain09 --edl edl.json --report voice_lab/voice.report.json
python $SKILLS/voice-clean/scripts/asr_diff.py --reference voice_cut.wav --candidate voice.wav --out voice_lab/asr_diff.json

# 7. caption text (the only text layer)
python $SKILLS/reel-captions/scripts/apply_corrections.py --words words.retimed.json --edits config/caption_edits.json --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json --out words.out.json

# 8. motion
python $SKILLS/reel-motion/scripts/plan_camera.py --cues cues.json --shots config/shots.json --out camera_plan.json
python $SKILLS/reel-motion/scripts/resolve_beatmap.py --cues cues.json --input config/beatmap.src.json --out beatmap.json --extra-sec 2.5
python $SKILLS/reel-director/scripts/beat_audit.py --beatmap beatmap.json --cues cues.json --camera camera_plan.json
python $SKILLS/reel-motion/scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll "$PWD/aroll.mp4" --public-dir "$PWD" --extra-sec 2.5 --out props.json
bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --still 0.0,1.0,7.3 --out out/stills
bash $SKILLS/reel-motion/scripts/render.sh --props props.json --public-dir "$PWD" --out out/gfx.mp4 --concurrency 4

# 9. sound
python $SKILLS/reel-sound/scripts/find_downbeats.py music/bed.mp3 --targets 0:3,8.0,16.0 --duration 49 --allow-edits --out music/downbeats.json
python $SKILLS/reel-sound/scripts/sfx_cues.py place --cues sfx_cues.json --library sfx/manifest.json --beats beatmap.json --words words.out.json --out sfx_placements.json
python $SKILLS/reel-sound/scripts/mix.py --voice voice.wav --music music/bed.mp3 --music-plan music/downbeats.json --sfx sfx_placements.json --duration 49.0 --bed-lift 46.5:4 --out-pre mix_pre.wav --out mix.wav --report qa/mix_report.json
python $SKILLS/reel-sound/scripts/credits.py --manifest sfx/manifest.json --manifest music/manifest.json --placements sfx_placements.json --used music/bed.mp3 --out CREDITS.txt

# 10. export (never overwrites: writes out/reel_vN.mp4)
python $SKILLS/reel-export/scripts/export.py --video out/gfx.mp4 --audio mix.wav --out-dir out --name reel --edl edl.json --extra-sec 2.5 --cover-time 0.4 --srt words.out.json

# 11. gates, then the critic loop (reel-qa/references/critic-prompt.md, max 3 passes)
python $SKILLS/reel-qa/scripts/qa.py --reel out/reel_v1.mp4 --asr-prompt "Brand. Acronyms." --dictionary $SKILLS/mailinfra-brand/caption-dictionary.json
```

Numbers in the example (`--duration 49`, `--extra-sec 2.5`, downbeat targets, still times) are placeholders: take them from your own `cues.json`, `beatmap.json` and `props.json`. Every script prints what it measured; read it, and look at every image a script writes, before moving to the next stage.

## Licence

Code and documentation: MIT, see [LICENSE](LICENSE). The Mail Infra logos are trademarks of Mail Infra and are excluded from the MIT licence ([NOTICE](skills/mailinfra-brand/assets/logos/NOTICE.md)). Fonts are under the SIL Open Font License 1.1 (licence texts next to the font files).
