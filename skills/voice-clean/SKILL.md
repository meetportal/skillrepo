---
name: voice-clean
description: Diagnose and clean talking-head dialogue audio for short-form video. Use when a reel, short or interview needs its voice track denoised, de-essed, de-hummed, compressed or checked for clicks and gating damage; when choosing between afftdn, RNNoise (arnndn) and DeepFilterNet; when A/B testing voice chains with measured noise floor, SNR and loudness; or when producing a processed voice.wav from a cut dialogue track and an EDL with per-clip settings.
---

# voice-clean

Measure first, treat second, listen last. Every choice in this skill is backed by a number the scripts print, and every number still needs a human ear before the mix is locked.

## Rules

1. **Diagnose before treating.** Run `diagnose.py` on every source clip. Do not pick a denoiser before you know the floor, the SNR and the noise type.
2. **Set afftdn `nf` from the measured floor** (room tone p5 + 1 dB). A guessed `nf` above the real floor does nothing; far below it eats speech.
3. **Never loudness-normalise the voice alone.** The voice leaves this skill un-normalised (it sits near -28 LUFS after chain09). Loudness is set once, on the final mix, with two-pass loudnorm. Normalising the voice and then the mix stacks gain and lifts the floor twice.
4. **Pauses are breaths and decay tails, not noise.** No denoiser moves them more than about 2 dB. Remove them by cutting, not by stronger NR.
5. **Compensate filter latency.** ffmpeg `afftdn` delays audio by 25 ms (1200 samples at 48 kHz) and `arnndn` by 10 ms. A plain `ffmpeg -af` pass silently shifts the voice late against the picture and drops the last 25 ms. `process_voice.py` measures each stage's delay by cross-correlation and removes it; never hand-roll the chain without the same correction.
6. **Downmix with an average, not ffmpeg `-ac 1` to float.** ffmpeg sums dual-mono to +3 dB when the output is float. The scripts average channels in numpy. If you extract by hand, use `pan=mono|c0=0.5*c0+0.5*c1`.
7. **Process the cut timeline, keep state continuous.** Run the chain over the whole cut voice so compressor, gate and noise tracker never restart at a splice. Per-clip settings are separate full renders that are switched at the EDL boundaries with a 5 ms crossfade.
8. **Write float WAV.** The chain can push inter-sample peaks over 0 dBFS before the master limiter; float keeps them.
9. **Verify by measurement and by ear**: length equality, room-tone floor, no clicks at splices, no words lost to the gate (ASR diff), then the listen list.

## Workflow

Scripts need Python 3.10+, ffmpeg 6+ and the packages in the repo `requirements.txt`. `S` is this skill's directory.

```bash
# 1. Diagnose each source clip (accepts video files directly)
python $S/scripts/diagnose.py clips/*.MP4 --out-dir work/voice_lab/diagnosis
# prints floor, SNR, LUFS, hum, sibilance balance, plosives, low-frequency bursts,
# recommendations and suggested params (afftdn_nf, deess_i, hum_hz); writes a spectrum PNG per clip. Look at the PNGs.

# 2. A/B candidate chains on the raw clips (and on the cut once it exists)
python $S/scripts/ab_render.py --input a.wav --input b.wav \
  --presets tone-only chain09 chain09-nogate deepfilter-gentle \
  --reference tone-only --gate-pair chain09:chain09-nogate \
  --clip-set a:deess_i=0.6 --spectrograms --listen-copies --out-dir work/voice_lab/ab
# writes <stem>__<preset>.wav, .png, .listen.wav (loudness-matched to -16 LUFS for fair listening) and results.json

# 3. Process the cut voice with per-clip settings
python $S/scripts/process_voice.py --input work/voice_cut.wav --output work/voice.wav \
  --preset chain09 --edl work/edl.json --clip-params work/voice_params.json --report work/voice_lab/voice.report.json

# 4. Verify
python $S/scripts/check_splices.py --edl work/edl.json --audio work/voice_cut.wav --audio work/voice.wav --out work/voice_lab/splices.json
python $S/scripts/asr_diff.py --reference work/voice_cut.wav --candidate work/voice.wav --model large-v3 --prompt "Brand, jargon" --out work/voice_lab/asr_diff.json
```

`voice_params.json` maps a clip's file stem to overrides, optionally with its own preset. A range's audio source is its `a_clip` when the EDL has one (J/L bridge ranges whose audio comes from the neighbouring clip), else its `clip`:

```json
{"CLIP_A": {"deess_i": 0.6}, "CLIP_D": {"preset": "arnndn-rustle", "rnnoise_model": "/models/cb.rnnn"}}
```

Global overrides go on the command line: `--set afftdn_nf=-56 --set gate_range=0.35`.

## Decision table by noise type

| Diagnosis (from `diagnose.py`) | Treatment | Preset / params |
|---|---|---|
| Quiet room, close mic: floor at or below -55 dBFS, SNR 35 dB or more | Light FFT denoise at the floor plus a gentle gate | `chain09`, `afftdn_nf` = floor + 1 |
| Steady broadband (fan, HVAC, hiss): SNR 25 to 35 dB, floor -55 to -45 | Raise `afftdn_nr` to 12 to 18; A/B against DeepFilterNet with an attenuation limit | `chain09 --set afftdn_nr=15`, `deepfilter-gentle` |
| Loud or changing noise (traffic, wind, crowd, keyboard, water): SNR under 25 dB | Neural enhancement; listen for warbled vowels and swallowed word ends | `deepfilter-full`, then `deepfilter-gentle` if it warbles |
| Mains hum: `hum_peak_above_local_db` 6 dB or more at 50/60 Hz or harmonics | Narrow notches at the fundamental and three harmonics | `chain09-hum --set hum_hz=50` (or 60) |
| Handling, cable or clothing rustle in a kept range | Cut it out first. If it must stay, RNNoise on that clip only | `arnndn-rustle` via `--clip-params` (model file licence must be checked) |
| Sibilance: 5-10 kHz band above -5 dB of total speech energy | Stronger de-ess on that clip only | `deess_i` 0.6 (above -5 dB) or 0.7 (above -3 dB) |
| Plosive pops: low-frequency bursts in `plosive_events` | The 80 Hz high-pass in every preset; raise to 100 Hz only if still audible | `--set highpass_hz=100` |
| Clipped samples | `adeclip` as the first stage, and flag the take | add `"adeclip"` to a copy of the preset |
| Hot true peak (above -1 dBTP) | Nothing here; the master limiter handles it | |
| Reverberant room | No reliable fix in this chain; prefer another take or a closer mic | |
| A music bed always runs under the voice and the gate is heard | Drop the gate | `chain09-nogate` |

## Default chain: chain09

```
highpass=f=80:poles=2,
afftdn=nr=10:nf=-58:tn=1,
equalizer=f=250:t=q:w=1.0:g=-2,
equalizer=f=3500:t=q:w=1.2:g=2.5,
deesser=i=0.5:m=0.5:f=0.5:s=o,
acompressor=threshold=-22dB:ratio=3:attack=5:release=90:makeup=1:knee=4,
agate=threshold=0.003:ratio=2:range=0.25:attack=5:release=150
```

Every number is a param in `presets/chain09.json` (`highpass_hz`, `afftdn_nr`, `afftdn_nf`, `lowmid_gain_db`, `presence_gain_db`, `deess_i`, `comp_threshold_db`, `comp_ratio`, `gate_threshold`, `gate_range`). The compressor removes about 8 dB of level; that is expected and is restored by the mix loudnorm.

## Presets

| Preset | Use |
|---|---|
| `chain09` | Default. |
| `chain09-nogate` | Gate A/B partner; use when the gate is audible. |
| `chain09-hum` | Mains hum present. |
| `tone-only` | No NR, no gate. The reference for measuring what a denoiser does to speech. |
| `deepfilter-gentle` | DeepFilterNet with an 18 dB attenuation limit in place of afftdn. |
| `deepfilter-full` | DeepFilterNet with no limit. Hard noise only. |
| `arnndn-rustle` | RNNoise in place of afftdn, needs `rnnoise_model=<path to .rnnn>`. |

Preset format (JSON or YAML): `params` holds defaults; `stages` is a list of ffmpeg filter strings with `{param}` placeholders, plus two special stages: `{"deepfilter": {"atten_lim_db": "{df_atten_db}", "post_filter": false}}` and `{"hum_notch": {"fundamental_hz": 50, "harmonics": 4, "q": 20, "gain_db": -30}}`. Copy a preset to the project folder to experiment; pass it by path.

## DeepFilterNet

Use the official prebuilt `deep-filter` binary from the DeepFilterNet GitHub releases (MIT or Apache-2.0, CPU only, no Python or torch needed). Pass it with `--deep-filter PATH` or `DEEP_FILTER_BIN`. Facts the scripts already handle: it accepts 48 kHz 16-bit or float WAV only (24-bit fails with `TooWide`), writes 16-bit, and returns a file 30 ms short; with `--compensate-delay` the output is aligned and the scripts pad it back to length. With no attenuation limit it writes digital silence in pauses, so the floor flips between black and room tone; prefer `deepfilter-gentle` unless the noise is severe. See `references/denoisers.md` for the measured comparison method.

## Verification gates

| Gate | Tool | Pass |
|---|---|---|
| Length | `process_voice.py` report | `length_difference_samples` = 0 and `alignment_lag_samples` = 0 |
| Floor | `ab_render.py` on the cut voice | `pause_rms_at_minus14_lufs_dbfs` at or below -45 dBFS and at least 2 dB under `tone-only` (compression always lifts the floor above the raw file; see `references/denoisers.md`) |
| Splices | `check_splices.py` | no curvature spike over 12 dB against context; any splice with a peak above -25 dBFS is a cut problem (word clipped), report it to the cutter |
| Gate | `ab_render.py --gate-pair` | `speech_frames_attenuated_pct` = 0, no reopen within 150 ms inside speech |
| Words | `asr_diff.py` | no missing words; differences only on the same uncertain word in both passes |

## Human listen

Hand the user at least five timestamps with what to listen for. `diagnose.py` and `ab_render.py` write a `listen` list per input: first speech onset (gate and denoiser attack), the strongest sibilant (de-esser), the strongest low burst (high-pass), the longest inner pause (floor, gate pumping) and the last tail (gate release). On the cut voice add the held pauses after list markers, where the gate is most likely to close. Compare the `.listen.wav` copies, which are loudness-matched so the louder file does not win by default.

## References

- `references/measurements.md`: what each metric means, how it is computed and the thresholds used above.
- `references/denoisers.md`: afftdn, arnndn and DeepFilterNet behaviour, latency, artefacts, and how to judge "materially better".
