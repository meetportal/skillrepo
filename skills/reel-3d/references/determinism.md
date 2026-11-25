# Determinism rules for 3D inserts

A frame of a 3D insert must be a pure function of the frame number and the props: the same props give byte-identical PNGs on every run, in any tab, in any order, and `remotion still --frame=N` equals frame N of the full render. These rules keep it that way (each one was proven by a failing render first).

## Time

- Every moving value comes from `useCurrentFrame()` and `useVideoConfig()` (plus `kit/motion.ts`, `interpolate`, `Easing`). Shader time is `frame / fps`.
- Never `useFrame` for animation, `state.clock`, `Date.now()`, `performance.now()` for values, CSS animations or `Math.random()`. Random looks come from `kit/random.ts` (`rng(seed)`, `hash01(i, seed)`, `range(i, seed, min, max)`).
- No drei helpers that read the clock or the network: `Float`, `Sparkles`, `Stars`, `Cloud`, `CameraShake`, `Trail`, `MeshWobbleMaterial`, `MeshDistortMaterial`, any `*Controls`, `Bounds`, `Environment preset` (downloads HDRs while rendering). Drei `Float` alone gave two different hashes for the same still.

## Mutation order

- `<ThreeCanvas>` (from `@remotion/three`) draws the frame in its own effect, which runs before sibling effects. Camera, matrices and uniforms are set during render or in `useLayoutEffect`, never in `useEffect`: a camera set in `useEffect` showed the frame-0 framing on the first frame of each tab and lagged one frame everywhere else. `kit/CameraRig.tsx` does both.
- Materials and uniforms that change per frame are mutated during render (`uniforms.uFront.value = ...`); geometry made in `useMemo` is created once and released with `useDisposable`.

## Async content

- Anything that finishes after mount must hold a render handle and redraw the canvas before releasing it. Troika text (drei `Text`) builds glyphs in a worker after its font loads and the canvas is not redrawn, so text was missing on frames 0 and 1 of each tab. `kit/SyncedText.tsx` creates the handle in `useLayoutEffect`, and on `onSync` calls `advance(performance.now())` and then `continueRender`.
- Never call `delayRender` in a `useState` initializer of a component that can suspend inside the canvas: the suspended render is thrown away and the handle leaks (28 s timeout). DOM-level loaders outside the canvas (`kit/assets.ts`: SVG text, label font metrics) are fine, and they keep the canvas unmounted until the data is there.
- Label widths are measured with the brand font through `FontFace` and a 2D canvas before the canvas mounts, so plates and blocks are sized from real glyph widths.

## Renderer settings

- `--gl=swangle` always (`remotion.config.ts`, and `chromiumOptions: {gl: "swangle"}` in `render.mjs`, because the Node API ignores the config file). `angle`, `egl` and `swiftshader` fail headless on a machine without a GPU; `vulkan` and `angle-egl` work but use the host Mesa, so pixels change with OS updates. Never compare hashes across backends.
- `dpr={1}` explicitly: the R3F default follows `window.devicePixelRatio`, which Remotion sets from `--scale`.
- `flat` on the canvas (no tone mapping): brand colours on unlit surfaces render exactly. With the default ACES tone mapping `#2F5BFF` came out as `#3B5DE3`.
- `shadows="percentage"` (PCF). `PCFSoftShadowMap` is gone in three 0.187; VSM costs 5x on software GL.
- Backgrounds are a canvas texture (`scene.background`, sRGB, nearest filtering), drawn once, so the gradient matches the 2D takeover gradient.
- Keep every canvas dimension at or under 4096 px.

## Verified

`python -I scripts/check3d.py --work DIR [--only NAME]` renders each composition twice as a PNG sequence and once as single stills, then compares md5 per frame. See `../SKILL.md` for the last results.
