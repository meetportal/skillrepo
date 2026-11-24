# Measurements

All scripts decode to 48 kHz mono float by averaging channels, then work on 30 ms RMS frames with a 10 ms hop. Frames at or below -90 dBFS (digital silence from fades or padding) are ignored when estimating floors.

## Levels and masks

| Name | Computation | Read it as |
|---|---|---|
| `room_tone_p5_dbfs` / `floor_p5_dbfs` | 5th percentile of frame RMS | The noise floor of a clip with some silence in it. A quiet room with a close mic sits near -59 dBFS. |
| `speech_rms_dbfs` | energy mean of frames above (p90 - 20 dB) | Speech level. |
| `snr_db` | speech RMS minus pause RMS | Over 35 dB: clean. 25 to 35: audible noise in pauses once compressed. Under 25: needs real NR. |
| `pause_rms_dbfs` | energy mean of frames that were under floor + 6 dB **in the source** | Uses the source mask for every chain so all chains are compared on the same frames. On a tightly cut track these frames are breaths and decays, not room tone. |
| `pause_rms_at_minus14_lufs_dbfs` | pause RMS shifted by the gain that would bring the output to -14 LUFS | The floor as the viewer hears it after the mix is normalised. Compare chains on this, not on raw dBFS, because compression changes the speech level. |
| `lufs_i_mono`, `lra_lu`, `true_peak_dbtp` | ffmpeg `ebur128=peak=true` | Mono integrated loudness is 3 dB under the same dual-mono file measured as stereo. |
| `astats_*` | ffmpeg `astats` overall | DC offset, peak, RMS, astats' own noise-floor estimate. |

## Tone

| Name | Computation | Threshold |
|---|---|---|
| `speech_band_balance_db` | energy in 80-250, 250-800, 800-2.5k, 2.5k-5k, 5k-10k, 10k-16k relative to 80 Hz-16 kHz, speech frames only | 5k-10k above -5 dB: sibilant, de-ess harder on that clip. A 2.5k-5k dip under -12 dB with a strong 5k-10k reads as "spitty and boxy" (presence lift plus de-ess). |
| `sibilance_5k10k_vs_300_3k_db` | 5-10 kHz against the 300-3k body | After de-essing aim for about -6 dB or lower. |
| `speech_lsd_vs_reference_db` | log-spectral distance between a chain and the reference chain on speech frames, level matched, 80 dB floor | How much a denoiser changes speech spectra. It also counts noise removed between harmonics, so it is an upper bound on damage. Differences under about 0.5 dB between chains are noise. |

## Events

| Name | Rule | Action |
|---|---|---|
| `hum_peak_above_local_db` | Welch PSD of pause audio, peak at 50/60 Hz and harmonics against the local median | 6 dB or more: notch it. |
| `sibilant_events` | 5-10k over body by more than 3 dB on a frame 15 dB above the floor | Listen to the strongest. |
| `plosive_events` | 20-120 Hz over body by more than 6 dB in the top 3 % of low-band frames | High-pass at 80 to 100 Hz. |
| `nonspeech_bursts` | Outside speech, 12 dB above the floor, 20-300 Hz above 300-3k by 3 dB, at least 30 ms | Handling, bumps, murmurs. Cut, or treat that clip with RNNoise. Breaths do not trigger it. |

## Gate behaviour (`ab_render.py --gate-pair WITH:WITHOUT`)

The two presets must differ only by the gate. Attenuation per frame is the level difference between them.

| Name | Pass |
|---|---|
| `closures`, `closed_time_s`, `closure_windows_s` | Closures should sit in pauses only. Listen to each window if there is no bed. |
| `speech_frames_attenuated_pct` | 0. Anything above 0 means the gate is cutting word onsets or tails: lower `gate_threshold`. |
| `reopen_within_150ms_at_s` | Empty inside speech. Fast reopen is chatter: raise release or lower the threshold. |

`pause_level_spread_db` (p95 minus p5 within pauses) and `gate_zone_gain_step_db` (frame-to-frame gain change near the threshold) are secondary; a gate that does its job raises the spread by roughly its range.

## Splices (`check_splices.py`)

Boundaries where the audio is continuous in the source (same audio clip, `a_out` equals the next `a_in`) are video-only cuts and are reported but never flagged. For real splices:

- `peak_dbfs` in the +/-20 ms window from ffmpeg `astats`. Above -25 dBFS means a word sits on the splice; that is a cut problem.
- `click_ratio_db`: the largest second difference in the window against the 99th percentile in the 200 ms around it. Above 12 dB is a click.
