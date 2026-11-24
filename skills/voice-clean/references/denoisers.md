# Denoisers

## afftdn (ffmpeg, FFT spectral subtraction)

- Best for stationary room tone and hiss. `nf` must be the measured floor (room tone p5 + 1 dB); `nr` 10 is light, 15 to 20 is strong.
- `tn=1` tracks the noise floor through the file. Process the whole cut voice in one pass so tracking never restarts.
- **Latency: 1200 samples (25 ms) at 48 kHz.** The output is late and the last 25 ms are dropped unless the chain is compensated. `process_voice.py` measures and removes it.
- Low speech damage at `nr` 10. It cannot touch non-stationary noise (rustle, bumps).

## arnndn (ffmpeg, RNNoise)

- Needs an `.rnnn` model file. The common community model set has no stated licence, so check before production use.
- The only classic tool that removes handling rustle. `mix` below 1 blends the original back.
- **Latency: 480 samples (10 ms)**, compensated by the scripts.
- Can dull the top octave on some voices (measured up to -0.7 dB at 5-10 kHz); compare band balance against `tone-only`.

## DeepFilterNet 3 (`deep-filter` binary)

- Official prebuilt binary from the DeepFilterNet GitHub releases; MIT or Apache-2.0; CPU; about 4x faster than real time on an 8-core CPU.
- Input: 48 kHz WAV, 16-bit or float. 24-bit fails with `TooWide`. Output: 16-bit, 30 ms shorter than the input. With `--compensate-delay` the content is aligned; the scripts pad it to length.
- `--atten-lim-db` caps how much noise is removed. 12 to 18 dB keeps a natural room under the voice. 100 (no limit) writes digital silence in pauses, so the background flips between black and room tone at every phrase. Only use it for severe noise and listen for it.
- Handles non-stationary noise (traffic, crowd, keyboard, wind) that afftdn cannot.
- The Python package (`pip install deepfilternet`) pulls in torch and torchaudio; the binary needs neither.

## Gate (agate)

- chain09's gate is gentle: ratio 2, range 0.25 (12 dB), threshold 0.003 (about -50 dBFS), release 150 ms.
- On a tightly cut reel most gaps are shorter than the release, so the gate closes only in the deliberately held pauses. It never needs to be stronger; if it is heard opening and closing without a music bed, use `chain09-nogate`.

## Why the floor rises after the chain

A 3:1 compressor lowers speech by several dB and leaves the quiet frames alone, so after loudness normalisation the floor is higher than in the raw recording. That is expected. Judge denoisers against `tone-only` (same EQ, de-ess and compression, no NR), never against the raw file.

## Judging "materially better"

A denoiser upgrade is worth its cost when, on the cut voice, it:

1. lowers `pause_rms_at_minus14_lufs_dbfs` by about 6 dB or more against the default (a doubling of perceived quietness needs about 10 dB; under 3 dB is inaudible under a music bed at -30 LUFS short-term),
2. keeps `speech_band_balance_db` within 0.5 dB of `tone-only` in every band,
3. does not raise `speech_lsd_vs_reference_db` by more than about 0.5 dB,
4. passes a listen at the listen timestamps with no warble, no swallowed word ends and no black-to-room flips.

Measure on the cut timeline, not only on raw clips: raw clips include pre-roll rustle and long silences that the cut removes, which exaggerates neural denoisers' advantage.
