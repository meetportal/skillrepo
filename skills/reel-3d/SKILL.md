---
name: reel-3d
description: Short deterministic 3D inserts for vertical talking-head reels, rendered with @remotion/three on software GL and played in reel-motion through the VideoInsert beat. Use when a reel needs a 3D moment (an email dropping into spam, a domain burning, an SPF/DKIM/DMARC shield closing, the logo turning to face the viewer), when deciding between a 3D and a 2D beat, when rendering, caching or checking 3D inserts, or when building a new 3D beat composition.
---

# Reel 3D (stage 8b)

3D is punctuation: one physical idea, 1 to 2.5 s, then back to the face. Each 3D beat is rendered once by its own Remotion project to a short opaque ProRes 4444 clip (`<work>/3d/<beatId>.mov`), cached by hash, and `reel-motion` plays it through the generic `VideoInsert` beat under the captions. three.js and software GL never enter the full reel render.

Read `references/when-3d.md` before planning a 3D moment (3D or 2D, budget, timing, sound, cost) and `references/determinism.md` before writing or changing a composition.

## Files

```
remotion/                     Remotion 4.0.542 project on @remotion/three (exact pins in package.json)
  remotion.config.ts          swangle GL, muted, bt709, overwrite
  render.mjs                  Node API renderer: one insert to ProRes 4444, stills or a PNG sequence; prints JSON
  src/Root.tsx                one composition per beat (+ BrandPatch3D for the colour check); size, fps and length from input props
  src/kit/Scene3D.tsx         ThreeCanvas: dpr 1, MSAA, PCF shadows, flat (no tone mapping), fov 32
  src/kit/Backdrop.tsx        navy gradient + soft spot as scene background (dithered), ShadowCatcher
  src/kit/Lights.tsx          hemisphere fill, key with 2048 PCF shadow, one rim in the meaning colour
  src/kit/BaseGlow.tsx        additive radial disc under the object in the meaning colour
  src/kit/CameraRig.tsx       camera set during render and in useLayoutEffect; principal point in pixels, kick shift, dolly creep
  src/kit/SyncedText.tsx      drei Text that holds the frame until troika glyphs are built
  src/kit/assets.ts           gated SVG fetch and label width measurement with the brand font
  src/kit/motion.ts           glide, creep, kick, entrance, holdSway, landFrameFor
  src/kit/random.ts           seeded mulberry32: rng, hash01, range
  src/kit/materials.ts        clay and tile presets (darkest floor as emissive), glow texture, shader patch helper
  src/kit/geometry.ts         rounded slabs, shield half curves, SVG to extruded geometry (fills and strokes)
  src/kit/brand.ts            brand input (colours + three tokens) to a palette; tone to colour
  src/kit/insert.ts           insert props, unknown-prop guard, calculateMetadata with events
  src/beats/*.tsx             EnvelopeToSpam3D, DomainBurn3D, AuthShield3D, LogoExtrude3D, BrandPatch3D
scripts/
  render3d.py                 beat map -> 3d/<id>.mov + 3d/<id>.json, cached by hash
  prepare_public.sh           copies brand.json, fonts and logos into remotion/public/.reel-3d-brand/
  check3d.py                  acceptance checks on mock props (determinism, still vs sequence, frozen, cost, logo IoU, colour)
references/when-3d.md         the 3D vs 2D decision, budget, sound, cost
references/determinism.md     the rules that keep every frame reproducible
```

## Setup

```bash
cd remotion && npm ci
ln -s ../../../reel-motion/remotion/node_modules/.remotion node_modules/.remotion
npx tsc -p .
bash ../scripts/prepare_public.sh
```

The symlink is optional: it reuses the Chrome headless shell that `reel-motion` already downloaded (`npx remotion browser ensure` downloads its own otherwise). Python scripts run under `python -I` and need numpy and Pillow only for `check3d.py`.

## Render the 3D beats of a reel

Run after `resolve_beatmap.py` and `build_props.py`, before `reel-motion/scripts/render.sh`:

```bash
export REEL_RENDER_LOCK=/path/to/render.lock REEL_CONCURRENCY=2
nice -n 19 ionice -c 3 python -I $SKILLS/reel-3d/scripts/render3d.py \
  --beatmap <work>/beatmap.json --props <work>/props.json --public-dir <work> --out-dir <work>/3d [--only spam3d] [--stills] [--force]
```

- A 3D beat is a beat with `component: "VideoInsert"` and `props.three = {composition, props}`. Frames = `round(to * fps) - round(from * fps)`, fps from `props.json` (or `--fps`).
- Inside `props.three.props`, every key ending in `At` is absolute output seconds (anchors resolve to them). `render3d.py` converts it to an insert-local frame and passes it as `<name>Frame` (`landAt` becomes `landFrame`). A time outside the beat fails. The beat-relative time rule of `reel-motion` does not apply under `props.three`.
- The beat's `props.src` must be the clip path relative to the public dir (`3d/<id>.mov`); a mismatch stops the run before anything renders.
- Brand: `$REEL_BRAND` (a brand folder with `brand.json` and `assets/`) or the bundled `mailinfra-brand`. The brand goes to the compositions as input props; no webpack alias.
- Cache: `sha256` of composition, converted props, size, fit, fps, frames, the brand tokens and files, and the `remotion/src` tree plus `render.mjs`, `package-lock.json`, `remotion.config.ts`. An unchanged beat prints `cached`. The bundle is cached under `remotion/out/bundle-<hash>`, keyed on the code tree plus everything in `remotion/public` (the brand logos and fonts that `prepare_public.sh` copies in and `remotion bundle` copies into the bundle), so a different `$REEL_BRAND` or a changed logo or font file re-bundles instead of rendering new colours with the old SVG and font.
- Each render runs `flock "$REEL_RENDER_LOCK"` when the variable is set, unless an ancestor process already holds that lock (wrapping the whole command in `flock` as well would otherwise deadlock). `REEL_CONCURRENCY` (default 2, max 2) sets the tabs.
- Output per beat: `3d/<id>.mov` (ProRes 4444, yuv444p10le, opaque, muted, bt709) and `3d/<id>.json`:
  ```json
  {"beat": "spam3d", "composition": "EnvelopeToSpam3D", "from": 2.0, "to": 3.36, "fps": 25, "frames": 34,
   "hash": "...", "gl": "swangle", "renderSec": 14.1,
   "events": [{"id": "whoosh", "t": 2.88, "kind": "whoosh"}, {"id": "land", "t": 2.92, "kind": "impact"}]}
  ```
  `t` is absolute output seconds; `kind` is `whoosh`, `impact`, `pop` or `glint` (reel-sound places SFX on them). The frame count is checked with ffprobe.
- `--stills` writes entry+4, mid and exit-2 PNGs per beat to `3d/stills/` (decoded from the clip, so they show what the reel will show). Look at them.

## VideoInsert in a beat map (reel-motion)

```json
{"id": "spam3d", "component": "VideoInsert", "mode": "takeover", "from": 2.0, "to": 3.36,
 "props": {"src": "3d/spam3d.mov", "fit": "full",
           "three": {"composition": "EnvelopeToSpam3D", "props": {"landAt": 2.96, "label": "Spam"}}}},
{"id": "burn3d", "component": "VideoInsert", "mode": "card", "from": 5.6, "to": 7.4,
 "props": {"src": "3d/burn3d.mov", "fit": "card",
           "three": {"composition": "DomainBurn3D", "props": {"burnAt": 6.16, "domain": "yourbrand.com"}}}}
```

| Prop | Default | Meaning |
|---|---|---|
| `src` | required | clip path under the public dir; a missing file fails the render (no black frames) |
| `fit` | `full` | `full` covers 1080x1920 and is opaque on the beat's first frame; `card` sits in `box` |
| `box` | `zones.card` (x 70 to 950, y 1150 to 1480) | card box; `render3d.py` renders the insert at this size |
| `radius` | `surface.cardRadius` (36) | card corner radius |
| `enterFrames` | 0 full, 8 card | card arrives from scale 1.15 and is already at opacity 0.4 on frame 0 |
| `exitFrames` | 0 | 5 gives the standard card exit; 0 is a hard cut |
| `startFromFrame` | 0 | trims the clip start |
| `three` | none | `{composition, props}` read only by `render3d.py` |

Caption mode follows the beat `mode` as for any beat: `takeover` keeps captions at y 1180 over the empty band, `card` lifts them to y 1060 above the card. The top logo stays on top of takeovers.

## Beats

All defaults are 25 fps mock values. Each beat lands 1 frame before its `*At` time with one kick (4.5 px, 7 frames, alternating decay), holds with a creep and a slow sway, and exits by hard cut.

| Composition | Fit and size | Length | Props (defaults) | What it shows |
|---|---|---|---|---|
| `EnvelopeToSpam3D` | full 1080x1920 | 1.2 to 1.5 s | `landAt`, `label: "Spam"`, `fromSide: "left"`, `tone: "danger"` | cream envelope with a blue seal arcs in over 12 frames with a 25 degree turn, pauses over an inbox tray, drops into a folder with a danger label plate and danger rim; rest pose inside y 380 to 1060 centred near (530, 715), about 520 px tall (the flight arc rises to about y 280) |
| `DomainBurn3D` | card 880x330 | 1.5 to 2 s | `burnAt`, `domain: "yourbrand.com"`, `tone: "danger"`, `seed: 7` | slate domain block with the label (font fitted to 0.78 units, cap height about 56 px); at the land a noisy char front crosses it in 18 frames with a hot edge, 6 to 10 additive fbm flame billboards along the top and seeded embers; ends on `three.burnt` (#3A1E24) |
| `AuthShield3D` | card 880x330 or full 1080x1920 (follows `fit`) | card 2 to 2.5 s; full 1.0 to 1.5 s (`lockAt` 0.8 to 0.9 s after `from`, so the 8-frame close and a 10 to 15 frame hold fit; `beat_audit.py` fails a takeover over 1.5 s) | `lockAt`, `labels: ["SPF", "DKIM", "DMARC"]`, `fromTone: "warning"`, `toTone: "success"` | three plates enter 3 frames apart with 30 degree turns, slide together at the lock, a shield outline draws closed from the top centre to the tip in 8 frames; rim and outline go warning to success at the lock, a light sweep runs down the outline; a row in a wide badge on a card, a stack in a tall shield on a takeover |
| `LogoExtrude3D` | full 1080x1920 | 0.8 to 1.0 s, the one takeover allowed under 1.0 s; never in the 3 s before the end card (the CTA window `beat_audit.py` fails), so it marks a brand moment earlier in the reel and hands off to a `LogoPop` card | `card: "navy"`, `logo: null`, `widthPx: 800`, `centerY: 870`, `yawDeg: 35` | the brand SVG extruded (depth 0.12, bevel 0.012 world units; fills and strokes) turns from 35 degrees to front-on over `frames - 4` frames (14 to 24), one glint, then the flat SVG fades in over the last 4 frames and the 3D mesh is hidden on the last one. `card`, `logo` and `widthPx` mean exactly what they mean on the `LogoPop` beat that follows (copy them, with its `centerY`): the mark is `widthPx - 2 x round(0.1 x widthPx)` wide (640 at the default 800), centred at x = the middle of `layout.safe` (510), and the logo defaults to `white` on navy and `color` on cream, so the final frame is the `LogoPop` mark pixel for pixel |

Events per composition (`3d/<id>.json`): EnvelopeToSpam3D `whoosh`, `land`; DomainBurn3D `ignite` (whoosh), `burn` (impact); AuthShield3D `plate1..n` (pop), `slide` (whoosh), `lock` (impact), `seal` (glint); LogoExtrude3D `turn` (whoosh), `glint`, `front` (pop).

Unknown keys in `props.three.props` fail the render with the list of known keys.

## Building a new 3D beat

1. Copy the closest file in `src/beats/`: export `<name>Defaults`, a `<name>Timeline(props, frames, fps)` that returns key frames and `events` (local frames), and the component taking `InsertProps<P>`. Register it in `src/Root.tsx` and add it to `COMPOSITIONS` in `scripts/render3d.py` and `MOCKS` in `scripts/check3d.py`.
2. Use the kit only: `Scene3D`, `Backdrop`, `CameraRig` (principal point in output pixels), `Lights` with the meaning tone, `BaseGlow`, `SyncedText` for at most one short label per object (cap height at least 56 px; 44 px card text minimum when three labels share a card row), `clay`/`tile` materials, `motion.ts` timing. One idea, one object, one label.
3. Colours come from the palette (`palette.color(token)`, `palette.tone(tone)`); rim, glow and label plates use the meaning colour. Glow only on fire, the shield edge and the glint. No bloom, no post-processing, no VSM.
4. `npx tsc -p .`, render stills at entry+4, mid and exit-2 and read them, then `python -I scripts/check3d.py --only <Name>`.

## Checks

```bash
nice -n 19 ionice -c 3 python -I scripts/check3d.py --work /path/to/scratch [--only EnvelopeToSpam3D] [--report report.json]
```

Per mock composition: two PNG-sequence renders compared by md5 per frame, `renderStill` of the mid frame against the sequence frame, frozen runs (12 or more frames with mean absolute grey difference under 0.25), cost per frame from a ProRes render minus a one-frame job, and for LogoExtrude3D the mask IoU of the last frame against the solid front-on 3D frame. The `BrandPatch3D` still and its ProRes decode are compared with the brand hex. Exit 1 on any failure.

Last results (bundled brand, swangle, concurrency 2, nice 19, shared 8 vCPU machine):

| Composition | Fit | Frames | Two runs identical | Still = sequence | Min frame diff | Frozen runs | ProRes job | One-frame job | s per frame |
|---|---|---|---|---|---|---|---|---|---|
| EnvelopeToSpam3D | full | 34 | 34/34 | yes | 0.18 | none | 10.2 s | 2.9 s | 0.221 |
| DomainBurn3D | card | 45 | 45/45 | yes | 0.37 | none | 5.5 s | 2.3 s | 0.073 |
| AuthShield3D | card | 56 | 56/56 | yes | 0.35 | none | 6.0 s | 2.4 s | 0.066 |
| AuthShield3D | full (`lockFrame` 21) | 36 | 36/36 | yes | 0.27 | none | 9.5 s | 3.2 s | 0.179 |
| LogoExtrude3D | full | 24 | 24/24 | yes | 0.01 | none | 6.3 s | 2.0 s | 0.185 |

Seconds per frame = (ProRes job - one-frame job) / (frames - 1), so browser start and page load are left out; a whole insert costs the ProRes job time plus about 25 s for a bundle when the code or the brand assets changed. LogoExtrude3D front-on mesh vs final flat mark silhouette IoU: 0.97 (the shaded bevel accounts for the rest); the final frame composited by reel-motion against a `LogoPop` beat (navy, `widthPx` 800, `centerY` 870) rendered by reel-motion itself, with `LogoExtrude3D` at its defaults (`widthPx` 800, `centerY` 870): logo mask IoU 0.987 to 0.994 (thresholds 128 to 200 inside the logo region).

On a 12 s mock reel (one EnvelopeToSpam3D takeover, one DomainBurn3D card): the takeover covers the frame on its first frame, the card sits in x 70 to 950, y 1150 to 1480 with captions centred at y 1056 above it, insert colours come through `VideoInsert` unchanged (median difference 0 on backdrop, label plate and envelope), the card clip is drawn 1:1 in its box with the border as an overlay (99th percentile difference 1 code against the decoded clip), a second `render3d.py` run prints `cached` for both beats, and a `src` that does not exist fails the render with "VideoInsert: ... returned 404". Brand patches (`BrandPatch3D`): `brandBlueOnDark`, `navyPanel`, `danger`, `success`, `accent`, `cream` render exactly (0 codes off) in PNG and within 1 code per channel after the ProRes 4444 round trip. `check3d.py` fails on more than 1 code in either.

## Values that won

- `flat` canvas plus front-biased key light: key (-4, 5, 8) at 3.0, hemisphere 1.0, rim (4.5, 3.5, -4) at 4.0. The prototype values (key (-4, 7, 6) at 2.2, hemisphere 0.9) were tuned under ACES tone mapping; with `flat` they rendered the cream envelope at about (166, 162, 156) and clipped top-facing bevels. Now the envelope face reads about (225, 220, 210) and only rim edges reach 255.
- `three.darkest` (#1A2038) as the emissive of every clay and tile material: unlit sides of navy plates were (2, 2, 8) before; nothing on an object now goes below the darkest token.
- Shadow catcher colour #060B1C at 0.35 instead of black at 0.42: the floor shadow stays navy.
- Char colour: the burned block renders about (58, 40, 44) for the #3A1E24 token (char albedo 0.8 x token, emissive 0.05 x token, the navy emissive floor removed where burnt; with the floor it turned mauve). The ember grain stays under 0.4 gain so the label stays the brightest thing on the card.
- The backdrop gradient carries a seeded 1-code dither; without it the 0.18 spot showed rings once encoded.
- Card cameras creep at 0.0015 per frame (the wide card fills its box; 0.0025 pushed the badge into the edges by the last frame); takeovers creep at 0.0025 (0.0015 for the tall shield).
- Strokes in the logo SVG become one offset outline per sub-path (miter offsets, round caps, ring with a hole for closed paths) before extrusion. Unioning a quad per segment and a disc per point gave criss-cross bevels at every corner.
- Logo side walls shaded to 0.12 of the face colour and emissive only on front faces: at 35 degrees full-white side walls made the wordmark look doubled, and at 0.42 the i-dots and the M still ghosted on the turn frames; at 0.12 the walls read as dark depth.
- Logo bevel 0.012 instead of 0.03 world units: at a 640 px mark (167 px per unit) 0.03 is 5 px, which ate most of the 12 px icon stroke and dropped the front-on mesh vs flat mark IoU to 0.83; at 0.012 it is 0.96.
- Takeover holds need real motion to pass the frozen check on a mostly empty navy frame: the tall shield went from creep 0.0015 and sway 1.3 degrees (diffs 0.17 to 0.24) to creep 0.0025 and sway 2.2 degrees.
- Envelope mesh at bevelSegments 4 and curveSegments 10 (from 6 and 16): 0.36 to about 0.22 s per frame with no visible change.

## Traps caught

- `--gl=angle` (the docs' and many templates' setting) fails headless on a machine without a GPU: "Initialization of all (2) EGL display types failed". Always `swangle`.
- A camera set in `useEffect` lags one frame and shows frame-0 framing on the first frame of each tab.
- Troika text missing on frames 0 and 1 of each tab until the text gate redraws the canvas.
- A text label at the same depth as the front of its plate z-fights into a broken "Spam"; labels sit 0.05 units in front of the plate face.
- `SVGLoader.createShapes` is deprecated in three 0.187; use `shapePath.toShapes()`.
- A lit `MeshStandardMaterial` never shows the brand hex; judge brand colour on the flat label plates and on `BrandPatch3D`, not on shaded faces.
- `flock` on the same lock file around a command that takes the lock again deadlocks forever. `render3d.py` skips its own lock when an ancestor holds it; do not wrap other entry points twice.
- The R3F directional light target is not in the scene, so `target-position` does nothing; scenes are built around the origin instead.
