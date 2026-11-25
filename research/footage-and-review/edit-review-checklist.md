# Reviewing a reel edit: what goes wrong and what to do instead

Agency and template edits of talking-head reels tend to fail in the same places. The script and the graphic ideas are often good; the execution loses viewers in the first second, sags in the middle, and ends on a long card nobody watches. This note is a review method, a checklist of the usual failures with the number that exposes each one, and the creative direction principles we drew from reviewing one such edit of a sample reel.

Use an earlier edit only as a reference to measure and critique. Never cut from it: every frame and sample of the new edit comes from the raw camera files ([`reel-director`](../../skills/reel-director/SKILL.md), hard rule 9).

## 1. How to review an edit in numbers

You cannot judge pacing or loudness by watching once. Measure first, then watch with the numbers next to you. [`craft-research/scripts/measure_reference.py`](../../skills/craft-research/SKILL.md) and [`reel-qa`](../../skills/reel-qa/SKILL.md) automate most of this.

| What | How | Watch out for |
|---|---|---|
| Loudness, true peak, LRA | `ffmpeg -i reel.mp4 -af ebur128=peak=true -f null -` | Measure the end card separately; it is often 10 dB quieter than the talking part |
| Pauses | Word timestamps from faster-whisper, gaps over 0.25 s | `silencedetect` misses pauses that a music bed covers; only word times show them |
| Speech rate | Words / speech duration | Short-form talking heads usually run 160 to 180 wpm |
| Shots | `select='gt(scene,0.2)'` cut times, then look at each | A cut that only joins two takes is not a rhythm device |
| Visual rhythm | Largest gap between any visual change (cut, scale change, graphic event) | Over 4 s sags |
| Frames | 2 fps stills plus timestamped contact sheets (12 s per sheet, 0.5 s per tile) | Look at frame 0 at full size: it is the thumbnail |
| Caption accuracy | Re-transcribe the audio with a large model and diff it against the on-screen words | Re-check the payoff and brand lines with a second model |
| Caption timing | On-screen reveal time of a word minus its spoken onset | A lead of 300 ms or more reads ahead of the speaker |
| Text size | Cap height in px at 1080 width | 18 to 22 px is about 1.5 mm tall on a 6-inch phone: unreadable |
| Safe zones | Overlay an Instagram Reels and TikTok UI template | The bottom 420 px and the right 140 px are under platform UI |
| Music on a phone | Spectrum of the bed in speech gaps and on the end card, by band | A bed with nothing between 500 Hz and 6 kHz is silent on a phone speaker |
| Series consistency | The same loudness and caption measures on other reels from the same source | An 8 dB loudness spread across one channel means there is no standard |

## 2. Checklist of typical failures

Ordered roughly by how much viewing time they cost. Each line: the symptom, the number that shows it, and the fix.

### Hook and thumbnail

- [ ] **Frame 0 is a blurred hand, an out-of-focus frame or a fade-in.** The start-recording gesture is left in, or the edit opens before autofocus settles. Fix: frame 0 is the speaker mid-word, face sharp, eyes open, mouth open, the headline already on screen. Hold the first sharp frame for up to 4 frames if needed. Gate: face sharpness of frames 0 to 2 at least 60 % of the shot median (`reel-qa` `first_frame`).
- [ ] **The hook has no visual headline.** The first 3 s show only word-by-word captions and a small graphic. Fix: a big kinetic headline in the top third (below the top UI zone) stating the promise in 2 to 4 words, slammed in over about 0.4 s, readable at arm's length inside 1.5 s.
- [ ] **The numbered structure is invisible.** A "three things" script is the strongest retention device in a list reel, but the numbering sits in tiny eyebrow text. Fix: make it a persistent, visible progress element that fills as each point lands, and open each point with a short title slam.

### Pacing

- [ ] **Pauses left in.** Typical: a dozen or more pauses over 0.25 s adding up to several seconds, with up to a second of dead air after a list marker. Fix: tighten every pause of 0.25 s or more to a residual of about 0.12 to 0.20 s, keep about 0.28 s after a list marker so a title slam can land ([`reel-cut`](../../skills/reel-cut/SKILL.md) rules).
- [ ] **One shot per take.** A handful of shots in a 50 s reel, around 10 s per shot, every cut just a take boundary. Fix: a visual change at least every 4 s. Alternate two scales (for example 100 % and 112 %) across every removed pause so jump cuts read as intentional, and add a short eased push on key words.
- [ ] **Slow delivery.** Around 130 wpm. Tightening pauses alone usually fixes it; a speed-up of the voice is an owner decision, not a default, because it changes how the speaker sounds.
- [ ] **Too long.** A 60 s reel whose talking ends at 50 s. Fix: aim for the talking part plus at most 3 s of end card.

### Captions

- [ ] **Wrong words in the payoff line.** A mis-heard verb in the last sentence, the one that carries the brand. Mistakes in the CTA line read as careless to a business audience. Fix: proofread every page against the audio, and run an ASR diff on the delivered file ([`reel-captions`](../../skills/reel-captions/SKILL.md)).
- [ ] **The brand spelled two ways.** Logo one way, caption another. Fix: one spelling in a brand dictionary that the caption layer enforces.
- [ ] **Captions rewrite the speaker.** A grammar fix is fair (restoring a swallowed past-tense "-d"); swapping a preposition for no reason is not. Fix: caption what was said, with only light, listed corrections.
- [ ] **Hallucinated text.** A speech recogniser invents words on near-silent music or hum (a sign-off phrase, a web address). Fix: strip every word in a silent tail; never caption a URL that came from ASR.
- [ ] **Reveal leads the audio.** Words appear 0.3 to 0.7 s before they are spoken. Fix: show a page at most 1 to 2 frames (0 to 80 ms) before its first word, from force-aligned onsets.
- [ ] **Grey preview of unspoken words.** It spoils the line before it is said. Fix: show only what has been spoken, or the whole page at once with the current word highlighted.
- [ ] **Ragged line breaks.** A line that ends on a function word, or sits off-centre. Fix: 2 to 4 words per page, at most 2 lines of about 22 characters, breaks on phrase boundaries.
- [ ] **A full-width subtitle bar.** Reads as broadcast subtitles, not a creator caption. Fix: white text with a soft dark shadow or a tight pill per page, one accent word per page at most.

### Graphics and layout

- [ ] **A permanent stack of boxes.** A caption box plus a data card covering about a third of the frame for the whole talking section. It hides hands and gestures (pointing, counting on fingers), leaves no visual rest, and its bottom sits inside the platform UI zone. Fix: the speaker full-frame with captions only between graphic moments.
- [ ] **Text nobody can read.** Labels, eyebrows and counters at about 20 px. A card nobody can read is decoration that fills the frame. Fix: at least 44 px for any text on a graphic, 140 px or more for hero numbers, 64 to 76 px for captions.
- [ ] **Dashboard sameness.** A dozen near-identical cards from one template: nothing changes scale, no full-screen moments, no type slams, no colour shifts. Fix: one big idea per point, shown big for 2 to 4 s, then out of the way. Vary the layout: talk with captions, a card in part of the frame, a full-frame takeover.
- [ ] **Meaningless counters.** "01 / 11" card numbers tell the viewer nothing. Fix: count the points of the script (1, 2, 3), not the cards.
- [ ] **Logo in a corner.** It collides with the Reels camera icon and the TikTok search icon. Fix: the brand mark at top centre in its own zone, or not at all (see [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) for one way to do it).
- [ ] **Recreated third-party UI or logos.** Fix: generic icons; name third-party products in text only.
- [ ] **A watermark across the face.** It marks a proof copy, not a deliverable, and it hides the expressions a talking head depends on. Fix: never post it; never accept stock assets with one.

### End card and CTA

- [ ] **A long end card without the speaker.** Typical: 8 to 10 s after the last word, a large share of the runtime. Retention collapses there and pulls down average watch percentage. Fix: 3 s at most, starting while the speaker is still on the brand line, so the CTA begins over live footage.
- [ ] **No CTA.** No URL, no handle, no "link in bio", no offer. Fix: one CTA, the URL in large text (72 px or more), "Link in bio" under it.
- [ ] **A list of claims.** Five claim rows staggering in. One claim is remembered, five are not. Fix: one offer line at most.
- [ ] **Claims that disagree with the brand's own site.** Prices, counts and rates on the card that differ from the live website. Fix: every claim on screen comes from one approved list, confirmed by the owner before shipping. Graphics use relative shapes instead of invented numbers.
- [ ] **A fade to silence and an empty frame at the end.** It breaks the loop. Fix: music to the last frame, and an end frame that cuts cleanly back to the opening so autoplay loops feel continuous.

### Sound

- [ ] **Broadcast loudness on a social feed.** Around -23 to -24 LUFS integrated with several dB of true-peak headroom unused, so the reel plays about 10 dB quieter than the reels around it. Fix: -14 LUFS integrated, true peak at or below -1.5 dBTP, one target for every reel in the series ([`reel-sound`](../../skills/reel-sound/SKILL.md)).
- [ ] **An uncontrolled voice.** LRA over 10 LU for a single talking head. Fix: gentle compression in the voice chain, LRA 7 LU or less on the master.
- [ ] **A bass-only music bed.** Nearly all the energy under 150 Hz and almost none at 2 to 6 kHz: effectively silent on a phone. Fix: a track with a mid-range element (pluck or keys), ducked under the voice and allowed up on the end card.
- [ ] **No sound design.** Card entrances and title slams with no SFX: with sound on, it feels flat. Fix: a small palette (6 to 8 sounds: whoosh, impact, soft pop, rising ticks, error buzz, a logo sting), 6 to 10 dB under the voice, never on a stressed syllable.

### Shoot problems to flag for the next shoot

- [ ] A handheld mic at the mouth for the whole reel (plosives, sibilance, and it hides the mouth). Clip a lav to the collar.
- [ ] The record gesture and lean-ins in frame at the start of every take. Start speaking 1 s after the hand leaves the lens.
- [ ] Different distances to the camera between takes, so shot size jumps at every join.

## 3. What is usually worth keeping

A weak edit often carries good ideas. Before starting over, list them:

1. **The script structure.** A hook that names the pain, the keyword and a numbered promise in one breath, followed by a numbered list, holds people because they wait for the last number.
2. **Graphics that animate in time with the words.** A bar that drains on the word that names the loss, a counter that climbs on a word about volume, tiles that light up one per spoken acronym. When it lands, the eye follows the argument. Keep the sync, fix the size.
3. **Strong visual metaphors.** A row flipping from healthy to failed with a stamp, a vital-signs line that flatlines for something failing, a rising line against a flat one for a diminishing-returns point, a side-by-side comparison for a bad and a good choice, a shield for the fix. Keep the idea, make it full-width and short.
4. **A caption treatment with personality.** A bold geometric sans with an italic serif accent word gives clear emphasis.
5. **A consistent colour system.** One accent colour for emphasis, red for failure, green for healthy, one end card colour. It already reads as a series.

## 4. Creative direction principles

These are the principles the review produced. The numbers are the defaults the skills now use.

1. **The first frame decides the swipe.** Sharp face, eyes open, mid-word, headline on screen, no fade in.
2. **One big idea per point.** About three graphic moments per point, each shown big for 2 to 4 s, then the speaker returns full-frame. No permanent dashboard.
3. **Make the structure visible.** A title slam of 0.5 to 0.7 s per point ("#1" in small caps, the point in 2 to 3 big words), and a progress element that fills as each point lands.
4. **Change something every 2 to 4 s.** A cut, a scale change, a graphic event or a caption style beat; never more than 4 s without one. Punch-ins stay at 115 % or less to stay sharp on 1080-wide source.
5. **Sync to the word, not the sentence.** Every graphic event, SFX and camera push is timed from force-aligned word onsets, and recomputed after every re-cut.
6. **Readable on a phone at arm's length.** Captions 64 to 76 px, graphic text 44 px or more, hero numbers 140 px or more. Nothing important above y 220, below y 1500 or in the right 140 px.
7. **Captions follow the voice.** At most 0 to 80 ms of lead, 2 to 4 words per page, one accent per page, captions rendered last, on top of everything.
8. **The CTA starts while the speaker talks.** The logo pops on the spoken brand name over live footage, then a short end card (3 s or less) with one offer line and a large URL.
9. **Loop-friendly ending.** Music runs to the last frame; the last frame cuts cleanly back to the first.
10. **Sound carries half the reel.** A cleaned voice at a fixed loudness, a bed that survives a phone speaker, sparse SFX on visible events.
11. **No invented numbers.** Every price, count or rate on screen is approved by the owner; anything else is shown as a relative shape.
12. **One standard for the series.** The same loudness target, caption style, safe zones and brand spelling on every reel, written down in the series style bible ([`reel-director`](../../skills/reel-director/SKILL.md)).

## 5. Turning the review into gates

Most of this checklist is automated in [`reel-qa`](../../skills/reel-qa/SKILL.md): `first_frame`, `rhythm` (largest gap between visual changes), `loudness`, `silence`, `captions` (safe zone, minimum page time, contrast), `asr` (caption words against the delivered audio), `levels`, and the contact sheets for every cut and graphic entrance. What the gates cannot judge (is the idea big enough, does the hook land, is the end card worth 3 s) goes to the independent critic pass in [`critic-prompt.md`](../../skills/reel-qa/references/critic-prompt.md), which scores the reel against the same standards.
