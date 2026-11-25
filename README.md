# Reel editing skills

Agent skills and scripts that edit vertical talking-head reels (1080x1920, Instagram Reels, TikTok, YouTube Shorts) from raw camera clips to a delivered, gated MP4: transcript-driven jump cuts, per-segment grade, cleaned dialogue, Remotion camera moves, graphics, 3D inserts and burned-in captions, music and SFX mixed to -14 LUFS, a fixed upload spec, and QA gates with an independent critic pass.

Each skill is a folder under `skills/` with a `SKILL.md` (when to use it, rules with numbers, commands), `scripts/` (Python 3.10+, ffmpeg, node) and sometimes `references/`. Start with `skills/reel-director/SKILL.md`: it is the entry point for "edit this reel" and routes every stage to the right skill; its [runbook](skills/reel-director/references/runbook.md) lists every command.

## Skills, in stage order

Stage numbers match the stage table of `reel-director`.

| # | Skill | One line |
|---|---|---|
| 0, 2 | [`reel-director`](skills/reel-director/SKILL.md) | Entry point: stage order, [runbook](skills/reel-director/references/runbook.md), `status.py`, templates, hard rules, beat sheet and beat audit, 3D budget, script brief, style bible, parallel builders, scored critic loop, source precedence, owner questions |
| 1 | [`reel-ingest`](skills/reel-ingest/SKILL.md) | Probe clips (range, rotation, tmcd, dual-mono), rotation sheet, per-frame sharpness, blinks and face boxes, faster-whisper transcript, cleaned text and force-aligned words, onset gates |
| 3, 5 | [`reel-cut`](skills/reel-cut/SKILL.md) | EDL from aligned words (pause tightening, pads, J/L cuts around blinks), single-pass A-roll and cut-voice render, retimed words, `cues.json`, drift and splice gates |
| 4 | [`reel-grade`](skills/reel-grade/SKILL.md) | Grade config: rotation, per-clip and per-segment tone curves, cheek-patch levels across cuts, exposure match over source time, one explicit full-to-tv range conversion |
| 6 | [`voice-clean`](skills/voice-clean/SKILL.md) | Diagnose noise, A/B denoise chains, process the cut voice with latency compensation and a hashed report, splice and word-loss checks |
| 7 | [`reel-captions`](skills/reel-captions/SKILL.md) | The one caption text layer (corrections + brand dictionary), page and accent rules, ASR diff for the cut and the delivered file |
| - | [`mailinfra-brand`](skills/mailinfra-brand/SKILL.md) | Example brand kit: tokens, colour meanings, fonts, logos, 3D tokens, CTA rules, claims policy (swap in your own brand folder) |
| 8 | [`reel-motion`](skills/reel-motion/SKILL.md) | Remotion 4 project: camera punch-ins, pushes, glides and kicks, beat graphics in Talk / Card / Takeover layouts, `VideoInsert` for rendered inserts, captions last, stills and the `gfx.mp4` pass |
| 8b | [`reel-3d`](skills/reel-3d/SKILL.md) | `@remotion/three` inserts rendered once per beat to `3d/<beat>.mov` (swangle GL, cached by hash): envelope to spam, domain burn, auth shield, logo extrude; when 3D beats 2D |
| 9 | [`reel-sound`](skills/reel-sound/SKILL.md) | Music licence check, downbeat sync, generated SFX kit, SFX cues on visible and 3D events, word-keyed duck, two-pass linear loudnorm, cue sheet, `CREDITS.txt` |
| 10 | [`reel-export`](skills/reel-export/SKILL.md) | Delivery encode (H.264 High 4.2, AAC 256k, BT.709 tv, faststart), never `-shortest`, ffprobe spec gate, cover image, SRT, versioning |
| 11 | [`reel-qa`](skills/reel-qa/SKILL.md) | `qa.py`: spec, loudness, drift and voice sync, rhythm, every-frame checks, cover windows, splice clicks, ASR diff, caption safe zone, levels, contact and side-by-side sheets; scored critic prompt |
| - | [`craft-research`](skills/craft-research/SKILL.md) | yt-dlp and gh research recipes, reference reels measured in numbers (`measure_reference.py`), turning tutorials and owner notes into tested rules, untrusted-content handling, vetted sources |

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

- **Python 3.10+** with `requirements.txt` (faster-whisper, librosa, numpy, opencv-python, pyyaml, scipy, soundfile, yt-dlp). The first transcription downloads the faster-whisper `large-v3` model (about 3 GB); it runs int8 on CPU, about 1 minute per minute of audio on 8 cores.
- **ffmpeg and ffprobe 6.1 or newer** on `PATH`, built with libx264 (and libzimg if you use `zscale`). Check: `ffmpeg -hide_banner -filters | grep -E "loudnorm|ebur128|afftdn|deesser|signalstats"`.
- **Node 20 or newer** (tested on 24) for the Remotion stages: `cd skills/reel-motion/remotion && npm ci && npx remotion browser ensure`, and `npm ci` in `skills/reel-3d/remotion` when the reel uses 3D inserts (see `reel-3d` for the shared headless browser). All `@remotion/*` packages are pinned to one exact version.
- **Face model** (not bundled): YuNet `face_detection_yunet_2023mar.onnx` from the OpenCV model zoo (MIT), see `reel-ingest`.
- **Remotion licence**: Remotion is free for individuals and for companies of up to 3 people. A larger for-profit company needs a Remotion company licence before rendering its videos with `reel-motion` or `reel-3d` (see remotion.dev/license). Everything else here is MIT.
- Optional: the `deep-filter` binary (DeepFilterNet) for hard noise, see `voice-clean`.

## Folder convention

- One **work folder per reel** (for example `work/<series>/<reel>/`). Every command runs from it and writes into it. Raw clips stay where they are and are only read. `bash $SKILLS/reel-director/scripts/new_reel.sh work/<series>/<reel>` creates it with mock templates for every config.
- `SKILLS` points at this repo's `skills/` folder. Scripts are always called as `python $SKILLS/<skill>/scripts/<script>.py` from the work folder, so data paths are relative to the work folder and script paths never are.
- Reel-specific settings (cut list, grade, shot config, beat map source, SFX cue list, caption corrections) live in the work folder's `config/`. Nothing reel-specific goes into this repo.
- One **style bible per series** (`style-bible.md` next to the reel folders): standing owner rules, values that won, traps caught. Read at stage 0, updated after every critic pass.
- A different brand: copy `skills/mailinfra-brand` to your own folder, change `brand.json`, fonts and logos, and set `REEL_BRAND=/path/to/brand-folder` for the Remotion stages.
- On a shared machine: `REEL_CONCURRENCY` (default 2) sets the Remotion concurrency and `REEL_RENDER_LOCK=/path/to/file.lock` makes every render and still wait for that lock.

```
work/<series>/
  style-bible.md        series rules, values that won, traps caught (reel-director)
  <reel>/
    project.md          plan, beat sheet, 3D moments, decisions, QA and critic scores (reel-director)
    config/             cutlist.json, grade.json, cues_config.json, corrections.json, shots.json, beatmap.src.json, sfx_cues.json
    ingest/             probe.json, frame_metrics.json, words_raw.json, words_snapped.json, transcript.json
    edl.json  aroll.mp4  voice_cut.wav  words.retimed.json  words.out.json  cues.json
    voice_lab/          diagnosis, A/B renders, voice.report.json
    voice.wav
    camera_plan.json  beatmap.json  props.json
    3d/                 <beat>.mov, <beat>.json (hash, events), stills/
    music/  sfx/        tracks and kits with manifest.json
    sfx_placements.json  mix_pre.wav  mix.wav  CREDITS.txt
    out/                stills/, gfx.mp4 (+ .aroll.md5), reel_vN.mp4 (+ .json, cover, .srt)
    qa/                 stage1/, report.md, report.json, captions_bbox.json, mix_report.json, cue_sheet.md, sheets/, sbs/
```

## End to end

Every command, in order, from raw clips to `qa.py`: **[`skills/reel-director/references/runbook.md`](skills/reel-director/references/runbook.md)**. At any point, from the work folder:

```bash
python $SKILLS/reel-director/scripts/status.py --raw /path/to/raw/clips
```

prints FRESH, STALE, UNKNOWN or MISSING for every output (staleness flows down the chain) and the next command to run. To try the pipeline without footage, `python $SKILLS/reel-director/scripts/make_mock_reel.py work/demo/mock` builds a 12 s synthetic reel; then `new_reel.sh work/demo/mock` and continue at stage 8 of the runbook. Before committing a change to any skill, `$SKILLS/../.venv/bin/python $SKILLS/reel-director/scripts/doc_lint.py` checks that every script path and flag in the docs still exists. Run it with the venv interpreter (it also picks `.venv/bin/python` for the `--help` calls when that exists, or takes `--python`): a script whose `--help` fails for a missing dependency is reported once as `help-failed`, not as flag misses.

## Licence

Code and documentation: MIT, see [LICENSE](LICENSE). The Mail Infra logos are trademarks of Mail Infra and are excluded from the MIT licence ([NOTICE](skills/mailinfra-brand/assets/logos/NOTICE.md)). Fonts are under the SIL Open Font License 1.1 (licence texts next to the font files). Parts of `reel-qa` and `reel-sound` are adapted from MIT-licensed code; their `NOTICE` files carry the copyright lines.
