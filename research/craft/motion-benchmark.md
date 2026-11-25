# Motion toolchain benchmark: Remotion versus ffmpeg only

Which renderer should put camera moves, captions and motion graphics over a cut talking-head A-roll, and how fast it runs on an ordinary machine. Both paths were prototyped on 3 s and 10 s rotated clips of a sample reel and timed.

**Machine:** 8 CPUs, about 32 GB RAM, **no GPU** (no render node, so no VAAPI either). Node 24, npm 11, ffmpeg 6.1 (a distribution build with libass, freetype, harfbuzz, fontconfig, librubberband, libvidstab, lut3d, libplacebo, frei0r).

**Bottom line:** Remotion works on such a machine without workarounds and renders 1080x1920 at 25 fps at about **9.5 frames/s** after a fixed startup of about **7 s**, so a 60 s reel (1500 frames) takes about **3 minutes**. The pipeline that came out of it: ffmpeg and Python build a clean A-roll and the audio master, Remotion adds every graphics layer, ffmpeg does the final mix, mux and loudness check. ffmpeg alone is fine for drafts and plain captions, and the wrong tool for dashboard-style motion graphics.

The production version of the Remotion project is [`reel-motion`](../../skills/reel-motion/SKILL.md) (and [`reel-3d`](../../skills/reel-3d/SKILL.md) for 3D inserts); use those rather than rebuilding the prototype.

## 1. Remotion

### 1.1 Versions

Remotion requires every `@remotion/*` package on the same exact version; bump them together or `npx remotion versions` fails the render.

| Package | Version tested |
|---|---|
| remotion, @remotion/cli, @remotion/renderer, @remotion/captions, @remotion/fonts, @remotion/google-fonts, @remotion/media | 4.0.542 (published 2026-11-09; 4.0.546 was the latest at the time) |
| react, react-dom | 19.3.1 |
| typescript / @types/react | 5.9.3 / 19.2.2 |
| chrome-headless-shell (downloaded by Remotion) | Chromium 158 |
| ffmpeg bundled in `@remotion/compositor-linux-x64-gnu` | n7.1 |

`reel-motion` pins the same 4.0.542 and React 19.3.1 in its `package.json`.

### 1.2 What the prototype contained

- `remotion.config.ts` with JPEG frames at quality 90, concurrency 8, overwrite on.
- A `Reel` composition: `<OffthreadVideo>` of the rotated clip with a slow eased punch-in from 1.00 to 1.08 (CSS `transform: scale`); word-by-word captions from a Remotion `Caption[]` file built with `createTikTokStyleCaptions` (each word springs in, the active word turns gold, uppercase Inter Black with a 14 px black stroke); a spring-animated hook card (`spring({damping: 14, stiffness: 160})`) with a gradient numeral badge springing in with rotation 8 frames later.
- Benchmark compositions: 249 frames over a 10 s clip with `OffthreadVideo`, the same with `@remotion/media` `<Video>`, and a transparent overlay with no video.
- Fonts loaded from local TTFs with `@remotion/fonts`, so renders need no network.

### 1.3 Commands that worked

```bash
ffmpeg -y -ss 0 -t 3 -i raw/CLIP.MP4 \
  -map 0:v:0 -map 0:a:0 -map_metadata -1 -write_tmcd 0 \
  -vf "transpose=2,scale=1080:1920:flags=lanczos,format=yuv420p" -r 25 \
  -c:v libx264 -preset fast -crf 16 -g 25 -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart public/test.mp4

npm install --no-audit --no-fund
npx remotion browser ensure
npx tsc -p .
npx remotion render Reel out/reel.mp4 --color-space=bt709
npx remotion still Reel out/still.png --frame=60
npx remotion render Overlay10 out/overlay10.mov --codec=prores --prores-profile=4444 --image-format=png --pixel-format=yuva444p10le
npx remotion render Overlay10 out/overlay10_png --sequence --image-format=png
npx remotion studio
```

`npm install` pulled 246 packages in 24 s (871 MB of `node_modules` including the browser); `browser ensure` downloaded a 102.5 MB headless shell in 5 s. The current install steps are in the [README](../../README.md) and [`reel-motion`](../../skills/reel-motion/SKILL.md).

### 1.4 Verification

- Frames pulled at 0.6 s and 2.6 s showed the hook card mid-spring with the badge still rotating (spring timing works), then settled with the gold active word in the captions and the subject upright, filling the frame.
- Output probe: h264 1080x1920 yuv420p 25 fps, 75 frames, AAC 48 kHz stereo, 3.008 s.
- Local-font and Google-font renders of the same frame were identical.
- A transparent overlay composited by ffmpeg matched the full Remotion render, apart from the punch-in, which only the full render can apply.
- Caught on the frames: the raw clip's pre-roll (a hand over the lens before speech) must be cut by the cut list; hidden caption words still took up layout space so the line looked off-centre; the hook card sat over the subject's hair, so card placement needs a face-aware rule.

### 1.5 Install issues and fixes

| Issue | Fix |
|---|---|
| npm 11 `allowScripts` warning: "esbuild (postinstall) not yet covered by allowScripts" | none needed: esbuild's platform binary comes from the `@esbuild/linux-x64` optional dependency and bundling works |
| headless Chrome | `npx remotion browser ensure` downloads chrome-headless-shell into `node_modules/.remotion/` (243 MB unpacked); no missing system libraries, no sandbox flags |
| only DejaVu and Liberation fonts installed system-wide | `@remotion/google-fonts` works but fetches from fonts.gstatic.com at render time. Better: download static TTFs (the Google Fonts CSS2 API returns TTF URLs to a non-browser user agent) and load them with `@remotion/fonts` `loadFont({family, url: staticFile(...), weight})`. The same TTFs serve libass and drawtext |
| camera files carry a `tmcd` timecode data track and are full-range `yuvj420p` | `-map 0:v:0 -map 0:a:0 -map_metadata -1 -write_tmcd 0` drops the track (otherwise ffmpeg writes a third "unknown" data stream); `format=yuv420p` converts pc to tv range |
| Remotion output tagged `unknown / iec61966-2-1` by default | pass `--color-space=bt709`; the output is then tagged tv/bt709 like the A-roll |
| `@remotion/media` `<Video>` (the newer decoder) | works, but was slower (36 to 47 s against 33 to 35 s for `OffthreadVideo` on 249 frames); keep `OffthreadVideo` |
| licence | free for individuals and for-profit companies of up to 3 employees; bigger needs a company licence |

### 1.6 Benchmarks

Wall clock, 1080x1920 at 25 fps, 8 CPUs, no GPU.

| Job | Frames | Wall | Notes |
|---|---|---|---|
| ffmpeg transpose of a 3 s test clip | 75 | 4.4 s | x264 fast, CRF 16 |
| Remotion `Reel`, cold (first bundle) | 75 | 36.6 s | 148 % CPU, max RSS 1.35 GB |
| Remotion `Reel`, cached bundle, concurrency 8 | 75 | 17.3 s | |
| Remotion `Reel`, cached bundle, concurrency 4 | 75 | 17.3 s | **concurrency above 4 does not help** |
| Remotion fixed overhead (2 frames) | 2 | 7.3 s | bundle + browser launch |
| `remotion still` | 1 | 6.9 s | quick design QA |
| 10 s `OffthreadVideo`, short-GOP source (2 runs) | 249 | 34.6 s, 33.3 s | 225 to 231 % CPU, RSS 860 MB |
| 10 s `OffthreadVideo`, long-GOP source | 249 | 31.9 s | GOP length does not matter |
| same, `--x264-preset=veryfast --crf=18` | 249 | 28.5 s | encode is about 15 % of the time |
| same, `--concurrency=6 --jpeg-quality=80` | 249 | 36.0 s | no gain |
| 10 s with `@remotion/media` `<Video>` | 249 | 47.0 s, 36.0 s | slower |
| transparent overlay, ProRes 4444 | 249 | 21.7 s | 86 MB, yuva444p12le |
| ffmpeg composite of that ProRes overlay on the A-roll | 249 | 12.1 s | overlay + x264 medium CRF 18 |
| transparent overlay, PNG sequence | 249 | 15.5 s | 35 MB |
| ffmpeg overlay of the PNG sequence on the A-roll | 249 | 9.4 s | |

Warm throughput of the full render is about 9.5 frames/s. **A 60 s reel: 7 s + 1500 / 9.5, about 2.8 minutes.** Rendering the overlay separately and compositing with ffmpeg costs about the same overall (25 to 34 s per 10 s); it only pays off while iterating on graphics alone.

Later production numbers in [`reel-motion`](../../skills/reel-motion/SKILL.md) agree: about 7 s startup plus 9 to 10 frames/s at concurrency 4 on an idle 8-core CPU, peak RSS about 830 MB; a batch of stills costs one bundle (about 15 s) plus 1 to 2 s per still. The skill defaults to concurrency 2 (`REEL_CONCURRENCY`) and can serialise renders with `REEL_RENDER_LOCK` on a shared machine, since the cores above 4 are better spent on parallel ffmpeg work.

## 2. ffmpeg only

### 2.1 Filters available on a typical 6.1 build

Video: `drawtext`, `ass`, `subtitles`, `overlay`, `zoompan`, `xfade`, `fade`, `crop`, `scale` (with `eval=frame`), `transpose`, `rotate`, `eq`, `curves`, `colorbalance`, `colortemperature`, `selectivecolor`, `lut3d`, `hue`, `unsharp`, `vignette`, `gblur`, `boxblur`, `hqdn3d`, `nlmeans`, `bm3d`, `atadenoise`, `vidstabdetect`/`vidstabtransform`, `deshake`, `chromakey`, `alphamerge`, `blend`, `tblend`, `lagfun`, `minterpolate`, `geq`, `drawbox`, `pad`, `xstack`, `sendcmd`, `zmq`, `libplacebo`, `zscale`, `frei0r`, `overlay_opencl`.

Audio: `highpass`, `lowpass`, `equalizer`, `afftdn`, `anlmdn`, `arnndn` (external RNNoise model), `agate`, `acompressor`, `deesser`, `dynaudnorm`, `speechnorm`, `loudnorm`, `ebur128`, `alimiter`, `sidechaincompress`, `amix`, `acrossfade`, `afade`, `silencedetect`, `silenceremove`, `rubberband`.

Encoders: libx264, libx265, prores_ks, qtrle, png, libvpx-vp9 (alpha), libsvtav1, aac, libopus. Hardware encoders compiled in have nothing to run on without a GPU.

### 2.2 Tests (10 s rotated clip unless noted)

| Test | Core of the command | Wall | Result |
|---|---|---|---|
| animated drawtext (3 s clip) | `drawtext=fontfile=fonts/Inter-900.ttf:text='3 MISTAKES':fontsize=110:borderw=10:x=(w-text_w)/2:y=300+60*max(0\,1-t/0.4):alpha='min(1\,t/0.4)'` | 3.2 s | slide-up and fade work |
| ASS karaoke captions (libass) | `ass=captions.ass:fontsdir=fonts` | 8.4 s | word by word, gold active word, `\t()` scale pop; Inter Black resolved from `fontsdir` |
| PNG sequence overlay | `-framerate 25 -i overlay/element-%03d.png` + `overlay=0:0:eof_action=pass` | 9.4 s | correct alpha |
| zoompan punch-in | `zoompan=z='if(between(in_time,4,6),1+0.15*(in_time-4)/2,...)':d=1:s=1080x1920:fps=25` | 8.6 s | works, but x/y round to whole pixels, so **slow pushes jitter** |
| scale + crop punch-in | `scale=w='1080*(1+0.15*clip((t-4)/2,0,1))':h=-2:eval=frame,crop=1080:1920:(iw-1080)/2:(ih-1920)/3` | 9.2 s | smoother than zoompan, still an integer crop |
| xfade + acrossfade | `xfade=transition=smoothup:duration=0.3:offset=3.7` + `acrossfade=d=0.3` | 8.0 s | works |
| voice chain + two-pass loudnorm | measure, then apply linear loudnorm | 2.1 s | -17.5 LUFS in, -14.2 LUFS out |

The ASS generator grouped words into chunks of at most 3, split on pauses over 0.35 s, and wrote one Dialogue event per word with the active word coloured and popping in. It is not kept: captions are now rendered in Remotion by [`reel-captions`](../../skills/reel-captions/SKILL.md) and [`reel-motion`](../../skills/reel-motion/SKILL.md), and two-pass linear loudnorm lives in `reel-sound/scripts/mix.py`.

### 2.3 Verdict

Good for: rotation, trims, concat, grade, denoise, loudness, simple titles and ASS captions (libass is fast and looks good). Weak for a motion-graphics brief:

- Dashboard-style graphics (UI cards with status pills, progress bars, animated counters, charts, icon tiles, end cards) are HTML/CSS UI. Rebuilding them as filter graphs is impractical.
- No spring physics or easing library; long expressions are hard to maintain.
- `zoompan` jitters.
- No preview UI, so iteration is slow.

## 3. Architecture that came out of it

```
raw MP4s --> [1: Python + ffmpeg]                          --> aroll.mp4 (1080x1920, source fps, graded, cut, video only)
             transcribe (faster-whisper, word timestamps)       voice master WAV (cleaned, cut, 48 kHz)
             cut list (EDL JSON) from the transcript            edl.json, re-timed words (Caption[])
                                                                cues.json (emphasis words, beats, zoom points, face box)
                         |
                         v
             [2: Remotion]  OffthreadVideo(aroll, muted) + camera moves + captions
                            + UI cards + logo bug + end card             --> gfx.mp4 (video only, bt709)
                         |
                         v
             [3: ffmpeg]    voice + ducked music + SFX at cue times, two-pass loudnorm,
                            mux, faststart, QA                           --> final.mp4
```

### Stage 1: A-roll and audio master

1. Probe every clip, drop the `tmcd` track, confirm the rotation on one frame.
2. Build the cut list from the word timestamps: trim the head slate, tighten gaps over about 0.25 to 0.35 s, remove retakes, false starts and fillers, keep 2 to 4 frames of handle before each word and 3 to 6 after. `auto-editor` and `silencedetect=n=-35dB:d=0.25` can help, but the transcript drives the cut.
3. Render all segments in one filtergraph with `trim`/`atrim` + `setpts` + `concat`, with a short fade or crossfade at every audio join. Grade with `eq`/`curves`/`colortemperature` or a `lut3d`. Encode with `-c:v libx264 -preset medium -crf 14 -g 25 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv`.
4. Run the cleanup chain on the concatenated voice and save a WAV. Set loudness only in stage 3, on the mix.
5. Remap the words onto the new timeline in the Remotion `Caption[]` shape.

Now: [`reel-ingest`](../../skills/reel-ingest/SKILL.md), [`reel-cut`](../../skills/reel-cut/SKILL.md), [`reel-grade`](../../skills/reel-grade/SKILL.md), [`voice-clean`](../../skills/voice-clean/SKILL.md).

### Stage 2: graphics

- Pass the EDL, words and cues as `--props`; set `durationInFrames` from the A-roll with `calculateMetadata`.
- Do zooms in React (CSS `scale`/`translate` with `spring`/`interpolate`): sub-pixel precision, so smooth, unlike `zoompan`. Small scale jumps (1.0 to 1.12) on hard cuts hide jump cuts.
- Captions from `createTikTokStyleCaptions` pages, reserving the full line from the first frame so it stays centred.
- Safe zones: text out of the top about 220 px, the bottom about 380 px and the right button rail (about 120 px). Place cards from a face box detected in stage 1 (OpenCV) and written into `cues.json`.
- Brand colours and fonts from a brand folder (see [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) for the example).
- Render: `npx remotion render Main out/gfx.mp4 --props=props.json --muted --color-space=bt709 --crf=16 --x264-preset=medium --concurrency=4`. Iterate with `npx remotion still Main out/check.png --frame=N` (about 7 s) and `npx remotion studio`.

Now: [`reel-motion`](../../skills/reel-motion/SKILL.md) (`scripts/render.sh` adds `--pixel-format=yuv420p`, CRF 14, an A-roll checksum check and a frame-count check).

### Stage 3: mix, mux, QA

```bash
ffmpeg -i voice_master.wav -i music.wav -i whoosh.wav -filter_complex \
 "[0:a]asplit=2[vo][sc];[1:a]volume=0.18[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];\
  [2:a]adelay=4120|4120[s1];[vo][md][s1]amix=inputs=3:duration=first:normalize=0[mix]" \
 -map "[mix]" -ar 48000 mix_pre.wav

V=$(ffprobe -v error -select_streams v -show_entries stream=duration -of csv=p=0 gfx.mp4)
ffmpeg -i gfx.mp4 -i mix.m4a -filter_complex "[1:a]apad,atrim=end=$V[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart final.mp4
ffmpeg -i final.mp4 -af ebur128=peak=true -f null -
```

Between the two commands, `mix_pre.wav` goes through two-pass linear loudnorm to `mix.m4a` (-14 LUFS, TP -1.5). The audio is padded or trimmed to the exact video length; never `-shortest`. Run end to end on a 10 s test (a sine as the bed, pink noise as the whoosh), the result had video 9.96 s / 249 frames, audio 9.96 s, -14.2 LUFS integrated, peak -2.4 dBFS. QA: count frames with `ffprobe -count_packets`, compare A/V durations, contact sheet every 2 s.

Now: [`reel-sound`](../../skills/reel-sound/SKILL.md) (word-keyed duck instead of a sidechain by default), [`reel-export`](../../skills/reel-export/SKILL.md) (re-encodes the graphics pass instead of stream-copying it, so profile, level, GOP and colour tags are its own), [`reel-qa`](../../skills/reel-qa/SKILL.md).

### Fallbacks

- If the Remotion licence is a blocker: the ffmpeg path with ASS captions and PNG or alpha overlays from another renderer. [Motion Canvas](https://github.com/motion-canvas/motion-canvas) and [Revideo](https://github.com/redotvideo/revideo) are MIT-licensed alternatives; neither was tested.
- Decoupled graphics: render an overlay composition with `--sequence --image-format=png` (the fastest graphics render, 15.5 s per 10 s) and `overlay=0:0:eof_action=pass` it onto the A-roll. You lose React-side transforms of the footage (zooms, blur, split layouts).

## 4. Gotchas (each hit and fixed)

1. Camera clips contain a `tmcd` data stream; ffmpeg copies it into new MP4s unless you use explicit `-map` and `-write_tmcd 0`.
2. Full-range `yuvj420p` sources: convert to tv range once in stage 1 so later stages do not double-convert.
3. With `-c copy`, `-shortest` dropped 4 video frames (249 to 245). Do not use it; match the audio to the video length instead.
4. libass `fontsdir` tries to load every file in the folder (it tried a `.css` file); keep that folder to font files only. The ASS `Fontname` `Inter Black` matches the static TTF.
5. Remotion's default colour tags are unknown/sRGB; always pass `--color-space=bt709`.
6. Remotion stops getting faster at concurrency 4 on 8 cores; give the other cores to ffmpeg work running at the same time.
7. `@remotion/google-fonts` needs the network at render time; local TTFs via `@remotion/fonts` give the same pixels offline.
8. Bump all `@remotion/*` versions together.
