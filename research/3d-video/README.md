# 3D and QA research

Background research behind the [`reel-3d`](../../skills/reel-3d/SKILL.md) skill and the QA, camera, sound and director upgrades that came with it. It started from one question: a popular tutorial showed animated 3D shorts made with Remotion and three.js through a free public plugin, so what of that is worth bringing into a talking-head reel, and how do you render 3D deterministically on a machine with no GPU?

The answer, in short: 3D is punctuation, not the medium. A talking-head reel gets 2 or 3 short 3D inserts (1 to 2.5 s each, 4 to 8 s per minute), rendered once per beat on software GL (`swangle`) and played over the A-roll as plain video clips. The bigger win from the plugin was not the look but its craft and tooling: every-frame QA, measured camera grammar, word-keyed music ducking, loudness-based SFX levels and a scored critic loop.

The notes keep the numbers and the reasons. The values the pipeline ships live in the skills: when a note here and a skill disagree, the skill wins, because its value was tested afterwards.

## Files

| File | What it covers |
|---|---|
| [reference-and-plugin.md](reference-and-plugin.md) | What the reference tutorial covers and what mromidev's public animated-shorts plugin (MIT, `gh repo list mromidev`) actually does: pipeline, look-match loop, determinism tricks, camera grammar measured on 20 shorts, toon and post techniques, QA tooling, sound, script formula, readability traps, what transfers to a talking-head reel and what does not, licensing, and the search log. |
| [remotion-three.md](remotion-three.md) | Remotion 4 plus `@remotion/three` on a CPU-only machine: working version set, the GL backend matrix (`swangle` works, `angle` fails headless), render timings, determinism proofs and the things that break it, tone mapping and brand colour, shadows, framing in 9:16, and the rules every 3D composition follows. |
| [styles-and-when-3d.md](styles-and-when-3d.md) | Why 3D shorts hold viewers (measured grammar), how B2B and SaaS brands use 3D, the B-roll and interrupt evidence for talking heads, and the transfer: when 3D beats 2D, budget, screen zones, motion recipe, look in brand tokens, a moment library and sample spacing for a reel. |
| [gaps-and-plan.md](gaps-and-plan.md) | The gap audit (30 items, prioritised) of the reel skills against a top editor plus the plugin, the plan that followed (decisions, contracts between work items, five parallel work items with acceptance checks) and what was done. |
| [build-log.md](build-log.md) | The build in decisions and traps: what each work item measured, the contract changes agreed between them, and the traps caught on the way (lock deadlock, empty entrance frames, time conventions, frozen 3D holds). |
| [images/](images/) | Stills and sheets from the acceptance runs. All synthetic: mock props (`yourbrand.com`), a flat grey mock A-roll with a skin-coloured box for the face, and the public brand logo. |

## How it maps to the skills

| Topic | Research | Skill that now holds the code and the shipped values |
|---|---|---|
| 3D inserts, determinism, cost, 3D or 2D | remotion-three, styles-and-when-3d | [`reel-3d`](../../skills/reel-3d/SKILL.md), its [when-3d.md](../../skills/reel-3d/references/when-3d.md) and [determinism.md](../../skills/reel-3d/references/determinism.md) |
| `VideoInsert` beat, kick, glide, auto creep, time rule, caption options | reference-and-plugin 4, gaps-and-plan items 3, 7 to 12, 14 | [`reel-motion`](../../skills/reel-motion/SKILL.md), [`reel-captions`](../../skills/reel-captions/SKILL.md) |
| Every-frame gate, cover gate, side-by-side sheets, scored critic | reference-and-plugin 6, gaps-and-plan items 2, 15, 20 | [`reel-qa`](../../skills/reel-qa/SKILL.md) (its `NOTICE` credits the plugin) |
| Word-keyed duck, rides, dropouts, LU levels, generated SFX, cue sheet | reference-and-plugin 7 | [`reel-sound`](../../skills/reel-sound/SKILL.md) (its `NOTICE` credits the plugin) |
| Runbook, status, templates, doc lint, 3D budget audit, beat sheet, style bible, script brief | gaps-and-plan items 1, 6, 17, 19, 29 | [`reel-director`](../../skills/reel-director/SKILL.md) |
| Reference measurement in numbers, YouTube fallback | reference-and-plugin 1, 2 and 6 | [`craft-research`](../../skills/craft-research/SKILL.md) |
| 3D brand tokens, logo extrude rule | styles-and-when-3d 5.4 | [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) |

## Source status

- The tutorial video itself was **not watched**: YouTube answered LOGIN_REQUIRED on every client tried. Its public page (chapters, title, view count) was read, and its chapters match the README and skill file of the public plugin, which was read end to end as data. Every rule credited to "the plugin" comes from that repository, not from the video.
- Plugin code was read, never executed. Two skills adapt plugin code (`reel-qa` frame checks and side-by-side sheet, `reel-sound` whoosh generator) and carry the MIT notice. Everything else was rewritten from the numbers.
- The plugin ships reference frames and contact sheets from another channel "for style study only". Those are not MIT and nothing from them is reproduced here.
- Measured numbers (timings, md5 checks, gate tests) come from an 8 vCPU virtual machine with no GPU, under `nice` and at Remotion concurrency 2.

## Images

| Image | Shows |
|---|---|
| [takeover-inserts.jpg](images/takeover-inserts.jpg) | `EnvelopeToSpam3D`, `AuthShield3D` (takeover) and `LogoExtrude3D` at entry+4, mid and exit-2 |
| [card-inserts.jpg](images/card-inserts.jpg) | `DomainBurn3D` and `AuthShield3D` as 880x330 card inserts |
| [authshield-takeover.jpg](images/authshield-takeover.jpg) | the shortened 36-frame full-frame shield: plates enter, close in warning colour, turn success |
| [mock-reel-integration.jpg](images/mock-reel-integration.jpg) | the inserts inside a 12 s mock reel: takeover covers the frame on its first frame, the card sits in the card zone with captions above |
| [logo-handoff.jpg](images/logo-handoff.jpg) | the logo turn ending on the exact flat mark, then the 2D logo card that follows |
| [logo-sidewalls.jpg](images/logo-sidewalls.jpg) | logo side walls shaded to 0.12 of the face colour on turn frames (brighter walls made the wordmark look doubled) |
| [qa-3d-frozen-and-uniform.jpg](images/qa-3d-frozen-and-uniform.jpg) | the `frames` gate on a synthetic 3D insert: a 15-frame frozen span and one uniform frame flagged red |
| [qa-freeze-and-pop.jpg](images/qa-freeze-and-pop.jpg) | the `frames` gate on injected faults: a 20-frame freeze and a one-frame pop flagged red |
| [camera-kick-strip.jpg](images/camera-kick-strip.jpg) | the camera kick over 9 frames: alternating offsets decaying to zero, no frame edge showing |
