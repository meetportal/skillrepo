# Footage and review research

Research notes behind the first two stages of the pipeline: looking hard at the raw camera clips before anything is cut, and reviewing an existing reel edit (an agency cut, a template edit, or your own earlier version) before deciding what to keep.

Both notes come from working through a sample reel: five vertical talking-head takes shot on a mirrorless camera with a handheld wireless mic, in a home office with a bright wall. The numbers are the ones we measured on that footage. They show what "normal" and "bad" look like, but every reel needs its own measurements: run the scripts, then read the frames.

| Note | What it covers |
|---|---|
| [footage-forensics.md](footage-forensics.md) | A method for analysing raw talking-head footage before editing: container facts (rotation tags, full vs tv range, dual-mono, timecode tracks), framing and shot-size matching, sharpness, motion, blinks, exposure and skin, audio noise, hum, plosives, sibilance and loudness, denoise chain tests, and transcription cross-checks across whisper models. Each check lists the method, the threshold and the kind of finding it produces, plus the early decisions that later measurements overturned. |
| [edit-review-checklist.md](edit-review-checklist.md) | How to measure an existing reel edit, a checklist of what typically goes wrong in agency and template edits (thumbnail, pacing, captions, graphics, safe zones, end card, mix, claims), what is usually worth keeping, and the creative direction principles that came out of the review. |

## Where the code lives

These notes explain the reasoning. The working code is in the skills, which already implement the methods below with paths as arguments and no project data:

- [`reel-ingest`](../../skills/reel-ingest/SKILL.md): probe, rotation sheet, per-frame sharpness, motion, faces, blinks, transcription, snapping, forced alignment, onset gates.
- [`voice-clean`](../../skills/voice-clean/SKILL.md): noise diagnosis, A/B denoise chains, the floor gate, splice and word checks.
- [`reel-grade`](../../skills/reel-grade/SKILL.md): tone curve, exposure match over source time, the single range conversion.
- [`reel-cut`](../../skills/reel-cut/SKILL.md): pause tightening, J/L cuts around blinks, held frames over soft frames.
- [`reel-captions`](../../skills/reel-captions/SKILL.md): the correction layer and the caption ASR diff.
- [`reel-qa`](../../skills/reel-qa/SKILL.md): the gates and the [critic prompt](../../skills/reel-qa/references/critic-prompt.md), which turn the review checklist into numbers.
- [`craft-research`](../../skills/craft-research/SKILL.md): measuring reference reels in numbers.
- [`reel-director`](../../skills/reel-director/SKILL.md): the hard rules and stage order these findings fed into.

## What is not here

No footage, frames, audio, transcripts, clip names or timecodes from the sample reel, and nothing that identifies the edit that was reviewed. Times in the notes are durations and offsets ("about 1 s after the take starts"), never positions in a real file.
