---
name: reel-motion
description: Remotion motion-graphics stage for vertical talking-head reels (1080x1920). Use when adding camera punch-ins, pushes and creeps over a cut A-roll, placing beat graphics (title slams, cards, takeovers, end cards), rendering burned-in captions, writing a beat map or camera plan, adding a new graphics component, or rendering stills and the graphics pass (gfx.mp4) of a reel.
---

# Reel motion (Remotion stage)

Stage 2 of the reel pipeline. Input: a graded A-roll (video only, tv range, bt709), `cues.json`, `words.out.json`. Output: `gfx.mp4` (muted H.264 CRF 14, bt709 tagged) that Stage 3 muxes with the mix. All scaling happens here (one resample); the A-roll stays at 1.00.

Brand tokens come from the brand skill (`../mailinfra-brand/brand.json`, imported by `remotion/src/theme.ts`). To use another brand, point the two imports in `theme.ts` and `fonts.ts` at that brand's `brand.json` and pass its folder to `prepare_public.sh`.

## Files

```
remotion/                      Remotion 4.0.542 project (all @remotion/* pinned to the same version, React 19)
  src/Root.tsx                 composition "Reel", 1080x1920, fps and duration from props (calculateMetadata)
  src/types.ts                 zod schema of the props (ReelProps) and BeatComponent type
  src/theme.ts                 colour, type, layout, motion, camera and caption tokens
  src/fonts.ts                 local fonts via @remotion/fonts + load assertion (render fails if a face is missing)
  src/Reel.tsx                 Camera -> BeatLayer -> Captions (captions always last)
  src/components/Camera.tsx    OffthreadVideo with scale/translate keys, origin at the face centre
  src/components/Captions.tsx  caption pages and word reveal
  src/components/BeatLayer.tsx renders each beat in a Sequence; unknown names show a red MISSING box
  src/components/registry.ts   component name -> component map
  src/lib/camera.ts            key sampling, translate clamp (never shows an edge)
  src/lib/captionPages.ts      page builder (createTikTokStyleCaptions tokens + page rules)
scripts/
  anchors.py                   resolves {"@word": "...", "n": 1, "edge": "start", "offset": -0.16}, {"@cut": 3}, {"@end": true}
  plan_camera.py               cues.json + shot config -> camera_plan.json
  resolve_beatmap.py           beat map source (anchors, per-beat mode) -> beatmap.json with captionModes
  build_props.py               cues + words + beatmap + camera plan -> props.json (validated)
  prepare_public.sh            copies brand fonts and logos into <public-dir>/brand/
  render.sh                    stills or full render with the colour and codec flags
```

## Setup

```bash
cd remotion && npm ci && npx remotion browser ensure && npx tsc -p .
npm run prepare-assets           # only for `npx remotion studio` with remotion/public
```

## Workflow

1. Write a shot config (per reel, kept in the reel work folder):
   ```json
   {"clips": {"CLIP_B": {"states": [1.06, 1.14], "startState": 0, "ty": 0}},
    "shots": {"0": {"scale": 1.10, "ty": 80}},
    "moves": [{"t": {"@word": "mistakes", "offset": -0.16}, "delta": 0.04, "ease": "push"},
              {"t": {"@word": "long before", "edge": "end"}, "scale": 1.15, "ease": "creep"}]}
   ```
   The timeline is split into visual shots at `cues.cuts` (bridging J/L segments of the same take are not shots). `clips` keys match a substring of the shot's clip name. Every shot starts with a `cut` key; consecutive shots of the same clip alternate through `states` (never two consecutive cuts at the same scale); `shots` overrides one shot by index. Then `python scripts/plan_camera.py --cues cues.json --shots shots.json --out camera_plan.json` and read its warnings.
2. Write a beat map source: `{"beats": [{id, component, mode, from, to, props, modeFrom?, modeTo?}], "accents": [...]}`. Any time, anywhere (including inside `props`), may be an anchor object resolved against `cues.json` words, so the map survives a re-cut. `python scripts/resolve_beatmap.py --cues cues.json --input beatmap.src.json --out beatmap.json --extra-sec 2.5` resolves the anchors and derives `captionModes` from each beat's `mode` (later beats win where they overlap, gaps are `talk`; `modeFrom`/`modeTo` narrow a beat's caption window, for example to let captions resume on a word). `--extra-sec` is the end card length after the A-roll.
3. `python scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll <dir>/aroll.mp4 --public-dir <dir> --extra-sec 2.5 --out <dir>/props.json`. The A-roll path must be inside the public dir; props store it relative to that dir. The A-roll stops at its own end; frames after it are black under the end card.
4. Stills first: `bash scripts/render.sh --props props.json --public-dir <dir> --still 0.0,1.0,7.3 --out <dir>/stills`. Look at them.
5. Full pass: `bash scripts/render.sh --props props.json --public-dir <dir> --out <dir>/out/gfx.mp4 --concurrency 4`. It always passes `--muted --color-space=bt709 --crf=14 --x264-preset=medium --pixel-format=yuv420p`.

The CLI symlinks the public dir into the bundle (no copy), so pointing `--public-dir` at the reel work folder is cheap.

## Camera keys

`{t, scale, tx, ty, ease}` in output seconds, applied at frame `round(t * fps)`:

- `cut`: hard change on that frame. Put one on every cut frame.
- `push`: eased move to the target over 8 frames with `cubic-bezier(0.16,1,0.3,1)`, starting at `t`. Emphasis pushes are +0.04 to +0.06, start 3 to 6 frames before the stressed word, at most one per 3 s, never on the same word as a caption accent pop or a card entrance.
- `creep`: slow ease-in-out from the current value to the target, spanning from `t` to the next key (or the end). +0.03 over 3 to 4 s on calm stretches.

Total scale is clamped to 1.00 to 1.20 (above 1.20 the upscale softens; check stills at 1.00/1.12/1.20 for each new camera body). Transform origin is the segment's median face centre from `cues.json`; translation is clamped so the frame edge never shows, so a large `ty` at a low scale is reduced automatically.

## Layout grammar

Graphics never use the bottom 420 px or the right 130 px. Universal safe box: x 70 to 950, y 220 to 1500.

| Mode | Speaker | Graphic zone | Captions |
|---|---|---|---|
| Talk | full frame | none (a small progress rail at most) | centre y 1180 |
| Card | full frame | lower stage card box x 70 to 950, y 1150 to 1480 | centre y 1060 (above the card, below the chin) |
| Takeover | hidden, at most 1.5 s (2.5 s once, only to cover a defect) | full frame, navy gradient | y 1180 over a band the graphic leaves empty, or mode `hidden` when the graphic spells the same words |

`captionModes` drive the caption position; a page that overlaps any `card` window sits at the card height for its whole life (no mid-page jumps). `hidden` suppresses captions frame by frame.

## Motion tokens (`theme.ts`)

- Entrances 8 frames, most travel in frames 1 to 5, `cubic-bezier(0.16,1,0.3,1)`. Exits 5 frames, ease-in.
- Stagger 3 frames between list items.
- Nothing grows from zero: arrive from scale 1.15 or a 40 px offset.
- Overshoot only on stamps and icons: scale 1.4 to 1.0 over 6 frames, at most 6 % overshoot. At most one visible spring per beat.
- Text lands 0 to 2 frames before the word it illustrates.
- Hold every card at least 0.3 s per word + 0.5 s.

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
- Recreated third-party UI (Google, Gmail, platform chrome)
- Anything in the bottom 420 px or right 130 px; captions over the mouth
- A red MISSING placeholder (means a beat names a component that is not registered)

## Adding a component

1. Create `remotion/src/components/<Name>.tsx` exporting `export const <Name> = ({ beat }: BeatRenderProps) => ...`. Parse `beat.props` with a zod schema declared in the same file (props come from JSON). Inside the component `useCurrentFrame()` is relative to `beat.from`; convert absolute word times with `Math.round((t - beat.from) * fps)`.
2. Add one import and one entry line to `remotion/src/components/registry.ts` (`<Name>,`). The registry key is the `component` string used in beat maps.
3. Use only `theme.ts` tokens for colour, type, easing and timing.
4. `npx tsc -p .`, then render stills at the entry (from + 4 frames), mid and exit (to - 2 frames) frames and look at each: text size, safe box, collisions with the face and captions, colour meanings.

## Verification

- Colour integrity check: render a props file with an empty camera, no beats and no captions, then compare the same frame with `signalstats` (YLOW, YHIGH, YAVG within 1 to 2 codes) and `psnr` against the A-roll (45 dB or more). A double range conversion shows as YLOW rising by about 10 codes.
- Caption timing: extract frames at a few word onsets; the word must be partly visible 1 frame before its onset and fully visible 3 frames after.
- Cut sync: frame-difference peaks of the render and the A-roll must fall on the same frame at every `cues.cuts` entry (camera `cut` keys use `round(t * fps)`, the same rounding as the cut frames).
- Throughput on an 8-core CPU: about 7 s startup plus 9 to 10 frames per second at concurrency 4 on an idle machine; a 49 s reel took 5 min while other heavy jobs shared the CPU. Peak RSS about 830 MB.
- Do not render while the A-roll is being rewritten: OffthreadVideo reads the file during the whole render. Check the A-roll checksum before and after.
