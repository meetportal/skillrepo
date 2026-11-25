# <Reel name>

Series style bible: `../style-bible.md` (read at stage 0, update after every critic pass).

## Brief
- Goal / audience / platform(s):
- Owner decisions needed (claims, music licence, brand system, CTA destination): <list, each with status>
- Source clips (read only): <folder>, <n> clips, <fps>, <rotation>, <range>
- Length target: <talking s> + <end card s>
- Reference reel (measured with `craft-research/scripts/measure_reference.py`): <name>, `research/ref.json`

## Script (packed)
<paste packed_transcript.py output for the kept takes>

## Beat sheet
<paste beat_sheet.py output; every GAP row needs a planned cut, scale change, kick or beat>

## Takes
| Clip | Role | Keep (source s) | Why / defects (blinks, blur, hand, sway) |
|---|---|---|---|
| CLIP_A | hook + body | 0.8-14.0 | |

## Hook
| Variant | Text | Visual at frame 0 | Chosen? Why |
|---|---|---|---|
| A | | | |
| B | | | |
| C | | | |

## Beat map
| Beat | Out s | Mode | Picture and graphic | Caption accent | SFX |
|---|---|---|---|---|---|
| hook | 0.00-1.11 | talk | HookHeadline | burning | pop on frame 0 |

## 3D moments
Budget (`../reel-3d/references/when-3d.md`): 2 to 3 moments, 4 to 8 s per 60 s, at most one full-frame 3D takeover per 15 s and each 1.0 to 1.5 s, none in the first 1.0 s or over the CTA.

| Beat id | Composition | Mode | Out s | Length s | Physical metaphor | Key anchor (`*At`) | Events (whoosh, impact, pop, glint) | `3d/<id>.json` hash |
|---|---|---|---|---|---|---|---|---|
| spam3d | EnvelopeToSpam3D | takeover | 1.11-2.23 | 1.12 | the email lands in spam | landAt = "spam" | land | |

## Decisions log
| When | Stage | Decision | Measured evidence | Source (precedence level) |
|---|---|---|---|---|

## Caption edits
| Word index / phrase | Spoken | Shown | Reason |
|---|---|---|---|

## QA and critic passes
| Version | qa.py verdict (blocking gates) | Critic BLOCKER/MAJOR count | Fixed in |
|---|---|---|---|

### Critic scores (1 to 10 per area, one row per pass)
| pass | hook | rhythm | cuts | captions | graphics | layout | grade | end | mean |
|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | |

### Side-by-side sheets
| Pass | Sheet | Our times | Reference times | What still differs |
|---|---|---|---|---|

## Open items for the owner
- <listen timestamps, claims to approve, licence questions>
