# Editing craft for talking-head reels

How a top short-form editor would cut, caption, animate, mix, grade and export a 30 to 60 s vertical (1080x1920) talking-head reel for a B2B or SaaS brand. Every section ends in numbers and, where useful, an ffmpeg or Remotion recipe. The shipped values live in the skills; notes marked **Shipped** say where a skill moved a value after testing on real footage.

Sources are listed at the end (section 17 for tutorials, 18 for written guides). The three open-source editing skills quoted most are browser-use's video-use, Nate Herk's herk-edit-kit and hassancs91's YouTube editor skills; see [toolchain-survey.md](toolchain-survey.md) for what each teaches.

## 1. Calibrate on the material first

Measure the raw takes before planning anything.

- **Speaking rate.** Raw scripted takes typically run 125 to 140 wpm. In a sample reel the raw takes held about 50 s of speech, 110 words (about 132 wpm), with 15 word gaps of 0.5 s or more and 26 of 0.3 s or more. Tightening every gap of 0.3 s or more to 0.12 to 0.18 s gave a 38 to 43 s cut at 155 to 170 wpm. That is the target length band for a script of that size.
- **Structure.** A hook, three numbered points and a payoff with a brand CTA is a listicle. It is made for a numbered-list motion-graphics spine and for "each list item gets its own shot".
- **Caption text versus audio.** ASR and on-camera slips produce wrong word forms (a noun read as an adjective, a dropped "-d"). Captions may tidy grammar and fix spelling; the audio stays as spoken. Shipped in [`reel-captions`](../../skills/reel-captions/SKILL.md) as one correction layer plus a brand dictionary.
- **Orientation.** Some cameras record a portrait shot into a 1920x1080 file with no rotation tag. If the head points to frame right, rotate 90 degrees counter-clockwise (`transpose=2`); check one extracted frame first, and use `transpose=1` if the face comes out upside down. The output then equals the native sensor resolution with no headroom, so every punch-in is a digital upscale (section 4). Shipped in [`reel-ingest`](../../skills/reel-ingest/SKILL.md) (rotation sheet) and [`reel-grade`](../../skills/reel-grade/SKILL.md).
- **Loudness.** A reel mastered at a broadcast-style level (around -23 to -24 LUFS) plays about 10 dB quieter than the reels around it in the feed. Measure the reference and your own output the same way.
- **Rhythm of a delivered reel.** List every visual change (ffmpeg scene score over 0.08 is a quick proxy). A stretch of 10 s or more with no change is exactly where retention graphs fall off. [`craft-research`](../../skills/craft-research/SKILL.md) has `measure_reference.py` for a proper measurement.

## 2. Hook: the first 1 to 2 seconds

The hook has to say what the video is about within 1 to 2 s (Kallaway, quoted secondhand; source not read). Visuals are processed before audio, so the first frame must work on mute. A strong hook stacks three layers at once: visual, on-screen text, spoken line.

1. **Frame 0 is never empty, black or a logo.** Start on motion, on the speaker mid-word if possible. Trim all pre-roll: cut in about 60 ms before the first word.
2. **Text hook on screen by frame 0 to 3** (0 to 120 ms at 25 fps): 3 to 6 words, about 1.4 to 1.8x caption size, in the upper-middle safe zone (y about 300 to 700 px). Pattern: "3 MISTAKES KILLING YOUR <THING>".
3. **Visual hook within 0.5 s:** a punch-in or scale-in on the first stressed word, or a pattern break such as a quick zoom from 100 to 112 % over 6 to 8 frames, or a themed graphic (an icon that catches fire, a red stamp).
4. **Do not cut the first spoken sentence**, but remove or shorten any pause inside it to under 150 ms.
5. **Promise a specific payoff.** "Three mistakes" opens a loop; a visible 3-slot checklist that fills as each point arrives is the retention device for the whole reel.
6. **Sound on frame 0:** a soft riser resolving into an impact or whoosh at the first punch-in, -18 to -22 dBFS peak under the voice, never covering the first consonant.

Shipped: [`reel-director`](../../skills/reel-director/SKILL.md) fails a reel whose first word starts after 0.3 s, that has no hook visual at frame 0, or that has a takeover in the first second.

## 3. Pacing and cut rhythm

### 3.1 Silence and gap removal

| Parameter | Value | Source / reasoning |
|---|---|---|
| Silences worth cutting | gaps of 0.30 s or more always; 0.15 to 0.30 s only at phrase ends after a visual check; never under 0.15 s (mid-phrase) | video-use: 400 ms or more is the cleanest cut, 150 to 400 ms usable with a check, under 150 ms unsafe. AutoCut: 0.3 to 0.5 s minimum silence for natural speech |
| Pre-roll pad (before the first kept word) | 40 to 60 ms (50 ms) | video-use: 50 ms before, 80 ms after, inside a 30 to 200 ms working window |
| Post-roll pad (after the last kept word) | 70 to 100 ms (80 ms); 120 to 180 ms after a sentence-final word or a question | ASR timestamps drift 50 to 100 ms; the pad absorbs it |
| Residual gap after a cut | 80 to 150 ms within a sentence, 150 to 250 ms between sentences, 250 to 400 ms after a list header ("First,") so the graphic lands | *(practice)*: natural cadence instead of machine-gun speech |
| Audio fades at every cut | 30 ms fade in and out (`afade d=0.03`); 10 to 20 ms minimum | video-use hard rule: removes clicks |
| auto-editor equivalent | `--edit audio:threshold=-30dB --margin 0.05s,0.08s` plus a minimum silence of about 0.3 s; the defaults (4 % threshold, 0.2 s margin) are too loose for reels | auto-editor docs, discussion #438 |
| Sanity detector | `silencedetect=n=-35dB:d=0.3` on the denoised voice | *(practice)*: run after denoise so room tone does not hide gaps |

Shipped in [`reel-cut`](../../skills/reel-cut/SKILL.md), after testing: pauses of 0.25 s or more are always tightened; residual gaps of 0.12 to 0.15 s mid-sentence, 0.16 to 0.20 s after a sentence end, about 0.28 s after a list marker; head pad at least 0.05 s, tail at least 0.06 s after the decayed word end. The 30 ms fade-out/fade-in pair was **replaced** by a 16 ms equal-power crossfade centred on the splice, because the fade pair left 40 to 60 ms holes 15 to 25 dB under room tone.

Rules:

- **Cut from word timestamps, not from the waveform alone.** Snap every edge to a word boundary; never cut inside a word.
- **Breaths:** delete audible inhales over about 150 ms between sentences, keep about one short breath per 10 to 15 s so the speaker sounds human, or duck a breath by 10 to 15 dB where deleting it would cause a visual jump *(practice)*. Never leave a breath at the very start.
- **Fillers:** remove "um", "uh", false starts and repeated words. Keep "So" or "And" only when it carries rhythm.
- **Target rate after cuts:** 155 to 175 wpm. Above about 185 wpm, B2B viewers stop parsing technical terms. Leave 200 to 300 ms after a dense acronym and let the graphic carry it.
- **Do not speed-ramp the voice above 1.05 to 1.08x** *(practice)*: pitch artefacts and a synthetic-voice feel appear. herk-edit-kit goes further: never speed the voice up.

### 3.2 Cut rhythm and shot length

- Common heuristic: a visual change every 1.5 to 3 s in the hook, every 2 to 4 s after it. Looser guides allow 3 to 5 s; one vendor says never hold a static talking head over about 4 s. The data is vendor-grade, and Emplifi found slow starts are not automatically worse. House rule: **no static frame longer than 4 s.**
- A visual change can be a jump cut, a punch-in or out, a caption style change, a graphic, a B-roll insert, a reframe or a colour flash. Not every change needs a hard cut, but something must change.
- Vary the rhythm: two short beats, then a longer one. A metronome feels robotic.
- Hold slightly longer (3 to 4 s) on the payoff line and the CTA.

Shipped: [`reel-director`](../../skills/reel-director/SKILL.md) plans one visual event every 1.5 to 2.5 s and fails any gap over 4 s.

## 4. Punch-in zooms

| Parameter | Value |
|---|---|
| Scale steps, 1080-wide source (no headroom) | base 100 %, medium 108 to 110 %, close 115 % max. On 4K source, 130 to 150 % is fine |
| Scale steps, 4K source or output cropped from a taller frame | 100 / 120 / 140 % |
| Hard punch (cut-based) | change scale on the jump cut itself, alternating 100, 110, 100. This hides the jump and is the main reason punch-ins exist (Adobe on jump cuts) |
| Animated push (emphasis) | 100 to 106-110 % over 6 to 10 frames (240 to 400 ms), ease-out (`cubic-bezier(0.16,1,0.3,1)` or `power3.out`), starting 3 to 8 frames before the stressed word (CapCut keyframe guide) |
| Slow creep (calm sections) | 100 to 104 % over 3 to 5 s, linear or sine in-out; keeps a static shot alive |
| Frequency | one scale event per 2 to 4 s, never two in a row in the same direction, anchored to sentence starts and stressed words (Vizard: sparse punch-ins when they "cycle too fast") |
| Framing | eyes on the upper-third line (y about 600 to 700 px of 1920); zoom toward the face centre, not the frame centre |
| Do not | combine a big zoom with a big reframe at the same moment (floaty); zoom during a caption pop (two competing motions); punch in on every cut |

When a graphic needs space, zoom out (or shrink the speaker to about 70 % and move them down) and give the upper half to the graphic; return with a punch-in when it leaves.

Shipped in [`reel-motion`](../../skills/reel-motion/SKILL.md): `push` is +0.04 to +0.06 over 8 frames, starting 3 to 6 frames before the word, at most one per 3 s; cuts alternate punch states at least 0.03 apart (forced step 0.06); total scale is clamped to `maxScale` 1.20 by default (at most 1.30; above 1.20 the upscale softens, so check stills per camera body). Do zooms in the renderer, not with ffmpeg `zoompan` (it jitters, see [motion-benchmark.md](motion-benchmark.md)).

## 5. J-cuts and L-cuts

- **J-cut:** the next shot's audio starts 4 to 8 frames (160 to 320 ms) before its picture. Use it going into B-roll or a graphic so the voice leads.
- **L-cut:** the speaker's audio runs 4 to 8 frames over the next picture. Use it coming out of a talking-head beat into a UI mockup.
- With one continuous voice track, J and L cuts mostly apply to cutaways: bring a full-screen graphic in 3 to 6 frames after the keyword (L), or 2 to 4 frames before it (J, which reads as inevitable; herk-edit-kit leads the visual about 0.2 s ahead on punchlines).
- Keep room tone and music continuous across every cut, so the bed never drops out at a splice.

## 6. Pattern interrupts

An interrupt is any change big enough to re-trigger attention. Schedule one every 4 to 6 s, plus a big one at each structural boundary (each list item, the payoff):

- full-screen graphic takeover (0.8 to 1.5 s) or a split layout (speaker bottom, graphic top)
- a caption style change for one key line (bigger, a different colour, a highlight box)
- a B-roll or UI insert (an admin console, a DNS record table, an inbox placement test)
- a camera move: punch-in, zoom-out, a quick 2-frame whip
- sound: a pop or whoosh with a matching visual (never an SFX without a visual)
- a brand colour wipe for 4 to 6 frames between list items
- a counter tick ("1/3" becomes "2/3" with a check mark)

No more than one big interrupt per 2 s, and at least one interrupt in every 6 s window.

## 7. Kinetic captions

### 7.1 Style (Hormozi and Kallaway family, tuned for B2B)

| Property | Value |
|---|---|
| Font | heavy geometric sans, all caps: Montserrat ExtraBold/Black (800 to 900), Anton or Inter Black. Inter and Montserrat read more "SaaS" than Anton |
| Size | 64 to 80 px cap height on 1080x1920; emphasis words 1.15 to 1.25x |
| Words on screen | 1 to 3 words per chunk in punchy hooks, otherwise 3 to 5 words on at most 2 lines, about 15 characters per line (Submagic preset). Grow a chunk to 3 words rather than flash one shorter than 0.35 s (video-use) |
| Timing | word-by-word reveal locked to word timestamps; each word appears 0 to 1 frame before its audio onset; a chunk stays until the next starts, no gaps or flicker |
| Base colour | white |
| Keyword highlight | one brand accent per chunk; highlight the nouns and numbers that carry meaning (the topic, the count, the named mistake, acronyms, the brand name) |
| Legibility | black stroke 6 to 10 px or a soft shadow (`0 4px 12px rgba(0,0,0,.6)`), not both at full strength. Modern B2B alternative: a rounded pill in brand colour behind the active word, radius 16 to 24 px |
| Animation | pop-in: scale 80 to 105 to 100 % over 120 to 200 ms (ease-out back); bounce only on keywords |
| Emojis | at most 1 per 8 to 10 s for B2B; prefer brand-drawn icons (shield, envelope, warning) |
| Case and grammar | uppercase; fix ASR errors and slips in the text; no trailing full stops; keep "?" on the hook |

herk-edit-kit's measured house style agrees: 1 to 3 words split on phrase boundaries, appearing 2 frames early, ExtraBold caps about 62 to 64 px, colour on 25 to 45 % of chunks by meaning, one boxed style for the whole reel, never white on a light background, never over the mouth or chin.

Shipped in [`reel-captions`](../../skills/reel-captions/SKILL.md): pages of at most 3 words in the hook and 4 after it, at most 2 lines of 22 characters, no page under 0.35 s, each word visible 1 frame before its onset, layout reserved from the first frame so lines never re-centre. A kinetic style (1 to 3 words, 100 px, a pill behind the active word) is an option; the pill read better than coloured text on a light wall.

### 7.2 Safe zones (1080x1920)

| Platform | Top | Bottom | Left | Right | Content box |
|---|---|---|---|---|---|
| Instagram Reels | 210 px | 310 px (more with a long audio title) | about 0 to 60 px | 84 to 90 px | x 0 to 996, y 210 to 1610 |
| TikTok | 108 px (plus the tabs) | 320 px (370 px for ads; 300 to 350 with captions shown) | 60 px | 120 px | x 60 to 960, y 108 to 1600 |
| YouTube Shorts | 120 px | 300 px (360 with the description open) | about 0 | 96 px | x 0 to 984, y 120 to 1620 |
| **Universal** | **220 px** | **380 px** | **70 px** | **130 px** | **x 70 to 950, y 220 to 1540** |

- Centre captions at y about 1150 to 1300 px (60 to 68 % down): below the chin, above all bottom UI. Never in the bottom 380 px.
- Keep the eyes at y about 600 to 750 px so headline graphics can live at y 250 to 550 without covering the face.
- Keep CTAs, URLs and logos clear of the right-hand action column (x over 950).

Shipped in [`reel-motion`](../../skills/reel-motion/SKILL.md) and [`reel-captions`](../../skills/reel-captions/SKILL.md): the safe box is x 70 to 950, y 220 to 1500 (the bottom 420 px stays clear, not 380), captions centre at y 1180 in talk mode and y 1060 over a card.

## 8. Motion graphics overlays

### 8.1 Timing and easing

- **Entrances 200 to 400 ms, ease-out** (`cubic-bezier(0.16,1,0.3,1)`, GSAP `power3.out` or `expo.out`). **Exits 150 to 250 ms, ease-in**, faster than the entrance. Material, Fluent and web.dev all sit in the 200 to 500 ms band: 200 to 300 for small UI, up to 500 for big reveals.
- Overshoot (back-out, 3 to 8 %) only on icons and stamps, never on text blocks.
- Stagger list items and words 60 to 120 ms apart (a 0.35 s cinematic word stagger is too slow for a reel).
- Hold every graphic long enough to read: **about 0.3 s per word + 0.5 s**. A 4-word callout needs about 1.7 s.
- Lead the visual by 2 to 5 frames on punchlines; otherwise land on the keyword's first frame.
- Motion blur on fast moves (whips, fly-ins) hides the cut and adds energy.
- **Palette cap:** 3 to 5 active hues, each with a meaning (herk-edit-kit: "palette is symbolic"). For example brand primary = the solution, red = mistake or danger, green = fixed or safe, white = information. See [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) for one worked brand.

motionmaxxing's measured laws tighten this: most travel in the first 4 to 8 frames then a long tail, median move about 10 frames at 30 fps, at most one visible spring per film, arrivals decelerate from oversize (nothing grows from zero), words land 0 to 2 frames before they are heard.

### 8.2 Graphic types

| Graphic | Spec | Typical use in a list reel |
|---|---|---|
| Numbered list / counter (the spine) | big numeral 240 to 360 px ("01", "02", "03") slides in with a headline; a persistent mini-counter (3 dots or "1/3") top-left inside the safe zone | each "First / Second / Third" |
| Callout / headline card | 2 to 6 words, 90 to 120 px, brand pill or glass card (blur 14 px, 1 px border), above the head (y 250 to 550) | the name of each point |
| Icon pop | 120 to 200 px line icon, scale-in with 5 % overshoot plus a pop SFX | warning, shield, envelope, flame, check |
| Stamp | rotated -8 to -12 degrees, red, 0.25 s scale 140 to 100 % with an impact SFX and a 2-frame shake of 3 to 6 px | "BLOCKED", "SPAM" |
| Data / stat chip | big number plus label, tick-up over 400 to 600 ms | only with an approved number; otherwise relative bars |
| UI mockup | rebuilt (not screenshot) cards: admin console, DNS records, inbox versus spam, a reputation meter going red to green | the technical points (section 9) |
| Lower third | name/role or brand, 0.6 s in, hold 2.5 to 3 s, left-aligned at y about 1350 to 1450, above the bottom safe zone | optional, first 3 to 5 s, builds trust |
| Progress bar | 6 to 10 px tall at the top of the safe area (y about 220), or segmented into one slot per point | makes the "3 points" promise visible |
| Logo / end card | hold 2 to 3 s minimum ("hold the hero shot") | final beat |

Layout rule: with a full graphic on screen, either shrink the speaker into the lower 55 % (picture in picture) or cover the speaker for at most 1.5 s with an L-cut so the voice carries. Never cover the face on a punchline.

Conflict to know about: motionmaxxing's never-ship list bans page chrome such as "01 / 03" counters and progress bars. In a list reel the numbers are the content, so use them as large content type tied to the spoken "First / Second / Third", not as HUD chrome.

Shipped in [`reel-motion`](../../skills/reel-motion/SKILL.md) as Talk, Card and Takeover layouts with a takeover cap of 1.5 s.

## 9. B-roll and UI mockups for a B2B brand

- Generic stock B-roll ("person typing", "server room") underperforms for founder-led B2B, and one SaaS guide argues that cinematic polish can hurt. **Product-truthful UI beats stock.**
- Build vector or HTML-rendered mockups (Remotion), not screenshots: they stay sharp, on brand and animatable. Patterns that work for an email-infrastructure topic: two cards side by side (a risky option with red flags versus the safe one with a shield); a send-volume line with a spike and a reputation gauge dropping into red, then the correct ramp; a DNS record table whose rows tick green one by one on the spoken acronyms (stagger at the word timestamps); an email card flipping from Inbox to Spam.
- Never invent numbers, prices, quotes or results on a mockup (Barty-Bart). Use relative bars or labels from the transcript, or numbers the brand has approved.
- Cursor moves: ease-in-out, 400 to 700 ms per move, a 150 ms click pulse ring. Zoom into the relevant UI region by 120 to 150 % (vector UI scales freely).
- Keep UI text at **36 px or larger** on the 1080 canvas (video-use flags 28 px as unreadable at phone size).

## 10. Sound design

Levels are relative to a voice peaking around -6 to -3 dBFS in a -14 LUFS mix.

| Layer | Level | Notes |
|---|---|---|
| Voice | reference; the whole mix normalised to -14 LUFS integrated | always the loudest element |
| Music bed | 20 to 28 dB below the voice (about -28 to -32 LUFS short-term under speech); sidechain duck 4 to 8 dB, attack 10 to 30 ms, release 250 to 400 ms; up 3 to 6 dB in gaps and on the end card | no universal number exists, tune by ear. Instrumental, 100 to 125 BPM, sparse low-mids (keys, plucks, light percussion) so it does not mask 1 to 4 kHz |
| Whooshes | -18 to -10 dBFS peak, 150 to 400 ms; peak-align the climax to the cut or the move's fastest frame (reverse whooshes start about 0.8 s early) | never louder than the voice |
| Pops / clicks | -20 to -14 dBFS, 30 to 80 ms, on text and icon appearances | pop = text, whoosh = motion, impact = stamp or reveal |
| Risers | -24 to -16 dBFS, 0.8 to 2 s, resolve into an impact on the hook word or the CTA | at most 2 per reel |
| Impacts / hits | -16 to -10 dBFS, low-passed sub hit for stamps | at most 3 per reel |
| Comic SFX | 0 to 1 per reel for B2B | |

Sources disagree on the bed: video-use ducks 12 to 15 dB under speech, herk-edit-kit sits the bed about 11 dB under the voice (9 to 14). video-use also finds about 8 SFX in 18 s reads as designed and 20 reads as stock.

Rules:

- Every SFX needs a visual partner, and every big visual event gets an SFX. Place them at real events, not on a timer.
- Keep SFX out of the first 50 ms of a word's consonant; shift 1 to 2 frames earlier if they mask speech. Measure each effect's attack and start it early so the transient hits the frame.
- About 15 to 30 small cues in a 40 s reel; vary samples (3 to 4 pop variants) to avoid repetition.
- Duck the music 2 to 3 dB under impacts so they read.

Shipped in [`reel-sound`](../../skills/reel-sound/SKILL.md): bed 10 LU under the voice, a word-keyed duck of 6 dB (no pumping, unlike a sidechain), per-word voice to bed + SFX margin with a median of 15 dB or more, and a -14 LUFS / -1.5 dBTP master.

## 11. Voice processing chain

Order (Rode, B&H, MacSales, ffmpeg-user and the editing repos agree): **high-pass, denoise, de-click/de-breath, subtractive EQ, de-ess, compression, presence/air EQ, limiter, loudness normalise.** De-ess before the compressor if sibilance triggers it.

| Stage | Setting |
|---|---|
| High-pass | 80 to 100 Hz, 12 to 18 dB/oct (male 80 to 90 Hz, female 100 to 120 Hz) |
| Denoise | gentle: `afftdn` with `nf` set from the measured floor, or RNNoise `arnndn`, or `noisereduce` (prop_decrease 0.6 to 0.8) with a room-tone profile. Over-denoising sounds underwater; aim for 10 to 12 dB of reduction |
| Mud cut | -2 to -4 dB, Q about 1.0 to 1.4, at 200 to 400 Hz (sweep to find the boxy frequency) |
| Nasal / harsh cut | -2 dB around 800 Hz to 1.2 kHz, or narrow at 2.5 to 3 kHz, only if needed |
| De-esser | 5 to 8 kHz (male 5 to 7, female 6 to 8), 3 to 6 dB on "s" peaks; ffmpeg `deesser=i=0.4:m=0.5:f=0.5:s=o` (`f` is normalised) |
| Compressor | 3:1 to 4:1, 4 to 8 dB of gain reduction on peaks, attack 5 to 15 ms, release 60 to 150 ms |
| Presence | +2 to +3 dB broad (Q about 0.8) at 3 to 5 kHz; optional air shelf +1.5 to 2 dB at 10 to 12 kHz |
| Warmth | +1 to +2 dB shelf at 120 to 150 Hz only for a thin voice |
| Limiter | ceiling -1.0 dBTP (-1.5 for safety after AAC), 1 to 2 dB of reduction at most |
| Loudness | -14 LUFS integrated on the final mix (voice + music + SFX), LRA 6 to 9 LU for talking head, TP -1.0 to -1.5. Two-pass loudnorm, and measure the final encoded MP4, not the WAV |

Sources split between -14 (social and short-form guides, video-use) and -16 LUFS (podcast norms); platforms publish no official Reels or TikTok target. Ship -14 LUFS / -1.5 dBTP or lower: louder files get turned down, quieter ones simply play quiet.

Starting chain (48 kHz mono voice, tune by ear):

```
highpass=f=85:poles=2,
afftdn=nr=12:nf=-35:tn=1,
equalizer=f=300:t=q:w=1.2:g=-3,
deesser=i=0.4:m=0.5:f=0.5:s=o,
acompressor=threshold=-20dB:ratio=3.5:attack=8:release=100:makeup=4dB,
equalizer=f=4000:t=q:w=0.8:g=2.5,
highshelf=f=11000:g=1.5,
alimiter=limit=0.89:attack=5:release=50
```

then, on the final mix, the second loudnorm pass: `loudnorm=I=-14:TP=-1.5:LRA=9:measured_I=..:measured_TP=..:measured_LRA=..:measured_thresh=..:offset=..:linear=true`.

Phone speakers roll off below about 200 Hz, so presence (2 to 5 kHz) carries intelligibility. Check on a phone speaker and on earbuds.

Shipped in [`voice-clean`](../../skills/voice-clean/SKILL.md), which **revised this chain** after measuring real clips: compression lifts the room tone once the mix is normalised, so a quiet room gets no denoiser, gentle 2:1 compression and a soft downward expander instead; `afftdn` tracking mode (`tn=1`) is not used (it raised musical noise); DeepFilterNet with a 10 dB attenuation limit is the preferred denoiser for harder noise; filter latency is compensated; the voice is never normalised on its own. See its [denoisers reference](../../skills/voice-clean/references/denoisers.md).

## 12. Colour

Order: **exposure and contrast, then white balance, then skin, then look, then vignette** (Adobe, Frame.io and video-use's CDL mental model).

| Step | Target |
|---|---|
| Exposure | skin highlights at about 60 to 70 IRE (luma 150 to 180 of 255); nothing important clipped; blacks at 2 to 5 IRE, not crushed |
| Contrast | gentle S-curve: shadows -3 to -5 %, highlights +3 to +5 %; `eq=contrast=1.05-1.10` |
| White balance | neutralise a white or grey reference (wall, shirt) so R, G and B match there; then warm slightly (about +100 to 300 K equivalent, or `colorbalance` moves of 0.02 to 0.05) for a friendly B2B feel |
| Skin | skin hues sit on the vectorscope skin-tone line (about 123 degrees, the I-line); sample cheek and forehead and nudge hue onto it; do not over-saturate skin |
| Saturation | +5 to +10 % overall (`eq=saturation=1.05-1.10`) with skin protected; pull down distracting background colours |
| Look | very light: a subtle warm-highlight / cool-shadow split, or a neutral punch (contrast + gentle S-curve, no hue shifts). Skip heavy teal-orange for B2B |
| Sharpen | `unsharp=5:5:0.5:5:5:0` after scaling to the output size (offsets platform compression) |
| Vignette | `vignette=angle=PI/5`, 10 to 20 % darkening at the corners, centred on the face; it should go unnoticed |
| Range | many cameras record full-range `yuvj420p`. Convert explicitly to limited (tv) `yuv420p` once, or blacks and whites shift on the platforms |

Grade per segment during extraction, or once on the base layer before graphics. Never grade on top of brand graphics (it shifts brand colours).

Shipped in [`reel-grade`](../../skills/reel-grade/SKILL.md): per-clip and per-segment tone curves, cheek-patch level matching across jump cuts, and exactly one explicit full-to-tv conversion with a legal clamp.

## 13. CTA and end card

- One CTA only: either a URL or offer line, or a comment-keyword CTA ("Comment <WORD> and I'll send the checklist"), which boosts engagement and enables DM automation. Use only offers the brand has approved.
- On screen in the last 3 to 5 s, announced by the spoken line. Animate the logo in on the spoken brand name (lead by about 3 frames), then add a URL or handle chip.
- The text CTA must work muted: logo + 3 to 6 word line + URL, at 60 to 80 px, inside the universal safe box. Keep the bottom 380 px clear.
- Hold the end card 2.0 to 3.0 s; the music swells 3 to 6 dB.
- **Loop trick:** end on a frame and sound that flow back into the hook (the end card wipes to a frame matching the first shot, or the last words lead into the first). Loops push average watch time over 100 % *(practice)*.

Brand rules for logos and CTAs: [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md).

## 14. Export

| Setting | Value |
|---|---|
| Resolution | 1080x1920, SAR 1:1 |
| Frame rate | keep the source rate (for 25 fps footage, deliver 25 fps; never mix 25 and 30 in one timeline). 30 fps is the generic advice but conversion adds judder |
| Video | H.264 (libx264) High, level 4.1 to 4.2, `yuv420p` limited range, BT.709 tags, progressive |
| Rate control | `-crf 18 -maxrate 16M -bufsize 32M`, or 2-pass at 10 to 16 Mbps. Platforms re-encode, so a clean high-bitrate file helps. Guides range from 3.5 to 5 Mbps (SocialPilot) to 8 to 16 Mbps (online-tech-tips); about 5 Mbps works but leaves less headroom |
| GOP | keyframe every 2 s (`-g 50 -keyint_min 25` at 25 fps), `-bf 2` |
| Audio | AAC-LC, 48 kHz, stereo, 192 to 320 kbps |
| Container | MP4 with `-movflags +faststart` |
| Length | 30 to 60 s; a three-point script lands at about 38 to 45 s |

```
ffmpeg -i master.mov \
  -vf "scale=1080:1920:flags=lanczos:out_range=tv,format=yuv420p" \
  -c:v libx264 -preset slow -profile:v high -level 4.2 -crf 18 -maxrate 16M -bufsize 32M \
  -g 50 -keyint_min 25 -bf 2 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
  -c:a aac -b:a 256k -ar 48000 -ac 2 \
  -movflags +faststart -r 25 out.mp4
```

Then verify: `ffprobe` the streams, run `ebur128=peak=true` on the MP4 (I = -14 within 1 LU, TP at most -1.5 dBTP, LRA at most 7 LU), and step through every cut at plus or minus 1.5 s.

Shipped in [`reel-export`](../../skills/reel-export/SKILL.md) (High 4.2, CRF 18 capped at 16M, AAC 256k, BT.709 tv, faststart, never `-shortest`, an ffprobe spec gate).

## 15. Listicle beat template (about 40 s)

For a script of hook + three points + payoff and CTA. Times are output times after gap tightening; scale them to your script.

| Out time | Beat | Picture | Captions / graphics | Sound |
|---|---|---|---|---|
| 0.0 to 0.2 | Cold open | speaker at 108 %, cut in 60 ms before the first word | hook headline slams in (scale 130 to 100 %, 200 ms); a themed stamp or icon | riser tail into an impact on the first stressed word |
| 0.2 to 4.8 | Hook line | punch back to 100 % on a stressed word; generic icon chips fly in (no third-party trademarks) | word-by-word captions with 2 or 3 keywords highlighted | pops on chips, bed enters |
| 4.8 to 6.8 | Open loop | push 100 to 110 % on the count ("three ...") | "3 <THINGS>" plus a 3-slot progress bar that stays all reel | whoosh |
| 6.8 to 14.5 | Point 1 | big "01" and headline; split layout, then a mockup | highlight the point's key nouns | whoosh in, a pop per detail, slot 1 fills |
| 14.5 to 22.5 | Point 2 | "02" and headline; a chart or gauge; punch-in on the strongest line | highlight | riser on the build, low hit at the drop |
| 22.5 to 31.5 | Point 3 | "03" and headline; a table or checklist ticking on the spoken terms | highlight the terms | tight clicks on each term, whoosh on any flip |
| 31.5 to 37.0 | Payoff | full-screen speaker, slow creep 100 to 104 %; progress bar completes | payoff headline | bed lifts 2 dB |
| 37.0 to 41.5 | CTA | logo lock-up on the spoken brand name (lead 3 frames), CTA chip | CTA line | impact on the logo, music swell, loop-friendly tail |

Checks for this shape: no pause over 0.3 s left, 250 to 400 ms kept after each list marker so the numerals land, no 4 s window without a visual change (the back half of a reel is where edits most often go static), captions spell every term and the brand name correctly.

The beat sheet and its audit are tools in [`reel-director`](../../skills/reel-director/SKILL.md) (`beat_sheet.py`, `beat_audit.py`).

## 16. Self-review checklist (on the rendered MP4)

1. First frame: is something moving, and is text visible by 0.12 s? Is the topic clear within 1 to 2 s on mute?
2. Cuts: no clipped word starts or ends, no clicks, no doubled words, no gap over 0.3 s left unintentionally.
3. Rhythm: list every visual change; the largest interval is 4 s or less.
4. Captions: in sync within 1 frame, inside y 220 to 1500 and x 70 to 950, no chunk under 0.35 s, every term and the brand spelled correctly.
5. Graphics: all text 36 px or larger, on screen long enough (0.3 s per word + 0.5 s), never covering the face on a punchline.
6. Audio: ebur128 I = -14 within 1 LU, TP at most -1.5 dBTP; voice intelligible on a phone speaker; music not masking; no SFX louder than the voice.
7. Colour: skin on the skin-tone line, no clipped highlights on the face, limited range tagged BT.709.
8. Export: H.264 High, yuv420p, 1080x1920, source frame rate, AAC 48 kHz, faststart.
9. A fresh critic pass by a reviewer who has not seen the plan, told to "roast, not praise", with timecodes (video-use workflow step 7).

Automated in [`reel-qa`](../../skills/reel-qa/SKILL.md) (`qa.py` and the scored critic prompt).

## 17. Tutorials (YouTube)

Found with `yt-dlp "ytsearchN:<query>" --flat-playlist`; views as of 2026-11-24. Subtitles could not be fetched (see the [README](README.md)), so these are a reading queue, not a source of the rules above.

| # | Channel | Title | Views | URL |
|---|---|---|---|---|
| 1 | Kallaway | Give me 15 mins, and I'll make your hooks impossible to skip | 1.21M | https://www.youtube.com/watch?v=2byPP_9F0-Q |
| 2 | Learn By Leo | How to edit SO good your viewers get addicted to your videos | 6.12M | https://www.youtube.com/watch?v=sLgHqZSe2o0 |
| 3 | Joseph, Video Editing | The Ultimate Guide to Master Short-Form Video Editing! | 754K | https://www.youtube.com/watch?v=R9Uu0JtvyMg |
| 4 | Joseph, Video Editing | How to Edit Viral Instagram Reels using ONLY Premiere Pro! | 791K | https://www.youtube.com/watch?v=jAvNgpcdD5k |
| 5 | Joseph, Video Editing | How to Edit VIRAL Instagram Talking Head Videos (NEW Style for 2025!) | 412K | https://www.youtube.com/watch?v=Qbntd8yud0o |
| 6 | Joseph, Video Editing | How to Edit Viral Alex Hormozi Reels in Premiere Pro! | 67K | https://www.youtube.com/watch?v=pelJlYOkn7s |
| 7 | Joseph, Video Editing | How to Edit Viral SaaS Animations in 2026 | 276K | https://www.youtube.com/watch?v=zWbLfFA9l8s |
| 8 | Think Media | How to Edit Talking Head Videos: 5 Video Editing Tips & Tricks | 196K | https://www.youtube.com/watch?v=xCl_zqJdjAc |
| 9 | TomsProject | How to Edit Viral Talking Head Videos Like Kallaway (2026 Guide) | 51K | https://www.youtube.com/watch?v=aNwKDaTag2Q |
| 10 | Usman Explains | Talking Head Motion Graphics Reel Breakdown In Premiere Pro | 138K | https://www.youtube.com/watch?v=uW-8SKO8kYE |
| 11 | (zoom-cut tutorial) | The Zoom Cut That Makes Talking Head Videos Pop | n/a | https://www.youtube.com/watch?v=MNWbIZ7MNoA |
| 12 | (jump-cut tutorial) | The Jump-Cut Mistake Making Your Videos Look Amateur | n/a | https://www.youtube.com/watch?v=KtICyJV7gDc |
| 13 | Taiyology | How to pace your videos SO good your viewers can't click off! | 44K | https://www.youtube.com/watch?v=aZ4jehTzoQw |
| 14 | DecodingYT | 6 Editing Hacks to Make ADDICTIVE YouTube Videos! | 685K | https://www.youtube.com/watch?v=EFLIUm3-ewA |
| 15 | Matt Loui | How to Edit Captions for Reels and Shorts like Alex Hormozi for FREE | 39K | https://www.youtube.com/watch?v=EQUyZC_cd0s |
| 16 | In The Mix | Make Your Voice Sound Better: Vocal EQ Zones | 1.24M | https://www.youtube.com/watch?v=pjMCyLsRNig |
| 17 | Joe Gilder, Home Studio Corner | How to Mix Spoken Word Vocals in 2 Minutes | 37K | https://www.youtube.com/watch?v=5N_xNbsjbXE |
| 18 | Joe at Claricast | EQ and Compression for Podcast Vocals | 11K | https://www.youtube.com/watch?v=CUPtHj5c1No |
| 19 | Denz Creates | How I Color Grade My Talking Head Shots | 8.6K | https://www.youtube.com/watch?v=3cZz_zhvRHw |
| 20 | AniThing | COLOR GRADING Secrets for YOUTUBE INDOOR VIDEOS | 201K | https://www.youtube.com/watch?v=Cjt17eJXUUo |

Also relevant: Ryan Herrick, How I Make Viral Talking Head Reels In DaVinci Resolve (https://www.youtube.com/watch?v=u9hrrZhkXmw); Vlad Sateev, How to Edit Viral Talking Head Reels in Premiere & After Effects (https://www.youtube.com/watch?v=wkWkHwFKcNE); Hamza Visualz, How to Edit Viral Instagram Reels from Scratch (After Effects 2026) (https://www.youtube.com/watch?v=vNAbF3dGONQ); Jason Yadlovski, DaVinci Resolve 20 Audio: Clean Up Dialogue (https://www.youtube.com/watch?v=8DPTayE7sus); Patrik Key, 10 VIRAL Caption Styles Using CapCut (https://www.youtube.com/watch?v=Q04FF5KZyt4); Usman Explains, How to Create Motion Graphics Talking Head Reels in After Effects (https://www.youtube.com/watch?v=msJ3HRuCjF0).

## 18. Written sources

- Safe zones: AdaptlyPost https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide ; TryMyPost https://www.trymypost.com/blog/instagram-reels-safe-zones-text-placement-2026 ; House of Marketers https://houseofmarketers.com/?p=9120 ; Kapwing https://www.kapwing.com/video-editor/instagram-reels/safe-zone
- Captions: Submagic https://www.submagic.co/blog/how-to-make-alex-hormozi-captions ; SendShort https://sendshort.ai/guides/hormozi-captions/ ; Blitzcut https://blitzcutai.com/blog/best-caption-colors-tiktok
- Silence removal: auto-editor https://pypi.org/project/auto-editor and discussion #438 https://www.github.com/WyattBlue/auto-editor/discussions/438 ; AutoCut https://www.autocut.com/blogs/autocut-silences-parameters
- Punch-ins and jump cuts: Adobe https://www.adobe.com/creativecloud/video/post-production/cuts-in-film/jump-cut ; CapCut keyframes https://cursa.app/en/page/keyframes-in-capcut-smooth-zooms-reframes-and-motion-that-follows-the-subject ; Vizard https://agent.vizard.ai/how-to/stop-the-punch-ins-cycling-too-fast-in-a-talking-head-edit.html ; AutoClip https://autoclip.dev/blog/punch-in-zoom-crop-zoom-speaker-zoom-guide ; PremiumBeat https://www.premiumbeat.com/blog/mastering-zoom-and-punch-in
- J and L cuts: Vimeo https://vimeo.com/blog/post/j-cuts-l-cuts ; TechSmith https://www.techsmith.com/blog/video-cuts-you-should-know/
- Pacing: Opus Clip https://www.opus.pro/blog/ideal-instagram-reels-length ; Emplifi https://emplifi.io/?p=23678 ; Medium https://medium.com/@techwithlandon/want-over-70-retention-on-your-short-form-videos-heres-how-to-do-it-5ce7bae94a43
- Hooks: Buffer https://buffer.com/resources/good-hooks/ ; Socialk.it https://socialk.it/en/blog/video-hooks-first-three-seconds ; Opus https://www.opus.pro/blog/the-science-of-hooks
- Voice processing: Rode https://rode.com/en/about/news-info/a-guide-to-audio-processing-and-fx-for-podcasting ; B&H https://www.bhphotovideo.com/explora/audio/tips-and-solutions/7-tips-mixing-stellar-podcast-vocals ; ffmpeg-user https://lists.ffmpeg.org/pipermail/ffmpeg-user/2021-January/051591.html ; ffmpeg audio filters https://ayosec.github.io/ffmpeg-filters-docs/7.1/Filters/Audio
- Loudness: OpenClip https://openclip.app/learn/audio-normalization ; Fora Soft https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026
- Mix levels and SFX: Epidemic Sound https://epidemicsound.com/blog/how-to-get-the-volume-right-in-your-videos ; Storyblocks https://www.storyblocks.com/resources/tutorials/7-essential-audio-editing-tips ; Descript https://www.descript.com/blog/article/pro-tips-for-using-edited-sound-effects-in-your-videos ; Boris FX https://borisfx.com/blog/what-is-audio-ducking-and-how-is-it-used/
- Motion timing: web.dev https://web.dev/choosing-the-right-easing/ ; Microsoft Fluent https://learn.microsoft.com/en-us/windows/apps/design/motion/timing-and-easing ; Material https://m1.material.io/motion/duration-easing.html
- Colour: Frame.io https://blog.frame.io/2020/10/05/skin-tones-in-davinci-resolve/ ; Adobe https://helpx.adobe.com/premiere-pro/how-to/correct-skin-tones.html ; No Film School https://nofilmschool.com/color-grading-skin-tone-secrets
- Export: SocialPilot https://www.socialpilot.co/insights/social-media-video-sizes-cheat-sheet ; online-tech-tips https://www.online-tech-tips.com/premiere-pro-export-settings-tiktok-instagram-reels-youtube-shorts/ ; Sprout Social https://sproutsocial.com/insights/social-media-video-specs-guide/
- B2B short form: Oktopost https://www.oktopost.com/blog/short-form-video-b2b-marketing-trust/ ; Opus https://www.opus.pro/blog/short-form-content-strategy-for-b2b ; Trupeer https://www.trupeer.ai/blog/linkedin-video-strategy-for-b2b-saas-what-formats-and-lengths-work
- Open-source editing skills read (not executed): [browser-use/video-use](https://github.com/browser-use/video-use) (cut craft, hard rules, subtitles, grade), [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) (motion laws, word reveal timing, reel pacing), hassancs91's YouTube editor skills (`gh repo list hassancs91`: SFX vocabulary, peak alignment, ducking), [Tejashmakwana/motionmaxxing](https://github.com/Tejashmakwana/motionmaxxing), [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics).
