# Toolchain survey: skills and tools for programmatic reel editing

A survey of agent skills, MCP servers, renderers and open-source tools for editing vertical talking-head reels from the command line, what the best repos teach, and the toolchain chosen for the skills in this repo, with reasons.

Surveyed 2026-11-24 with `gh search repos` (25+ queries), `gh search code --filename SKILL.md` for technique-level hits (`silencedetect`, `arnndn`, `auto-editor`), `gh repo view` for metadata and web search for licence facts. 14 repos were shallow-cloned into an untrusted folder and read, not executed. Stars, dates and licences change: re-check before borrowing. The maintained short list is [`craft-research/references/sources.md`](../../skills/craft-research/references/sources.md); this file keeps the long form and the reasons.

Some repo names contain a vendor product name; those are referred to by owner with a `gh repo list <owner>` pointer instead.

## 1. Short answer

1. **Read as references, borrow patterns, rewrite in your own words and code:**
   - [browser-use/video-use](https://github.com/browser-use/video-use) (31.5k stars, MIT): the best editor mindset. Its hard rules, packed-transcript reading view, EDL format, self-eval loop and parallel animation brief are the backbone.
   - [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) (3.1k, MIT): the best short-form talking-head craft: measured reel pacing, caption rules, the cut-silences then cut-mistakes split, quality gates, and a "lessons that cost us time" list.
   - hassancs91's YouTube editor skills (392, MIT, `gh repo list hassancs91`): the best cut-engineering and audio lessons: A/V drift causes, transcript timing lies, envelope snapping, a second ASR pass on the render, diagnose noise before denoising.
   - [remotion-dev/skills](https://github.com/remotion-dev/skills) (7.9k, no licence file, official) and [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok): the canonical Remotion caption and timeline patterns.
   - [Tejashmakwana/motionmaxxing](https://github.com/Tejashmakwana/motionmaxxing) (1.8k, Apache-2.0): the best anti-slop checklist for motion graphics and measured motion timing laws.
   - [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics) (1.5k, MIT): graphics timed to a talking head's words with density rules, and a measured SFX pass with a CC0 kit.
2. **Toolchain:** ffmpeg for everything on the raw media (rotation, cuts, denoise, loudness, grade, encode); faster-whisper for word timestamps with VAD and envelope snapping; a custom transcript-driven cutter (auto-editor only as a cross-check); Remotion for captions and motion graphics over a pre-cut, comp-native base video. Reasons in section 6.
3. **Denoise:** in this survey `highpass=80` then `arnndn` (model `sh` or `cb`, `mix` 0.8 to 0.9) measured best; DeepFilterNet is the upgrade for hard noise; `afftdn` needs `nf` from a measured floor. Later testing in [`voice-clean`](../../skills/voice-clean/SKILL.md) changed the default (section 3).
4. **Licence flags:** Remotion is free only for individuals and companies of up to 3 people (company licence otherwise; at the time a "Creators" tier at $25 per seat per month, check [remotion.dev/license](https://www.remotion.dev/docs/license/pricing.md)). `appariciojunior/video-editor-skills` is CC BY-NC 4.0: ideas only, never text or code in anything commercial. `remotion-dev/skills` has no licence file: reference it, do not vendor it.

## 2. Environment the choices were made on

A Linux machine with **8 CPUs, about 32 GB RAM, no GPU**.

**ffmpeg 6.1** (a distribution build with libzimg, librubberband, libvidstab, libass, libfreetype, ladspa, lv2, libx264, libx265, libsvtav1):

| Feature | Note |
|---|---|
| `arnndn` | needs an external `.rnnn` model file ([richardpl/arnndn-models](https://github.com/richardpl/arnndn-models): bd, cb, lq, mp, sh, std; no stated licence) |
| `afftdn` | FFT denoiser; set `nf` to the measured noise floor |
| `anlmdn` | non-local-means denoiser; strong, artefact risk |
| `loudnorm` | EBU R128; two-pass with the measured JSON |
| `deesser`, `zscale` (libzimg, for correct range and matrix conversion) | present |
| `libx264`, `libx265`, `libsvtav1`, `prores_ks` (ProRes 4444 for alpha overlays) | present; hardware encoders are compiled in but have nothing to run on without a GPU |
| also useful | `dynaudnorm`, `speechnorm`, `acompressor`, `agate`, `equalizer`, `silencedetect`, `silenceremove`, `rubberband`, `ass`, `subtitles`, `drawtext`, `xfade`, `zoompan`, `vidstabdetect`/`vidstabtransform`, `lut3d`, `minterpolate`, `unsharp` |

**Python:** faster-whisper 1.2 with ctranslate2 4.9 ships `silero_vad_v6.onnx`, so VAD works without torch. auto-editor 29.3 (its `--version` hung for 2 minutes; use `auto-editor info FILE` and `--preview`). noisereduce, librosa, opencv, numpy, soundfile. Not installed and not needed: torch, whisperX, stable-ts, moviepy, pyloudnorm, mediapipe.

**Node 24.** Remotion 4.0.546 was the latest at the time. Only DejaVu and Liberation fonts were installed system-wide: Inter, Montserrat or Poppins have to be downloaded (Google Fonts, OFL) and asserted loaded before rendering, or renders fall back silently.

Material facts that shaped the pipeline (one sample reel, five single-line takes):

- Several transcripts started their first word at exactly 0.00 s, a Whisper artefact. Real onsets must be snapped with VAD or the RMS envelope before cutting.
- One raw take measured -17.4 LUFS integrated, LRA 3.2 LU, noise floor about -52.8 dBFS RMS against speech about -22.0 dBFS RMS (SNR about 31 dB): a clean close-mic recording that needs light treatment, not heavy isolation.
- The footage was landscape-encoded with the subject rotated 90 degrees and no rotation tag: rotate with `transpose` before anything else.

## 3. Denoise A/B (measured, not listened)

12 s of one raw take, mono 48 kHz. "Noise" = 0.2 to 1.5 s (before the first word), "speech" = 2 to 8 s. Every chain starts with `highpass=f=80`.

| Chain | Noise RMS (dBFS) | Speech RMS (dBFS) | Noise drop | Speech change |
|---|---|---|---|---|
| raw | -52.8 | -22.0 | | |
| `arnndn=m=sh.rnnn:mix=0.85` | -65.9 | -22.3 | 13.1 dB | -0.26 dB |
| `arnndn=m=cb.rnnn:mix=0.85` | -65.0 | -22.1 | 12.2 dB | -0.12 dB |
| `afftdn=nr=12:nf=-50:tn=1` | -53.9 | -22.0 | 1.1 dB | 0 |
| `anlmdn=s=7:p=0.002:r=0.006` | -76.3 | -22.1 | 23.5 dB | -0.04 dB |

Reading: arnndn looked like the safe default. afftdn did almost nothing because `nf=-50` sat above the real floor (-53); it must be set from the measured floor. anlmdn removes the most but is known to smear consonants and sound underwater at strong settings; it cannot be judged without listening.

What changed after this (see [`voice-clean`](../../skills/voice-clean/SKILL.md) and its [denoisers reference](../../skills/voice-clean/references/denoisers.md)): noise RMS alone is the wrong pass criterion. Compression later in the chain lifts room tone once the mix is normalised, so the real gate is "the background is not louder relative to the voice than in the raw cut", judged at matched loudness. On a quiet room that favours no denoiser plus a soft downward expander; for harder noise DeepFilterNet with a 10 dB attenuation limit measured the smallest rise in musical noise; `arnndn` stays for handling rustle; `afftdn` tracking mode (`tn=1`) is avoided.

## 4. Candidate survey

Stars and last push from `gh` on 2026-11-24. Quality is a judgment after reading.

### 4.1 Agent skills for editing footage

| Repo | Stars | Last push | Licence | What it does | Quality / relevance |
|---|---|---|---|---|---|
| [browser-use/video-use](https://github.com/browser-use/video-use) | 31.5k | 2026-10-08 | MIT | Conversational editor skill: transcribe, packed transcript, EDL, per-segment grade, overlays, burned subtitles, loudnorm, self-eval. Python + ffmpeg helpers. Vendors a Manim skill | **High.** Best editor mindset and hard rules. Uses a cloud ASR by default and calls local CPU Whisper too slow; for 1 min reels it is not |
| [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) | 3.1k | 2026-10-14 | MIT (+ third-party notices) | 15 skills: short-form-edit, cut-silences, cut-mistakes, edit-video, video-storytelling, HyperFrames. Measured house reel style | **High.** Best reel craft and quality gates. Built on HyperFrames and paid cloud services |
| hassancs91's YouTube editor skills (`gh repo list hassancs91`) | 392 | 2026-11-05 | MIT | clean-cut, clean-audio, make-tsx (Remotion), suggest-sfx, thumbnail, packaging | **High** on engineering lessons |
| AgriciDaniel's shorts clipper (`gh repo list AgriciDaniel`) | 499 | 2026-07-11 | MIT | Long-to-short clipper: faster-whisper, segment scoring, boundary snapping, Remotion captions, platform export presets | **Medium.** Clipping-focused; caption presets and the platform encode table are useful |
| [appariciojunior/video-editor-skills](https://github.com/appariciojunior/video-editor-skills) | 484 | 2026-10-23 | CC BY-NC 4.0 | DaVinci Resolve first-pass editor: rough cut, pacing, captions, B-roll, voice, music | **Medium.** Good learnings file. Non-commercial: ideas only |
| [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics) | 1.5k | 2026-10-13 | MIT | motion-broll (graphics timed to talking-head words), object separation, explainers, sound-effects (CC0 kit + measured mix) | **High** for B-roll density and the SFX pass |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | 6.1k | 2026-11-24 | Unlicense | Silence and motion cutter CLI, ships its own agent skills | **Medium.** Excellent tool, wrong primitive for scripted reels (6.2). Good for preview and NLE export |
| [snow-shen/snowcut](https://github.com/snow-shen/snowcut) | 2 | 2026-11-06 | other | Talking head: transcribe, cut gaps, browser preview, render | Low (tiny) |
| [MakeMyClip/editor](https://github.com/MakeMyClip/editor) | 30 | 2026 | ? | MCP editor: silence and repeated-take removal with whisper.cpp | Not read |
| [Viprasol-Tech](https://github.com/Viprasol-Tech) video editing skills | 43 | 2026 | ? | 95 skills for Reels and Shorts | Not read; breadth over depth |
| [kmilo93sd/agent-video-editor](https://github.com/kmilo93sd/agent-video-editor) | 10 | 2026 | ? | Editing judgment + 128 CC0 sounds, 26 CC0 graphics | Possible CC0 asset source; not read |

### 4.2 Motion-graphics skills and renderers

| Repo | Stars | Last push | Licence | What | Notes |
|---|---|---|---|---|---|
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | 75.4k | 2026-11-24 | Remotion License | React video framework | free for companies of up to 3 people, else paid |
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | 7.9k | 2026-11-23 | none | Official agent skills: best practices, captions, markup (silence detection, video editing, text highlights, SFX, transitions), render, studio | authoritative API patterns; Remotion also publishes the same skills as an editor plugin |
| [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok) | 308 | 2026-11-23 | none | TikTok captions with whisper.cpp + `createTikTokStyleCaptions` | read its `Page.tsx` for the active-word pattern |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 89.3k | 2026-11-24 | Apache-2.0 | HTML + GSAP compositions rendered to video; CLI lint, validate, render; media skills | strong renderer; its media skill pushes a vendor sign-in and sends a usage beacon, so use the renderer only, locally. Reported slow (23 min for a 15 s brief in one benchmark) |
| [Tejashmakwana/motionmaxxing](https://github.com/Tejashmakwana/motionmaxxing) | 1.8k | 2026-10-06 | Apache-2.0 | Anti-slop motion direction, measured timing laws, scripted gates | built for standalone promo films, not overlays on footage |
| [charlie947/motion-graphics-skills](https://github.com/charlie947/motion-graphics-skills) | 797 | 2026-10-11 | MIT | 13 skills incl. reel-export, brand intake, motion effects | reel-export has a clean upload-safe ffmpeg recipe |
| [nexu-io/html-video](https://github.com/nexu-io/html-video) | 4.9k | 2026-11-17 | Apache-2.0 | HTML to MP4 with pluggable engines | alternative to HyperFrames; not read |
| digitalsamba's video toolkit (`gh repo list digitalsamba`) | 2.7k | 2026-11-23 | MIT | Broad toolkit: Remotion, ffmpeg, moviepy, TTS, music generation, cloud GPU | breadth, generic ffmpeg recipes; low marginal value |
| [Liamrjohnston/remotion-motion-graphics-skill](https://github.com/Liamrjohnston/remotion-motion-graphics-skill) | 176 | 2026-07-24 | MIT | Remotion motion graphics | not read |
| [social-media-skills/remotion-shorts-skill](https://github.com/social-media-skills/remotion-shorts-skill) | 26 | 2026-11-11 | MIT | Kinetic-text shorts | not read |
| [jincheng2026/jc-remotion-skills](https://github.com/jincheng2026/jc-remotion-skills) | 18 | 2026-08-22 | other | Chinese talking-head workflow: rough cut + SRT in, motion packaging, SFX, mastering out | closest workflow shape; small, Chinese-language |

### 4.3 Curated lists

| Where | Stars | Notes |
|---|---|---|
| zhuyansen's curated list of video skills (`gh repo list zhuyansen`) | 2.7k, CC0 | about 540 repos, security-graded, categorised (editing 67, shorts 72). Best index for the next survey. Its own benchmark note: an agent with no skill made a film that passed every check in 4.4 minutes, so a skill earns its place with a look, a workflow or footage to edit |
| wilwaldon's video toolkit index (`gh repo list wilwaldon`) | 127 | index of video skills and MCP servers |
| general "awesome skills" lists (`gh search repos "awesome skills" --sort stars`) | 16k to 80k | general; few video entries |

### 4.4 MCP servers

| Repo | Stars | Last push | Licence | Notes |
|---|---|---|---|---|
| [samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) | 4.3k | 2026-11-24 | MIT | needs Resolve Studio; not useful headless |
| [KyaniteLabs/kinocut](https://github.com/KyaniteLabs/kinocut) | 280 | 2026-11-24 | Apache-2.0 | guardrailed ffmpeg + HyperFrames MCP |
| [video-creator/ffmpeg-mcp](https://github.com/video-creator/ffmpeg-mcp) | 156 | 2026-05-20 | MIT | thin ffmpeg wrapper |
| [egoist/ffmpeg-mcp](https://github.com/egoist/ffmpeg-mcp) | 122 | 2025-03-29 | none | stale |
| [pireel/pireel](https://github.com/pireel/pireel) | 1.5k | 2026-11-18 | AGPL-3.0 | full editor with MCP, Premiere and Resolve export; AGPL |

Verdict: none adds capability over a shell with ffmpeg. Skip MCP; write skills with scripts.

### 4.5 Underlying tools

| Tool | Stars | Licence | Role |
|---|---|---|---|
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 27k | MIT | ASR with word timestamps, int8 CPU, built-in Silero VAD |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | 25.6k | BSD-2 | faster-whisper + wav2vec2 forced alignment; needs torch |
| [jianfch/stable-ts](https://github.com/jianfch/stable-ts) | 2.3k | MIT | timestamp stabilisation, alignment to a known script |
| [linto-ai/whisper-timestamped](https://github.com/linto-ai/whisper-timestamped) | 2.9k | AGPL-3.0 | word timestamps + confidence; AGPL |
| [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | 5.1k | MIT or Apache-2.0 | speech enhancement; prebuilt `deep-filter` CPU binary, 48 kHz WAV only |
| [richardpl/arnndn-models](https://github.com/richardpl/arnndn-models) | 54 | none stated | RNNoise models for `arnndn` |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | 6.1k | Unlicense | silence cutting, NLE export |
| [Zulko/moviepy](https://github.com/Zulko/moviepy) | 15.2k | MIT | Python compositing; not recommended (6.1) |

## 5. What the deep-read repos teach

### 5.1 video-use

- **Hard rules** (worth adopting, in your own words):
  1. Subtitles are the last layer, after every overlay.
  2. Short audio fades at every segment boundary to kill pops (they use 30 ms `afade`; [`reel-cut`](../../skills/reel-cut/SKILL.md) later replaced this with a 16 ms equal-power crossfade, because a fade pair leaves a hole under room tone).
  3. Overlays shifted with `setpts=PTS-STARTPTS+T/TB` so frame 0 lands at the window start.
  4. Output-timeline caption times: `out = word.start - seg.start + seg.offset`.
  5. Never cut inside a word; snap every edge to a word boundary; pad 30 to 200 ms (for example 50 ms before the first word, 80 ms after the last).
  6. Word-level verbatim ASR only, never SRT or phrase mode (phrase mode loses gap data; normalised fillers lose editorial signal).
  7. Cache transcripts per source; never re-transcribe unchanged media.
  8. Parallel workers for animations, one file each.
- **Packed transcript:** one markdown line per phrase, broken on silences of 0.5 s or more, prefixed `[start-end]`. About a tenth of the tokens of raw JSON and enough to pick cuts. Shipped as `reel-director/scripts/packed_transcript.py`.
- **Cut craft:** silences of 400 ms or more are clean cut targets; 150 to 400 ms usable with a visual check; under 150 ms unsafe.
- **EDL JSON** with `sources`, `ranges[{source,start,end,beat,quote,reason}]`, `grade`, `overlays[{file,start_in_output,duration}]`, `subtitles`, `total_duration_s`.
- **Self-eval loop** (at most 3 passes): filmstrip and waveform at every cut on the render; check for flashes, waveform spikes, captions hidden behind overlays, wrong overlay frames; `ebur128` loudness and true peak; a critic told to "roast, not praise".
- **Animation rules:** start a reveal `reveal_duration` before the spoken payoff word so it lands on the word; never linear easing; hold the final frame 1 s or more; never reveal two independent elements at once; centre typing text on the full string width; fonts fail silently, so assert `document.fonts.check(...)` before rendering.
- **Sound:** fewer SFX (about 8 in 18 s reads as designed, 20 as stock); measure each effect's attack and start it early so the transient hits the frame; duck music 12 to 15 dB under speech; master once with two-pass loudnorm (-14 LUFS, TP at most -1 dBTP).
- **Disagree with:** "never run Whisper locally on CPU" (fine for 1 min reels with large-v3 int8) and "extract per segment then `-c copy` concat" (measured to drift, 5.3).

### 5.2 herk-edit-kit

- **Pipeline as stages:** cut-silences (deterministic, transcript-driven), then cut-mistakes (review-gated: stutters, retakes, false starts), then graphics. Each stage writes an EDL and a **re-timed transcript**, so downstream timing never has to be recomputed.
- **cut-silences defaults:** trim pauses over 0.55 s; keep a breath of 0.24 s for pauses of 2 s or more, 0.20 s after sentence enders, 0.14 s otherwise; head pad 0.22 s, tail pad 0.34 s; render with `trim`/`atrim` + `concat` in one filtergraph.
- **Measured reel pacing (27 top reels):** speech starts within 0.1 s; pauses between phrases under 0.2 s, natural beats after a comma or "First," 0.2 to 0.4 s; median inter-word gap 0.04 s; 4.0 to 4.7 words/s; shots average 1.1 to 1.4 s, none over 2.8 s; first cut at 0.6 to 1.0 s on the first charged word; each list item gets its own shot. Never speed the voice up.
- **Cut between phrases, never inside one.** A filler that runs straight into the next word stays, because cutting it clips the neighbours. A version with fewer cuts that ran 5 s longer sounded better.
- **Transcripts end words 40 to 80 ms before the consonant dies:** cut only after the word decays.
- **Captions:** 1 to 3 words split on phrase boundaries, appearing 2 frames before the word; ExtraBold caps about 62 to 64 px; colour on 25 to 45 % of chunks by meaning (red = loss, teal = concept, green = payoff); one boxed style per reel; never white on light (measure the pixels behind); never over the mouth or chin, especially in the first second.
- **Safe region** 1080x1920: x 90 to 930, y 200 to 1600.
- **Audio:** bed about 11 dB under the voice (9 to 14), ducked under speech; SFX only on visible actions, soft taps, clicks, paper and air, no lasers or plops; vary files for repeated items; master near -14 LUFS, TP at most -1.5 dBTP; measure the final encoded file on the stereo delivery; never fade the last word.
- **First 3 seconds gate:** "is someone convinced they need to watch until the end?" Build three different openings from the same truthful speech, compare, record why one won.
- **Verification:** lip sync by matching cut frames against the raw; frame strips 10 frames either side of every cut; contrast behind captions; fresh ASR on the final; the first 2.5 s frame by frame; an honest statement of what could not be checked (no listening).
- **Feedback loop:** every owner note becomes a rule. **Brand assets:** never redraw a logo; use the official asset with its source and checksum.

### 5.3 hassancs91's YouTube editor skills

- **A/V drift, measured:** per-segment AAC + `concat -c copy` drifts 15 to 20 ms per cut; MP4 segments cut mid-frame gain a padding frame that accumulates. Fixes: one sample-exact audio stream; concat video through MPEG-TS; always gate on `v:0 duration == a:0 duration`. For a 1 min reel the simplest fix is a **single-pass `filter_complex` trim/atrim/concat**, which has no per-file padding at all.
- **The transcript lies about time:** late token starts clip onsets, inflated tokens hide seconds of silence, merged repeats hide doublings, phantom tokens have no audio. Detect kept words over 1.0 s long, or with over 0.35 s of leading or trailing silence; cross-check against the RMS envelope.
- **Snap-to-audio tails:** walk forward after the last word until RMS falls to the clip's 10th-percentile floor plus a margin; the head must exceed the speaker's onset ramp (0.18 s on their speaker). Tight values: `internal_gap 0.4, min_tail 0.14, max_tail 0.4, head 0.11 to 0.17, soft_gap 1.2, soft_max_tail 0.6`.
- **Spoken slates:** search for "another take", "one more time", "cut that" and handle them first. **Doubled phrases: cut the first one.**
- **Second ASR pass on the render:** extra words = ghost fragments that rode along; missing words = clipped.
- **Pick the denoiser by noise type:** stationary (hiss, fan, room) suits RNNoise; dynamic broadband (water, wind, traffic) needs ML isolation. Diagnose with `astats`, `ebur128`, SNR in gaps and a `showspectrumpic` spectrogram. Preserve levels by RMS matching, not LUFS, after denoising (integrated LUFS drops when noise goes). Offer a faint ambience bed if isolation sounds vacuum-sealed.
- **Remotion input:** transcode footage comp-native (target size and fps, 8-bit H.264) before `OffthreadVideo`, or decoder starvation duplicates frames and stutters.

### 5.4 Remotion official skills and the TikTok template

- Captions as JSON in the `Caption` type `{text, startMs, endMs, timestampMs, confidence}`, with a leading space on each word's text.
- `createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds})`: 1200 ms default; 200 ms means one word at a time. Pages render inside `<Sequence from durationInFrames>`; the active token is `fromMs <= t < toMs`.
- Template look: 120 px max font fitted with `fitText` to 90 % width, white with a 20 px black `WebkitTextStroke` and `paintOrder: stroke`, bottom 350 px, enter spring scale 0.8 to 1 and translateY 50 to 0.
- Keep each clip's video and its captions under one `Sequence` (or `TransitionSeries.Sequence`), with `trimBefore`, `durationInFrames` and `playbackRate` on that parent.
- Adaptive silence detection: run `loudnorm=print_format=json` and use `input_thresh` as the `silencedetect` noise threshold. Cheap, and better than a fixed -30 dB.
- `@remotion/rough-notation` for hand-drawn highlights, circles and underlines driven by `interpolate(frame, ...)`.
- They advise rendering only when asked and previewing in Studio; an unattended pipeline renders drafts itself.

### 5.5 motionmaxxing

- **Never-ship list** that applies to overlays on a talking head: page chrome (corner labels, "01 / 03" counters, progress bars, timecodes), deck layouts, generic web-card UI with invented numbers, invented stats, slogan copy ("Not just X. It's Y.", "Unlock", "the future of"), colour floods or circle wipes between every beat, a pinned pill in the same spot across three shots, a web-footer ending held over 1.4 s.
- **Measured motion laws:** most travel in the first 4 to 8 frames then a long tail, no bounce; median move about 10 frames at 30 fps (0.33 s); at most one visible spring per film; arrivals decelerate from oversize, nothing grows from zero; almost nothing fades; cut on motion, not rest; words land 0 to 2 frames before they are heard; whole words 2 to 12 frames apart.
- **Gates computed by script, not self-certified:** the render exists and moves, no more than 3 consecutive flat frames, end hold at most 1.4 s, one hero per frame, no page chrome; a note quoting the numbers.
- Caveat: in a "3 mistakes" reel the numbers are the content. Use them as large content type tied to the spoken words, not as HUD chrome.

### 5.6 Barty-Bart motion-graphics

- **B-roll density:** light 2 to 4 cutaways per minute, medium 4 to 7, heavy most lines. No cutaway in the first second of the hook or on personal or opinion lines; at least 2 s of face between cutaways; a cutaway lasts the length of the idea (3 to 10 s); one change per spoken beat, 0.4 to 1.2 s apart; a state change lands on its word (`clip-local time = word time - clip in-point`).
- **Plan table before code:** `# | In-Out | line covered | what the shape does on which words | treatment | why`.
- **Never invent numbers, quotes, prices or results;** use relative bars or transcript labels.
- **sound-effects:** never synthesise SFX in code (this repo's [`reel-sound`](../../skills/reel-sound/SKILL.md) does generate a kit, adapted from an MIT-licensed generator and credited in its NOTICE); a bundled CC0 kit (whoosh, click, pop, riser, impact, tick); mix to -16 LUFS with true peaks under -4 dBFS measured on the exported MP4 (this repo masters to -14 LUFS / -1.5 dBTP instead); hand a human 5 timestamps to check on headphones; write `CREDITS.txt`.

### 5.7 Smaller takeaways

- AgriciDaniel's clipper, caption presets: Bold (Montserrat 800, 72 px, caps, 2 to 3 words, 800 ms window, active word #FFD700, pop spring damping 12 / stiffness 200), Clean (Inter 700, 56 px, 3 to 5 words, 1500 ms). Bottom 350 px. faster-whisper `large-v3`, `int8` on CPU, `word_timestamps=True`, `vad_filter=True`.
- appariciojunior (ideas only): cut from words, not volume (volume-only gave 800 pieces, the transcript cut 120); punch in only on jump cuts, and a punch-in lasts one line; normalising a silent clip boosted hiss by 30 dB; captions are for reading, so fix grammar, keep the voice, and read every cue after filler filters; re-render under a new filename to avoid stale cached frames.
- charlie947 reel-export: `scale=out_color_matrix=bt709:out_range=tv,format=yuv420p`, `-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709`, `-movflags +faststart`; an ffprobe gate on codec, size, pix_fmt, range and colourspace; logos on their own dark tile; text out of the bottom 500 px and right 120 px.

## 6. Chosen toolchain, with reasons

### 6.1 Motion graphics and captions: Remotion; ffmpeg for the base; HyperFrames not needed

| Option | Verdict | Why |
|---|---|---|
| **Remotion 4** | **Use** | Official caption primitives (`createTikTokStyleCaptions`, `fitText`, rough-notation); React components reuse across reels as a brand kit; spring and easing at sub-pixel precision; CPU render of a 60 s 1080x1920 comp takes about 3 minutes ([motion-benchmark.md](motion-benchmark.md)). Licence: check the company headcount |
| HyperFrames (HTML + GSAP) | Optional | Excellent and Apache-2.0, but a second framework adds nothing missing; its media skills nudge toward a vendor sign-in and telemetry; reported slow. Keep as a reference for caption-group exit guarantees and style tables |
| ffmpeg only (`drawtext`, `ass`) | Base only | Perfect for rotation, cuts, audio, grade, encode. ASS karaoke captions work, but animation and typography are far below Remotion |
| MoviePy | Skip | Slow per-frame Python compositing, weak text; nothing ffmpeg + Remotion do not do better |
| PIL + PNG sequence + ffmpeg | Niche | Fine for a one-off card, not for a reusable brand system |

**Architecture:** ffmpeg builds the A-roll (rotated, cut, graded, 1080x1920, **CFR at the source frame rate**, 8-bit H.264) and the clean audio, plus the EDL and re-timed words. Remotion composes `OffthreadVideo(aroll)` + camera moves + graphics + captions (captions last) at the same frame rate, rendered muted. ffmpeg then mixes, muxes and does the delivery encode. Rendering at the source rate avoids conversion judder; Instagram and TikTok accept 25 fps. Shipped across [`reel-cut`](../../skills/reel-cut/SKILL.md), [`reel-motion`](../../skills/reel-motion/SKILL.md), [`reel-sound`](../../skills/reel-sound/SKILL.md) and [`reel-export`](../../skills/reel-export/SKILL.md).

### 6.2 Silence and mistake cuts: a custom transcript-driven cutter

- Scripted reels need cuts **between phrases at word boundaries**, retake selection and natural breaths. auto-editor's model is loud versus quiet per timebase: it over-fragments (800 versus 120 pieces in one measurement) and cannot tell a retake from a keeper.
- The cutter takes word JSON and writes keep ranges: never cut inside a word; trim pauses over about 0.35 to 0.55 s down to a breath (0.14 s mid-phrase, 0.20 s after a sentence end, up to 0.30 s after a list marker); head pad at least the speaker's measured onset ramp; tail by envelope decay (0.08 to 0.4 s); a short crossfade at every join.
- A word-time correction pass first: VAD (faster-whisper's bundled Silero ONNX) plus an RMS envelope (librosa) to fix 0.00 s starts, inflated tokens and phantoms.
- Render every cut in **one** `filter_complex` (`trim`, `setpts`, `atrim`, `asetpts`, `concat`), not per-segment files plus `-c copy`. With 15 to 30 joins it is fast and drift-free. Gate on equal stream durations.
- auto-editor `--edit audio:threshold=-NdB --preview` only as an energy sanity check.

Shipped as [`reel-ingest`](../../skills/reel-ingest/SKILL.md) (transcribe, snap, align) and [`reel-cut`](../../skills/reel-cut/SKILL.md) (`plan_cuts.py`, `render_aroll.py`, `drift_gate.py`, `splice_check.py`), with the tightened values listed in [editing-craft.md](editing-craft.md) section 3.

### 6.3 Voice chain

The chain proposed at survey time, on the cut audio at 48 kHz:

```
highpass=f=80,
arnndn=m=<models>/sh.rnnn:mix=0.85,
equalizer=f=250:t=q:w=1.2:g=-2,
equalizer=f=3500:t=q:w=1:g=2,
deesser=i=0.4,
acompressor=threshold=-20dB:ratio=3:attack=10:release=120:makeup=2,
alimiter=limit=0.89
```

then two-pass `loudnorm=I=-14:TP=-1.5:LRA=7` on the **final mix**, verified with `ebur128=peak=true` on the delivered MP4. Reasons at the time: arnndn measured -13 dB on the floor with negligible speech change, is native to ffmpeg and deterministic, and `mix` under 1.0 keeps some room tone so cuts do not sound vacuum-sealed. EQ values are starting points to verify per speaker with a spectrum. Nobody listening means every audio decision has to be reported as numbers plus timestamps for a human check.

Superseded by the presets in [`voice-clean`](../../skills/voice-clean/SKILL.md) (section 3 above explains why).

### 6.4 Word timestamps: faster-whisper large-v3 + VAD + envelope snapping

- faster-whisper `large-v3`, `compute_type=int8`, `word_timestamps=True`, `vad_filter=True`, `language="en"`, with an `initial_prompt` or `hotwords` list of brand and technical terms so they are spelled right.
- WhisperX forced alignment would tighten word edges but needs torch (a large install); envelope snapping gets most of the benefit for cut decisions. [`reel-ingest`](../../skills/reel-ingest/SKILL.md) later added a forced-alignment step (`align_words.py`).
- Captions use a **corrected text** layer on top of ASR timing; never change timestamps when cleaning text.
- After the final render, transcribe the delivered audio again and diff it against the intended words (missing = clipped, extra = ghost).

### 6.5 Delivery encode

```
-c:v libx264 -preset slow -crf 18 -profile:v high -level 4.2 -pix_fmt yuv420p
-vf "...,scale=out_color_matrix=bt709:out_range=tv"
-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709
-c:a aac -b:a 192k -ar 48000 -movflags +faststart
```

Full-range `yuvj420p` sources must be converted to limited range explicitly (`zscale=rangein=full:range=limited` or `scale=in_range=full:out_range=tv`), or colours wash out after upload. Shipped in [`reel-export`](../../skills/reel-export/SKILL.md) with AAC raised to 256k and a 16M rate cap.

### 6.6 QA

- A motion QA pass on every frame; on a jump-cut reel, cut frames are expected, so allow the EDL's cut frames and treat everything else as a real stutter or pop.
- Contact strips 10 frames either side of every cut and every graphic entrance and exit.
- `ffprobe` gates: 1080x1920, h264, yuv420p, tv range, bt709, fps, `v:0 duration == a:0 duration`, duration within 0.1 s of the EDL.
- Audio: `ebur128` integrated and true peak on the final MP4; voice-to-bed ratio per section; no clipped last word.
- Captions: contrast of the pixels behind each caption, never over the mouth (face box from OpenCV), all text inside the safe region.
- Fresh ASR diff.
- A critic who has not seen the plan reviews the render and writes ranked problems with timecodes.

Shipped in [`reel-qa`](../../skills/reel-qa/SKILL.md).

## 7. How the skills were split

Each skill is a folder with `SKILL.md`, `references/` and `scripts/`, with scripts written fresh (no code copied from unlicensed or non-commercial repos).

| Skill | Job | Structure borrowed from |
|---|---|---|
| [`reel-ingest`](../../skills/reel-ingest/SKILL.md) | probe, rotate, extract 48 kHz WAV, transcribe with key terms, VAD and envelope word fixes | video-use packed transcript; hassancs91 key terms and timing-lie detectors |
| [`reel-cut`](../../skills/reel-cut/SKILL.md) | retakes and slates, between-phrase tightening, single-pass render, re-timed words, cut QA | herk cut-silences + cut-mistakes; hassancs91 snap tails and drift gates; video-use hard rules |
| [`voice-clean`](../../skills/voice-clean/SKILL.md) | diagnose noise, A/B denoisers on a sample, voice chain, level preservation | hassancs91 clean-audio |
| [`reel-motion`](../../skills/reel-motion/SKILL.md), [`reel-captions`](../../skills/reel-captions/SKILL.md) | Remotion brand kit: captions, hook card, numbered cards, checklists, CTA lock-up, camera moves; payoff-word timing | Remotion captions skill; Barty-Bart density rules; motionmaxxing never-ship list |
| [`reel-sound`](../../skills/reel-sound/SKILL.md) | music bed, ducking, SFX on visible events only, two-pass loudnorm on the final | Barty-Bart sound-effects; herk audio rules; video-use attack offset |
| [`reel-qa`](../../skills/reel-qa/SKILL.md) | all gates in 6.6, an honest report of what could not be checked, critic pass | herk quality gates; motionmaxxing script gates |
| [`reel-export`](../../skills/reel-export/SKILL.md) | upload-safe encode + ffprobe gate | charlie947 reel-export; the clipper's platform table |

Plus a `project.md` session log per reel (video-use) and a series style bible where every owner note becomes a rule (herk loop), both in [`reel-director`](../../skills/reel-director/SKILL.md).

## 8. Risks and caveats

- **Remotion licence:** above 3 people a company licence is needed.
- **Fonts:** download OFL fonts and assert they loaded, or renders fall back silently.
- **No listening:** all audio claims here are measurements; a human must listen before a chain is locked.
- **Untrusted repos:** nothing cloned was executed. HyperFrames' media skill contacts its vendor and sends a usage event; do not run it without the owner's say-so. See [`craft-research`](../../skills/craft-research/SKILL.md) section 4 for handling untrusted material.
- **Licence hygiene:** appariciojunior (CC BY-NC) and remotion-dev/skills (no licence) are reference only; Barty-Bart's CC0 SFX files are reusable; herk, video-use, hassancs91 and AgriciDaniel are MIT, so copying code needs their copyright notice.
- **Conflicts resolved:** per-segment `-c copy` concat (video-use) versus single-pass or sample-exact audio (herk, hassancs91): single-pass filtergraph. Cloud ASR (video-use and herk defaults) versus local: local faster-whisper large-v3.

## Sources

- The repos linked in section 4 (metadata from `gh repo view`, 2026-11-24).
- Remotion pricing: https://www.remotion.dev/docs/license/pricing.md
- DeepFilterNet: https://github.com/Rikorose/DeepFilterNet
- WhisperX paper and README: https://arxiv.org/abs/2303.00747 , https://github.com/m-bain/whisperx
