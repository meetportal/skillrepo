# Stage defaults from the plan

The numbers the plan set for each stage, generalised from the first reel. They are a starting point with their reasons. Where the first build changed one, it is marked and explained in [revisions.md](revisions.md); the skill linked in each section holds the current value.

## Cut ([`reel-cut`](../../skills/reel-cut/SKILL.md))

1. Cut only between words, on word edges snapped to the audio (later: force-aligned). Never inside a word. A spoken slip is fixed in the caption text, never by cutting into the word.
2. Pauses of 0.25 s or more are always tightened. Pauses of 0.15 to 0.25 s only when a blink or blur sits in them. Under 0.15 s never touched.
3. Residual gap after a cut: about 0.12 s mid-sentence (60 ms tail + 60 ms lead), 0.16 to 0.20 s after a sentence end or a question, about 0.28 s after a list marker so a title slam can land.
4. Head pad at least 50 ms before a word onset (40 ms at clip joins), tail at least 60 ms after the snapped end (the snap already includes the decay).
5. Audio splices: 30 ms afade out and in. **Revised** to a 16 ms equal-power crossfade.
6. Video and audio edges may differ at a splice (J/L cut) as long as each range keeps equal video and audio durations. The EDL carries `v_in`/`v_out` and `a_in`/`a_out`. Typical uses: the picture leaves a take before a blink while the sound finishes the word (L-cut), or the next take's sound starts under the previous picture so a blink at the head of a take is never shown (J-cut).
7. Render all ranges in one `filter_complex` (`trim,setpts` / `atrim,asetpts` / `concat`). Gate: video and audio durations equal within 1 frame, and equal to the EDL total within 1 frame.
8. No `atempo`, no speed change.

Why a breath after list markers: in the source takes the speaker usually ran straight from the marker into the item. A title slam needs about 7 frames to read; without the extra pause it lands on top of the next word.

## Voice ([`voice-clean`](../../skills/voice-clean/SKILL.md))

The plan's chain, chosen because it had the lowest measured floor on two test clips (room tone 38 to 44 dB below speech after normalisation) and de-essing brought loudnorm into linear mode:

```
highpass=f=80:poles=2,
afftdn=nr=10:nf=-58:tn=1,
equalizer=f=250:t=q:w=1.0:g=-2,
equalizer=f=3500:t=q:w=1.2:g=2.5,
deesser=i=0.5:m=0.5:f=0.5:s=o,
acompressor=threshold=-22dB:ratio=3:attack=5:release=90:makeup=1:knee=4,
agate=threshold=0.003:ratio=2:range=0.25:attack=5:release=150
```

**Revised**: tracking `afftdn` (`tn=1`) and this gate were replaced by a no-denoiser default with a soft downward expander for quiet rooms. Keep these principles from the plan:

- Diagnose the noise type before choosing a denoiser (stationary hiss, handling rustle, broadband).
- Set `afftdn nf` from the measured floor, not from a guide.
- Run per clip so the most sibilant take can get stronger de-essing (measure 5 to 10 kHz against the speech body; within about 1.5 dB means sibilant).
- A high-pass at 80 Hz handles most plosives on a close mic.
- Use `arnndn` only for handling rustle, and check the model licence first.
- Never loudness-normalise the voice alone; Stage 3 normalises the mix.

## Captions ([`reel-captions`](../../skills/reel-captions/SKILL.md))

Text layer: timings never change, only the displayed text. Fix spelling, brand names, acronyms and clear slips where the intended word is unambiguous; never rewrite the speaker. One spelling convention (US by default) and one brand spelling everywhere. Strip words with no energy under them and ASR hallucinations on hum or music tails (for example a "thank you for watching" that nobody said). After the final render, re-transcribe the delivered audio and diff it against the intended words: missing means clipped, extra means a ghost.

Style (values for the example brand in [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md)):

- Bold sans at 68 px (cap height about 48 px), near-white, soft shadow `0 4px 16px rgba(0,0,0,0.6)`, no full-width box.
- Exactly one accent word or phrase per page, serif italic at 1.08x size in the accent colour. Pick accents from the nouns and verbs that carry the argument, about one per sentence.
- Sentence case; caps only for title slams and the hook headline.
- Pages: 1 to 3 words until the first cut, then 2 to 4; at most 2 lines of 22 characters, split on phrase boundaries; no page shorter than 0.35 s (merge instead).
- Reveal: the page layout is reserved for the full page so the line stays centred; each word fades and rises in (6 px over 4 frames) 1 frame (40 ms) before its onset. No grey preview of unspoken words.
- Position by layout mode (Talk and Takeover y 1180, Card y 1060). Never below y 1500, never right of x 950, never over the mouth (check against the face box).
- Contrast: check the luma behind each page; a bright wall behind one side of the frame is the usual failure.

## Audio mix ([`reel-sound`](../../skills/reel-sound/SKILL.md))

- **Music bed**: instrumental, 100 to 120 BPM, confident and minimal (pluck, keys, light percussion), with a mid-range element that survives phone speakers. A bass-only bed is inaudible on a phone. Licence checked before it touches the timeline.
- **Bed level** in the plan: about -30 LUFS short-term under speech (about 16 LU under the voice), sidechain-ducked a further 6 dB (`sidechaincompress=threshold=0.03:ratio=6:attack=15:release=300`), rising about 4 dB in larger gaps, about -20 LUFS short-term on the end card, running to the last frame with no fade so the loop is clean. **Revised** to 10 LU under the voice with a word-keyed duck.
- **SFX levels** in the plan were peak targets (pops -20 to -14 dBFS, whooshes -18 to -12, impacts -16 to -10, risers -24 to -16). **Revised** to loudness targets relative to the voice; the peaks are now only a safety cap.
- **Master**: mix with `amix normalize=0`; two-pass loudnorm `I=-14:TP=-1.5:LRA=7` in linear mode (if pass 2 falls back to dynamic mode, fix the cause instead of accepting it); a safety `alimiter=limit=0.84:level=false` after it; pad or trim to the video length; mono content upmixed to stereo.
- **Gate on the delivered MP4**: `ebur128=peak=true` gives I = -14 +/- 1 LUFS, TP at or below -1.5 dBTP, LRA at or below 7 LU.

## End card ([`reel-motion`](../../skills/reel-motion/SKILL.md), copy rules in the brand skill)

1. The logo card pops over live footage 1 frame before the spoken brand name.
2. A 0.3 s wipe to the card colour.
3. About 2.5 s of card, content inside x 70-950, y 300-1450: the header logo mark (colour version on cream), a two-line headline with one accent word, the bare domain (no `www.`, no `https://`) in the CTA pill, a small "Link in bio" line.
4. Any offer or proof line only after the owner approves it.
5. Music up to about -20 LUFS short-term, no fade. The last frame cuts to frame 0, where the hook headline is already on screen, so an autoplay loop reads as continuous.

## Export ([`reel-export`](../../skills/reel-export/SKILL.md))

```
ffmpeg -i gfx.mp4 -i mix.wav \
  -filter_complex "[1:a]apad,atrim=end=${V},aformat=channel_layouts=stereo[a]" \
  -map 0:v:0 -map "[a]" \
  -c:v libx264 -preset slow -profile:v high -level 4.2 -crf 18 -maxrate 16M -bufsize 32M \
  -g 50 -keyint_min 25 -bf 2 -pix_fmt yuv420p -r 25 \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
  -c:a aac -b:a 256k -ar 48000 \
  -map_metadata -1 -movflags +faststart out/reel_v1.mp4
```

`V` is the video duration in seconds. No range conversion here: Stage 1 already produced tv range. CRF 18 with a 16 Mbit/s cap lands a 50 s reel with graphics at about 10 Mbit/s; platforms re-encode everything, and a clean high-bitrate upload survives that better than a 3 to 5 Mbit/s file. Never overwrite a delivery: every export is a new `_vN`.
