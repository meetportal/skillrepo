# Measurements

All scripts decode to 48 kHz mono float by averaging channels, then work on 30 ms RMS frames with a 10 ms hop. Frames at or below -90 dBFS (digital silence from fades or padding) are ignored when estimating floors.

## Levels and masks

| Name | Computation | Read it as |
|---|---|---|
| `room_tone_p5_dbfs` / `floor_p5_dbfs` | 5th percentile of frame RMS | The noise floor of a clip with some silence in it. A quiet room with a close mic sits near -59 dBFS. |
| `room_tone_window_s` | longest run of frames within 3 dB of the floor, at least 0.2 s | The window to pass as `room_tone=<clip>@start:end` to `dialogue-nr`. |
| `speech_rms_dbfs` | energy mean of frames above (p90 - 20 dB) | Speech level. |
| `snr_db` | speech RMS minus pause RMS | Over 35 dB: clean. 25 to 35: audible noise in pauses once compressed. Under 25: needs real NR. |
| `pause_rms_dbfs` | energy mean of frames that were under floor + 6 dB **in the source** | The source mask is used for every chain so all chains are compared on the same frames. |
| `pause_rms_at_minus14_lufs_dbfs` | pause RMS shifted by the gain that would bring the output to -14 LUFS | The floor as the viewer hears it after the mix is normalised. |
| `floor_vs_source_db`, `floor_pass` | chain minus source of the line above | **The floor gate: must be 0 or lower.** `process_voice.py` reports the same as `floor_at_minus14_lufs_dbfs`. |
| `low_level_rms_at_minus14_lufs_dbfs`, `low_level_vs_source_db` | same, on source frames between floor + 6 and floor + 20 dB (breaths, mouth noise, word decays) | How much breaths come up relative to the voice. 2:1 compression alone lifts them by about 2 dB; 3:1 at -22 dB lifted them by about 3 dB. |
| `lufs_i`, `lra_lu`, `true_peak_dbtp` | ffmpeg `ebur128=peak=true` | Mono integrated loudness is 3 dB under the same dual-mono file measured as stereo. |
| `astats_*` | ffmpeg `astats` overall | DC offset, peak, RMS, astats' own noise-floor estimate. |

## Noise character

| Name | Computation | Threshold |
|---|---|---|
| `pause_kurtosis` | in every source pause of at least 0.12 s (trimmed by 20 ms each side): STFT (1024, hop 256), power per bin 1-12 kHz divided by the frame's mean power in that band, excess kurtosis of each bin over time, median over bins; then the median over pauses | Spiky time-frequency power is musical noise. Normalising each frame removes broadband gain changes, so an expander does not move it. Within about 0.15 of the source is clean. |

## Tone

| Name | Computation | Threshold |
|---|---|---|
| `speech_band_balance_db` | energy in 80-250, 250-800, 800-2.5k, 2.5k-5k, 5k-10k, 10k-16k relative to 80 Hz-16 kHz, speech frames only | 5k-10k above -5 dB: sibilant, raise `deess_i` on that clip. |
| `sibilance_5k10k_vs_300_3k_db` | 5-10 kHz against the 300-3k body | After de-essing aim for about -5 to -7 dB. Much lower (the old 0.5/0.5 de-ess reached -15 on sibilant frames) means a lisp. |
| `speech_lsd_vs_reference_db` | log-spectral distance between a chain and the reference chain on speech frames, level matched, 80 dB floor | How much a stage changes speech spectra. Differences under about 0.5 dB between chains are noise. |

## Words

| Name | Computation | Threshold |
|---|---|---|
| `word_levels_vs_reference` | RMS over each word's span (words json, start/end or startMs/endMs) in the chain minus the same in the reference chain (`tone-only`, same per-clip settings) | `softened_over_limit` empty at 1 dB: nothing beyond compression, EQ and de-ess is taking level out of words (expander or denoiser eating onsets and tails). |
| `asr_diff.py` `changes` | faster-whisper word sequences of the raw cut and the processed voice, aligned with difflib | No missing or changed words. |
| `asr_diff.py` `confidence_drops` | matched words whose probability falls by more than 0.15 | Listen to each, especially the brand name and sibilant words; a drop with no level loss points at timbre (de-ess, EQ). |

## Events

| Name | Rule | Action |
|---|---|---|
| `hum_peak_above_local_db` | Welch PSD of pause audio, peak at 50/60 Hz and harmonics against the local median | 6 dB or more: notch it. |
| `sibilant_events` | 5-10k over body by more than 3 dB on a frame 15 dB above the floor | Listen to the strongest. |
| `plosive_events` | 20-120 Hz over body by more than 6 dB in the top 3 % of low-band frames | High-pass at 80 to 100 Hz. |
| `nonspeech_bursts` | Outside speech, 12 dB above the floor, 20-300 Hz above 300-3k by 3 dB, at least 30 ms | Handling, bumps, murmurs. Cut, or treat that clip with RNNoise. Breaths do not trigger it. |

## Expander behaviour (`ab_render.py --gate-pair WITH:WITHOUT`)

The two presets must differ only by the expander (`dialogue:tone-only`). Attenuation per frame is the level difference between them.

| Name | Pass |
|---|---|
| `closures`, `closed_time_s`, `closure_windows_s` | Frames more than 3 dB down. With a fast-release expander these are the gaps between phrases; that is its job. |
| `speech_frames_attenuated_pct` | 0. Anything above 0 means it is biting word onsets or tails: lower the threshold or raise the release. |
| `max_attenuation_db` | At most the range (6 dB for `range=0.5`). |

## Splices (`check_splices.py`)

Boundaries where the audio is continuous in the source (same audio clip, `a_out` equals the next `a_in`) are video-only cuts and are reported but never flagged. For real splices:

- `peak_dbfs` in the +/-20 ms window from ffmpeg `astats`. Above -25 dBFS means a word sits on the splice; that is a cut problem.
- `click_ratio_db`: the largest second difference in the window against the 99th percentile in the 200 ms around it. Above 12 dB is a click.
- `dip_below_room_floor_db`: the file's room-tone floor (p5 of 10 ms frames) minus the quietest 10 ms frame within 60 ms of the splice. Above 6 dB is a room-tone hole (fade-out/fade-in pairs or a gate closing on the splice).
