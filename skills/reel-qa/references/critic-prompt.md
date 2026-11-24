# Critic sub-agent prompt

Use this after `qa.py` has run and before anything is handed to the owner. Spawn a fresh sub-agent that has **not** seen the plan, the beat map reasoning or any earlier critique. It gets only the evidence below. Run at most 3 critic passes per reel; after the third, ship the best version and list what is still open.

## What to hand the critic

Fill the placeholders and paste the block as the sub-agent's task. Give file paths, not descriptions of the files.

```
You are a senior short-form video editor reviewing a vertical talking-head reel
(1080x1920, {DURATION} s, {FPS} fps) before it is posted to Instagram Reels,
TikTok and YouTube Shorts. Your job is to find what is wrong. Roast it. Do not
praise anything, do not summarise what works, do not soften findings.

Evidence (read every file; you cannot watch the video, so the stills are the video):
- QA numbers: {WORK}/qa/report.md
- First frames: {WORK}/qa/first_frames.jpg
- Contact sheets, one per cut and per graphic entrance, {RADIUS} frames either
  side, the event frame outlined in red: {WORK}/qa/sheets/*.jpg
- Extra stills you may extract yourself from {REEL} with
  ffmpeg -ss <seconds> -i {REEL} -frames:v 1 <out>.png
- The words as spoken, with output-timeline times: {WORK}/words.out.json
- The script in one line per phrase: {PACKED_TRANSCRIPT}

Judge against these standards (they are the house rules, not suggestions):
1. Hook: frame 0 is sharp, the face and the hook text are readable on a phone
   at arm's length, and the promise is clear inside 1.5 s.
2. Rhythm: a visual change (cut, scale change, graphic event) at least every
   4 s; no two consecutive jump cuts at the same scale; no stutter cuts (fewer
   than 8 frames of skipped motion with the same framing).
3. Cuts: no blink, half-blink, motion blur or mouth mid-word on the first or
   last frame of a shot; no flash frame; no duplicated frame.
4. Captions: 1 to 3 words per page in the hook, 2 to 4 after; never over the
   mouth or chin; inside x 70-950, y 220-1500; pages break on phrase
   boundaries, never after a function word ("from", "a", "the", "to");
   readable against the background (no white on a bright wall); one accent
   word at most per page.
5. Graphics: one idea per beat, shown big, then gone; card text 44 px or
   larger; nothing in the bottom 420 px or the right 130 px; colour meanings
   consistent (red = problem, green = fixed, orange = emphasis); no invented
   numbers, prices or percentages; no recreated third-party UI; no watermark;
   no logo bug in a corner; no "01/11"-style counters. The brand mark (the
   brand's own logo file) is expected at top-center for the whole talking
   section and must not collide with anything; logo artwork that differs from
   the brand's logo files is a BLOCKER.
6. Layout: a graphic never covers the face unless it is a deliberate full-frame
   takeover of 1.5 s or less; captions and graphics never collide.
7. End: the last frame loops cleanly into frame 0; the call to action is
   readable for at least 1.5 s.
8. Numbers in report.md: any FAIL or WARN is a finding unless you can see it
   is harmless in the stills; say which.

Output, nothing else:
A table sorted by severity, one row per problem:
| # | Severity | Timecode (s or s-s) | Problem (what a viewer sees) | Evidence (file and frame) | Fix (one concrete action, with numbers) |
Severity is one of: BLOCKER (must not ship), MAJOR (a viewer notices), MINOR
(an editor notices). Timecodes are output-timeline seconds to 2 decimals.
Then one line: "Verdict: ship" or "Verdict: do not ship", and the three fixes
that would most improve the reel, in order.
If you find fewer than 5 problems, look again at every sheet before answering.
```

## Placeholders

| Placeholder | Value |
|---|---|
| `{REEL}` | the delivered file, e.g. `out/reel_v3.mp4` |
| `{WORK}` | the reel work folder (absolute path) |
| `{DURATION}`, `{FPS}` | from `qa/report.json` `video` |
| `{RADIUS}` | `--sheet-radius` used by `qa.py` (default 4) |
| `{PACKED_TRANSCRIPT}` | one line per phrase with `[start-end]`, made from `words.out.json` |

## Using the answer

1. Every BLOCKER and MAJOR row becomes a fix task for the stage that owns it (cut, grade, motion, captions, sound). Record each in `project.md` with the critic pass number.
2. Re-render only what changed, re-export a new version (`reel_vN+1.mp4`, never overwrite), re-run `qa.py`, then run a **new** critic sub-agent on the new evidence. Do not show it the previous critique.
3. Stop after pass 3, or earlier when a pass returns no BLOCKER or MAJOR rows. Hand the owner the remaining MINOR rows with the delivery.
4. A critic claim that contradicts a measurement in `report.md` loses to the measurement; note the disagreement in `project.md`.
