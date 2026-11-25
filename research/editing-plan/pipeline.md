# Pipeline: three stages, one timeline

The plan settled on three stages with a hard boundary between them. Each stage writes files that the next one reads, and nothing downstream reaches back into the raw clips.

```
raw camera clips (read only)
  |
  |- Stage 1  Python + ffmpeg
  |    ingest  -> probe, rotation, blinks, sharpness, face boxes, word timings
  |    plan    -> edl.json (ranges with separate video and audio in/out points)
  |    render  -> aroll.mp4       1080x1920 25p CFR, graded, tv range, BT.709, video only, CRF 14, GOP 25
  |               voice_cut.wav   48 kHz mono, cut, cleaned in a later step, NOT loudness-normalised
  |               words.out.json  corrected caption text on output-timeline timings (Remotion Caption[])
  |               cues.json       shots, cuts, face box per shot, cover windows, keyword onsets
  |
  |- Stage 2  Remotion
  |    Camera (OffthreadVideo of the A-roll, muted) -> graphics -> captions (always last) -> end card
  |    -> gfx.mp4   H.264 CRF 14 intermediate, BT.709, muted
  |
  '- Stage 3  ffmpeg
       voice + bed + SFX -> mix_pre.wav -> two-pass loudnorm -> mix.wav
       gfx.mp4 + mix.wav -> delivery encode -> reel_vN.mp4
       QA gates -> report + contact sheets + critic pass
```

The skills split these stages further (ingest, cut, grade, voice, captions, motion, 3D, sound, export, QA); the numbered stage table is in [`reel-director`](../../skills/reel-director/SKILL.md) and every command is in the [runbook](../../skills/reel-director/references/runbook.md).

## Why three stages

- **Stage 1 is where frames and samples are decided.** Cutting, grading and the range conversion happen once, on the raw files, in a single ffmpeg graph. Everything after it works on one output timeline and never sees source timecodes.
- **Stage 2 only adds pixels.** Remotion moves the camera and draws graphics and captions over the finished A-roll. It never cuts, never retimes and never touches audio.
- **Stage 3 only adds sound and packaging.** The mix is built to the exact length of the graphics pass, and the delivery encode sets the profile, level, GOP and colour tags.

A change upstream invalidates everything below it. A re-cut means re-running every later stage in order; outputs from two different cuts are never mixed. `reel-director/scripts/status.py` tracks this.

## Stage boundaries that matter

| Rule | Reason |
|---|---|
| Full-range camera files become tv range exactly once, in the A-roll render, with an explicit `scale=in_range=full:out_range=tv` | An implicit conversion (letting `format=yuv420p` negotiate) or a second conversion later lifts blacks by about 10 codes and dulls whites |
| All scaling for shot matching and punch-ins happens in Remotion | One resample only; the A-roll stays at scale 1.00 |
| Audio is padded or trimmed to the exact video length (`apad,atrim=end=V`); never `-shortest` | `-shortest` silently drops the tail of whichever stream is longer and hides drift |
| The voice is not loudness-normalised on its own | Normalising the mix once, at the end, keeps the relative levels of voice, bed and SFX that were set in the mix |
| The graphics pass is re-encoded for delivery, never stream-copied | Remotion's own output carries its own level and GOP; the delivery spec must be ours |
| Source handling: `-map 0:v:0 -map 0:a:0 -map_metadata -1 -write_tmcd 0`, rotation applied with `transpose` and `setsar=1`, audio folded to mono | Phone and mirrorless clips carry timecode and data streams, rotation tags and dual-mono audio that break later stages if passed through |

## Chosen tools

| Layer | Tool | Why it won |
|---|---|---|
| Probe, rotate, cut, grade, audio DSP, mix, encode | ffmpeg / ffprobe 6.1 | Has every filter the pipeline needs (transpose, zscale, afftdn, arnndn, deesser, acompressor, agate, loudnorm, ebur128, sidechaincompress, libx264) and was tested end to end in a prototype |
| Speech recognition and word timing | faster-whisper large-v3, int8 on CPU, plus RMS-envelope snapping of word edges (later replaced by forced alignment, see `reel-ingest`) | Smaller models absorbed silence into word starts and put onsets hundreds of milliseconds early; large-v3 with snapping matched the waveform |
| Frame analysis | OpenCV `FaceDetectorYN` (YuNet), Laplacian sharpness, frame difference | Finds blinks, focus hunting, sway and the face box that graphics and captions must avoid |
| Camera moves, graphics, captions | Remotion 4 with React, `@remotion/captions`, `@remotion/fonts`, `OffthreadVideo` | Rendered on the test machine with no workaround; sub-pixel smooth zooms where ffmpeg `zoompan` jitters; real UI cards and springs |
| Fonts | Local font files loaded with `@remotion/fonts` from `staticFile` | Never fetch fonts from the network at render time; assert they loaded before the first frame |
| SFX | A CC0 kit with a manifest (see [sources](../../skills/craft-research/references/sources.md)), later joined by a generated kit in `reel-sound` | Licence is clear and every file is recorded in `CREDITS.txt` |

**Pin every `@remotion/*` package to one exact version** and check it with `npx remotion versions`. The plan pinned the version that had been benchmarked rather than the newest release; the skills keep that rule.

Measured render speed on the test machine: about 9.5 fps after a 7 s startup for a 1080x1920 composition with captions and a few cards. A 50 s reel at 25 fps (1250 frames) therefore takes about 7 s + 1250 / 9.5, roughly 2.3 minutes. This was extrapolated from 10 s benchmarks; see [open-gaps.md](open-gaps.md).

## Rejected tools

| Tool | Why not |
|---|---|
| ffmpeg-only graphics (drawtext, ASS subtitles) | Fine for drafts and as the fallback when Remotion's licence does not cover the company; too weak for UI cards, springs and layout that reacts to the face box |
| auto-editor as the cutter | Volume-threshold cutting over-fragments a scripted take and cannot judge phrases. At most its `--preview` as an energy cross-check |
| HyperFrames | A second framework; its media skill pushes a vendor sign-in and sends usage telemetry; renders were reported slow |
| MoviePy, MCP servers for editing | No capability that Bash plus ffmpeg does not already have |
| Per-segment extract then `-c copy` concat | Drifts: each segment rounds to its own keyframes and timestamps. One `filter_complex` with `trim`/`atrim`/`concat` does not |
| ffmpeg crops for punch-ins | A second resample, and `zoompan` steps visibly on slow moves |
| The brand's website palette inside the reel | The series already had its own reel look; mixing systems breaks continuity. Only the website's CTA colour was borrowed, for the CTA pill |

## The first plan's starting look (Stage 1)

The skills now build the grade from measurements ([`reel-grade`](../../skills/reel-grade/SKILL.md)); this is the uniform look the plan started from, with a per-clip exposure step in the middle:

```
transpose=2,setsar=1,
<per-clip exposure>,
colortemperature=temperature=6000:mix=0.3,
eq=contrast=1.06:saturation=1.10,
unsharp=5:5:0.4:5:5:0,
scale=in_range=full:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709,
format=yuv420p
```

- Target skin luma (Y on a cheek patch) about 150, accepted 145 to 155, with YMIN at or above 16 and YMAX at or below 235 after the render.
- On the first reel the five takes measured skin Y from 134 to 170; corrections of `eq=gamma` between 0.85 and 1.2, plus one highlight curve for a take with a hot wall, brought them into the band.
- **Cool down, not warm up, when the footage measures warm.** Every take measured warm (wall red minus blue spread 33 to 51), so a light cool-down won over the common "warm up by 100 to 300 K" advice. Measure before applying a generic look.
- No vignette (graphics share the frame) and no LUT.
