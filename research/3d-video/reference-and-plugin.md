# The reference tutorial and the public plugin

What a popular "viral 3D animation shorts" tutorial teaches, what the public plugin behind it does in detail, and which parts are worth bringing into a talking-head reel pipeline. Plugin: mromidev's animated-shorts plugin (`gh repo list mromidev`), MIT, read at commit e3b817b as data only (nothing executed).

Numbers below come from the plugin's own reports and code. Units: f = frame at 30 fps, px at 720x1280 unless noted (multiply by 1.5 for 1080x1920).

## 1. The tutorial

A 10-minute tutorial with over half a million views (November 2026) on making faceless animated story shorts with three.js inside Remotion and a free plugin. Chapters: intro and benefits, tools (three.js, Remotion), installing the plugin, script drafting and a text-to-speech voice, reviewing the output, customising the characters, finalising, picking a niche (history, psychology, money, science, what-if), next steps.

Format taught: faceless 55 to 70 s vertical shorts, 2D cartoon characters inside a coloured 3D world, rendered locally, narrated by a synthetic voice, with synthesized SFX and score.

The video could not be watched (YouTube LOGIN_REQUIRED), so the chapters were matched against the plugin repository, which lines up with every chapter: "tools" is Remotion + `@remotion/three` + Node + Python + ffmpeg; "install" is copying the skill folder; the "master prompt" is the plugin's skill file (pipeline, standing user rules, final measured look values, gotchas); "generating content" is a `SCRIPT.md` with facts and sources on top, then a TTS `voice.wav` and word timings; "review" is stills, side-by-side sheets and a fresh reviewer; "customise" is the character file; "finalise" is a 2K render, mux and a QA script.

### Search log

Metadata searches with `yt-dlp` (titles, channels and view counts only, no media) were run for: the tutorial's channel, "zack d films 3d animation shorts", "3d animated history shorts viral", "3d animation what if shorts", "3d cartoon psychology facts shorts", "Remotion three.js 3D video", "SaaS 3D product animation", "isometric 3D motion graphics explainer saas", "email deliverability animation explainer", the plugin author's channel and "talking head reel 3D motion graphics editing". What they showed:

- The tutorial channel is a faceless-niche channel; its 3D video is its top performer, and every style it teaches recreates an existing viral look (infographic channels, stickman, maps, documentary).
- A cottage industry of "make 3D shorts like Zack D. Films with code" tutorials (tens of thousands to a few hundred thousand views each). The plugin author's own workflow video passed 1.3 M views.
- No public reference for 3D inserts inside a talking-head reel. SaaS 3D videos are agency product ads (After Effects, Blender); deliverability explainers are flat 2D. So the 3D budget for talking heads had to be derived (see [styles-and-when-3d.md](styles-and-when-3d.md)), not copied.

## 2. Pipeline shape

1. Topic and facts: one surprising true story with a visible cause and effect plus one everyday analogy; facts with sources at the top of the script file.
2. Script at about 3.7 words/s, 55 to 70 s (formula in section 7).
3. Voice and word timings, hand-fixed. Everything is timed to the word file.
4. A shot plan file: shots (id, start and end frames, light, crowd mode, story-time mapping), crossfade frames at place or time changes, a flash frame, camera keys `{f, dur?, cut?, s: f => {pos, look, fov, roll}}`, kicks, a depth-of-field table, foreground props. Every reaction lands 0 to 3 f before its word.
5. World, characters, post-processing in separate files.
6. Sound from an event table that mirrors the shot plan; synthesized SFX and an original score; `mix.wav` at the exact length; stems; a cue sheet. Rule: lock picture timing before sound, and any timing change re-runs sound.
7. Look checks: stills, side-by-side sheets against the reference, a fresh reviewer.
8. Final: render at `--scale 1.3333` (1440x2560), mux with explicit maps, frame QA, fix, deep audit.

The skill file's structure is worth copying: a short list of standing user rules on top (language, voice tone, mix standard, export size, "save after every step"), then the pipeline, then the **final measured values that won** (with per-area scores after 4 review rounds), then gotchas and "readability traps the reviewer caught". It records outcomes, not intentions. The reel skills now end with "Values that won" and "Traps caught" sections for the same reason.

### Look-match loop (its strongest process idea)

1. **Measure the reference first.** One analysis pass per topic (motion, depth, textures, characters, lighting, outlines, grade), each writing numbers to a report from a shared brief: goal, material, stack versions, tools allowed, deliverable = tables + a recipe for our stack + top 5 by visual impact + a summary under 200 words. The reports are the source of truth for every later step.
2. **One owner per file.** Sandboxed copies of the project per area (camera, world, materials, characters, post), each with its own Remotion entry for stills.
3. **Merge by owned files**: back up main, copy only owned files, type-check, re-sync every sandbox.
4. **Verify with a fresh reviewer**: side-by-side sheets, a score out of 10 per area plus a numbered fix list with frame numbers, each fix routed to the owner of that file. Scores went from 5/3/4/5/4/7/4/6 to 7/5-6/5-6/6/5-6/7/6-7/6-7 over 4 rounds.
5. **Contracts are exported constants**; changing one means telling every reader.

Also: they measured their own camera from the code with the same statistics as the reference, without rendering.

Where it went: the brief template and "measure references in numbers" are in [`craft-research`](../../skills/craft-research/SKILL.md) (`measure_reference.py`); per-area scores and side-by-side sheets in [`reel-qa`](../../skills/reel-qa/SKILL.md); one owner per file and the style bible in [`reel-director`](../../skills/reel-director/SKILL.md).

## 3. Determinism and renderability

- Every frame is a pure function of (shot id, frame): the world is posed from `useCurrentFrame()`, never from the R3F clock or `Math.random`.
- Seeded randomness: a sine hash `frac(sin(i * 127.1 + s * 311.7) * 43758.5453)` reproduced bit-exact in Python so sound events match picture; a Park-Miller generator per texture key; a seeded numpy generator for audio.
- Assets load under `delayRender` / `continueRender` with a per-file `.catch`, so a missing prop never hangs the render.
- Canvas textures cached by key; character drawings pooled by quantised parameters so identical poses share one canvas. Drawing resolution in tiers by distance.
- The sun is frozen per shot and camera-relative, so light does not swim during moves.
- **Every pixel-sized post parameter is specified at 1080x1920 and multiplied by `height / 1920`** in the shader, so half-scale stills, 1080 and 1440 finals match. R3F clamps dpr to at least 1, so a small-stills prop forces a smaller buffer.
- No temporal noise: fixed sampling patterns; grain (off by default) is a hash seeded by the frame number.
- A/B switches for stills through input props (`{post: {ink: false, lens: false}}`).
- Crossfades are two stacked `ThreeCanvas` layers with DOM opacity; a white flash is a DOM layer with opacities `[1, .75, .45, .2]` over 4 f.
- Canvas settings: `antialias: false`, an effect composer with `multisampling={4}`, near 0.2 / far 1500, 4096 shadow maps with a per-frame shadow-camera fit.
- Stills: one bundle, then `renderStill` per frame with `chromiumOptions {gl: "angle"}`. That backend failed headless on a no-GPU machine (see [remotion-three.md](remotion-three.md)).
- Gotchas they hit: each `bundle()` copied `public/` (about 1.3 GB) into the temp folder and never deleted it (60+ GB, disk full); Remotion writes a silent audio track (mux with explicit maps); scratch `.ts` files under `out/` break the type check; film grain at 2.5 % made the file 910 MB instead of about 250 MB and turns to mush after upload.
- Fragility: one shader string-patches a three.js shader chunk and throws if the chunk changes, so three must be pinned exactly. Their stack: Remotion 4.0.290, three 0.175, @react-three/fiber 9.1.2, @react-three/postprocessing 3.0.4, postprocessing 6.37.2.

## 4. Camera grammar (measured on 20 reference shorts, 32,337 frames)

- 65 % of frames move, 10 % hold (under 0.3 px/f), no hand-held float (residual 0.08 px). 6.0 moves per 10 s.
- Move peak median 13.7 px/f (p75 24.6). Attack about 10 f, release about 10 f, 62 % symmetric, about 23 f total. A typical move is about 101 px with 23 % zoom.
- Their first version used quartic ease-out bursts (peak in frame 1, up to 115 px/f with a 3 f attack): the biggest "cheap" tell. The "ease-out burst" in their own style notes was a measurement artefact (integer phase correlation cannot see under 4 px/f).
- The fix: **glide** = smootherstep `u^3 (u (6u - 15) + 10)` over 18 to 40 f. Peak speed = 1.875 x distance / duration, so `duration >= 0.075 x distance` (720p px) keeps peaks at or under 25 px/f. Reframes bigger than about half a frame width or 40 % zoom become hard cuts. Glides are centred on the word: the key starts `dur / 2` early so peak speed (and the whoosh) lands on the word.
- **Holds push in**: 0.0015 to 0.0035 per frame (0.15 to 0.35 %/f), an emphasis punch of 0.006 for about 35 f with 8 f soft edges, the push stops at an impact. Reference quiet-frame push median 0.14 %/f, p75 0.34; push-in runs median 35 f, +22 %.
- **Rolls** 3.6 degrees median over 18 f on emphasis keys; dutch tilt on about 2 % of frames.
- **Impact kick**: the image offset flips sign every frame, about 3 px at 720p per unit, decay `(1 - n/7)^1.5` over 7 f, roll +-0.23 degrees per unit, gains 0.5 to 1.6. It replaced a sine wobble (6.4 Hz over 15 f) that read 2 to 5 times too strong.
- Whip pans only with blur: 45 to 93 px/f, 2 to 3 f ramps, a 12-tap directional blur.
- Composition rules: head top at 0.28 of height (close-up) to 0.50 (wide); camera height about 0.79 x character height; fov 34 to 46; a blurred foreground object in about a third of medium and close shots.
- Character timing: animated on ones, no idle loops, expression swaps instant and 0 to 3 f before the word, blinks every 0.5 to 2.3 s, extras frozen except on cue.

Where it went: `kick`, `glide`, auto creep and a peak-speed report are in [`reel-motion`](../../skills/reel-motion/SKILL.md) (`plan_camera.py`), and the 3D kit's `motion.ts` in [`reel-3d`](../../skills/reel-3d/SKILL.md). For talking-head punch-ins our 8-frame ease-out push stayed the default: the plugin's finding was about 3D world moves, and punch-ins are an accepted idiom; change it only after measuring talking-head references.

## 5. Look techniques (studied, not adopted)

These need a depth buffer and a world, which an A-roll does not have. Kept here because the methods are portable.

- **Lens blur**: thin-lens circle of confusion `cInf x |1 - focus / depth|` (x1.2 in front of focus, max 24 px at 1080), two passes (16-tap pre-blur, 64-tap Vogel disc plus a 32-tap near-field gather), occlusion-aware and renormalised. Depth of field on about a third of screen time, never a focus pull inside a shot. Postprocessing's stock depth-of-field effect failed (max disc radius of a few px, grainy).
- **Ink outlines**: a screen-space depth and normal edge pass on a world-only re-render; depth term is the signed second difference of 1/z (exactly 0 on planes), crease at a 35 to 50 degree normal angle; width 5.1 px at 6 m down to 3.3 px at 90 m at 1080x1920; runs before the blur. Reference: about 74 % of geometry edges carry a line, about 3 px wide, ink about 2 to 2.6 % of pixels.
- **Two-tone shading** replacing diffuse lighting via `onBeforeCompile`; coloured shadows (violet-blue under warm light), never pure black (darks at L* 16 to 22: navy `#262c51`, aubergine `#2e2439`, plum `#3d2530`); no SSAO; specular only on metal.
- **Tone-map inversion**: iterate a JS copy of the tone mapper so self-lit things land on an exact on-screen hex. Unlit materials for signs, because side-lit painted text went grey.
- **Bloom** only on HDR emissives (threshold 1.0, intensity 0.5); white faces never glow.
- **Grade**: a display-referred 7-knot monotone cubic tone curve plus zone saturation, zone tint and a vignette, fitted to reference quantiles with smoothness and tint caps (an unregularised fit produced a magenta shadow). Lesson: "a grade fixes curve, blacks, saturation, cast and vignette; it cannot fix albedo, shadow colour or missing hues: fix those at the source."

What we did take: lifted coloured darks (never pure black), one meaning colour per rim light, bloom only on true emissives (in the end no bloom at all on software GL), no grain, brand colour on unlit or tone-map-exempt surfaces.

## 6. QA tooling

- **Frame QA script**: ffprobe specs; EBU R128 loudness; `silencedetect n=-45dB d=0.3`; decodes the whole video once at 180x320 rgb24 into numpy; per frame: luma mean, std, p2, p98, saturation (masked where max channel < 0.06) and frame difference. Flags: **pops** (diff > 3 x local median over +-8 f, + 1.0, outside planned events), **black** (mean luma < 0.04), **unplanned white** (> 0.93), **frozen spans** (diff < 0.02 for 12+ f); per-shot colour medians; 2 s contact sheets (10 x 6 thumbs at 108x192) with frame numbers.
- A shot parser that lists planned cuts, crossfades, the flash and kick windows so QA ignores intentional events.
- **Side-by-side sheet**: our row above the reference row at equal height, white gutters. Used every review round.
- Reviewer contract: fresh reviewer, 1 to 3 images, under 200 words, a score per area out of 10, numbered fixes with frame numbers mapped to file owners.
- Measurement methods named in the reports: camera similarity fit from 9-tile sub-pixel phase correlation at 360x640, with the caption band (55 to 86 % of height) masked, outlier tiles rejected, path smoothed (sigma 1.2 f); classes hold < 0.3 / drift < 2 / move >= 2 px/f. Edge-spread blur fit. Blink detection from eye-strip dark pixels.

Where it went: [`reel-qa`](../../skills/reel-qa/SKILL.md) `framecheck.py` (the `frames` gate), the `silence` gate and `sbs_sheet.py`, adapted with a NOTICE. Our frozen threshold is 0.25 mean grey difference, not 0.02: calibrated on talking-head reels and creeping holds (see [build-log.md](build-log.md)). Planned events come from the beat map, camera plan, caption pages, 3D event files and mix dropouts.

## 7. Sound

- Everything synthesized in numpy/scipy: Butterworth filters, coloured noise, spectral shaping, modal resonators, a synthetic reverb, and its own BS.1770 meter with 4x true peak.
- An SFX cue returns `(signal, anchor)`: where the sound's moment sits inside the file, so it is placed at `t - anchor`.
- **Levels by loudness, not peak**: each event's gain puts its max momentary loudness (400 ms) at a target in LU relative to the voice's integrated loudness. Measured in their final mix: impacts -6 to -11 LU, whooshes -17 to -18, a crowd cheer -12, ambience beds -19 to -30 integrated.
- Distance model for on-screen sources: gain `-14 log10(d / 3.5)` dB, low-pass `17000 x (3.5 / d)^0.55` Hz.
- **Whoosh generator**: coloured noise through a Gaussian band (width in octaves) whose centre sweeps low to high up to the peak, envelope `(t / peak)^2.2` then `exp(-(t - peak) / tail)`, plus a little high-passed air. Presets: camera move 0.6 s, peak 0.09 s, 330 to 2000 Hz, 0.8 octave, tail 0.18 s, air 0.15; transition 0.8 s, peak 0.32 s, 300 to 1600 Hz; a reverse swell 500 to 4200 Hz on the flash.
- Score composed to picture at 120 bpm; the strongest moment is a **dead stop**: music silent through a key line, then a warm return.
- **Duck keyed from word timings, not the audio**: speech spans merged across gaps under 0.3 s, opened 80 ms early and held 120 ms after, one-pole attack 70 ms and release 450 ms at a 1 kHz control rate. Music per section at a set LU under the voice (9.5 to 12). **Rides**: 2 to 4 dB dips under quiet sentence-final words. Master: -15 LUFS, a look-ahead limiter to -1.2 dBTP, LRA 2.6.
- Report: every event (time, frame, target LU, applied LU, measured), a per-section table and the **speech p10 margin** over 400 ms windows centred on words: a single number for "is any word buried".

Where it went: [`reel-sound`](../../skills/reel-sound/SKILL.md): `--duck-mode words` (default) with rides and dropouts, `sfx_cues.py --level-mode lu`, `sfx_synth.py` (generated licence-free kit, whoosh adapted with a NOTICE), per-beat margins and a cue sheet. Our master stays at -14 LUFS for the platforms.

## 8. Style bible, script and retention numbers

- Format on 20 shorts: 31 to 78 s (median about 60), voice starts at frame 1 to 4, no intro, logo, outro or CTA, the video ends on the last word. One narrator at 3.5 to 4.1 words/s (median 3.7); total word gaps over 0.25 s under 1 s per video. -14 LUFS, LRA about 2.4, bed 5 to 10 dB under speech. Captions one word at a time, white bold sans with a thin outline, hard swaps.
- **Script formula** (20 of 20): hook = a paradox stated as fact in sentence 1, no setup, 10 to 16 words; setting in 1 to 2 lines with concrete details; 3 to 6 escalation beats; one mystery beat; a pivot ("You see," in 14 of 20) into an everyday analogy; an ironic payoff in the last 1 to 2 sentences. Sentences median about 13.5 words, contractions, jargon explained in the next clause.
- Picture: every sentence illustrated literally; props carry the joke; lighting changes with the story beat; inserts and top-down cutaways on about 22 % of frames.
- Editing: hard cuts rare (0 or 1 in 12 of 20 videos), 4-frame white flash cuts, 6 to 8 f crossfades on place changes, continuous moves that follow an object. The example short: 15 shots in 67.5 s, about 36 camera keys, so a camera event every 1.9 s; the hook is a flash-forward of the climax ending on a white flash.

Where it went: the script brief for speakers in [`reel-director`](../../skills/reel-director/references/script-brief.md), marked as untested (A/B before it becomes a rule), and the visual-event density target (median gap 1.5 to 2.5 s) in `beat_audit.py` and `beat_sheet.py`.

## 9. Readability traps (general rules)

- A prop that reads as something else gets redesigned, not explained.
- Anything closer than about 2 m to the lens becomes a cut-off blob: a foreground element must be recognisable or gone.
- Check symbols and colour pairs for unintended reads (flags, political colours).
- Text on lit surfaces loses contrast: text and logos go on unlit, tone-map-exempt materials.
- Lines crossing torsos at chest height: move the lens.
- Flat holds read as freezes in QA (12+ frames): every hold creeps.

## 10. What transfers to a talking-head reel, ranked

1. **Whole-reel frame analysis** with planned events: pops, black, white, frozen, silence, full contact sheets.
2. **Side-by-side sheets and per-area scores** out of 10, logged per pass.
3. **Camera grammar**: impact kick (replacing a 2-frame shake), glide as an option next to the push, a peak-speed report (flag over about 37 px/f at 1080 at the frame corner, radius 1101 px), a higher creep floor (ours read as held at +0.03 per shot; the reference pushes 0.14 %/f on quiet frames), visual event density as a WARN.
4. **Sound**: LU-relative SFX levels, a procedural whoosh fallback, the word-keyed duck, rides and planned dropouts, a per-beat margin table, a cue sheet.
5. **Measure references in numbers** before building.
6. **Script craft** for hook variants and shoot feedback, cold-open flash-forward as an option to test.
7. **3D inserts** for short takeovers only, rendered once per beat to an intermediate clip.
8. **Process**: "values that won" and "traps caught" in every skill, one owner per file, A/B switches in props for stills, no film grain.

## 11. What does not fit

- The cartoon cast, the 3D town, painted textures, physics: a talking-head reel has a real speaker.
- Lens blur, fog, aerial perspective, sun rigs: they need a depth buffer and a world.
- A composed score and 200+ SFX per minute: talking-head reels use licensed beds and 15 to 30 visible-event SFX.
- "No captions" and "no CTA": reels are watched sound-off and end on a CTA and an end card. One-word captions: keep 3 to 4 word pages, maybe A/B the hook.
- -15 LUFS / -1.2 dBTP (platforms want -14 / -1.5 here).
- Frame constants mirrored by hand between picture and sound code: word anchors resolved from the transcript are strictly better.
- GPU-heavy post (4096 shadows, 112-tap blur, 2K at about 4 fps on a GPU): on software GL only short 3D beats are realistic.
- Shipping another channel's frames in a public repo: never. Reference material stays in private work folders.

## 12. Licence

MIT. Any code copied or adapted needs a `NOTICE` in the receiving skill with the plugin's copyright line and the MIT permission text; `reel-qa` and `reel-sound` carry one, and their `NOTICE` files hold the exact wording. Numbers and ideas (rates, thresholds, recipes) carry no obligation. No reference frames, sheets or report crops are copied.
