# Denoisers and the expander

## Why a quiet room gets no denoiser

Compression lowers speech and leaves quiet frames alone. Once the mix is normalised, everything quiet (room tone, breaths, mouth noise) comes up by roughly the loudness the compressor took away. On a close mic in a quiet room a light FFT denoiser removes about 2 dB of room tone, a 3:1 compressor gives about 3 dB back, and the result is a louder background than the raw file plus a musical-noise signature. The fix is to stop lifting the floor rather than to subtract noise:

- compress gently (2:1 from -14 dB),
- add a soft downward expander under -45 dBFS that pushes the quiet frames down by up to 6 dB,
- judge the chain against the raw cut at matched loudness, not against another processed chain.

## Downward expander (ffmpeg agate as an expander)

- `agate=threshold=-45dB:ratio=3:range=0.5:knee=6:attack=5:release=50:detection=rms`.
- `range=0.5` caps reduction at 6 dB, so room tone never drops to black and splices never turn into dead air. A gate (high ratio, range 0.25 or lower) does, and it closes exactly in the short room-tone gaps that a cut leaves at splices.
- Release must be short. Gaps in a tight cut are 50 to 200 ms; with a 250 ms release the expander never engages and the floor is unchanged.
- It is broadband gain, so it adds no musical noise (pause kurtosis stays at the source value).
- Check it with `ab_render.py --gate-pair dialogue:tone-only`: `speech_frames_attenuated_pct` must be 0, and with `--words` no word may lose more than 1 dB.

## afftdn (ffmpeg, FFT spectral subtraction)

- **Tracking mode (`tn=1`) is not used.** On measured raw clips it raised median pause kurtosis from 2.2 to 4.0 and from 1.8 to 3.6 (musical noise), and it re-tracks the noise estimate across every splice.
- `dialogue-nr` runs afftdn with a fixed profile (`tn=0`) sampled from a room-tone window through `asendcmd ... afftdn sn start/stop`. The room tone is prepended to the chain input and removed at the end. It still raised pause kurtosis by about 0.7 to 1.3 on the same clips, so prefer `dialogue-df`.
- `nr` 6 is light, 10 to 12 is strong for this mode.
- **Latency: 1200 samples (25 ms) at 48 kHz.** Compensated by `apply_chain`.

## DeepFilterNet 3 (`deep-filter` binary)

- Official prebuilt binary from the DeepFilterNet GitHub releases; MIT or Apache-2.0; CPU; about 4x faster than real time on an 8-core CPU.
- Input: 48 kHz WAV, 16-bit or float. 24-bit fails with `TooWide`. Output: 16-bit, 30 ms shorter than the input. With `--compensate-delay` the content is aligned; the scripts pad it to length.
- `--atten-lim-db` caps how much noise is removed. 10 dB (`dialogue-df`) keeps a natural room under the voice and measured the smallest kurtosis rise of any denoiser (+0.04 to +0.35). 100 (no limit, `deepfilter-full`) writes digital silence in pauses so the background flips between black and room tone; only for severe noise.
- Handles non-stationary noise (traffic, crowd, keyboard, wind) that afftdn cannot.
- It changes speech spectra more than no denoiser (log-spectral distance about 1.5 dB against `tone-only`); listen for dulled consonants.

## arnndn (ffmpeg, RNNoise)

- Needs an `.rnnn` model file. The common community model set has no stated licence, so check before production use.
- The only classic tool that removes handling rustle. `mix` below 1 blends the original back.
- **Latency: 480 samples (10 ms)**, compensated by the scripts.
- Can dull the top octave on some voices (measured up to -0.7 dB at 5-10 kHz); compare band balance against `tone-only`.

## Judging "materially better"

A denoiser earns its place on a reel when, on the cut voice and against `dialogue`:

1. it lowers `pause_rms_at_minus14_lufs_dbfs` by about 6 dB or more (under 3 dB is inaudible under a music bed at -30 LUFS short-term),
2. `pause_kurtosis` stays within about 0.15 of the source,
3. `speech_band_balance_db` stays within 0.5 dB of `tone-only` in every band and `speech_lsd_vs_reference_db` does not rise by more than about 0.5 dB,
4. no word loses more than 1 dB against `tone-only`,
5. a listen at the listen timestamps finds no warble, no swallowed word ends and no black-to-room flips.

Measure on the cut timeline, not only on raw clips: raw clips include pre-roll rustle and long silences that the cut removes, which exaggerates neural denoisers' advantage.
