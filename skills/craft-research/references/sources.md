# Vetted sources

Surveyed 2026-11-24 with `gh search repos`, `gh search code --filename SKILL.md` and `gh repo view`; the repos marked "read" were shallow-cloned and read, never executed. Stars and licences change: re-check with `gh repo view` before borrowing. "Borrow" means ideas and numbers rewritten in our own words and code, unless the licence and an attribution notice allow more.

## Agent skills for editing footage

| Repo | Licence | Read | What to borrow | Reject |
|---|---|---|---|---|
| [browser-use/video-use](https://github.com/browser-use/video-use) | MIT | yes | Hard rules (captions last, 30 ms fades at every join, never cut inside a word, word-level ASR only), the packed transcript (one line per phrase with `[start-end]`), EDL JSON shape, self-eval loop with a "roast, do not praise" critic, parallel animation sub-agents with one file each, assert fonts loaded before rendering | per-segment extract then `-c copy` concat (drifts); cloud ASR as default |
| [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) | MIT | yes | Measured reel pacing (speech within 0.1 s, phrase gaps under 0.2 s, shots 1.1 to 1.4 s, first cut 0.6 to 1.0 s, each list item its own shot), cut-silences then cut-mistakes split, caption rules (1 to 3 words, 2 frames early, never over mouth or chin), bed 9 to 14 dB under voice, measure loudness on the final file, every user note becomes a rule | HyperFrames and paid cloud services in the core path |
| hassancs91's YouTube editor skills (`gh repo list hassancs91`) | MIT | yes | A/V drift causes and the single-pass trim/atrim/concat fix, "the transcript lies about time" detectors, RMS snap-to-audio tails, second ASR pass on the render (missing = clipped, extra = ghost), diagnose noise type before denoising, comp-native input for Remotion | |
| [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics) | MIT (CC0 SFX kit) | yes | B-roll density rules (no cutaway in the first second, 2 s of face between cutaways, one change per spoken beat), plan table before code, never invent numbers, SFX on visible events only, CC0 SFX kit with a manifest, 5 listen timestamps for a human | |
| [Tejashmakwana/motionmaxxing](https://github.com/Tejashmakwana/motionmaxxing) | Apache-2.0 | yes | Never-ship list (counters, timecodes, colour floods, invented stats, slogan copy), measured motion laws (most travel in the first 4 to 8 frames, at most one visible spring, nothing grows from zero, words land 0 to 2 frames early), gates computed by script | "no numbered counters" when the numbers are the content of a list reel |
| AgriciDaniel's shorts clipper (`gh repo list AgriciDaniel`) | MIT | yes | Caption style presets (sizes, words per page, spring values), platform export table, faster-whisper large-v3 int8 settings | long-to-short clipping logic (different job) |
| [charlie947/motion-graphics-skills](https://github.com/charlie947/motion-graphics-skills) | MIT | yes (reel-export) | Upload-safe ffmpeg recipe (BT.709 tags, tv range, faststart) and its ffprobe gate; logos on their own tile; text out of the bottom 500 px and right 120 px | |
| [appariciojunior/video-editor-skills](https://github.com/appariciojunior/video-editor-skills) | CC BY-NC 4.0 | yes | Ideas only: cut from words not volume, punch-in only on jump cuts, never normalise a silent clip, re-render under a new filename | any text or code (non-commercial licence) |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | Unlicense | yes | `--preview` as an energy cross-check; NLE export | volume-threshold cutting for scripted reels (over-fragments, cannot judge phrases) |
| [jincheng2026/jc-remotion-skills](https://github.com/jincheng2026/jc-remotion-skills) | other | no | Closest workflow shape (rough cut + SRT in, motion packaging, SFX, mastering out); Chinese-language | |

## Remotion and renderers

| Repo | Licence | What to borrow | Note |
|---|---|---|---|
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | Remotion License | the renderer | Free for individuals and companies of up to 3 people; larger for-profit companies need a company licence. Pin every `@remotion/*` package to one exact version. |
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | none stated | caption patterns (`Caption` type with leading-space text, `createTikTokStyleCaptions`), keep each clip and its captions under one `Sequence`, adaptive `silencedetect` threshold from `loudnorm` `input_thresh` | reference only, do not vendor |
| [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok) | none stated | page and active-word pattern, `fitText` sizing | reference only |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | Apache-2.0 | caption-group exit guarantees, style tables | its media skill pushes a vendor sign-in and sends a usage beacon; renders reported slow |
| [nexu-io/html-video](https://github.com/nexu-io/html-video) | Apache-2.0 | alternative HTML-to-MP4 engine | not read |

## Core tools

| Tool | Licence | Role |
|---|---|---|
| [ffmpeg](https://ffmpeg.org) 6.x | LGPL/GPL build | probe, rotate, cut, grade, denoise, loudness, encode; filters used: transpose, scale (range), eq, curves, colortemperature, afftdn, arnndn, deesser, acompressor, agate, loudnorm, ebur128, sidechaincompress, signalstats |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | word timestamps; large-v3 int8 on CPU; bundled Silero VAD |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | BSD-2 | forced alignment upgrade (needs torch) |
| [jianfch/stable-ts](https://github.com/jianfch/stable-ts) | MIT | timestamp stabilisation, alignment to a known script |
| [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | MIT or Apache-2.0 | speech enhancement for hard noise (prebuilt CPU binary, 48 kHz WAV) |
| [richardpl/arnndn-models](https://github.com/richardpl/arnndn-models) | none stated | RNNoise models for `arnndn`; check licence before production use |
| [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) YuNet | MIT | face boxes and landmarks |
| [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | search, metadata, subtitles |

Avoid in the cut path: MoviePy (slow per-frame Python, weak text), ffmpeg `zoompan` for punch-ins (jitters; do zooms in the renderer), MCP wrappers around ffmpeg (no capability over a shell), AGPL tools such as whisper-timestamped and pireel (do not vendor).

## Curated lists (for the next survey)

| Where | Note |
|---|---|
| zhuyansen's curated list of video skills (`gh repo list zhuyansen`) | CC0, about 540 repos, security-graded and categorised (editing, shorts) |
| wilwaldon's video toolkit index (`gh repo list wilwaldon`) | index of video skills and MCP servers |
| `gh search repos "awesome video skills" --sort stars` | general lists, few video entries |

## Tutorial queue (YouTube, found with `ytsearchN`, transcripts not yet read)

| Topic | Channel | Title | URL |
|---|---|---|---|
| Hooks | Kallaway | Give me 15 mins, and I'll make your hooks impossible to skip | https://www.youtube.com/watch?v=2byPP_9F0-Q |
| Retention editing | Learn By Leo | How to edit SO good your viewers get addicted to your videos | https://www.youtube.com/watch?v=sLgHqZSe2o0 |
| Short-form editing | Joseph, Video Editing | The Ultimate Guide to Master Short-Form Video Editing! | https://www.youtube.com/watch?v=R9Uu0JtvyMg |
| Talking-head reels | Joseph, Video Editing | How to Edit VIRAL Instagram Talking Head Videos | https://www.youtube.com/watch?v=Qbntd8yud0o |
| SaaS motion graphics | Joseph, Video Editing | How to Edit Viral SaaS Animations in 2026 | https://www.youtube.com/watch?v=zWbLfFA9l8s |
| Talking-head basics | Think Media | How to Edit Talking Head Videos: 5 Video Editing Tips & Tricks | https://www.youtube.com/watch?v=xCl_zqJdjAc |
| Talking-head reels | TomsProject | How to Edit Viral Talking Head Videos Like Kallaway (2026 Guide) | https://www.youtube.com/watch?v=aNwKDaTag2Q |
| Motion graphics breakdown | Usman Explains | Talking Head Motion Graphics Reel Breakdown In Premiere Pro | https://www.youtube.com/watch?v=uW-8SKO8kYE |
| Punch-ins | (zoom-cut tutorial) | The Zoom Cut That Makes Talking Head Videos Pop | https://www.youtube.com/watch?v=MNWbIZ7MNoA |
| Jump cuts | (jump-cut tutorial) | The Jump-Cut Mistake Making Your Videos Look Amateur | https://www.youtube.com/watch?v=KtICyJV7gDc |
| Jump cuts | Premiere Gal | Hide Jump Cuts Like a PRO | https://www.youtube.com/watch?v=wVmi89tBORc |
| Pacing | Taiyology | How to pace your videos SO good your viewers can't click off! | https://www.youtube.com/watch?v=aZ4jehTzoQw |
| Captions | Matt Loui | How to Edit Captions for Reels and Shorts like Alex Hormozi for FREE | https://www.youtube.com/watch?v=EQUyZC_cd0s |
| Voice EQ | In The Mix | Make Your Voice Sound Better: Vocal EQ Zones | https://www.youtube.com/watch?v=pjMCyLsRNig |
| Spoken-word mix | Joe Gilder, Home Studio Corner | How to Mix Spoken Word Vocals in 2 Minutes | https://www.youtube.com/watch?v=5N_xNbsjbXE |
| Dialogue cleanup | Jason Yadlovski | DaVinci Resolve 20 Audio: Clean Up Dialogue | https://www.youtube.com/watch?v=8DPTayE7sus |
| Colour | Denz Creates | How I Color Grade My Talking Head Shots | https://www.youtube.com/watch?v=3cZz_zhvRHw |
| Colour | AniThing | COLOR GRADING Secrets for YOUTUBE INDOOR VIDEOS | https://www.youtube.com/watch?v=Cjt17eJXUUo |

Fetch the subtitles sequentially with a throwaway-account cookies file (see `SKILL.md` section 1), distil each into `LEARNINGS.md`, and mark every rule from this queue "untested" until it is measured on real footage.
