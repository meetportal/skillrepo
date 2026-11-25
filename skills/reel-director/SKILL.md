---
name: reel-director
description: Entry point for editing a vertical talking-head reel (Instagram Reels, TikTok, Shorts) from raw camera clips to a delivered, QA-checked MP4. Use whenever someone says "edit this reel", "cut this video into a reel", "make a short from these takes", or asks what stage comes next, which command to run, what is stale after a change, how to plan the beats or the 3D moments, how to brief the speaker before a shoot, how to split work between sub-agents, how to run the critic loop, how to keep a series style bible, or which source wins when two guides disagree. Routes to reel-ingest, reel-grade, reel-cut, voice-clean, reel-captions, reel-motion, reel-3d, reel-sound, reel-export and reel-qa.
---

# reel-director

You own the reel from raw clips to delivery. You plan, route each stage to its skill, keep `project.md` and the series style bible current, and do not hand anything over until `reel-qa` passes and the critic loop has run.

## Conventions

- **Work folder**: one folder per reel inside its series folder (`work/<series>/<reel>/`; the series folder holds the series `style-bible.md`). Every command runs from it; every output lands in it. Raw clips are read-only: never write next to them.
- **Skills**: `export SKILLS=/path/to/this/repo/skills`. Scripts run as `python $SKILLS/<skill>/scripts/<script>.py ...` from the work folder (`bash $SKILLS/reel-motion/scripts/render.sh` for the shell ones). Every script has `--help`.
- **Reel-specific config** (cut lists, grade, shot config, beat map source, SFX cues, corrections) lives in the work folder's `config/`, never in the skills repo. `scripts/new_reel.sh <work-dir>` creates the layout and copies mock templates for every config (`templates/`).
- **Versions**: deliveries are `out/<name>_vN.mp4`, never overwritten.
- **Shared machine**: heavy steps run under `nice -n 19 ionice -c 3`; `REEL_CONCURRENCY` (default 2) and `REEL_RENDER_LOCK` (a lock file every Remotion render and still waits on) apply to `reel-motion` and `reel-3d`.

## Tools

| Script or file | Does |
|---|---|
| `references/runbook.md` | Every command from raw clips to `qa.py`, one per step, with the re-run rules. The single source for commands. |
| `references/script-brief.md` | Script and hook brief for the speaker before a shoot (level 4, A/B first). |
| `scripts/status.py` | Walks the stage graph of the work folder: FRESH, STALE (also when an input is itself stale), UNKNOWN or MISSING per output and the next command (`--json` for agents). |
| `scripts/new_reel.sh <work-dir>` | Folder layout plus templates (`config/*.json`, manifests, `project.md`, the series `style-bible.md`); never overwrites. |
| `scripts/make_mock_reel.py <work-dir>` | Synthetic 12 s fixture (A-roll, `edl.json`, words, `cues.json`) to smoke-test stages 8 to 11 without footage. |
| `scripts/packed_transcript.py` | One line per phrase with the pause after it: the script as text. |
| `scripts/beat_sheet.py` | One row per phrase: start, end, words/s, pause, seconds since the last planned visual event, GAP markers. |
| `scripts/beat_audit.py` | Plan gate on the resolved beat map: hook, rhythm, cover windows, takeovers, cards, kicks, 3D budget. |
| `scripts/doc_lint.py` | Every script path and `--flag` in the docs exists in the code. Run it with the repo's venv interpreter (the default when `.venv/` exists, else `--python`) before every skill commit. |

## Stage order

| # | Stage | Skill to load | Inputs | Outputs (work folder) |
|---|---|---|---|---|
| 0 | Brief and plan | this skill | owner brief, raw clip list, brand skill, series style bible | `project.md` (`templates/project.md`), owner questions |
| 1 | Probe, rotation, frame metrics, transcript | `reel-ingest` | raw clips | `ingest/probe.json`, `qa/stage1/rotation_check.jpg`, `ingest/frame_metrics.json`, `ingest/words_raw.json`, `ingest/words_snapped.json`, `ingest/transcript.json` (force-aligned words) |
| 2 | Read the script, plan beats | this skill (`packed_transcript.py`, `beat_sheet.py`) | `ingest/transcript.json` | beat table, 3D moments, take choice and hook variants in `project.md` |
| 3 | Cut list and EDL | `reel-cut` | transcript, frame metrics, `config/cutlist.json` | `edl.json`, `plan_report.json` |
| 4 | Grade config | `reel-grade` | draft A-roll, cheek-patch levels | `config/grade.json` |
| 5 | Render A-roll and cut voice, retime words, cues | `reel-cut` (+ `reel-captions` for the text, `reel-grade` to iterate) | EDL, grade | `aroll.mp4`, `voice_cut.wav`, `words.retimed.json`, `words.out.json`, `cues.json`; cut strips in `qa/stage1/cuts/` |
| 6 | Voice clean | `voice-clean` | `voice_cut.wav`, `edl.json` | `voice.wav` (not loudness-normalised), `voice_lab/voice.report.json` with hashes |
| 7 | Caption text | `reel-captions` (+ the brand skill's dictionary) | `words.retimed.json`, `config/corrections.json` | `words.out.json` (run inside stage 5 so `cues.json` carries the final text) |
| 8 | Camera plan, beat map, props, stills, graphics pass | `reel-motion` (+ brand skill) | `aroll.mp4`, `cues.json`, `words.out.json`, `config/shots.json`, `config/beatmap.src.json` | `camera_plan.json`, `beatmap.json`, `props.json`, stills, `out/gfx.mp4`, `qa/captions_bbox.json` |
| 8b | 3D inserts | `reel-3d` | `beatmap.json` (`VideoInsert` beats with `props.three`), `props.json` | `3d/<beatId>.mov`, `3d/<beatId>.json`, `3d/stills/`; runs after `resolve_beatmap.py` and `build_props.py`, before `render.sh` |
| 9 | Music, SFX, mix, master, credits | `reel-sound` | `voice.wav` + report, `beatmap.json`, `words.out.json`, `3d/*.json` events, licensed or generated audio | `mix.wav` (exact video length, -14 LUFS), `qa/mix_report.json`, `qa/cue_sheet.md`, `CREDITS.txt` |
| 10 | Delivery encode, cover, SRT | `reel-export` | `out/gfx.mp4`, `mix.wav` | `out/<name>_vN.mp4` + `.json` sidecar, cover JPGs, `.srt` |
| 11 | Gates and critic loop | `reel-qa` | the delivered MP4 + work folder | `qa/report.md`, `qa/report.json`, `qa/sheets/`, `qa/sbs/`, critic scores in `project.md` |

Commands for every row: `references/runbook.md`. Smoke test of the tools: `python $SKILLS/reel-director/tests/test_director.py`. Dependencies: 6 and 8 can run in parallel after 5; 8b needs the resolved beat map and props; 9 needs 6 and the resolved beat map (and 8b for 3D event cues); 10 needs 8 and 9. Any re-cut (stage 3 or 5) invalidates everything after it: re-run 5 to 11 in order and never mix outputs of two cuts. `python $SKILLS/reel-director/scripts/status.py` shows what is stale (an input newer than its output or itself stale, `out/gfx.mp4.aroll.md5` not matching `aroll.mp4`, a `3d/<id>.json` whose hash differs from the one `render3d.py` would compute now, a voice report whose hash does not match `voice_cut.wav`) and prints the next command.

**Exactly one caption text layer.** `retime_words.py` writes the spoken text into `words.retimed.json`, then `reel-captions/scripts/apply_corrections.py` (reel corrections + brand dictionary) writes `words.out.json`, then `reel-cut/scripts/build_cues.py` writes `cues.json` from it. Index corrections use the word index `i` of `words.retimed.json`.

**Which ASR check when.** After stage 5: `reel-captions/scripts/asr_diff.py --mode cut` on `voice_cut.wav` (clipped edges, ghost words, chunked at the EDL splices). After stage 6: `voice-clean/scripts/asr_diff.py` comparing `voice_cut.wav` with `voice.wav` (words lost to the gate or the denoiser). After stage 10: the `asr` gate of `reel-qa` on the delivered MP4.

## Hard rules

1. **Never cut inside a word.** Cut between words on force-aligned edges; head pad at least 50 ms, tail at least 60 ms after the aligned end. Spoken slips are fixed in the caption text, never by cutting into a word.
2. **Captions last**, twice over: the caption layer renders on top of every graphic and every 3D insert, and caption text is finalised only after the cut is locked (stage 7 inside stage 5).
3. **One range conversion.** Full-range camera files become tv range exactly once, in the A-roll render. Remotion, 3D inserts and the final encode never convert range again.
4. **One render pass for the cut**: a single `filter_complex` with frame and sample indices; an equal-power crossfade at every audio splice. No per-segment files with `-c copy`.
5. **No `-shortest`, anywhere.** Pad or trim audio to the video length (`apad,atrim=end=V`) and gate v/a durations within 40 ms.
6. **No speed change** on the voice (no `atempo`, no rubberband) unless the owner asks for an A/B.
7. **No invented numbers.** Prices, percentages, counts, limits and ratings appear only if they are in the brand's approved claims list. Graphics use relative shapes instead.
8. **No watermark, no logo bug in a corner, no recreated third-party UI.** The brand mark sits persistently at top-center (`TopLogo` in `reel-motion`, top logo zone y 120 to 220) for the whole talking section, hidden only under the end card.
9. **Never edit from previous agency or platform renders.** Use them only as a reference to critique or measure. Every frame and sample comes from the raw camera files.
10. **Measure, then look, then claim.** Every "done" is backed by a number from a script and a frame you have looked at (Read the image). Audio choices are numbers plus timestamps for a human listen; never claim something sounds good.
11. **No invented facts about the footage.** Recompute every graphic, 3D and SFX time from `words.out.json` after each cut; planning estimates are never used for timing.

## Stage 0: project.md and the style bible

- `new_reel.sh` copies `templates/project.md`: brief, packed script, beat sheet, takes, hook variants, beat map, **3D moments** table, decisions log, caption edits, QA passes, the **critic score table** (one row per pass, areas `hook, rhythm, cuts, captions, graphics, layout, grade, end`, each 1 to 10, plus the mean) and the side-by-side sheet log. Keep it short; numbers over prose.
- **Style bible discipline.** Each series has one `style-bible.md` in its work root (next to the reel folders, never in this repo; template in `templates/style-bible.md`): standing owner rules on top, then the measured **values that won** (camera, captions, colour, mix, 3D, rhythm), then **traps caught**, each with the frame or number that showed it. Read it at stage 0 before planning, apply every standing rule without asking again, and start from the values that won. Update it after every critic pass: a value moves in only after a render or a gate showed it working, a trap only with its evidence. It records outcomes, not intentions.

## Planning the beats (stage 2)

1. `scripts/packed_transcript.py ingest/transcript.json` (per clip) and, after the cut, `scripts/packed_transcript.py words.out.json` (output timeline). Read it like a script.
2. `scripts/beat_sheet.py words.out.json --beatmap beatmap.json --camera camera_plan.json --cues cues.json` (or on the transcript before the cut): one row per phrase with words/s, the pause after it and the seconds since the last planned visual event; a `GAP` marker where the picture would stay unchanged for more than 2.5 s. The header gives words/s and the pauses over 0.25 s (target about 3.7 words/s and under 1 s of such pauses per 15 s after the cut).
3. **Hook in the first 1 to 2 s.** Speech starts within 0.3 s of frame 0. Frame 0 already shows the hook text or visual (on screen by frame 2), the face is sharp and readable. The promise is stated or shown by 1.5 s. No takeover and no 3D in the first second: the face and the hook own the opening. Write three hook variants from the same truthful speech (`references/script-brief.md`), build each as a still, pick one, record why in `project.md`.
4. **One idea per beat.** A beat is one spoken idea and at most one graphic, shown big, then gone. No card stacks, no two cards on screen at once.
5. **Layout modes**: every beat is one of
   - **Talk**: speaker full frame, no graphic (a small progress element at most), captions at the lower-middle line (y about 1180).
   - **Card**: speaker full frame, one card in the lower stage (x 70-950, y 1150-1480), captions move up above it (y about 1060, below the chin).
   - **Takeover**: full-frame graphic, speaker hidden for at most 1.5 s (one exception up to 2.5 s, only to cover a defect such as sway blur), at least 2 s of face between takeovers. Captions over an empty band, or suppressed when the graphic spells the same words.
6. **One visual event every 1.5 to 2.5 s**, never a gap over 4 s: a cut, a scale change (alternate two punch states on jump cuts, never two cuts in a row at the same scale), a glide, a kick on an impact word (at least 3 s apart), or a graphic entrance or exit. Plan the camera states, kicks and graphics together on the beat sheet until no `GAP` row is left.
7. **3D is punctuation.** Use it only for a physical metaphor the viewer should follow (the email, the domain, the shield, the logo); text, numbers, lists and comparisons stay 2D. Budget for a 45 to 60 s reel: 2 to 3 moments, 4 to 8 s in total, at most one full-frame 3D takeover per 15 s and each 1.0 to 1.5 s, none in the first second or over the CTA. Full rules and costs: `../reel-3d/references/when-3d.md`. Fill the "3D moments" table in `project.md`.
8. **List scripts get a numbered spine.** When the speaker says "three mistakes / first / second / third", each item gets a title slam on its marker word (the number as large content, not as a "01/03" HUD counter), its own shot, and a breath of about 0.28 s after the marker so the slam lands.
9. Graphics land 0 to 2 frames before the word they illustrate; hold each card at least 0.3 s per word on it + 0.5 s.
10. Text at least 44 px on cards, numerals at least 140 px, nothing in the bottom 420 px or right 130 px; universal safe box x 70-950, y 220-1500. The top logo zone (y 120-220) belongs to the persistent top logo only.
11. After `reel-motion` resolves the beat map: `scripts/beat_audit.py --beatmap beatmap.json --cues cues.json --camera camera_plan.json`.
    - FAIL: first word after 0.3 s, no hook visual at frame 0, a takeover in the first second, a gap over 4 s without a visual change, a takeover over 1.5 s (one up to 2.5 s is a warning), a `cues.cover` window not inside one `takeover` or `hidden` beat, a 3D beat (`VideoInsert` with `props.three`) starting before 1.0 s or overlapping the last `--cta-sec` (3) of talk before the end card (a 3D logo handoff that starts after the talking ends is exempt).
    - WARN: median gap between visual events (cuts, scale changes including glides, kicks, beat in and out) over 2.5 s, under 2 s of face between takeovers, overlapping cards, beats under 0.6 s, kicks under 3 s apart, more than one 3D takeover in any 15 s, 3D total outside 4 to 8 s per 60 s of talk, a 3D takeover over 1.5 s.

## Running builders in parallel (stage 8)

- **One owner per file.** The lead (you) owns the shared theme (colour, type, motion tokens from the brand skill), the camera component, the captions component, the registry and the beat map. Nobody else edits them. Each sub-agent owns its own files and nothing else; a change it needs elsewhere goes back to you as a written request.
- One graphics component per sub-agent, one file each (for example `TitleSlam`, `CompareCards`, `EndCard`, or one 3D composition in `reel-3d`). Group by visual family when components share code, never by reel order.
- Each brief contains: the component name and file path, the beat rows it serves (out times, mode, words it lands on, the props schema and the time rule: anchors in `beats[].props` are beat-relative seconds, anchors in `props.three.props` are absolute output seconds), the theme tokens it must use, the never-ship list, and the acceptance check: type-check, then stills at `from + 0`, entry (from + 4 frames), mid and exit (to - 2 frames), each one looked at.
- **Merge with a backup.** Before copying a builder's files into the main project, copy the current versions to `backup/<time>/`, copy only the files that builder owns, compare (a file nobody changed stays byte-identical), type-check, then render stills. Roll back from the backup if anything breaks.
- Sub-agents never render the full reel and never touch another agent's file. The lead renders, after all components are registered.

## Critic loop (stage 11)

1. Run `reel-qa` (`qa.py`) on the delivered version. Fix every FAIL first.
2. If the owner named a reference reel, measure it once with `craft-research/scripts/measure_reference.py` (cuts, visual events, camera motion, words/s) and measure ours the same way; make side-by-side sheets with `reel-qa/scripts/sbs_sheet.py` (our frames above the reference at matching moments). Reference media stays outside the repo and is deleted after.
3. Spawn a fresh critic sub-agent with `reel-qa/references/critic-prompt.md`. It has not seen the plan. It scores each area 1 to 10 (`hook, rhythm, cuts, captions, graphics, layout, grade, end`) with a one-line reason, then returns a severity-ranked fix list: timecode and frame, problem, evidence, one concrete fix, owning stage.
4. Log the scores as a row of the critic score table in `project.md`. Route each fix to the owner of that stage or file (resume the same builder when possible), export a new version, re-run `qa.py`, spawn a **new** critic (never show it the old critique).
5. Stop after at most 3 passes, or earlier when a pass has no BLOCKER or MAJOR rows and the mean score stopped rising. Update the style bible (values that won, traps caught).
6. Hand over: the version number, `qa/report.md`, the score table, the open MINOR rows, what could not be verified (listening), and 5 listen timestamps (hook, first slam, loudest SFX, a held pause, end card).

## When sources disagree

Precedence, highest first:

1. **Measured on this reel's own footage** (probe, frame metrics, force-aligned words, skin and noise measurements).
2. **Measured on renders or on this machine** (QA numbers on our outputs, encoder and renderer benchmarks, A/B tests, reference measurements with `measure_reference.py`).
3. **Defaults of well-maintained tools and skill repos** (the numbers baked into these skills, upstream repo defaults).
4. **Written guides and tutorials** (blogs, videos, books, other people's style bibles).
5. **Habit and taste** (including yours).

A lower level never overrides a higher one; when you overrule a number, write the decision and the measurement that justified it in the decisions log. When two sources at the same level disagree, measure.

## When to ask the owner (and keep working meanwhile)

Ask in one message, early (stage 0), and continue with the safe default:

| Topic | Ask | Safe default until answered |
|---|---|---|
| Claims | exact wording and figures for any price, percentage, count, limit, offer, rating or certification | show no numbers; use relative graphics and number-free proof lines |
| Music licence | the track or library to use and its licence (or approval of a CC0 / platform-licensed pick, with the licence evidence) | a CC0 or clearly social-media-licensed track with `licence.md`, or the generated SFX kit and room tone only |
| Brand system | which visual system the reels use (fonts, colours, logo lockups) when the website and existing reels differ | the system the existing reels already use |
| CTA | URL form, handle, where "link in bio" points | the bare domain, no `www.`, no `https://` |
| Reference reel | a reel whose pace or look the owner wants matched | the values that won in the style bible |
| Rendering licence | whether the company qualifies for Remotion's free tier or holds a company licence | do not render client work with Remotion until confirmed |
| Hearing | the listen pass at the 5 timestamps | ship nothing as final until someone has listened |

Never ask about things you can measure (loudness, timing, sharpness, levels). Never ask for approval of each stage; ask for decisions only the owner can make. Write every answer into the style bible's standing rules so it is never asked twice.
