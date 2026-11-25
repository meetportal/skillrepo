# Decision record

The plan was assembled from several research tracks: written editing guides, a survey of open-source editing skill repos, the brand kit, measurements of the raw footage, a teardown of an earlier edit, and motion-tooling prototypes with benchmarks. They disagreed often. This file records one decision per topic and the reason it won.

Some of these values were later changed by measurements on the first build. Those changes are in [revisions.md](revisions.md); the skills hold the current numbers.

## Source precedence

When two sources disagree, the higher one wins:

1. **Measured on this reel's own raw clips** (probe, frame metrics, aligned words, skin and noise measurements).
2. **Measured on renders or on the working machine** (QA numbers on our outputs, encoder and renderer benchmarks, A/B tests).
3. **Defaults of well-maintained tools and skill repos.**
4. **Written guides and tutorials.**
5. **Habit and taste.**

A lower level never overrides a higher one. When two sources at the same level disagree, measure. Write every overruled number and the measurement that overruled it in the reel's decisions log. The rule now lives in [`reel-director`](../../skills/reel-director/SKILL.md#when-sources-disagree).

## Decisions at a glance

| Topic | Decision |
|---|---|
| Toolchain | Three stages: Python + ffmpeg (A-roll, voice, EDL, retimed words), then Remotion (camera moves, graphics, captions, end card), then ffmpeg (mix, loudness, delivery encode, QA). See [pipeline.md](pipeline.md) |
| Source handling | Map only the first video and audio stream, strip metadata and timecode, apply rotation explicitly, convert full to tv range once, fold dual-mono to mono |
| Transcript | Word timings from the large model with edges snapped to the audio; never planning from a small model's timings |
| Cut | Transcript-driven, between words only, with separate video and audio edges (J/L cuts), rendered as one `filter_complex` |
| Length | Whatever the cut gives after pause tightening; no target length forced onto the speech, no voice speed-up |
| Look | The series' existing reel system, not the website system. No watermark |
| Captions | One bold sans in sentence case, one serif-italic accent word per page, 1 to 3 words per page in the hook then 2 to 4, appear 1 frame before the word, position set by layout mode |
| Graphics | One idea per beat, shown big, then gone. Three layout modes (Talk, Card, Takeover). Text at least 44 px, numerals at least 140 px. No invented numbers |
| Audio | Cleaned voice, music bed ducked under speech, SFX only on visible events, two-pass loudnorm to -14 LUFS and -1.5 dBTP on the final mix, verified on the delivered MP4 |
| Export | H.264 High 4.2, CRF 18 slow, maxrate 16M, 25 fps CFR, GOP 50, yuv420p tv range, BT.709 tags, AAC-LC 256k 48 kHz stereo, `+faststart`, 1080x1920 |
| End card | Brand mark lands over live footage on the spoken brand name, then a short card (about 2.5 s) with the logo, a two-line headline with one accent word, the bare domain in a CTA pill, and "Link in bio". It cuts cleanly back to frame 0 so autoplay loops read as continuous |
| Claims | No prices, percentages, counts or offers on screen unless the owner has approved them. Relative shapes instead |

## Conflicts and resolutions

Grouped by area. "Craft" means written editing guides; "repo defaults" means the surveyed open-source skill repos (listed in [sources](../../skills/craft-research/references/sources.md)); "footage" means measurements on the raw clips; "prototype" means the motion-tooling tests.

### Timing and transcript

| Topic | Conflict | Resolution and reason |
|---|---|---|
| Hook onset | Tracks that used a small ASR model put the first word several hundred milliseconds earlier than the footage measurement | **Use the energy-snapped onset.** The small model absorbed leading silence into word starts. Cutting in at its time would have left half a second of dead air at frame 0 |
| Target length | Guides and the edit teardown estimated a much shorter reel than the footage measurement | **Length comes out of the cut.** The short estimates counted pauses from small-model timings; on the first reel their pause total was about double the energy-snapped total of pauses over 250 ms. Do not set a length target from guide numbers |
| Transcript source | Early tracks planned on a small-model transcript | **Only the large-model, aligned transcript** is used for planning and timing |
| Voice speed-up | Teardown: optional 1.05 to 1.08x; a repo default: never; guides: not above 1.05 to 1.08x | **No speed-up.** A sped-up variant is rendered only for an A/B listen if the owner asks |
| auto-editor thresholds | Guides gave threshold settings; the repo survey said keep it out of the cut path | **Not used** for cutting |

### Picture

| Topic | Conflict | Resolution and reason |
|---|---|---|
| White balance | Guides: warm up 100 to 300 K; footage: measured warm | **Cool down** (`colortemperature=6000:mix=0.3`), because the measurement outranks the guide |
| Range conversion | Prototype relied on `format=yuv420p` converting implicitly; others: explicit | **Explicit**, once, in Stage 1 |
| Where zooms happen | Footage track: ffmpeg crops; prototype: Remotion transforms | **Remotion only**: one resample, sub-pixel smooth |
| Punch-in ceiling | Guides: 115 % max; exact shot matching between takes needed 1.24 to 1.35 | **Total scale capped at 1.20.** Shot sizes do not need to match exactly: a different size between sections reads as a new camera. Above 1.20 the upscale softens (verify stills per camera body) |
| Final encode | Prototype: stream-copy the Remotion render; guides and repo defaults: re-encode to spec | **Re-encode** the CRF 14 intermediate so level, GOP and tags are ours |
| Remotion version | Newest release vs the benchmarked one | **Pin the benchmarked version**; upgrade deliberately, never implicitly |

### Audio

| Topic | Conflict | Resolution and reason |
|---|---|---|
| Denoiser | Repo-survey A/B favoured `arnndn`; footage in-chain test favoured `afftdn` plus a gate | **The footage test won** because the repo A/B's noise window contained hand rustle at the start of a take, so it measured rustle removal, not room-tone removal. Lesson: check what is inside the noise window before trusting a denoiser A/B. (The chosen chain was itself replaced later, see [revisions.md](revisions.md)) |
| `afftdn` noise floor | Guides -35 to -40, prototype -25, repo -50 (did nothing), footage -58 | **Match `nf` to the measured floor** (about -59 dBFS on the first reel). A guessed floor either does nothing or eats speech |
| Join fade | 30 ms afade (a repo default), 10 to 20 ms (prototype), 80 ms crossfade (footage track) | **30 ms afade** in the plan; replaced after measurement by a 16 ms equal-power crossfade, see [revisions.md](revisions.md) |
| True peak | Guides -1.0; everyone else -1.5 | **-1.5 dBTP.** Platform re-encodes add overs; the extra headroom is cheap |
| LRA | Guides 6 to 9, teardown 6 or less, repo 7, raw footage measured 11 | **7 LU or less** on the final mix |
| Bed level | Guides 20 to 28 dB under voice; repo and footage 10 to 12 dB; teardown 15 to 18 dB of duck | **About 16 LU under the voice plus a 6 dB duck** in the plan, tuned by ear; the skills later settled on 10 LU under with a word-keyed duck, see [revisions.md](revisions.md) |
| AAC bitrate | 192k, 256k, 320k | **256k**: transparent for speech plus music, and platforms re-encode anyway |

### Captions and layout

| Topic | Conflict | Resolution and reason |
|---|---|---|
| Brand system | Prototype used the website colours and font; brand kit and teardown used the reel system | **Reel system.** Series continuity beats the website. Only the website CTA colour appears, on the CTA pill |
| Caption font and case | Guides: heavy sans in all caps; repo defaults: ExtraBold caps; brand: sans with a serif-italic accent | **Bold sans, sentence case, serif-italic accent.** The serif italic reads badly in caps; caps are kept for title slams and the hook headline only |
| Active-word highlight | Guides and teardown: highlight the active word; an earlier house style: grey preview of unspoken words | **Neither.** Reveal each word on its onset; the accent word alone carries emphasis. (A `kinetic` style with an active-word pill was added later as an option in `reel-captions`) |
| Caption lead | 2 frames (a repo default), 0 to 1 frame (guides), 0 to 80 ms (teardown), 0 to 2 frames (motion laws) | **1 frame (40 ms) early**, gated at 0 to 2 frames |
| Safe zone | Guides x 70-950 y 220-1540; a repo x 90-930 y 200-1600; brand y 220-1500 with 140 px right margin | **x 70-950, y 220-1500**: the strictest bottom edge, because platform UI covers the lower part of the frame |
| Progress counter | Guides and teardown wanted a 3-slot rail; a never-ship list bans counters and progress bars | **Keep a segment rail as content** (it pays off at the wrap when it becomes the checklist), with no numeric "n/3" label. The ban targets decorative HUD chrome, not a list whose numbers are the content |
| Logo bug | An earlier house style kept a corner logo; the teardown found it collided with platform UI | **No corner logo** in the plan; later moved to a persistent top-centre mark, see [revisions.md](revisions.md) |
| Invented numbers | The teardown proposed illustrative prices, rates and percentages; repo defaults and the brand kit: never invent numbers | **No invented numbers.** Only owner-approved figures, otherwise relative shapes |
| List item labels | Punchy disparaging labels vs the speaker's own word | **Use the speaker's word** in title slams: it matches the audio and avoids disparaging copy |
| Hook text | Three sources proposed three different headlines | **Pick one default and keep two alternates**; build all three as stills and record why one won |
| Reusing earlier renders | Earlier edits existed | **Never edit from earlier renders.** Use them only to measure or critique. Every frame and sample comes from the raw camera files |
