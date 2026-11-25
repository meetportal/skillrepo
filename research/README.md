# Research

The notes, measurements and decisions behind the skills in [`skills/`](../skills). Each folder explains why a skill works the way it does; the skills hold the commands, the code and the values that ship. When a note and a skill disagree, the skill wins, because its value was tested afterwards. No skill reads anything from this folder at run time.

| Folder | What it covers | Main skills it feeds |
|---|---|---|
| [`craft/`](craft/README.md) | How strong short-form editors cut, caption, animate, mix, grade and export a talking-head reel; a survey of open-source tools and skills; the Remotion versus ffmpeg benchmark | all reel skills, [`craft-research`](../skills/craft-research/SKILL.md) |
| [`editing-plan/`](editing-plan/README.md) | The consolidated plan the skills were built from: three-stage pipeline, decisions and conflicts, stage defaults, beat map, gates, open gaps and what the first build revised | [`reel-director`](../skills/reel-director/SKILL.md) and every stage it routes to |
| [`footage-and-review/`](footage-and-review/README.md) | Analysing raw talking-head footage before the cut, and a checklist for reviewing an existing agency or template edit | [`reel-ingest`](../skills/reel-ingest/SKILL.md), [`voice-clean`](../skills/voice-clean/SKILL.md), [`reel-grade`](../skills/reel-grade/SKILL.md), [`reel-qa`](../skills/reel-qa/SKILL.md) |
| [`3d-video/`](3d-video/README.md) | Deterministic 3D inserts on a CPU-only machine, when 3D beats 2D, what a public MIT plugin teaches, the gap audit and build log that followed | [`reel-3d`](../skills/reel-3d/SKILL.md), [`reel-motion`](../skills/reel-motion/SKILL.md), [`reel-qa`](../skills/reel-qa/SKILL.md), [`reel-sound`](../skills/reel-sound/SKILL.md) |
| [`brand-research/`](brand-research/README.md) | Deriving a brand kit from a public website: site audit, colour sampling, fonts, logo rebuild, claims policy, plus two small tools | [`mailinfra-brand`](../skills/mailinfra-brand/SKILL.md) (the example brand) |

## Reading order

1. [`editing-plan/`](editing-plan/README.md) for the shape of the pipeline and why it looks like that.
2. [`craft/`](craft/README.md) for the editing rules and the tool choices.
3. [`footage-and-review/`](footage-and-review/README.md) before cutting new footage or reworking someone else's edit.
4. [`3d-video/`](3d-video/README.md) before adding a 3D moment.
5. [`brand-research/`](brand-research/README.md) when setting up a brand other than the example one.

## What is not here

No footage, frames, audio, transcripts or project files from any real reel, and no fonts or logo files: those ship only once, in [`skills/mailinfra-brand/assets`](../skills/mailinfra-brand/assets). Third-party sources are linked, not copied; code adapted into a skill is credited in that skill's `NOTICE`. The images in [`3d-video/images/`](3d-video/images) are synthetic renders made with mock props.
