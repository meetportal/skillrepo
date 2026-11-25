# The beat-map approach

The beat map is the plan for Stage 2: one row per spoken idea, saying what the picture does, where the graphic sits, where the captions go and which sound marks it. It is written after the cut is locked, from the retimed words, and every time in it is resolved from word onsets, never typed in from planning notes.

The skills implement this as a beat map source with word anchors (`reel-motion/scripts/resolve_beatmap.py`), a beat sheet (`reel-director/scripts/beat_sheet.py`) and a plan gate (`reel-director/scripts/beat_audit.py`). This file explains the reasoning behind their rules.

## Core rules

1. **One idea per beat.** A beat is one spoken idea and at most one graphic, shown big, then gone. No card stacks, no two cards on screen at once.
2. **Every beat has a layout mode** (below). The mode decides where the speaker, the graphic and the captions are.
3. **A visual event every 1.5 to 2.5 s, never a gap over 4 s.** A visual event is a cut, a scale change, a push, a graphic entrance or exit. The first reel's plan had a longest stretch of about 2.9 s.
4. **Graphics land 0 to 2 frames before the word they illustrate.** Hold each card at least 0.3 s per word on it plus 0.5 s.
5. **Recompute every time after each cut.** Planning estimates drift by tenths of a second once the real render exists. The beat map anchors to words (`{"@word": "..."}`) so it survives re-cuts.

## Layout modes

| Mode | Speaker | Graphic zone | Captions |
|---|---|---|---|
| **Talk** | full frame | none (a small progress element at most) | centre y about 1180 |
| **Card** | full frame | lower stage, card box x 70-950, y 1150-1480 | move up to centre y about 1060, which must stay below every chin (measure the lowest chin across takes from the face boxes) |
| **Takeover** | hidden, at most 1.5 s (one exception up to 2.5 s, only to cover a defect such as sway blur) | full frame | over a band the graphic leaves empty, or suppressed when the graphic spells the same words |

- **Universal safe box: x 70-950, y 220-1500.** Nothing in the bottom 420 px (captions, handle, music line of the platform UI) or the right 130 px (like, comment, share buttons).
- At least 2 s of face between takeovers. No takeover in the first second: the face and the hook own the opening.
- A takeover is also the tool for hiding a defect the cut could not avoid (a soft run of frames, a blink that had to stay, a sway blur). `cues.json` lists such windows as `cover`, and the gate fails if a takeover does not span each one completely.

## Camera states

The camera is a CSS transform on the A-roll with its origin at the face centre of each shot.

| Rule | Value |
|---|---|
| Base scale per take | Chosen to bring shot sizes roughly together, capped so total scale never exceeds 1.20 |
| Jump cuts inside a take | Alternate between two punch states, a hard change on the cut frame (for example 1.06 and 1.14). Never two cuts in a row at the same scale |
| Micro jump cuts (6 source frames or fewer skipped) | Must get a scale change, or they read as a stutter |
| Emphasis push | +0.04 to +0.06 over 8 frames, `cubic-bezier(0.16,1,0.3,1)`, starting 3 to 6 frames before the stressed word, at most one per 3 s, never during a caption pop of the same word or a card entrance |
| Slow creep on calm stretches | about +0.03 over 3 to 4 s |
| Hook framing | A slightly tighter base (about 1.10) at frame 0 hides soft focus at the start of a take; it can ease back to 1.00 on a stressed word. Shift the frame down (up to about 80 px) while a top headline is on screen so it clears the head |
| Sway | A static crop at 1.12 to 1.20 holds a speaker who sways about 100 px either way; larger drift needs a cover or a tracked crop |

Shot sizes do not need to match exactly: a bigger change in size at a section boundary reads as a deliberate new camera. Upscale softness at 1.18 to 1.20 must be checked on stills for each new camera body.

## Motion tokens

- Entrances 8 frames (320 ms at 25 fps) with most of the travel in frames 1 to 5, `cubic-bezier(0.16,1,0.3,1)`.
- Exits 5 frames (200 ms), ease-in.
- Stagger 3 frames (120 ms) between list items.
- Overshoot only on stamps and icons (for example scale 1.4 to 1.0, at most 6 % overshoot). At most one visible spring per beat.
- Nothing grows from zero: arrive from scale 1.15 to 1.0 or from a 40 px offset.
- Text at least 44 px on cards (36 px only for a deliberately small mono detail line), numerals at least 140 px.

## The list-reel spine

Many talking-head reels are lists ("three mistakes", "five tips"). The plan gives them a fixed spine:

- **A title slam on each list marker word** ("First", "Second", "Third"): a kicker with the item number plus a short title in the speaker's own words, 0.6 to 0.75 s, either as a band in the Card zone or as a short takeover with a giant numeral. The number is large content, not a "01/03" HUD counter.
- **A breath of about 0.28 s after each marker** in the cut, so the slam lands before the next word.
- **Each item gets its own shot** (a different scale or a different take).
- **A segment rail** (one small segment per item, no text label) can carry the state: grey for not reached, orange for active, red for the problem, green for fixed. It pays off at the wrap, where the segments turn green and become the checklist.
- **The music downbeats** land on the hook frame, each title slam and the logo pop when the track allows it (`reel-sound/scripts/find_downbeats.py`).

## Hook

- Speech starts within 0.3 s of frame 0. Frame 0 is the thumbnail and the loop frame: sharp face, eyes open, headline already on screen by frame 2.
- The promise is stated or shown by 1.5 s.
- Write three hook variants from the same truthful speech, build each as a still, pick one and record why. Typical variants: a number-led headline, an imperative headline, and a visual-led opening where the graphic is the hero.
- Captions in the hook use 1 to 3 words per page; after the first cut, 2 to 4.

## SFX pairing

Every SFX cue is paired with a visible event in the beat map; nothing plays over a static frame. The plan's density was about 25 cues in a 50 s reel, inside a 15 to 30 band. Categories by event:

| Visual event | Sound |
|---|---|
| Hook headline slam | soft impact, with a short riser tail ending on it |
| Title slam | whoosh + impact |
| Card or rail entrance | short whoosh |
| Tile, chip or list item landing | click, tick or pop, varied files for repeats |
| Something breaking or failing | small glitch |
| Gauge or meter sweep | short riser into the peg |
| Item fixed, seal, check | soft ding or pop |
| Logo pop | riser resolving into a soft sting |
| Wipe to end card | whoosh |

At most 3 impacts and 2 risers per reel. Shift each file so its transient lands on the visual frame, and move it 1 to 2 frames earlier if it would land on a stressed consonant. Never synthesise ad-hoc SFX in graphics code; use a kit with a manifest so every file is in `CREDITS.txt`. Current level targets are in [`reel-sound`](../../skills/reel-sound/SKILL.md).

## Template beat table

Columns of the plan table, written before any component code. The example rows are synthetic (a reel of about 38 s listing three common mistakes when setting up a home office) and only show the shape.

| Beat | Out (s) | Mode | Picture and graphics | Captions (accent word) | SFX |
|---|---|---|---|---|---|
| B0 Hook | 0.00-3.40 | Talk + top headline | Speaker at 1.10, shifted down; headline "3 MISTAKES" plus a one-line subhead with the accent word, on screen by frame 2; exits on the first cut | 1 to 3 words per page, y 1180 | soft impact at 0.00 |
| B1 Open loop | 3.40-5.60 | Talk | Hard cut to the other punch state; rail drops in on the spoken number | 2 to 4 words, accent on the number | short whoosh on the rail |
| M1a Title | 5.60-6.30 | Card (band) | Band in the lower stage: kicker "MISTAKE 01", title in the speaker's words; rail segment 1 orange | suppressed under the band text; marker word above it at y 1060 | whoosh + impact |
| M1b Explain | 6.30-10.80 | Card | One comparison card (wrong vs right), 44 px minimum text, relative shapes only | y 1060, accent on the key noun | short whoosh in |
| M1c Mark | 10.80-11.40 | Talk | Rail segment 1 turns red; cut changes scale | y 1180 | tick |
| M2a to M3c | ... | ... | Same spine for items 2 and 3; one takeover of at most 1.5 s somewhere in the middle third | ... | ... |
| W1 Fix | 28.00-31.00 | Card | Rail segments flip to green checks and slide into a checklist | y 1060 | three pitch-varied pops |
| W2 Payoff | 31.00-34.40 | Talk | Slow creep; cut to a tighter state for the last line | y 1180 | none |
| W3 Logo pop | 34.40-35.20 | Card | Logo card pops 1 frame before the spoken brand name | accent on the brand name | riser into sting |
| END | 35.20-37.70 | Takeover (end card) | Logo, two-line headline, bare domain in a CTA pill, "Link in bio" | none | whoosh on the wipe, pop on the pill |

## Gate on the plan

After resolving the beat map, `reel-director/scripts/beat_audit.py` fails the plan when the first word starts after 0.3 s, frame 0 has no hook visual, a takeover starts in the first second, any gap passes 4 s without a visual change, a takeover runs over 1.5 s (one up to 2.5 s is a warning), or a `cover` window is not inside a takeover. It warns on a median gap over 2.5 s, under 2 s of face between takeovers, overlapping cards, beats under 0.6 s and kicks closer than 3 s. The 3D budget it also checks was added after this plan ([`reel-3d`](../../skills/reel-3d/SKILL.md)).
