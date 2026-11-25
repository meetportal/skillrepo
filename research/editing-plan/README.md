# Editing plan and decision record

This folder is the consolidated plan that the reel skills in this repo were built from: how a vertical talking-head reel (1080x1920, 25 fps, 40 to 60 s) goes from raw camera clips to a delivered MP4, which tool does each job and why, how the beats are planned, which gates block delivery, and what was still open when the plan was written.

It was written for the first reel of a series and then generalised. Everything tied to one script, one set of takes or one timeline has been removed. What is left are the methods, the numbers that apply to any talking-head reel, and the reasons behind each decision, so that another editor can reuse them or argue with them.

The skills are the source of truth for commands and current defaults. Where the first build changed a number from this plan, [revisions.md](revisions.md) says what changed and why. Read the plan for the reasoning; run the skills for the work.

## Files

| File | Covers |
|---|---|
| [pipeline.md](pipeline.md) | The three-stage pipeline (Python + ffmpeg, then Remotion, then ffmpeg), the files passed between stages, why each tool was chosen, what was rejected and why |
| [decisions.md](decisions.md) | Decisions at a glance, the source precedence rule, and every conflict between sources with the side that won and the measurement behind it |
| [stage-defaults.md](stage-defaults.md) | The plan's numbers per stage with their reasons: cut rules, voice chain principles, caption style and page rules, bed and SFX levels, master, end card, export command |
| [beat-map.md](beat-map.md) | The beat-map approach: layout modes, rhythm targets, camera states, caption placement per mode, SFX pairing, list-reel spine, and a template beat table |
| [gates.md](gates.md) | QA gates with their pass values, the human listen pass, and the critic loop |
| [open-gaps.md](open-gaps.md) | Owner decisions, items that were unverified when the plan was written, things no source covered, and where each one stands in the skills now |
| [revisions.md](revisions.md) | Plan values the first build overturned (splice fades, voice chain, bed duck, SFX levels, logo placement, 3D) and the measurement that overturned them |

## How it maps to the skills

| Plan topic | Skill that now holds it |
|---|---|
| Stage order, hard rules, beat planning, source precedence, owner questions, critic loop | [`reel-director`](../../skills/reel-director/SKILL.md), [runbook](../../skills/reel-director/references/runbook.md) |
| Probe, rotation, frame metrics, transcript and word alignment | [`reel-ingest`](../../skills/reel-ingest/SKILL.md) |
| Cut rules, EDL, single-pass render, retimed words, `cues.json` | [`reel-cut`](../../skills/reel-cut/SKILL.md) |
| Per-clip exposure, white balance, one range conversion | [`reel-grade`](../../skills/reel-grade/SKILL.md) |
| Voice diagnosis and cleaning | [`voice-clean`](../../skills/voice-clean/SKILL.md) |
| Caption text layer, page rules, ASR diff | [`reel-captions`](../../skills/reel-captions/SKILL.md) |
| Camera moves, layout modes, beat graphics, end card | [`reel-motion`](../../skills/reel-motion/SKILL.md) |
| 3D inserts (added after this plan) | [`reel-3d`](../../skills/reel-3d/SKILL.md) |
| Music, SFX, mix and master | [`reel-sound`](../../skills/reel-sound/SKILL.md) |
| Delivery encode, spec gate, cover, SRT | [`reel-export`](../../skills/reel-export/SKILL.md) |
| Gates and the critic prompt | [`reel-qa`](../../skills/reel-qa/SKILL.md) |
| Brand tokens, fonts, logo, claims policy | [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) (example brand) |
| Sources, licences, research recipes | [`craft-research`](../../skills/craft-research/SKILL.md), [sources](../../skills/craft-research/references/sources.md) |

## Reading order

1. [pipeline.md](pipeline.md) for the shape of the system.
2. [decisions.md](decisions.md) for why it looks like that, and [stage-defaults.md](stage-defaults.md) for the numbers.
3. [beat-map.md](beat-map.md) before planning a new reel.
4. [gates.md](gates.md) before calling a reel done.
5. [open-gaps.md](open-gaps.md) and [revisions.md](revisions.md) to see what the plan got wrong or left open, so you do not repeat it.
