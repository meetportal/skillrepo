# Craft research

Background research behind the reel skills: how a strong short-form editor cuts, captions, animates, mixes, grades and exports a 30 to 60 s vertical talking-head reel, which open-source skills and tools already exist for that job, and which motion toolchain renders it fastest on an ordinary CPU machine. It was written while building the first reel with these skills and is kept general, so it applies to any talking-head reel.

The numbers here are starting points and the reasons behind them. The values the pipeline actually ships live in the skills: when a note here and a skill disagree, the skill wins, because its value was tested on real footage afterwards. Where that happened, the note says so and links the skill.

## Files

| File | What it covers |
|---|---|
| [editing-craft.md](editing-craft.md) | The craft rules with numbers: hook, silence removal and pads, cut rhythm, punch-ins, J and L cuts, pattern interrupts, kinetic captions, safe zones, motion timing and graphic types, UI mockups, sound design levels, voice chain, colour order and targets, CTA and end card, export settings, a listicle beat template and a self-review checklist. With the tutorial and written sources. |
| [toolchain-survey.md](toolchain-survey.md) | GitHub survey of agent skills, renderers, MCP servers and core tools for programmatic video editing, what each well-built repo teaches, the licence flags, a denoise A/B, and the chosen toolchain with the reasons for every choice. |
| [motion-benchmark.md](motion-benchmark.md) | Remotion versus ffmpeg only (drawtext, libass, zoompan, overlays): install notes, render speeds on an 8 CPU machine with no GPU, gotchas hit and fixed, and the three-stage architecture that came out of it. |

## How it maps to the skills

| Topic | Research | Skill that now holds the code and the shipped values |
|---|---|---|
| Research method, source vetting, YouTube recipes | all three files | [`craft-research`](../../skills/craft-research/SKILL.md), vetted list in [sources.md](../../skills/craft-research/references/sources.md) |
| Stage order, beat sheet, rhythm gate, critic pass | editing-craft sections 2, 3, 6, 16 | [`reel-director`](../../skills/reel-director/SKILL.md) |
| Word timestamps, VAD, onset snapping | toolchain-survey 6.4 | [`reel-ingest`](../../skills/reel-ingest/SKILL.md) |
| Silence removal, pads, single-pass render, drift | editing-craft 3, toolchain-survey 6.2 | [`reel-cut`](../../skills/reel-cut/SKILL.md) |
| Colour and range | editing-craft 12 | [`reel-grade`](../../skills/reel-grade/SKILL.md) |
| Denoise and voice chain | editing-craft 11, toolchain-survey 3 and 6.3 | [`voice-clean`](../../skills/voice-clean/SKILL.md) |
| Captions | editing-craft 7 | [`reel-captions`](../../skills/reel-captions/SKILL.md) |
| Punch-ins, graphics, Remotion setup | editing-craft 4, 8, motion-benchmark | [`reel-motion`](../../skills/reel-motion/SKILL.md), [`reel-3d`](../../skills/reel-3d/SKILL.md) |
| Music, SFX, ducking, loudness | editing-craft 10 | [`reel-sound`](../../skills/reel-sound/SKILL.md) |
| Delivery encode | editing-craft 14 | [`reel-export`](../../skills/reel-export/SKILL.md) |
| Gates and checks | editing-craft 16, toolchain-survey 6.6 | [`reel-qa`](../../skills/reel-qa/SKILL.md) |
| Brand colours, fonts, logo | (example brand) | [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) |

## Method and source status

- Tutorials were found with `yt-dlp "ytsearchN:<query>" --flat-playlist` (8 queries, about 70 candidates, the 20 most credible kept). Their subtitles could not be downloaded: YouTube answered every request with `LOGIN_REQUIRED` ("Sign in to confirm you're not a bot"), most likely because several requests ran in parallel from one IP. Rules that would have come from those videos are therefore built from written guides, the public repos and standard practice instead; the videos stay as a reading queue. [`craft-research`](../../skills/craft-research/SKILL.md) section 1 has the safe way to fetch them (sequential, spaced requests, a cookies file from a throwaway account only) and the fallback order.
- Written guides and docs were found by web search and are listed at the end of each file.
- GitHub repos were found with `gh search repos` and `gh search code --filename SKILL.md`, then shallow-cloned into a separate untrusted folder and read, never executed.
- Local measurements (denoise A/B, render benchmarks) were run on one sample reel's footage on a machine with 8 CPUs, about 32 GB RAM and no GPU. Only the numbers are kept.
- Where sources disagree, the range is given with the value chosen. Claims not tied to a source are marked *(practice)*.
- Stars, versions and licences are as of 2026-11-24. Re-check with `gh repo view` and the package registry before relying on them.

## Licences of what is referenced

Everything third party is linked, not copied. Code borrowed into the skills is credited in their `NOTICE` files. Two repos here are reference only: one is CC BY-NC 4.0 (non-commercial) and Remotion's official skills have no licence file. Remotion itself is free for individuals and companies of up to 3 people; larger for-profit companies need a company licence (remotion.dev/license).
