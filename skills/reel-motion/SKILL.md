---
name: reel-motion
description: Remotion motion-graphics stage for vertical talking-head reels (1080x1920). Use when adding camera punch-ins, pushes and creeps over a cut A-roll, placing beat graphics (title slams, cards, takeovers, end cards), rendering burned-in captions, writing a beat map or camera plan, building or previewing a beat component, or rendering stills and the graphics pass (gfx.mp4) of a reel.
---

# Reel motion (Remotion stage)

Stage 2 of the reel pipeline. Input: a graded A-roll (video only, tv range, bt709), `cues.json`, `words.out.json`. Output: `gfx.mp4` (muted H.264 CRF 14, bt709 tagged) that the export stage muxes with the mix. All scaling happens here (one resample); the A-roll stays at 1.00.

## Files

```
remotion/                        Remotion 4.0.542 project (all @remotion/* pinned to the same version, React 19)
  src/Root.tsx                   composition "Reel", 1080x1920, fps and duration from props (calculateMetadata)
  src/types.ts                   zod schema of the props (ReelProps), BeatContext, BeatProps<P>
  src/theme.ts                   colour, type, zone, surface, motion, camera and caption tokens
  src/lib/brand.ts               the brand file (alias target) and brandAsset()/brandLogo() for public assets
  src/fonts.ts                   local fonts via @remotion/fonts + load assertion (render fails if a face is missing)
  src/Reel.tsx                   Camera -> BeatLayer -> Captions (captions always last)
  src/components/Camera.tsx      OffthreadVideo with scale/translate keys, origin at the face centre
  src/components/Captions.tsx    caption pages and word reveal
  src/components/BeatLayer.tsx   one Sequence per beat; parses props with the component's schema
  src/components/registry.ts     component name -> defineBeat(schema, Component)
  src/components/beats/*.tsx     one file per beat component (default export + `schema`)
  src/components/ui/             shared primitives: Card, Tile, Pill, Kicker, Icon, AccentText, SafeArea, motion hooks
  src/lib/camera.ts              key sampling, translate clamp (never shows an edge)
  src/lib/captionPages.ts        page builder (createTikTokStyleCaptions tokens + scored page breaks)
  src/lib/rail.ts                progress rail events and state lookup
  PREVIEW.md                     render one beat over the real A-roll (still and short clip)
scripts/
  anchors.py                     time anchors: @word, @keyword, @cutBefore, @cutAfter, @end (and legacy @cut)
  plan_camera.py                 cues.json + shot config -> camera_plan.json
  resolve_beatmap.py             beat map source (anchors, per-beat mode) -> beatmap.json with captionModes
  build_props.py                 cues + words + beatmap + camera plan -> props.json (validated)
  prepare_public.sh              copies the brand into <public-dir>/.reel-motion-brand/
  render.sh                      stills (one bundle for all) or a full render with the colour and codec flags
  stills.mjs                     the stills renderer used by render.sh --still
  brand-webpack.mjs              REEL_BRAND alias shared by remotion.config.ts and stills.mjs
  test_captions.sh               page-builder unit test on a synthetic fixture
```

## Setup

```bash
cd remotion && npm ci && npx remotion browser ensure && npx tsc -p .
bash ../scripts/test_captions.sh
```

Licence: Remotion is free for individuals and companies of up to three people; larger for-profit organisations need a Remotion company licence (see remotion.dev/license) before rendering with this skill.

Python scripts run under `python -I` (they add their own folder to `sys.path`).

## Brand

The brand is a folder with `brand.json` and `assets/fonts`, `assets/logos` (see the bundled `../mailinfra-brand`). Set `REEL_BRAND=/path/to/brand-folder` to use another one; unset, the bundled brand is used. `render.sh` passes it to the webpack alias (`scripts/brand-webpack.mjs`, used by `remotion.config.ts` and `stills.mjs`) and to `prepare_public.sh`. The other brand's `brand.json` must have the same keys as the bundled one (TypeScript types come from it).

`prepare_public.sh <public-dir> [brand-dir]` copies `brand.json`, `fonts/` and `logos/` into `<public-dir>/.reel-motion-brand/` and touches nothing else. The folder carries a marker file; a folder of that name without the marker is never replaced. In components, load brand files with `brandAsset("logos/logo.svg")` or `brandLogo("primary")` from `src/lib/brand.ts`, never with a hard-coded path.

## Workflow

1. Write a shot config (per reel, kept in the reel work folder):
   ```json
   {"clips": {"CLIP_B": {"states": [1.06, 1.14], "startState": 0, "ty": 0}},
    "shots": {"0": {"scale": 1.10, "ty": 40}},
    "moves": [{"t": {"@word": "example", "offset": -0.16}, "delta": 0.04, "ease": "push"},
              {"t": {"@word": "second example", "edge": "end"}, "scale": 1.15, "ease": "creep"},
              {"t": {"@word": "third"}, "ease": "hold"}]}
   ```
   The timeline is split into visual shots at `cues.cuts` and at any `cues.needs_punch` time (`[t, ...]` or `[{t}]`, or `"needs_punch": true` on a segment: a jump inside a take that a punch has to hide). `clips` keys match a substring of the shot's clip name. Every shot starts with a `cut` key; consecutive shots of the same clip alternate through `states`; `shots` overrides one shot by index. After the moves are applied, every cut whose scale is within `--min-cut-change` (0.03) of the scale before it is forced up (or down near the ceiling) by `--punch-step` (0.06), and the shot's relative moves follow it. Then `python -I scripts/plan_camera.py --cues cues.json --shots shots.json --out camera_plan.json` and read its warnings (forced punches, edge clamps with the scale that would allow the requested offset, close pushes).
2. Write a beat map source: `{"beats": [{id, component, mode, from, to, props, modeFrom?, modeTo?}], "accents": [...]}`. Any time, anywhere (including inside `props`), may be an anchor resolved against `cues.json`:
   - `{"@word": "phrase", "n": 1, "edge": "start"|"end", "offset": -0.1}`: the n-th occurrence of a word or phrase (punctuation and case ignored).
   - `{"@keyword": "authent", "n": 1}`: the n-th word starting with that stem (survives caption corrections such as plural or tense).
   - `{"@cutBefore": "phrase"}`: the last cut at or before the phrase starts (cuts up to 0.12 s after the word onset count, set `snap` to change).
   - `{"@cutAfter": "phrase"}`: the first cut at or after the phrase ends.
   - `{"@end": true}`: the A-roll end.
   - `{"@cut": 3}` is a positional index and breaks after a re-cut; it still resolves but prints a warning. Use `@cutBefore`/`@cutAfter`.
   
   `python -I scripts/resolve_beatmap.py --cues cues.json --input beatmap.src.json --out beatmap.json --extra-sec 2.5` resolves the anchors and derives `captionModes` from each beat's `mode` (later beats win where they overlap, gaps are `talk`; `modeFrom`/`modeTo` narrow a beat's caption window). `--extra-sec` is the end card length after the A-roll. Content anchors keep the map valid after a re-cut; a phrase that was cut out fails loudly.
3. `python -I scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll <dir>/aroll.mp4 --public-dir <dir> --extra-sec 2.5 --out <dir>/props.json`. The A-roll path must be inside the public dir; props store it relative to that dir. The A-roll stops at its own end; frames after it are black under the end card.
4. Stills first: `bash scripts/render.sh --props props.json --public-dir <dir> --still 0.0,1.0,7.3 --out <dir>/stills` (one bundle for all stills). Look at them.
5. Full pass: `bash scripts/render.sh --props props.json --public-dir <dir> --out <dir>/out/gfx.mp4 --concurrency 4`. It always passes `--muted --color-space=bt709 --crf=14 --x264-preset=medium --pixel-format=yuv420p`, records the A-roll md5 in `<out>.aroll.md5`, and fails if the A-roll changed during the render or the frame count differs from `round(durationSec * fps)`. Re-run steps 1 to 3 whenever `cues.json` or `words.out.json` change; a render from stale props drifts after the first changed cut.

The CLI symlinks the public dir into the bundle (no copy), so pointing `--public-dir` at the reel work folder is cheap.

## Camera keys

`{t, scale, tx, ty, ease}` in output seconds, applied at frame `round(t * fps)`:

- `cut`: hard change on that frame. One on every cut frame, always with a scale change.
- `push`: eased move to the target over 8 frames with `cubic-bezier(0.16,1,0.3,1)`, starting at `t`. Emphasis pushes are +0.04 to +0.06, start 3 to 6 frames before the stressed word, at most one per 3 s, never on the same word as a caption accent pop or a card entrance.
- `creep`: slow ease-in-out from the current value to the target, spanning from `t` to the next key (or the end). +0.03 over 3 to 4 s on calm stretches.
- `hold`: keeps the current value (ends a creep early without a visible change). Its scale/tx/ty are ignored by the renderer.

Total scale is clamped to 1.00 to 1.20 (above 1.20 the upscale softens; check stills at 1.00/1.12/1.20 for each new camera body). Transform origin is the shot's face centre from `cues.json`; translation is clamped so the frame edge never shows: at scale `s` the largest downward `ty` is `(s - 1) * face.cy`. `plan_camera.py` warns when a key asks for more.

## Layout grammar

Graphics never use the bottom 420 px or the right 130 px. Zones (`zones` in `theme.ts`, `SafeArea` in `ui/`):

| Zone | Box |
|---|---|
| safe | x 70 to 950, y 220 to 1500 |
| card | x 70 to 950, y 1150 to 1480 |
| headline | x 70 to 950, y 236 to 440 |
| rail | from the brand's `layout.rail` (x 70, y 236, three 64x10 segments) |
| takeoverBand | x 70 to 950, y 380 to 1060 (leaves y 1180 free for captions) |

| Mode | Speaker | Graphic zone | Captions |
|---|---|---|---|
| Talk | full frame | none (a small progress rail at most) | centre y 1180 |
| Card | full frame | card zone | centre y 1060 (above the card, below the chin) |
| Takeover | hidden, at most 1.5 s (2.5 s once, only to cover a defect) | full frame, navy gradient | y 1180 over a band the graphic leaves empty, or mode `hidden` when the graphic spells the same words |

`captionModes` drive the caption position; a page that overlaps any `card` window sits at the card height for its whole life (no mid-page jumps). `hidden` suppresses captions frame by frame.

## Captions

- Pages come from scored breaks inside each phrase (a phrase ends at punctuation or a pause of 0.25 s). A page costs more when it ends on a function word (`a an the from to your and too of in with by`, other articles, prepositions, possessives, conjunctions, intensifiers) or a dangling subject or auxiliary, when it is a single word, or when it is shown for under 0.35 s; larger gaps after a page are rewarded. Max 3 words per page in the hook (before the first cut) and 4 after, enforced exactly; at most 2 lines of 22 characters.
- Accents: `"word"` (first occurrence), `{"text": "word", "n": 2}` (that occurrence) or `{"text": "word", "n": "all"}`. At most one accent per page, an accent phrase is never split across pages, and leading or trailing punctuation renders in the base style.
- Legibility: white Poppins and orange Lora both carry a tight dark shadow stack and a dark `paint-order` stroke, so accents read over skin and hands. Still run the contrast check of the captions skill.

## Motion tokens (`theme.ts`, hooks in `ui/motion.ts`)

- Entrances 8 frames, most travel in frames 1 to 5, `cubic-bezier(0.16,1,0.3,1)` (`useEntrance`, `entranceStyle`). Exits 5 frames, ease-in (`useExit`, `exitStyle`, or `useEnterExit` for both).
- Stagger 3 frames between list items (`index` option, `staggerStart`).
- Nothing grows from zero: arrive from scale 1.15 or a 40 px offset.
- Overshoot only on stamps and icons: scale 1.4 to 1.0 over 6 frames, at most 6 % overshoot (`useStamp`, `stampStyle`). At most one visible spring per beat. `shakeOffset` for a 2-frame camera-style shake.
- Text lands 0 to 2 frames before the word it illustrates.
- Hold every card at least 0.3 s per word + 0.5 s (`holdFramesFor`).

## Density rules

- One idea per beat, shown big, then gone. No permanent card stack.
- No cutaway or takeover in the first second; the face and the hook headline own frame 0.
- At least 2 s of face between takeovers.
- No window over 4 s without a cut, scale change or graphic event.
- Card text at least 44 px, numerals at least 140 px.

## Never ship

- Counters such as "01/11", timecodes, "n/3" labels
- Invented numbers, prices or percentages (only figures in the brand's approved claims list)
- Text under 44 px on cards (36 px only for a mono code line)
- A colour flood between every beat; a persistent logo bug; a watermark
- Recreated third-party UI (search pages, mail clients, platform chrome)
- Anything in the bottom 420 px or right 130 px; captions over the mouth
- A red MISSING or BAD PROPS box (a beat names an unregistered component, or its props fail the schema)
- A beat stub (a card labelled "<id> stub")

## Beat components

Each component lives in `remotion/src/components/beats/<Name>.tsx`:

```tsx
export const schema = z.object({ title: z.string(), at: timeSchema });
export type ExampleProps = z.infer<typeof schema>;
const Example = ({ props, frame, durationInFrames, fps, toFrame, beat }: BeatProps<ExampleProps>) => ...;
export default Example;
```

- `registry.ts` maps the beat map's `component` string to `defineBeat(schema, Component)`. Adding a new component is one import and one entry there; editing an existing component never touches it.
- `frame` is the beat's local frame (0 at `beat.from`), `durationInFrames` its length. Times in props are absolute output seconds (anchors resolve to them); `toFrame(t)` converts one to a local frame.
- Build from `components/ui` (Card, Tile, Pill, Kicker, Icon, AccentText with `*accent*` markup, zones, motion hooks) and `theme.ts` tokens only. Colours carry fixed meanings: danger = mistake, success = fixed, accent = emphasis/active, brand blue = the brand itself.
- `ProgressRail` and `Checklist` share geometry (`railSegmentRect`, `checklistRowRect`) and rail events (`src/lib/rail.ts`: `{t, segment, state}` with states `empty`, `active`, `marked`, `fixed`), so the rail can persist across many beats and hand off to the checklist at `morphIntoChecklistAt`.
- `npx tsc -p .`, then render stills at the entry (from + 4 frames), mid and exit (to - 2 frames) and a short clip (see `remotion/PREVIEW.md`), and look at each: text size, zones, collisions with the face and captions, colour meanings.

## Verification

- Colour integrity check: render a props file with an empty camera, no beats and no captions, then compare the same frame with `signalstats` (YLOW, YHIGH, YAVG within 1 to 2 codes) and `psnr` against the A-roll (45 dB or more). A double range conversion shows as YLOW rising by about 10 codes.
- Caption timing: extract frames at a few word onsets; the word must be partly visible 1 frame before its onset and fully visible 3 frames after.
- Cut sync: frame-difference peaks of the render and the A-roll must fall on the same frame at every `cues.cuts` entry (camera `cut` keys use `round(t * fps)`, the same rounding as the cut frames).
- Throughput on an 8-core CPU: about 7 s startup plus 9 to 10 frames per second at concurrency 4 on an idle machine; peak RSS about 830 MB. A batch of stills costs one bundle (about 15 s) plus 1 to 2 s per still.
- Do not render while the A-roll is being rewritten: OffthreadVideo reads the file during the whole render. `render.sh` checks the md5 before and after.
