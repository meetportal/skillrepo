# Forensic analysis of raw talking-head footage

Before cutting a single frame, measure the raw takes. Every later stage depends on facts that are invisible in a player: how the pixels are oriented, what range they use, which frames are soft, where blinks fall, how loud and how noisy each take is, and what was actually said. An hour of measuring saves a day of fixing artifacts that were baked in by a wrong assumption.

The method below was worked out on a sample reel (five takes of 10 to 12 s each, 25 fps, a mirrorless camera turned on its side, a handheld wireless mic close to the mouth). The numbers are what we measured there; use them as a sense of scale, not as constants. The code that implements each step lives in [`reel-ingest`](../../skills/reel-ingest/SKILL.md), [`voice-clean`](../../skills/voice-clean/SKILL.md) and [`reel-grade`](../../skills/reel-grade/SKILL.md).

General rules for the whole pass:

- Only read the raw clips. Write every output into a separate work folder.
- Measure on the rotated frame, so every face box, crop and safe-zone check is in final pixel space.
- A number is a reason to look, not a conclusion. For every surprising value, extract the frame or listen to the window before acting on it.
- Write findings as source-time windows per take ("soft from 0.8 to 1.6 s"), so the cut planner can avoid them.

## 1. Container and stream facts

Probe every clip with ffprobe (`reel-ingest/scripts/probe.py` does all of this and prints the flags to use).

| Check | How | What we found | What it means |
|---|---|---|---|
| Orientation | `rotate` tag and displaymatrix side data | Neither present; the pixels are 1920x1080 landscape with the subject lying on their side | The camera recorded vertical as landscape. You must rotate explicitly (next section). If a tag is present, ffmpeg auto-rotates and an added transpose rotates twice. |
| Pixel format and range | `pix_fmt`, `color_range` | `yuvj420p`, full range (0 to 255) | Convert to tv range (16 to 235) exactly once, explicitly. An implicit conversion plus an explicit one compresses the range twice and lifts blacks by about 10 codes. See [`reel-grade`](../../skills/reel-grade/SKILL.md). |
| Extra tracks | stream list | A `tmcd` timecode track | Map only `v:0` and `a:0`, write no timecode; data tracks break some muxers and players. |
| Audio layout | RMS of L minus R against L | Stereo, but L and R identical to -60 to -63 dBFS | Dual-mono. Fold to mono once with an average (`pan=mono\|c0=0.5*c0+0.5*c1`). Left as stereo it reads 3 LU hot in loudness meters. |
| Bitrate, fps | stream info | H.264 about 28 Mb/s, 25p, AAC 48 kHz | Plenty of detail for a 1.1 to 1.15x digital punch-in. Keep the delivery at the source fps. |

Lesson that changed a rule: the first draft folded dual-mono with `-ac 1`. On a float pipeline that sums the two identical channels and comes out up to 3 dB hot. The skills now always average.

## 2. Rotation and mirroring

A camera turned on its side usually writes no rotation tag. Two of the four 90-degree options give an upright subject only if the image is not also mirrored, so check visually:

1. Render one frame per clip with `none`, `transpose=1` (90 degrees clockwise), `transpose=2` (90 degrees counter-clockwise), 180 and `hflip` side by side (`reel-ingest/scripts/rotation_check.py`).
2. Pick the option where the subject is upright **and background text reads left to right** (a book spine, a poster, a label). Upright but mirrored text means you also need `hflip`.
3. Check every clip, not just the first. A camera can be flipped between takes.

On the sample reel `transpose=2` was upright and unmirrored for every take, and the rotated frame was exactly 1080x1920, so the 9:16 delivery needed no scaling: `transpose=2,setsar=1`.

## 3. Framing and shot size

Run a face detector (YuNet from the OpenCV model zoo, MIT) on every frame of the rotated video and summarise over the speech window only.

| Measure | Why | Sample range |
|---|---|---|
| Face centre x, median and p5 to p95 | Sway and drift; whether a static crop holds the face | Median 537 to 583 px on a 1080 frame; a swaying take spanned 455 to 684 |
| Eyeline y (eye landmarks) as % of height | Headroom | 29 to 31 % from the top in every take: on the upper third, no reframe needed |
| Face width as % of frame width | Shot size; how much the scale jumps at a cut between takes | 21 % to 40 %: from a wide-ish shot to a medium close-up |
| Camera jitter | Tripod or handheld | Phase correlation on background strips: 0.3 to 0.7 px RMS on a tripod |

**Shot-size mismatch between takes.** When face width varies by almost 2x, a cut between takes jumps in scale. Match the takes to a reference take: punch-in = reference face width / take face width, then crop around the face so the eyeline stays at 30 % and the face stays centred, and scale back to 1080x1920 with lanczos. Cap the punch-in: on 1080-wide source, 1.15x stays sharp, up to 1.25x is acceptable, and the 1.35x one take needed was visibly soft. Keep the tightest take as it is and use it as the natural "punch-in" beat instead of shrinking the others.

**Camera move or subject move?** Mean frame difference cannot tell them apart. Measure motion on a strip of background (the top corners, away from the head) with phase correlation: if the background is still while the frame difference spikes, the subject moved (a lean or a sway); if the background moves, the camera moved (a bump or a slow reframe). On the sample reel one take had a slow background drift of about 100 px over its first 4 s (a reframe), and another had a fast body sway with a still background.

**Caption room.** Overlay the platform UI zones on a rotated frame (top about 250 px, bottom about 420 px, right-side button rail about 140 px). On this footage the face sat clear of all of them, and the free area for captions was y about 1000 to 1450, on the chest, where dark clothing gave white text strong contrast.

## 4. Sharpness, motion and bad frames

Per frame, on a quarter-size grey frame (270x480):

- **Sharpness**: variance of the Laplacian.
- **Motion**: mean absolute difference to the previous frame.
- **Luma**: mean.
- **Face box and landmarks**: from the detector; a frame with no face is a flag in itself.

Normalise sharpness per clip: medians on the sample reel ranged from about 570 to 1200, so an absolute threshold means nothing. A frame under 45 % of its clip median is "soft".

Kinds of bad frames we found, and what each looks like in the numbers:

| Event | Signature | Typical size | Treatment |
|---|---|---|---|
| Hand over the lens (the start-recording gesture) | Luma spike, motion diff 18 to 29, no face for several frames | About 1 s at the start of a take | Start the cut after it. Never let it be frame 0, which is the thumbnail. |
| Autofocus hunt after an occlusion | Sharpness falls to 2 to 4 % of the median, then climbs back over about 1.2 s | The first spoken word landed at about 55 % of normal sharpness | Start late, hold the first sharp frame for up to 4 frames, or cover the first 0.3 to 0.4 s with a hook graphic. |
| Lean-in and pull-back at the start | Face width jumps to about 600 px, then sharpness drops to about 20 % of the median with motion blur | 0.5 to 0.8 s before speech | Start after it settles. |
| Fast body sway mid-sentence | Motion diff up to about 18, sharpness down to about 1/6 of the median, background still | About 0.6 s, overlapping the end of one word and the start of the next with only a 0.26 s pause between them | A jump cut alone cannot remove it. Keep the audio continuous and cover the video with a full-screen graphic, or cut and punch in so the jump reads as intentional. |

Whole-frame sharpness misses a soft face on a sharp background. For any frame that will be a thumbnail, a loop frame or a cut frame, also measure the Laplacian variance of the face crop at full resolution and look at it.

## 5. Blinks

Blinks on the first or last frame of a shot look like a stutter. Detect them so the cut planner can avoid them.

Method (in `reel-ingest/scripts/frame_metrics.py`):

1. Only use frames with a face and reasonable sharpness (soft frames give false hits).
2. Take a small patch around each eye landmark, about 1/14 of the face width.
3. Measure the 15th-percentile brightness of each patch. An open eye has dark pupil and lashes; a closed lid is skin and reads brighter.
4. Subtract a 15-frame running median, so slow light changes and head turns do not count.
5. A blink is a run of frames above max(12 codes, 3.5 x the standard deviation of that residual).

Findings: 3 to 5 blinks per 10 s take, each 1 to 3 frames at 25 fps (0.04 to 0.12 s). Most fell inside words and do not matter. The ones that matter fall on a pause edge or the first frame of speech: one take blinked exactly on its first word. Treatments, in order of preference:

- If the blink sits inside a pause that will be tightened anyway, it disappears with the pause.
- Otherwise, offset the video cut from the audio cut by 2 frames (a J or L cut) so the picture enters or leaves after or before the blink while the sound stays put.
- Keep any cut frame at least 3 frames away from a blink. [`reel-cut`](../../skills/reel-cut/SKILL.md) searches offsets up to 6 frames to clear blinks and soft windows.
- Or cover it with a title card that was planned for that moment anyway.

Verify the borderline hits by eye on a contact sheet of the frames around them.

## 6. Exposure, white balance and skin

Measure on the rotated video at about 5 fps (ffmpeg `signalstats`, plus OpenCV on landmark patches):

| Measure | How | Sample range | Use |
|---|---|---|---|
| Frame mean luma (YAVG) | signalstats | 127 to 145 median per take; one swaying take ranged 101 to 151 as the framing changed | Exposure drift inside a take |
| Clipped background | % of pixels at 250 or above | 0 % to 22.9 % (a bright wall at the top of the frame) | The wall cannot be recovered; pull highlights a little so the face does not look hot next to other takes |
| Clipped face | % of the face box at 245 or above | 0 % to 5.5 % (forehead and cheek highlights) | Flags a take that needs a highlight roll-off |
| Skin brightness | Median Y of two cheek patches between eye and nose wing, each 1/10 of the face width | Cheek Y 134 to 170 across takes | The value to match across cuts. Target about 150. |
| Skin hue | Angle of (Cb - 128, Cr - 128), compared with the vectorscope skin line (about 123 degrees) | 122 to 128 degrees in every take | All on the skin line: no hue correction, only a small red pull on the reddest take |
| White balance proxy | Mean RGB of mid-bright pixels of a neutral wall | Every take warm, R minus B 33 to 51 codes | One uniform cool-down across all takes, never per take |
| Saturation | signalstats SATAVG | 12 to 17 of 255 | Low; a mild S-curve and about 1.1x saturation give a creator look without pushing skin |

Exposure drifts inside a take as well as between takes (a swaying subject moves in and out of window light). Match on cheek brightness over source time, not one number per clip, so a jump cut inside a take reads the curve at its own time and does not step. [`reel-grade`](../../skills/reel-grade/SKILL.md) fits one curve per take and checks both sides of every cut.

Lesson that changed a rule: the first draft matched exposure with `eq=gamma`. Gamma lifts a black of Y 20 to about 30 at gamma 1.6, so dark clothing and hair go milky and jump cuts between a lifted and an unlifted take look wrong. The grade now uses a shadow-neutral tone curve that acts like gamma in the mids and fades out at the toe.

## 7. Audio forensics

Fold to mono first (average), then measure each take. [`voice-clean/scripts/diagnose.py`](../../skills/voice-clean/SKILL.md) prints all of these.

| Measure | How | Sample result | Threshold or reading |
|---|---|---|---|
| Room tone | 5th percentile of a 30 ms RMS envelope | -59 dBFS in every take | At or below -55 dBFS with SNR 35 dB or more is a quiet room: no denoiser |
| SNR | Speech level (90th percentile of the envelope) minus room tone | 40 to 43 dB | |
| Integrated loudness, LRA | `ebur128` | -16.3 to -18.8 LUFS, LRA 2 to 3.2 LU | A 2.5 LU spread between takes is normal; loudness is set once on the final mix |
| True peak vs sample peak | `ebur128=peak=true` | One take had a sample peak of -0.26 dBFS but a true peak of +0.2 dBTP on a consonant onset | No sample clipping, yet over 0 dBTP between samples: a true-peak limiter is mandatory |
| Hard clipping | Count of samples at full scale | None | Any hit means `adeclip` first and flag the take |
| DC offset | Mean | Negligible | |
| Noise spectrum | Welch PSD of the quiet frames (envelope under floor + 6 dB), in bands | About -93 dB/Hz under 300 Hz falling to -104 above 6 kHz: low and sloping | No audible hiss |
| Mains hum | Peak at 50, 100, 150, 60, 120, 180 Hz above the median of neighbouring bins | At most 3.6 dB | Treat hum only at 6 dB or more |
| Plosives | Frames where 20 to 120 Hz energy is more than 6 dB above the 300 Hz to 3 kHz body and in the top 3 % of low energy | Two minor pops, 10 to 20 dB under the voice | An 80 Hz high-pass removes them |
| Sibilance | 5 to 10 kHz energy against the 300 Hz to 3 kHz body, per frame and as a band balance of total speech | The worst take carried 5 to 10 kHz only 1.5 dB under its body; band balance -3.7 dB of total | The main tonal problem of a mic held at the mouth. De-ess per take by how high that band sits |
| Band balance | Speech energy per band relative to 80 Hz to 16 kHz total | A 5 to 10 kHz lift with a 2.5 to 5 kHz dip: "spitty yet boxy" | A small 250 Hz cut, a gentle 3 to 4 kHz presence lift, a light de-esser |
| Reverb | Decay rate at phrase ends | 128 to 388 dB/s (equivalent T60 150 to 470 ms, an upper bound since articulation decay is included) | A close mic gives a high direct-to-reverberant ratio: no dereverb |
| Handling noise | Low-frequency bursts outside speech | Only the lens-cover rustle before speech | Cut it out; if it must stay, RNNoise is the only tool that removed it |

Also listen to the tail of every take. One take ended with a faint voiced hum (about -45 dBFS) after the last word. It must stay outside the cut, and it is exactly the kind of sound a speech recogniser turns into a phantom sentence (section 9).

### Denoise chain tests

We rendered ten chains on two takes, each ending in the same two-pass linear loudnorm to -14 LUFS, and measured room tone, pauses, a rustle window and band balance on the normalised output. Lower room tone after normalisation is better.

| Chain | Room tone after normalising (take A / take B) | Reading |
|---|---|---|
| Loudnorm only | -46.7 / -47.1 dBFS | The baseline |
| Tone EQ + de-ess + 3:1 compressor | -39.3 / -41.9 | **Compression raised the floor by about 7 dB.** This is the effect to beat, not a denoiser failure |
| + afftdn (tracking or learned profile) | -45.0 to -45.6 / not run | Wins back about 6 dB |
| + RNNoise | -46.7 / -49.7 | The only chain that removed non-stationary rustle (that window went from about -34 to -50 dBFS) |
| + anlmdn | -49.5 / -53.7 | |
| + noisereduce (stationary, profile from room tone) | -51.5 / -54.1 | |
| + light afftdn + soft gate | -52.9 / -58.2 | Lowest floor in both takes |

What the numbers taught:

- Pauses inside the speech are breaths and decay tails, not noise. No denoiser moved them more than about 2 dB. Remove them by cutting, never by stronger noise reduction, which only adds artifacts.
- De-ess plus EQ worked: sibilance fell from -1.5 to -6.2 dB relative to the body on the worst take, presence rose about 3.5 dB, and with the sibilant peaks tamed linear loudnorm could reach -14 LUFS, which it could not on that take alone.

Lessons that changed the rules: the "winning" chain above was later dropped. Tracking afftdn (`tn=1`) nearly doubled pause kurtosis (musical noise) and re-tracked across every splice; a gate closed in the short room-tone gaps of a tight cut and widened them into dead air; and 3:1 compression from -22 dB lifted the floor more than any expander could safely take back. The rule that survived is simpler: **processing must not make the background louder relative to the voice than it was in the raw cut**. On a quiet room like this one that means no denoiser, a soft downward expander, 2:1 compression from -14 dB, a light high de-esser, and loudness set once on the final mix. See [`voice-clean`](../../skills/voice-clean/SKILL.md) for the gate and the presets.

## 8. Speech map: where the words really are

The cut is only as good as the word timings. Whisper's full-clip word timestamps are good for text and poor for edges: it absorbs leading silence into the first word of a phrase (one word was reported 0.48 s before its real onset), and inside continuous speech its boundaries are off by about +/-60 ms, sometimes up to 0.5 s.

The method we used, and what replaced parts of it:

1. Build a 10 ms RMS envelope. Noise floor = 5th percentile.
2. Find voiced segments with hysteresis: open at floor + 18 dB, close at floor + 10 dB, merge gaps under 150 ms, drop runs under 60 ms.
3. Re-transcribe every voiced segment in isolation (with about 80 ms of handle and 0.5 s of silence padded on each side). This settles which words sit before and after each pause, which full-clip runs get wrong.
4. Snap the first and last word of each segment to the energy edges (about 10 ms accuracy).
5. Check ambiguous joins by hand with band energy and pitch (pYIN) traces.
6. List every pause over 250 ms and every 150 to 250 ms gap per take: these are the candidate cut points.

On the sample reel the five takes held 47.9 s of speech from first word to last word, with 1 to 4 pauses over 250 ms per take (0.26 to 0.46 s each). Tightened to residual gaps of about 120 to 200 ms, the talking part came to about 45 s.

Energy snapping cannot place an onset inside continuous speech, and it counts a breath before a phrase as speech. The skills now force-align the cleaned text with a CTC aligner and gate every onset to within one video frame: see steps 5 to 7 of [`reel-ingest`](../../skills/reel-ingest/SKILL.md).

## 9. Transcription cross-checks across whisper models

One transcript is an opinion. Run several and compare word by word:

- faster-whisper `large-v3` (int8 on CPU) with a brand keyterm prompt
- `large-v3` with a short neutral prompt (brand name, product terms, acronyms only)
- `large-v3` with no prompt
- `medium.en`
- `small.en` (or whatever the earlier transcript came from)
- the per-segment isolated run from section 8

Settings that mattered: beam 5, word timestamps, `condition_on_previous_text=False`, no VAD filter (it trims onsets), language fixed. Feed a float32 array decoded by ffmpeg instead of a path if your PyAV build breaks faster-whisper's decoder. `large-v3` took about 160 s and `medium.en` about 80 s for 56 s of audio on 8 CPU cores.

The kinds of disagreement we found, and how to settle each:

| Kind | Example of the pattern | Verdict rule |
|---|---|---|
| A short coarticulated function word | A 20 to 40 ms pronoun after a long word: the small model heard a different pronoun | Trust the agreement of the larger models |
| A final consonant merged into the next word | A past-tense "-ed" swallowed by a following "s" | Larger models agree on the full form; caption the full form |
| A contraction | "you'll" vs "you will", split 3 to 2 across runs | Genuinely ambiguous; check the pitch trace for a glide, then pick one and use it consistently |
| A spoken slip against the script | The speaker said a shorter form of a product word. Every model agreed, even with the intended word in the prompt | It is what was said. Fix it in the caption layer, never by cutting into the word |
| The brand name | Heard as a different phrase by a small model, spelled two ways by large models | A brand dictionary in the caption layer; spell it one way everywhere |
| A clipped onset in an isolated segment | A short, clipped first word mis-heard when transcribed alone | The full-clip runs win for text; isolated runs win for segment membership |
| Non-speech | A faint hum after the last word became "Thank you for watching"; on near-silent music an earlier transcript appended a web address nobody said | Strip it into non-speech events. Any word in a silent tail is a hallucination until proven otherwise |
| Spelling variant | British vs US spelling | Pick the spelling the brand's site uses |

A keyterm prompt biases spelling. It does not change what was heard, which is why a slip that survives the prompt is a real slip. Caption text corrections live in one layer ([`reel-captions`](../../skills/reel-captions/SKILL.md)) and timings never change there.

## 10. The report to hand on

End the pass with a short report per take, in source time, that the cut planner can act on:

1. Rotation filter and range conversion for all takes.
2. First and last word times, pauses over 250 ms, and the 150 to 250 ms gaps.
3. Bad windows: occlusions, focus hunts, lean-ins, sways, no-face frames.
4. Blinks, with the ones on a pause edge or first word called out.
5. Shot size and the punch-in that matches it to the reference take.
6. Exposure: cheek Y, clipped percentages, hue, and the direction of correction.
7. Audio: floor, SNR, LUFS, true peak, hum, plosives, sibilance by take, and the recommended preset.
8. Transcript flags: every word where models disagree, with a verdict and the evidence.
9. Shoot notes for next time (for example: clip a lav to the collar instead of holding the mic at the mouth, start talking 1 s after the hand leaves the lens, keep the same distance to the camera between takes).

[`reel-director`](../../skills/reel-director/SKILL.md) stores these per reel in `project.md`, and the standing ones (camera always needs the same transpose, this speaker always blinks on first words) in the series style bible.
