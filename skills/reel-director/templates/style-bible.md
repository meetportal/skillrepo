# <Series name> style bible

One file per series, kept in the series work root (next to the reel folders), never in the skills repo. The lead reads it at stage 0 of every reel and updates it after every critic pass. It records outcomes, not intentions: a value goes in only after a render or a measurement showed it working, a trap only with the frame or number that showed it.

## Standing owner rules
Rules the owner gave once and never wants to repeat. Each has a date and applies to every reel of the series until the owner changes it.

| Since | Rule | Why (owner's words, short) |
|---|---|---|
| YYYY-MM-DD | The CTA is the bare domain `yourbrand.com`, no `www.` | |
| YYYY-MM-DD | No numbers on screen unless they are in the approved claims list | |

## Values that won
Measured values that survived a critic pass. Replace a row when a later pass beats it; keep the old value in the history column.

| Area | Value | Measured on | Evidence (number, frame, sheet) | History |
|---|---|---|---|---|
| Camera | punch states 1.06 / 1.14, glide 18 frames, kick 4.5 px over 7 frames | reel <n> pass <k> | `qa/sheets/full_02.jpg` | |
| Captions | 3 words per page in the hook, 4 after, accent style `serif` | | | |
| Colour | cheek Y target, look chain | | `cut_levels.py` report | |
| Mix | bed under voice, duck mode, SFX levels in LU | | `qa/mix_report.json` | |
| 3D | moments per reel, takeover length, rim colours | | `3d/<id>.json` renderSec | |
| Rhythm | median visual-event gap, words/s | | `beat_audit.py`, `beat_sheet.py` | |

## Traps caught
Things that looked fine in the plan and failed on screen or in a gate. Each row names the frame or the number that showed it, and the rule that now prevents it.

| Reel / pass | Trap | Shown by (frame, time, number) | Rule now |
|---|---|---|---|
| | A card entrance had an empty first frame | `qa/sheets/full_01.jpg` frame 87 | stills at `from + 0` for every new beat |

## Critic score history
| Reel | pass | hook | rhythm | cuts | captions | graphics | layout | grade | end | mean |
|---|---|---|---|---|---|---|---|---|---|---|
