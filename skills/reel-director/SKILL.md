---
name: reel-director
description: Entry point for editing a vertical talking-head reel (Instagram Reels, TikTok, YouTube Shorts) from raw camera clips to a delivered, QA-checked MP4. Use whenever someone says "edit this reel", "cut this video into a reel", "make a short from these takes", or asks what stage comes next, which skill to load, how to plan the beats, how to split work between sub-agents, how to run the critic loop, or which source wins when two guides disagree. Routes to reel-ingest, reel-grade, reel-cut, voice-clean, reel-captions, reel-motion, reel-sound, reel-export and reel-qa.
---

# reel-director

You own the reel from raw clips to delivery. You plan, route each stage to its skill, keep `project.md` current, and do not hand anything over until `reel-qa` passes and the critic loop has run.

## Conventions

- **Work folder**: one folder per reel (for example `work/<reel>/`). Every command runs from it; every output lands in it. Raw clips are read-only: never write next to them.
- **Skills**: `export SKILLS=/path/to/this/repo/skills`. Scripts run as `python $SKILLS/<skill>/scripts/<script>.py ...` from the work folder (`bash $SKILLS/reel-motion/scripts/render.sh` for the shell ones). Every script has `--help`.
- **Reel-specific config** (cut lists, grade, shot config, beat map source, SFX cues, corrections) lives in the work folder (`config/` or next to the outputs), never in the skills repo.
- **Versions**: deliveries are `out/<name>_vN.mp4`, never overwritten.

## Stage order

| # | Stage | Skill to load | Inputs | Outputs (work folder) |
|---|---|---|---|---|
| 0 | Brief and plan | this skill | owner brief, raw clip list, brand skill | `project.md` (template below) |
| 1 | Probe, rotation, frame metrics, transcript | `reel-ingest` | raw clips | `ingest/probe.json`, `qa/rotation_check.jpg`, `ingest/frame_metrics.json`, `ingest/words_raw.json`, `ingest/transcript.json` (energy-snapped words) |
| 2 | Read the script, plan beats | this skill (`packed_transcript.py`) | `ingest/transcript.json` | beat table in `project.md`, take choice, hook text variants |
| 3 | Cut list and EDL | `reel-cut` | transcript, frame metrics, cut config | `edl.json`, `plan_report.json` |
| 4 | Grade config | `reel-grade` | raw frames, skin measurements | `config/grade.json` |
| 5 | Render A-roll and cut voice, retime words | `reel-cut` (+ `reel-grade` to iterate the grade) | EDL, grade | `aroll.mp4`, `voice_cut.wav`, `words.retimed.json`, `cues.json`; cut strips in `qa/cuts/` |
| 6 | Voice clean | `voice-clean` | `voice_cut.wav`, `edl.json` | `voice.wav` (not loudness-normalised), A/B report, listen list |
| 7 | Caption text | `reel-captions` (+ the brand skill's dictionary) | `words.retimed.json` | `words.out.json` |
| 8 | Camera plan, beat map, props, stills, graphics pass | `reel-motion` (+ brand skill) | `aroll.mp4`, `cues.json`, `words.out.json`, shot config, beat map source | `camera_plan.json`, `beatmap.json`, `props.json`, stills, `out/gfx.mp4` |
| 9 | Music, SFX, mix, master, credits | `reel-sound` | `voice.wav`, `beatmap.json`, `words.out.json`, licensed music, SFX library | `mix.wav` (exact video length, -14 LUFS), `CREDITS.txt` |
| 10 | Delivery encode, cover, SRT | `reel-export` | `out/gfx.mp4`, `mix.wav` | `out/<name>_vN.mp4` + `.json` sidecar, cover JPGs, `.srt` |
| 11 | Gates and critic loop | `reel-qa` | the delivered MP4 + work folder | `qa/report.md`, `qa/report.json`, `qa/sheets/`, critic table in `project.md` |

Dependencies: 6 and 7 can run in parallel after 5; 8 needs 5 and 7; 9 needs 6 and the resolved beat map from 8; 10 needs 8 and 9. Any re-cut (stage 3 or 5) invalidates everything after it: re-run 5 to 11 in order and never mix outputs of two cuts (`reel-qa` catches a stale graphics pass or voice file, but only after the fact).

**Exactly one caption text layer.** Run `retime_words.py` without corrections into `words.retimed.json`, then `reel-captions/scripts/apply_corrections.py` (index edits + brand dictionary) into `words.out.json`. Do not also pass corrections to `retime_words.py`: two layers apply edits twice or against shifted indices. Index edits use the word index `i` of `cues.json` `words` (the same list as `words.retimed.json`). `cues.json` keeps the spoken text, so beat-map word anchors match what was said, not the corrected caption.

**Which ASR check when.** After stage 5: `reel-cut/scripts/verify_asr.py` on `voice_cut.wav` (clipped edges, ghost words). After stage 6: `voice-clean/scripts/asr_diff.py` comparing `voice_cut.wav` with `voice.wav` (words lost to the gate or the denoiser). After stage 10: the `asr` gate of `reel-qa` on the delivered MP4.

## Hard rules

1. **Never cut inside a word.** Cut between words on energy-snapped edges; head pad at least 50 ms, tail at least 60 ms after the snapped end. Spoken slips are fixed in the caption text, never by cutting into a word.
2. **Captions last**, twice over: the caption layer renders on top of every graphic, and caption text is finalised only after the cut is locked (stage 7 after stage 5).
3. **One range conversion.** Full-range camera files become tv range exactly once, in the A-roll render. Remotion and the final encode never convert range again.
4. **One render pass for the cut**: a single `filter_complex` with frame and sample indices; 30 ms `afade` at every audio splice. No per-segment files with `-c copy`.
5. **No `-shortest`, anywhere.** Pad or trim audio to the video length (`apad,atrim=end=V`) and gate v/a durations within 40 ms.
6. **No speed change** on the voice (no `atempo`, no rubberband) unless the owner asks for an A/B.
7. **No invented numbers.** Prices, percentages, counts, limits and ratings appear only if they are in the brand's approved claims list. Graphics use relative shapes instead.
8. **No watermark, no logo bug in a corner, no recreated third-party UI.** The brand mark sits persistently at top-center (`TopLogo` in `reel-motion`, top logo zone y 120 to 220) for the whole talking section, hidden only under the end card.
9. **Never edit from previous agency or platform renders.** Use them only as a reference to critique. Every frame and sample comes from the raw camera files.
10. **Measure, then look, then claim.** Every "done" is backed by a number from a script and a frame you have looked at (Read the image). Audio choices are numbers plus timestamps for a human listen; never claim something sounds good.
11. **No invented facts about the footage.** Recompute every graphic and SFX time from `words.out.json` after each cut; planning estimates are never used for timing.

## project.md template

Create it in stage 0 and append to it at every stage. Keep it short; numbers over prose.

```markdown
# <Reel name>

## Brief
- Goal / audience / platform(s):
- Owner decisions needed (claims, music licence, brand system, CTA destination): <list, each with status>
- Source clips (read only): <folder>, <n> clips, <fps>, <rotation>, <range>
- Length target: <talking s> + <end card s>

## Script (packed)
<paste packed_transcript.py output for the kept takes>

## Takes
| Clip | Role | Keep (source s) | Why / defects (blinks, blur, hand, sway) |

## Hook
| Variant | Text | Visual at frame 0 | Chosen? Why |

## Beat map
| Beat | Out s | Mode | Picture and graphic | Caption accent | SFX |

## Decisions log
| When | Stage | Decision | Measured evidence | Source (precedence level) |

## Caption edits
| Word index / phrase | Spoken | Shown | Reason |

## QA and critic passes
| Version | qa.py verdict (blocking gates) | Critic BLOCKER/MAJOR count | Fixed in |

## Open items for the owner
- <listen timestamps, claims to approve, licence questions>
```

## Planning the beats (stage 2)

1. `python $SKILLS/reel-director/scripts/packed_transcript.py ingest/transcript.json` (per clip) and, after the cut, `... words.out.json` (output timeline). Read it like a script: one line per phrase, `[start-end]`, the pause after it.
2. **Hook in the first 1 to 2 s.** Speech starts within 0.3 s of frame 0. Frame 0 already shows the hook text or visual (on screen by frame 2), the face is sharp and readable. The promise (what the viewer gets by staying) is stated or shown by 1.5 s. No takeover in the first second: the face and the hook own the opening. Write three hook variants from the same truthful speech, build each as a still, pick one, record why in `project.md`.
3. **One idea per beat.** A beat is one spoken idea and at most one graphic, shown big, then gone. No card stacks, no two cards on screen at once.
4. **Layout modes**: every beat is one of
   - **Talk**: speaker full frame, no graphic (a small progress element at most), captions at the lower-middle line (y about 1180).
   - **Card**: speaker full frame, one card in the lower stage (x 70-950, y 1150-1480), captions move up above it (y about 1060, below the chin).
   - **Takeover**: full-frame graphic, speaker hidden for at most 1.5 s (one exception up to 2.5 s, only to cover a defect such as sway blur), at least 2 s of face between takeovers. Captions over an empty band, or suppressed when the graphic spells the same words.
5. **Visual change at least every 4 s**: a cut, a scale change (alternate two punch states on jump cuts, never two cuts in a row at the same scale) or a graphic entrance or exit. Plan the camera states and the graphics together.
6. **List scripts get a numbered spine.** When the speaker says "three mistakes / first / second / third", each item gets a title slam on its marker word (the number as large content, not as a "01/03" HUD counter), its own shot, and a breath of about 0.28 s after the marker so the slam lands. A small progress element may track the items and pay off in the wrap (for example turning into the checklist of fixes).
7. Graphics land 0 to 2 frames before the word they illustrate; hold each card at least 0.3 s per word on it + 0.5 s.
8. Text at least 44 px on cards, numerals at least 140 px, nothing in the bottom 420 px or right 130 px; universal safe box x 70-950, y 220-1500. Above it, the top logo zone (y 120-220) belongs to the persistent top logo only; hook headline, progress rail and takeover content start at y 236 or lower.
9. After `reel-motion` resolves the beat map: `python $SKILLS/reel-director/scripts/beat_audit.py --beatmap beatmap.json --cues cues.json --camera camera_plan.json`. It fails on a late first word, no hook visual at frame 0, a takeover in the first second, any 4 s gap without a visual change, takeovers over 1.5 s (one up to 2.5 s is a warning); it warns on less than 2 s of face between takeovers, overlapping cards and beats under 0.6 s.

## Running builders in parallel (stage 8)

- The lead (you) owns the shared theme (colour, type, motion tokens from the brand skill), the camera component, the captions component, the registry and the beat map. Nobody else edits them.
- One graphics component per sub-agent, one file each (for example `TitleSlam`, `CompareCards`, `Gauge`, `EndCard`). Group by visual family when components share code, never by reel order.
- Each brief contains: the component name and file path, the beat rows it serves (out times, mode, words it lands on, the props schema), the theme tokens it must use, the never-ship list, and the acceptance check: type-check, then stills at entry (from + 4 frames), mid and exit (to - 2 frames), each one looked at (text size, safe box, face and caption collisions, colour meanings).
- Sub-agents never render the full reel and never touch another agent's file. The lead renders, after all components are registered.
- Same pattern for other parallel work: one output file per agent, one owner per shared file.

## Critic loop (stage 11)

1. Run `reel-qa` (`qa.py`) on the delivered version. Fix every FAIL first.
2. Spawn a fresh critic sub-agent with `reel-qa/references/critic-prompt.md`. It has not seen the plan. It roasts, it does not praise, and it returns a severity-ranked table: timecode, problem, evidence, one concrete fix.
3. Fix BLOCKER and MAJOR rows at the owning stage, export a new version, re-run `qa.py`, spawn a **new** critic (never show it the old critique).
4. Maximum 3 passes. Stop earlier when a pass has no BLOCKER or MAJOR rows. Log each pass in `project.md`.
5. Hand over: the version number, `qa/report.md`, the open MINOR rows, what could not be verified (listening), and 5 listen timestamps (hook, first slam, loudest SFX, a held pause, end card).

## When sources disagree

Precedence, highest first:

1. **Measured on this reel's own footage** (probe, frame metrics, energy-snapped words, skin and noise measurements).
2. **Measured on renders or on this machine** (QA numbers on our outputs, encoder and renderer benchmarks, A/B tests).
3. **Defaults of well-maintained tools and skill repos** (the numbers baked into these skills, upstream repo defaults).
4. **Written guides and tutorials** (blogs, videos, books).
5. **Habit and taste** (including yours).

A lower level never overrides a higher one; when you overrule a number, write the decision and the measurement that justified it in the decisions log. When two sources at the same level disagree, measure.

## When to ask the owner (and keep working meanwhile)

Ask in one message, early (stage 0), and continue with the safe default:

| Topic | Ask | Safe default until answered |
|---|---|---|
| Claims | exact wording and figures for any price, percentage, count, limit, offer, rating or certification | show no numbers; use relative graphics and number-free proof lines |
| Music licence | the track or library to use and its licence (or approval of a CC0 / platform-licensed pick, with the licence evidence) | a CC0 or clearly social-media-licensed track with `licence.md`, or SFX and room tone only |
| Brand system | which visual system the reels use (fonts, colours, logo lockups) when the website and existing reels differ | the system the existing reels already use |
| CTA | URL form, handle, where "link in bio" points | the bare domain, no `www.`, no `https://` |
| Rendering licence | whether the company qualifies for Remotion's free tier or holds a company licence | do not render client work with Remotion until confirmed |
| Hearing | the listen pass at the 5 timestamps | ship nothing as final until someone has listened |

Never ask about things you can measure (loudness, timing, sharpness, levels). Never ask for approval of each stage; ask for decisions only the owner can make.
