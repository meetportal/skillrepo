---
name: reel-motion
description: Remotion motion-graphics stage for vertical talking-head reels (1080x1920). Use when adding camera punch-ins, pushes, glides, creeps and impact kicks over a cut A-roll, placing beat graphics (title slams, cards, takeovers, end cards), rendering burned-in captions, writing a beat map or camera plan, building or previewing a beat component, or rendering stills and the graphics pass (gfx.mp4) of a reel.
---

# Reel motion (Remotion stage)

Stage 2 of the reel pipeline. Input: a graded A-roll (video only, tv range, bt709), `cues.json`, `words.out.json`. Output: `gfx.mp4` (muted H.264 CRF 14, bt709 tagged) that the export stage muxes with the mix. All scaling happens here (one resample); the A-roll stays at 1.00.

## Files

```
remotion/                        Remotion 4.0.542 project (all @remotion/* pinned to the same version, React 19)
  src/Root.tsx                   composition "Reel", 1080x1920, fps and duration from props (calculateMetadata), plus "CaptionBoxes"
  src/CaptionBoxes.tsx           lays out the caption pages in the browser (real fonts) and returns their boxes as metadata props
  src/types.ts                   zod schema of the props (ReelProps), BeatContext, BeatProps<P>
  src/theme.ts                   colour, type, zone, surface, motion, camera and caption tokens
  src/lib/brand.ts               the brand file (alias target) and brandAsset()/brandLogo() for public assets
  src/fonts.ts                   local fonts via @remotion/fonts + load assertion (render fails if a face is missing)
  src/Reel.tsx                   Camera -> LookOverlay -> BeatLayer -> TopLogo -> Captions (captions always last)
  src/components/Camera.tsx      OffthreadVideo with scale/translate keys and kick offsets, origin at the face centre
  src/components/Captions.tsx    caption pages, word reveal and layoutCaptionPages() (the boxes the renderer draws)
  src/components/BeatLayer.tsx   one Sequence per beat, ordered by `layer`; parses props with the component's schema
  src/components/TopLogo.tsx     persistent top-center brand mark (props `topLogo`)
  src/components/LookOverlay.tsx vignette and seeded film grain over the footage, under every graphic (props `look`)
  src/components/registry.ts     component name -> defineBeat(schema, Component)
  src/components/beats/*.tsx     one file per beat component (default export + `schema`)
  src/components/ui/             shared primitives: Card, Tile, Pill, Kicker, Icon, AccentText, SafeArea, motion hooks
  src/lib/camera.ts              key sampling (cut, push, glide, creep, hold), kick offsets, edge clamp (never shows an edge)
  src/lib/captionPages.ts        page builder (createTikTokStyleCaptions tokens + scored page breaks) and page timing
  src/lib/rail.ts                progress rail events and state lookup
  PREVIEW.md                     render one beat over the real A-roll (still and short clip)
scripts/
  anchors.py                     time anchors: @word, @keyword, @cutBefore, @cutAfter, @end, @rel (and legacy @cut)
  plan_camera.py                 cues.json + shot config -> camera_plan.json (auto creep, peak speeds, kick checks)
  resolve_beatmap.py             beat map source (anchors, per-beat mode) -> beatmap.json with captionModes
  build_props.py                 cues + words + beatmap + camera plan -> props.json (validated)
  prepare_public.sh              copies the brand into <public-dir>/.reel-motion-brand/
  render.sh                      stills (one bundle for all) or a full render with the colour and codec flags
  stills.mjs                     the stills renderer used by render.sh --still
  caption_boxes.mjs              caption page boxes for reel-qa (render.sh --caption-boxes)
  brand-webpack.mjs              REEL_BRAND alias shared by remotion.config.ts and stills.mjs
  test_captions.sh               page-builder and page-timing unit test on a synthetic fixture
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

`prepare_public.sh <public-dir> [brand-dir]` copies `brand.json`, `fonts/` and `logos/` into `<public-dir>/.reel-motion-brand/` and touches nothing else. The folder carries a marker file; a folder of that name without the marker is never replaced. In components, load brand files with `brandAsset("logos/mailinfra-logo-white.svg")` or `brandLogo("white")` from `src/lib/brand.ts`, never with a hard-coded path. Logo keys come from the brand's `logos` (bundled brand: `white`, `onDark`, `color`, `iconWhite`).

## Workflow

1. Write a shot config (per reel, kept in the reel work folder):
   ```json
   {"clips": {"CLIP_B": {"states": [1.06, 1.14], "startState": 0, "ty": 0}},
    "shots": {"0": {"scale": 1.10, "ty": 40}},
    "moves": [{"t": {"@word": "example", "offset": -0.16}, "delta": 0.04, "ease": "push"},
              {"t": {"@word": "second example", "edge": "end"}, "scale": 1.15, "ease": "creep"},
              {"t": {"@word": "third"}, "ease": "hold"},
              {"t": {"@word": "fourth"}, "delta": 0.05, "ease": "glide", "frames": 18},
              {"t": {"@word": "burned"}, "ease": "kick"}]}
   ```
   The timeline is split into visual shots at `cues.cuts` and at any `cues.needs_punch` time (`[t, ...]` or `[{t}]`, or `"needs_punch": true` on a segment: a jump inside a take that a punch has to hide). `clips` keys match a substring of the shot's clip name. Every shot starts with a `cut` key; consecutive shots of the same clip alternate through `states`; `shots` overrides one shot by index. After the moves are applied, every cut whose scale is within `--min-cut-change` (0.03) of the scale before it is forced to the scale before it plus or minus `--punch-step` (0.06): the direction that keeps the next cut at least `--min-cut-change` away wins, then the one closer to the planned scale, and the shot's relative moves follow it. When more than half the cuts are forced, a warning says the clip states do not alternate enough. After the forced punches, every shot of 2 s or more with no push, glide or creep gets an automatic creep (see Auto creep), and the forced-punch rule runs again. Then `python -I scripts/plan_camera.py --cues cues.json --shots shots.json --out camera_plan.json` and read its output: one `speed:` line per move (see Peak speed) and the warnings (forced punches, edge clamps with the scale that would allow the requested offset, close pushes, close kicks, kicks without headroom, glides that cross a cut, moves over the speed limit).
2. Write a beat map source: `{"beats": [{id, component, mode, from, to, layer?, props, modeFrom?, modeTo?}], "accents": [...], "captions": {...}, "topLogo": {...}}` (`captions` and `topLogo` are optional, see Caption options and Top logo; `resolve_beatmap.py` and `build_props.py` pass them through). Any time, anywhere, may be an anchor resolved against `cues.json`; inside a beat's `props` it resolves beat-relative (see Time rule):
   - `{"@word": "phrase", "n": 1, "edge": "start"|"end", "offset": -0.1}`: the n-th occurrence of a word or phrase (punctuation and case ignored).
   - `{"@keyword": "authent", "n": 1}`: the n-th word starting with that stem (survives caption corrections such as plural or tense).
   - `{"@cutBefore": "phrase"}`: the last cut at or before the phrase starts (cuts up to 0.12 s after the word onset count, set `snap` to change).
   - `{"@cutAfter": "phrase"}`: the first cut at or after the phrase ends.
   - `{"@end": true}`: the A-roll end.
   - `{"@cut": 3}` is a positional index and breaks after a re-cut; it still resolves but prints a warning. Use `@cutBefore`/`@cutAfter`.
   - `{"@rel": <anchor or output seconds>}`: inside `beats[].props` only, the explicit beat-relative form (a bare anchor there means the same). `{"@rel": 9.5}` turns an absolute time into seconds from the beat's `from`.
   
   `python -I scripts/resolve_beatmap.py --cues cues.json --input beatmap.src.json --out beatmap.json --extra-sec 2.5` resolves the anchors and derives `captionModes` from each beat's `mode` (later beats win where they overlap, gaps are `talk`; `modeFrom`/`modeTo` narrow a beat's caption window). Window edges snap to the frame grid with the renderer's rounding, and a window under one frame is dropped with a warning (no zero-length `talk` slivers from float sums). `--extra-sec` is the end card length after the A-roll. Content anchors keep the map valid after a re-cut; a phrase that was cut out fails loudly.
3. `python -I scripts/build_props.py --cues cues.json --words words.out.json --beatmap beatmap.json --camera camera_plan.json --aroll <dir>/aroll.mp4 --public-dir <dir> --extra-sec 2.5 --out <dir>/props.json [--captions-config captions.json]`. The A-roll path must be inside the public dir; props store it relative to that dir. The A-roll stops at its own end; frames after it are black under the end card. It rejects a time inside `props` below -0.5 s or past the beat length (the old absolute-seconds habit), a `layer` outside -10 to 10, kick and glide parameters out of range, and invalid caption options; it writes `cameraLimits.maxScale` (the plan's `maxScale`, or `--max-scale`).
4. Stills first: `bash scripts/render.sh --props props.json --public-dir <dir> --still 0.0,1.0,7.3 --out <dir>/stills` (one bundle for all stills; `--still-frames 90,91,92` takes output frame numbers). Look at them.
5. Full pass: `bash scripts/render.sh --props props.json --public-dir <dir> --out <dir>/out/gfx.mp4`. `--concurrency` defaults to `$REEL_CONCURRENCY` or 2; on a shared machine set `REEL_RENDER_LOCK=/path/to/remotion.lock` and every render, still batch and caption-box run waits for `flock` on that file, so two Remotion jobs never overlap. When a parent process already holds that lock (a caller that wraps the command in `flock` on the same file), `render.sh` runs inside it instead of waiting on itself. It always passes `--muted --color-space=bt709 --crf=14 --x264-preset=medium --pixel-format=yuv420p`, records the A-roll md5 in `<out>.aroll.md5`, and fails if the A-roll changed during the render or the frame count differs from `round(durationSec * fps)`. Re-run steps 1 to 3 whenever `cues.json` or `words.out.json` change; a render from stale props drifts after the first changed cut.

6. Caption boxes for QA: `bash scripts/render.sh --props props.json --public-dir <dir> --caption-boxes --out <dir>/qa/captions_bbox.json`. It runs the `CaptionBoxes` composition, which builds and times the pages with the same code as `Captions`, measures every line with the loaded brand fonts and returns one box per page; nothing is rendered (a few seconds). Each page lists `start`/`end` (output seconds of its first and last visible frame, frames in `hidden` windows excluded), `bbox` `[x0, y0, x1, y1]` (widest line by the summed line heights at the page's caption height), `firstFrame`, `endFrame`, `visibleFrameCount`, `scale` and `centerY`. Pages hidden for their whole life are left out. Re-export it whenever `props.json` changes; `reel-qa` reads it from `qa/captions_bbox.json`.

The CLI symlinks the public dir into the bundle (no copy), so pointing `--public-dir` at the reel work folder is cheap.

## Top logo

`TopLogo` draws the brand mark persistently at top-center, above every beat (navy takeovers included) and below the captions. It is off unless the props enable it, so props without `topLogo` render as before. Props (`topLogo` in the beat map source or `props.json`, times in absolute output seconds, anchors allowed in the source):

```json
"topLogo": {
  "enabled": true,
  "logo": "white",
  "widthPx": 320,
  "centerY": 170,
  "ranges": [{"from": 0.24, "to": {"@end": true, "offset": 2.5}}],
  "hideDuring": ["EndCard"],
  "enterFrames": 8,
  "exitFrames": 5,
  "slidePx": 14,
  "shadow": 1,
  "scrim": 0.22
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | draw the layer at all |
| `logo` | `"white"` | brand logo key or asset path; always the white mark on footage and navy |
| `widthPx` | brand `layout.topLogo.widthPx` (320) | 280 to 400 |
| `centerY` | brand `layout.topLogo.centerY` (170) | vertical centre, y 120 to the brand's `layout.topLogo.centerYMax` (280). Instagram's top UI covers about y 0 to 210: 250 puts a 320 px wordmark at about y 225 to 275, inside the safe box; then keep top graphics at y 300 or lower (the rail at x 70 to 290 can stay at y 236 beside a centred mark) |
| `ranges` | `[]` (whole reel) | visible windows `{from, to}` in seconds; each one fades and slides in over `enterFrames` at `from` and fades out over `exitFrames` before `to` |
| `hideDuring` | `["EndCard"]` | component names whose beat windows are cut out of the ranges (the logo fades out before the beat starts and back in after it ends) |
| `slidePx` | 14 | downward slide of the entrance |
| `shadow` | 1 | strength of the soft dark drop shadow (0 to 1) |
| `scrim` | 0.22 | opacity of a soft dark radial glow behind the mark, so the white mark reads on bright walls (0 to switch off) |

The logo must be fully in by 1.0 s (`build_props.py` fails otherwise): start the first range at 0 to 0.68 s. `enterFrames: 0` with a range from 0 shows it fully on frame 0 (the feed thumbnail). Add `LogoPop` to `hideDuring` so the top mark fades out as the logo card pops instead of showing two logos. Keep the hook headline, progress rail and any other top graphic at y 236 or lower and look at stills where the hook, the rail and each takeover are on screen.

`LogoPop` (`card` `cream` or `navy`; the logo defaults to `color` on cream and `white` on navy) animates the icon first and the wordmark after it, split at the brand's `logoMark.iconSplit` (`markSplit: null` pops the whole mark at once). `EndCard` uses the `color` mark (default `logoWidthPx` 640); its `handoff` takes the pop's `card`, `widthPx` and `centerY`, and a navy pop card fades to cream while the white mark crossfades to the colour mark.

## Look overlay

`look` (beat map source or `props.json`, off unless set) draws a cinematic vignette and film grain above the camera and below every beat, the top logo and the captions. In framed layout it sits inside the window (see Framed layout), so the navy background and the window border stay clean.

```json
"look": {"vignette": 0.5, "grain": 0.35, "grainSizePx": 2, "seed": 0}
```

| Key | Default | Meaning |
|---|---|---|
| `vignette` | 0 | 0 to 1: radial darkening toward the edges, centred a little above the frame centre (the face). 0.5 darkens the bottom corners by about 10 % and leaves the face untouched |
| `grain` | 0 | 0 to 1: monochrome fractal noise blended with `overlay`, so the mean brightness does not move. 0.3 to 0.4 reads as film grain on a phone; above 0.6 it reads as noise |
| `grainSizePx` | 2 | grain cell size (the noise is drawn at 1/size resolution and scaled up) |
| `seed` | 0 | the noise seed is `seed + frame`: every frame has new grain and the same frame always renders the same grain (no `Math.random`) |

Both at 0 (or no `look`) render nothing. Keep it subtle: compare a still with and without at the face and at a bright wall corner; the face must not get darker.

## Camera keys

`{t, scale, tx, ty, ease}` in output seconds, applied at frame `round(t * fps)`:

- `cut`: hard change on that frame. One on every cut frame, always with a scale change.
- `push`: eased move to the target over 8 frames with `cubic-bezier(0.16,1,0.3,1)`, starting at `t`. The default emphasis move: +0.04 to +0.06, start 3 to 6 frames before the stressed word, at most one per 3 s, never on the same word as a caption accent pop or a card entrance.
- `glide`: symmetric smootherstep `u^3 (u (6u - 15) + 10)` to the target over `frames` (default 18, 12 to 24), centred on `t`: it starts `frames / 2` frames before `t`, so the peak speed lands on the word. Peak speed is 1.875 x distance / frames. Use it for a reframe that should read as a camera move rather than a punch (a slow reveal, a move toward a card); `push` stays the emphasis move. A glide that would start before its shot's cut is moved later with a warning.
- `creep`: slow ease-in-out from the current value to the target, spanning from `t` to the next key (or the end). Auto creep adds up to 0.06 per quiet shot (see below); a hand-written creep overrides it.
- `hold`: keeps the current value (ends a creep early without a visible change). Its scale/tx/ty are ignored by the renderer.
- `kick`: an impact shake on top of whatever the camera is doing. It does not change the state (its scale/tx/ty copy the current state and are ignored) and does not end a creep. See Kick.

Total scale is clamped to 1.00 to `cameraLimits.maxScale` (default 1.20, at most 1.30; above 1.20 the upscale softens, `plan_camera.py --max-scale` and `build_props.py` warn; check stills at 1.00/1.12/ceiling for each new camera body). Transform origin is the shot's face centre from `cues.json`; translation is clamped so the frame edge never shows: at scale `s` the largest downward `ty` is `(s - 1) * face.cy`. `plan_camera.py` warns when a key asks for more.

### Kick

`{"t": {"@word": "burned"}, "ease": "kick", "px": 4.5, "frames": 7, "rollDeg": 0.2, "angleDeg": 60}` (all but `t` and `ease` optional, defaults shown). On frame `n = frame - round(t * fps)`, for `n` in 0 to `frames - 1`, the signal is `s_n = (-1)^n (1 - n / frames)^1.5`: it flips sign every frame and is gone after `frames` frames. The renderer adds `px * s_n * (cos a, sin a)` to the translate and `rollDeg * s_n` degrees of roll, after the edge clamp, and raises the scale just enough that no edge shows (for a roll about the frame centre that is `cos r + (16/9) sin r`, plus the translate headroom; the renderer searches the exact smallest scale about the face origin), capped at `maxScale`; if even the cap is not enough, the kick amplitude shrinks instead. Measured on the mock fixture: offsets of +2.4/+3.9, -1.8/-3.1, +1.3/+2.4 ... px, matching the formula within 0.1 px, and no frame edge.

- Values: 4.5 px at 1080 wide, roll 0.1 to 0.35 degrees, 6 to 8 frames (kicks accept 2 to 12 frames everywhere: zod, `build_props.py` and `plan_camera.py`; glides 12 to 24). Stronger reads as a cheap sine wobble.
- At most one kick per 3 s, on the hit word (a stamp, a crack, a flatline), never inside a push: let the push stop on the hit. `plan_camera.py` warns on kicks under 3 s apart, kicks inside a push, and shots with under 6 px of edge headroom (at scale 1.00 the kick has to raise the scale by about 1 %, which reads as a small zoom pop: give the shot 1.04 or more).
- A graphic's own shake (`shakeOffset` in `ui/motion.ts`) uses the same alternating decay; do not stack it on a camera kick on the same frame (`DomainChips` `shakeFirstStamp` is off by default).

### Auto creep

`plan_camera.py --auto-creep 0.06` (default; `0` disables) adds a creep of up to 0.06 from one frame after the cut to the next cut across every shot of 2 s or more that has no push, glide or creep. The creep never ends within `--min-cut-change` of the next cut's scale, so it cannot force that cut. A full 0.06 that fits between 1.0 and the ceiling wins; between two full options the one moving away from the next cut's scale wins (up when the shot is the last one). When neither direction fits the full amount it takes the largest smaller change, and a shot with less than 0.02 of room gets no creep (a warning says so). The forced-punch rule then runs again; it finds nothing to force unless a hand-written move changed, and if it does force a cut the creeps are re-targeted. This is the floor that keeps a quiet shot or a held frame from reading as frozen; a plan with `--auto-creep 0` must pass the frozen check of `reel-qa` some other way.

### Peak speed

`plan_camera.py` prints one line per move: `speed: t=2.47 push +0.050 over 8 f: peak 31.8 px/frame at the corner`. The distance is `1101 x |scale change| + |translate change|` (1101 px is the half diagonal of 1080x1920, the frame corner), times the largest per-frame step of the move's ease. It warns above 37 px/frame (`--speed-limit`), the upper quartile of measured reference moves scaled to 1080 wide; a push of +0.06 is about 38, so keep emphasis pushes at +0.04 to +0.05 or use a glide. Kicks report `(px + 1101 x roll in radians) x` the largest frame-to-frame signal change (about 15 px/frame at the defaults). That figure leaves out the cover scale a kick needs on a shot with less than `px` of edge headroom (measured at scale 1.00: the scale rises about 0.009 on the first kick frame, about 10 px more at the corner, then decays over the kick); the headroom warning flags those kicks. The plan file keeps the rows under `speeds`.

## Layout grammar

Graphics never use the bottom 420 px or the right 130 px. Zones (`zones` in `theme.ts`, `SafeArea` in `ui/`):

| Zone | Box |
|---|---|
| safe | x 70 to 950, y 220 to 1500 |
| card | x 70 to 950, y 1150 to 1480 |
| headline | x 70 to 950, y 236 to 440 |
| rail | from the brand's `layout.rail` (x 70, y 236, three 64x10 segments) |
| takeoverBand | x 70 to 950, y 380 to 1060 (leaves y 1180 free for captions) |
| topLogo | x 70 to 950, y 120 to 220 (brand `layout.topLogo`): reserved for the persistent top logo, nothing else is drawn there |

| Mode | Speaker | Graphic zone | Captions |
|---|---|---|---|
| Talk | full frame | none (a small progress rail at most) | centre y 1180 |
| Card | full frame | card zone | centre y 1060 (above the card, below the chin) |
| Takeover | hidden, at most 1.5 s (2.5 s once, only to cover a defect) | full frame, navy gradient | y 1180 over a band the graphic leaves empty, or mode `hidden` when the graphic spells the same words |

`captionModes` drive the caption position; a page that overlaps any `card` window sits at the card height for its whole life (no mid-page jumps). `hidden` suppresses captions frame by frame. Mode windows are applied on frames with the same rounding as the beats (`round(from * fps)` to `round(to * fps)`), so a takeover or hidden beat and its caption mode start on the same frame. A page whose last word has finished never holds into a `takeover` or `hidden` window: its hold ends on the frame that window starts (a page still being spoken when a takeover starts stays, at y 1180).

## Captions

Details, caption options and accent styles live in `../reel-captions/SKILL.md`. In short:

- Pages come from scored breaks inside each phrase (a phrase ends at punctuation or a pause of 0.25 s). A page costs more when it ends on a function word (`a an the from to your and too of in with by`, other articles, prepositions, possessives, conjunctions, intensifiers) or a dangling subject or auxiliary, when it is a single word, or when it is shown for under 0.35 s; larger gaps after a page are rewarded. Max 3 words per page in the hook (before the first cut) and 4 after, enforced exactly; at most 2 lines of 22 characters.
- Accents: `"word"` (first occurrence), `{"text": "word", "n": 2}` (that occurrence) or `{"text": "word", "n": "all"}`. At most one accent per page, an accent phrase is never split across pages, and leading or trailing punctuation renders in the base style.
- Legibility: white Poppins and orange Lora both carry a tight dark shadow stack and a dark `paint-order` stroke, so accents read over skin and hands. Still run the contrast check of the captions skill.
- Across cuts: a page that would end 1 to 3 frames after a cut ends on the cut frame, so the old page never shows for a frame or two on the new shot.
- Caption options (`captions` in the beat map source, or `--captions-config`, stored as `props.captionOptions`): `hookMaxWords` 3, `bodyMinWords` 2, `bodyMaxWords` 4, `mergeAcrossPauseSec` 0.25, `accentStyle` `serif` | `serifHeavy` | `sansUnderline`, `localScrim` 0 to 0.4. The defaults give exactly today's pages and look.

## Motion tokens (`theme.ts`, hooks in `ui/motion.ts`)

- Entrances 8 frames, most travel in frames 1 to 5, `cubic-bezier(0.16,1,0.3,1)` (`useEntrance`, `entranceStyle`). `entranceProgress` samples one frame ahead, so a beat's local frame 0 already shows the first step of its entrance (opacity above 0) and nothing is ever empty on `from + 0`; `TopLogo` entrances do the same, and so do the hand-rolled entrance ramps (the `EnvelopeToSpam` cover and backdrop, the `TitleSlam` takeover fade with `cutIn: false`, the `Checklist` card and its first row in rail mode, the `EndCard` wipe, the `LogoPop` card, the `AuthTiles` slots). A component that ramps its own entrance from frame 0 samples `frame + 1` the same way. Exits 5 frames, ease-in (`useExit`, `exitStyle`, or `useEnterExit` for both).
- Stagger 3 frames between list items (`index` option, `staggerStart`).
- Nothing grows from zero: arrive from scale 1.15 or a 40 px offset.
- Overshoot only on stamps and icons: scale 1.4 to 1.0 over 6 frames, at most 6 % overshoot (`useStamp`, `stampStyle`). At most one visible spring per beat. `shakeOffset(frame, start, frames, amplitudePx)` for a graphic's own shake: the kick's alternating decay `(-1)^n (1 - n/frames)^1.5` along (1, -0.5).
- Text lands 0 to 2 frames before the word it illustrates.
- Hold every card at least 0.3 s per word + 0.5 s (`holdFramesFor`).

## Density rules

- One idea per beat, shown big, then gone. No permanent card stack.
- No cutaway or takeover in the first second; the face and the hook headline own frame 0.
- At least 2 s of face between takeovers. When two takeovers come too close, turn one into a card: `EcgFlatline` takes `card: true` (beat mode `card`), which draws the trace and label on a navy panel in the card zone (or its `band`) instead of a full-frame background; timing props are unchanged.
- No window over 4 s without a cut, scale change or graphic event.
- Card text at least 44 px, numerals at least 140 px.

## Never ship

- Counters such as "01/11", timecodes, "n/3" labels
- Invented numbers, prices or percentages (only figures in the brand's approved claims list)
- Text under 44 px on cards (36 px only for a mono code line)
- A colour flood between every beat; a logo bug in a corner; a watermark; any logo other than the brand's files
- Anything in the top logo zone (y 120 to 220) except `TopLogo`
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
- `frame` is the beat's local frame (0 at `beat.from`), `durationInFrames` its length. Times in props are beat-relative seconds (see Time rule); `toFrame(t)` converts one to a local frame on the output frame grid (`round((from + t) * fps) - round(from * fps)`, so an event lands on the same frame as the word it was anchored to).
- Build from `components/ui` (Card, Tile, Pill, Kicker, Icon, AccentText with `*accent*` markup, zones, motion hooks) and `theme.ts` tokens only. Colours carry fixed meanings: danger = mistake, success = fixed, accent = emphasis/active, brand blue = the brand itself.
- `ProgressRail` and `Checklist` share geometry (`railSegmentRect`, `checklistRowRect`) and rail events (`src/lib/rail.ts`: `{t, segment, state}` with states `empty`, `active`, `marked`, `fixed`), so the rail can persist across many beats and hand off to the checklist at `morphIntoChecklistAt`.
- `npx tsc -p .`, then render stills at the first frame (from + 0, must not be empty), the entry (from + 4 frames), mid and exit (to - 2 frames) and a short clip (see `remotion/PREVIEW.md`), and look at each: text size, zones, collisions with the face and captions, colour meanings.
- 3D inserts play through the generic `VideoInsert` beat; see `../reel-3d/SKILL.md`.

### Time rule

One rule for every beat: **times inside `beats[].props` are seconds relative to that beat's `from`**. Anchors there resolve beat-relative (`{"@rel": anchor}` is the explicit synonym, and `{"@rel": 9.5}` converts an absolute time); plain numbers are taken as already relative. Exceptions: everything under `props.three` (the 3D insert spec of `VideoInsert`) stays in absolute output seconds, and the top-level `topLogo` and `accents` stay absolute. `build_props.py` rejects a relative time (keys `t`, `at`, `*At`, `*Times`, `*Start`, `*End`) below -0.5 s or past the beat length. Rail state history (`events`, `railEvents` of `ProgressRail` and `Checklist`) may go further back than -0.5 s, because a checklist that takes over from the rail needs the rail's earlier events; it may not run past the beat end. In components call `toFrame(t)` for every time prop; never add `beat.from` yourself.

### Chaining and layers

- `chainIn` / `chainOut` (`Gauge`, `LineChart`): two card beats that follow each other on the same panel. `chainOut: true` on the first keeps its panel on screen at its end (only the content fades); `chainIn: true` on the second skips the panel arrival and only fades its content in. Set both sides, put the second beat's `from` on the first one's `to`, and the panel never blinks.
- `layer` (integer, default 0, -10 to 10): beats draw in ascending `layer`, list order within a layer. Give a persistent `ProgressRail` `"layer": 1` so it draws above takeovers that are listed after it, or a negative layer to sit under them.

## Verification

- Colour integrity check: render a props file with an empty camera, no beats and no captions, then compare the same frame with `signalstats` (YLOW, YHIGH, YAVG within 1 to 2 codes) and `psnr` against the A-roll (45 dB or more). A double range conversion shows as YLOW rising by about 10 codes.
- Caption timing: extract frames at a few word onsets; the word must be partly visible 1 frame before its onset and fully visible 3 frames after.
- Cut sync: frame-difference peaks of the render and the A-roll must fall on the same frame at every `cues.cuts` entry (camera `cut` keys use `round(t * fps)`, the same rounding as the cut frames).
- Throughput on an 8-core CPU: about 7 s startup plus 9 to 10 frames per second at concurrency 4 on an idle machine; peak RSS about 830 MB. The default is concurrency 2. A batch of stills costs one bundle (about 15 s) plus 1 to 2 s per still.
- Do not render while the A-roll is being rewritten: OffthreadVideo reads the file during the whole render. `render.sh` checks the md5 before and after.
