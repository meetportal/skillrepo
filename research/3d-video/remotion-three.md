# Remotion and three.js on a CPU-only machine

Measured before the [`reel-3d`](../../skills/reel-3d/SKILL.md) skill was built, with a small prototype (an extruded envelope, a variant with drei helpers and a colour-check composition). The skill's [determinism.md](../../skills/reel-3d/references/determinism.md) holds the rules as they ship and its kit (`src/kit/`) holds the code; this note keeps the measurements and the reasons.

Machine: 8 vCPU virtual machine, no GPU and no display, 31 GB RAM, Node 24, Remotion's Chrome headless shell 158. Every job ran under `nice -n 19 ionice -c 3` at `--concurrency=2`.

Sources read: the Remotion docs (`/docs/three`, `/docs/three-canvas`, `/docs/gl-options`, `/docs/videos/as-threejs-texture`), [remotion-dev/skills](https://github.com/remotion-dev/skills) notes on 3D, Lottie, transitions and render stability, the R3F Canvas API docs, the installed source of `@remotion/three`, `@react-three/fiber`, `@react-three/drei` and `three`, and the plugin templates (read as data).

## Working version set

All installed and rendered together; the skill pins the same versions exactly (`npm install --save-exact`).

| Package | Version | Note |
|---|---|---|
| remotion, @remotion/cli, @remotion/renderer, @remotion/three | 4.0.542 | `@remotion/three` peers: three >= 0.137, fiber >= 8 |
| react, react-dom | 19.3.1 | fiber 9.8.2 requires react >= 19 and < 19.4 |
| @react-three/fiber | 9.8.2 | latest stable (10.x was alpha only) |
| three, @types/three | 0.187.0 | fiber needs >= 0.156, drei >= 0.159 |
| @react-three/drei | 10.7.9 | optional; pulls troika-three-text 0.52.5 and three-stdlib 2.36.1 |
| typescript | 5.9.3 | strict `tsc -p .` clean |

Install took about 30 s. npm warns that esbuild's postinstall is not allow-listed; bundling still works. The Chrome shell can be shared with another Remotion project by symlinking `node_modules/.remotion` instead of downloading it again.

## GL backend matrix (headless)

| `--gl` | Result | WebGL renderer |
|---|---|---|
| `angle` | **FAIL**: "Initialization of all (2) EGL display types failed", then "Error creating WebGL context" | none |
| `egl` | FAIL, same context error | none |
| `swiftshader` | FAIL, same context error | none |
| `swangle` | OK | ANGLE on Vulkan 1.3 over SwiftShader (Chrome's bundled software renderer), WebGL2, MSAA 4 |
| `vulkan` | OK | ANGLE on the host Mesa llvmpipe, WebGL2, MSAA 4 |
| `angle-egl` | OK | ANGLE on the host Mesa llvmpipe (OpenGL ES 3.2), WebGL2, MSAA 4 |
| no flag | OK, byte-identical to `swangle` | Chrome's software fallback, with a deprecation warning |

**Decision: always pass `--gl=swangle` explicitly**, in the config (`Config.setChromiumOpenGlRenderer("swangle")`) and in every Node API call (`chromiumOptions: {gl: "swangle"}`), because `renderMedia` and `renderStill` ignore the config file. Reasons:

- `angle`, the docs' desktop recommendation and the plugin's setting, does not start without a GPU.
- `swangle` is bundled with Chrome, so its pixels do not depend on the host graphics stack; it is the documented choice for GPU-less machines.
- `vulkan` and `angle-egl` are about 1.5x faster but use the system Mesa, so pixels change with OS updates and differ from `swangle`.
- The no-flag default happens to match `swangle` today, but relies on a deprecated fallback.

## Timings

1080x1920, 30 fps, 60 frames, prebundled once (`npx remotion bundle`, 24 s). Fixed overhead per CLI job (browser launch, page load, first frame), measured with `--frames=0-0`: 2.7 to 3.0 s. Per frame = (total - one-frame job) / 59, the wall throughput with two tabs.

| Scene and variant | Backend | 60 frames | Per frame |
|---|---|---|---|
| Extruded rounded envelope with flap and seal, standard material, hemisphere + directional (2048 PCF shadow) + point light, MSAA, PNG sequence | swangle | 12.6 to 13.2 s | 0.17 s |
| same, h264 crf 16 | swangle | 11.4 to 11.7 s | 0.15 s |
| same, PNG sequence | vulkan | 9.1 to 9.4 s | 0.11 s |
| same, PNG sequence | angle-egl | 9.0 to 9.1 s | 0.10 s |
| antialias off | swangle | 10.8 s | 0.14 s |
| shadows off | swangle | 12.8 s | 0.17 s (the shadow pass is nearly free) |
| dpr 2 (2160x3840 buffer) | swangle | 29.9 s | 0.46 s (2.7x) |
| dpr 2 | vulkan | 21.0 s | 0.31 s |
| VSM shadows (radius 6, 16 blur samples) | swangle | 54.2 s | 0.87 s (5x) |
| VSM shadows | vulkan | 15.1 s | 0.21 s |
| drei variant: RoundedBox, clearcoat physical material, Environment from 3 Lightformers (`frames={1}`), ContactShadows 512, troika Text | swangle | 16.1 to 19.3 s (27.9 s cold font) | 0.23 to 0.28 s |
| one `remotion still` CLI call | swangle | 2.7 s wall; `renderStill()` alone 1.1 to 1.4 s | |

A 10 s 3D insert at 30 fps with the standard look costs about 45 to 55 s on `swangle` at concurrency 2. Keep VSM and dpr 2 out of software renders. The shipped beats measured 0.07 s per frame (880x330 cards) to 0.22 s per frame (full-frame takeovers); the table is in the skill.

These costs are why 3D lives in its own Remotion project: each insert renders once per beat to a short clip, cached by hash, and the 50 s reel render never loads three.js or software GL.

## Determinism

Checked by md5 of PNG frames.

- Same backend, two full runs: 60 of 60 frames identical for `swangle`, `vulkan` and `angle-egl`, and for the drei variant once its text was gated.
- `remotion still --frame=30` equals frame 30 of the full sequence byte for byte. Order and tab assignment do not matter, so QA stills are trustworthy.
- Across backends: `swangle` vs `vulkan` PSNR 55.9 dB (visually equal, not identical); `vulkan` vs `angle-egl` 93.9 dB. **Never compare hashes across backends; pin one per project.**

Breakers proven by a failing render:

| Breaker | What happened | Fix |
|---|---|---|
| drei `<Float>` | reads the wall clock; two stills of the same frame gave different hashes | animate from `useCurrentFrame()` only; avoid every clock-reading helper |
| camera set in `useEffect` | the first frame each tab renders shows the frame-0 framing and every later frame lags one frame, because `<ThreeCanvas>` draws in its own effect, which runs before sibling effects | set the camera during render or in `useLayoutEffect` (the skill's `CameraRig.tsx`) |
| troika `<Text>` (drei) | glyphs are built in a worker after the font loads, and the canvas is not redrawn (`frameloop` is `never` while rendering, `invalidate()` does nothing): text missing in every still and on frames 0 and 1 at concurrency 2 | hold a `delayRender` handle created in `useLayoutEffect`; on `onSync`, call `advance(performance.now())` and then `continueRender` (the skill's `SyncedText.tsx`); text then on all 60 frames and still = sequence |
| `delayRender` in a `useState` initializer of a component that can suspend | the suspended render is thrown away and the handle leaks: a 28 s timeout | create the handle in `useLayoutEffect` |

## Visual quality

- **Antialiasing**: R3F's default `antialias: true` gives MSAA x4 on every working backend; the thin flap line stays clean. Off: clear stair steps on rounded corners. dpr 2 is smoother still but costs 2.7x.
- **Shadows** in three 0.187: `PCFSoftShadowMap` was removed. R3F's `shadows` or `shadows="soft"` still asks for it and three falls back with a warning. Use `shadows="percentage"` (PCF) or `"variance"` (VSM).
  - PCF is a 5-tap rotated disk; deterministic, but the penumbra is a visible stipple fixed to screen pixels. Fine for small contact shadows.
  - VSM gives a smooth penumbra but costs 5x on `swangle`.
  - Best value: PCF for self-shadowing plus drei `<ContactShadows>` for the ground (smooth, deterministic, cheap).
- **Brand colour**: R3F's default ACES Filmic tone mapping shifts colours even on unlit materials: `#2f5bff` rendered as `#3b5de3`; with `<ThreeCanvas flat>` it is exact; with Neutral tone mapping `#2452f0`. For brand-exact elements use `flat` on the canvas or `toneMapped={false}` on that material. Lit materials always shade, so judge brand colour on flat areas (the skill checks a flat patch per brand token: 0 codes off in PNG, at most 1 after a ProRes 4444 round trip).
- **Framing in 9:16**: `fov` is vertical, so horizontal coverage is only 0.5625 of it. A 3.2-unit object needs the camera about 15 to 20 units away at fov 32 to fill 60 to 70 % of the width. A first attempt at 7 to 11 units filled the frame.

## Rules every composition follows

1. All 3D inside `<ThreeCanvas width height>` from `@remotion/three`. While rendering it forces `frameloop="never"`, holds a `delayRender` until the canvas exists, and per frame calls `advance(performance.now())`. Suspense inside it (loaders, fonts) is covered by its own loader.
2. Every moving value from `useCurrentFrame()` (plus `interpolate`, `Easing`, `spring`). No `useFrame` animation, no `state.clock`, no unseeded `Math.random()`, no CSS animation.
3. Imperative objects (camera, matrices, uniforms) mutated during render or in `useLayoutEffect`, never in `useEffect`.
4. Anything that finishes asynchronously after mount holds a `delayRender` and calls `advance(performance.now())` before `continueRender`; `invalidate()` is not enough while rendering.
5. `<Sequence>` inside the canvas needs `layout="none"`. `ThreeCanvas` accepts Sequence props itself since 4.0.528.
6. `dpr` set explicitly. R3F's default `[1, 2]` follows `window.devicePixelRatio`, which Remotion sets from `--scale`, so the buffer silently changes with scale; and R3F clamps to at least 1, so a half-scale preview still renders a full-size buffer.
7. Each canvas dimension at or under 4096 px (Chromium WebGL limit). dpr 2 at 1080x1920 = 2160x3840 works.
8. Geometries and materials made in `useMemo` are disposed in a cleanup; long software renders leak otherwise.
9. No drei helpers that read the clock or the network: `Float`, `Sparkles`, `Stars`, `Cloud`, `MeshWobbleMaterial`, `MeshDistortMaterial`, `CameraShake`, `Trail`, `useAnimations` (drive the mixer with `mixer.setTime(frame / fps)` instead), any `*Controls`, `Bounds`, `Environment preset` (downloads HDRs at render time). Verified safe: `RoundedBox`, `Environment` with `Lightformer` children and `frames={1}`, `ContactShadows`, `Text` with the gate. Clock-free in source but not tested: `Center`, `Text3D` with a local font JSON, `useGLTF` from `staticFile`, `MeshReflectorMaterial`. `Html` positions DOM from `useFrame`: use a Remotion overlay above the canvas instead.
10. Lottie and `@remotion/transitions` work at DOM level: a 3D canvas sits inside a transition sequence like any scene.
11. Post-processing works in this model, but every pass is a full-screen software draw; the skill uses none.

## Gotchas

- Harmless with fiber 9.8.2 and three 0.187: "THREE.Clock: This module has been deprecated".
- "GPU stall due to ReadPixels" on llvmpipe backends: harmless.
- The CLI with `--log=verbose` does not forward a page `console.log`, only warnings: use `console.warn` for diagnostics, or the Node API with `onBrowserLog`.
- Remotion writes a silent audio track unless muted (`setMuted(true)`); mux with explicit `-map`.
- Every bundle copies `public/` into the temp folder: keep large assets out of the 3D project's `public/`, or bundle once and render from the bundle folder.
- For an NLE or OpenTimelineIO export, anything drawn by `@remotion/three` must be flattened to a clip first.
- Inserts are rendered opaque (ProRes 4444, full frame on the navy backdrop, or at card size on a navy panel). `<ThreeCanvas>` defaults to `alpha: true`, so transparent overlays are possible (`--image-format=png --pixel-format=yuva444p10le`), but alpha output was not tested and is out of scope.

## Pipeline shape that came out of it

```
beatmap.json + props.json
  -> reel-3d/scripts/render3d.py   one Remotion bundle, one ProRes 4444 clip per 3D beat (3d/<beat>.mov + .json with events), cached by hash
  -> reel-motion VideoInsert beat  plays the clip under the captions, opaque on its first frame
  -> reel-sound                    places whoosh / impact / pop on the events in 3d/<beat>.json
  -> reel-qa frames gate           3D windows must never freeze for 12+ frames or go uniform
```

Commands, flags and the measured cost per shipped beat: [`reel-3d/SKILL.md`](../../skills/reel-3d/SKILL.md).
