# When to use a 3D insert, and how much

3D is punctuation in a talking-head reel, not the medium. The face carries the reel; a 3D moment lands one physical idea the viewer should follow with their eyes, then gets out of the way.

## 3D or 2D

| Use 3D | Use 2D (`reel-motion` beats) |
|---|---|
| a physical metaphor the viewer follows: the email that lands in spam, the domain that burns, the shield that closes, the logo that turns to face them | text, numbers, lists, comparisons, charts, anything the viewer reads |
| one object, one action, one label at most | several labels, a sentence, a checklist |
| a moment the script lingers on for at least 1 s | a word or phrase that passes in under 0.6 s |

If the idea still reads when the object is drawn flat, draw it flat: 2D renders in a fraction of the time and stays sharp at caption size.

## Budget for a 45 to 60 s reel

| Rule | Value |
|---|---|
| 3D moments | 2 to 3 |
| total 3D time | 4 to 8 s per 60 s |
| full-frame takeovers | at most one per 15 s window, each 1.0 to 1.5 s (`LogoExtrude3D` alone may be 0.8 to 1.0 s) |
| card inserts | 1.5 to 2.5 s |
| all graphics together | 35 to 50 % of runtime |
| first second | no 3D (the face and the hook own frame 0) |
| CTA, end card and any personal story | no 3D over them |
| face between two takeovers | at least 2 s |
| models | the same envelope model everywhere in a reel; one look per series |

`reel-director/scripts/beat_audit.py` enforces the first-second, CTA, takeover-density, total-time and takeover-length rules on the beat map. Its CTA window is the last 3 s before the end card (or the A-roll end), and any 3D beat touching it FAILs, so a 3D logo turn never leads straight into the end card: use `LogoExtrude3D` for a brand moment earlier in the reel (the first time the brand is named, handing off to a `LogoPop` card) and let `EndCard` own the close.

## Timing and sound

- Every `*At` prop is the spoken word the motion illustrates. The object lands 1 frame before it (0 to 3 allowed) with one kick, never on it.
- Sound (reel-sound reads `3d/<id>.json` events): the whoosh peaks 1 frame before the land, one impact on the land frame, a glint gets a pop at -16 LU at most. Nothing else.
- Holds creep (0.0015 to 0.0035 scale per frame) and turn slowly, so no 12-frame span is frozen.
- Exits are a hard cut, or 5 frames with `exitFrames: 5` on a card.

## Cost (software GL, this pipeline)

| Item | Cost |
|---|---|
| fixed per insert (browser start, page load, first frame) | about 3 s |
| bundle of the 3D project | about 25 s, once per code change (cached under `remotion/out/bundle-<hash>`) |
| 1080x1920 takeover, standard look | 0.15 to 0.3 s per frame at concurrency 2 |
| 880x330 card | under 0.1 s per frame |
| dpr 2 | 2.7x |
| VSM shadows | 5x (never use) |
| a re-render with nothing changed | 0 (cached by hash) |

The measured numbers per beat are in `../SKILL.md`.

## Source levels

- The B-roll and density guidance comes from written practitioner guides and a public plugin's style notes (level 4: not yet A/B tested on our reels; treat as a starting point and check retention).
- The cost and determinism numbers were measured on this pipeline (level 2).
