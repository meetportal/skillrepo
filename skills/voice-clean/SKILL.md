---
name: voice-clean
description: Diagnose and clean talking-head dialogue audio for short-form video. Use when a reel, short or interview needs its voice track de-essed, compressed, de-hummed or denoised, or checked for clicks, splice dips and noise that processing brings up; when choosing between no denoiser, a downward expander, afftdn with a room-tone profile, RNNoise and DeepFilterNet; when A/B testing voice chains on matched-loudness floor, pause kurtosis and per-word level; or when producing a processed voice.wav from a cut dialogue track and an EDL with per-clip settings.
---

# voice-clean

Measure first, treat second, listen last. Every choice here is backed by a number the scripts print, and every number still needs a human ear before the mix is locked.

## The one rule that decides the chain

**Processing must not make the background louder relative to the voice than it was in the raw cut.** Compression lowers speech and leaves quiet frames alone, so after the mix is normalised the room tone, breaths and mouth noise come up. The pass criterion is `floor_at_minus14_lufs_dbfs.output <= .input` in the `process_voice.py` report (the same number is `floor_vs_source_db <= 0` in `ab_render.py`). A chain that fails it is worse than doing nothing.

## Rules

1. **Diagnose before treating.** Run `diagnose.py` on every source clip: floor, SNR, noise type, hum, sibilance, and a clean room-tone window.
2. **No denoiser on a quiet room.** At a floor of -55 dBFS or lower with SNR 35 dB or more, the default `dialogue` chain uses a soft downward expander instead. A denoiser there removes about 2 dB that compression gives straight back and adds musical noise.
3. **Never use tracking afftdn (`tn=1`).** On measured footage it nearly doubled pause kurtosis (musical noise) and re-tracks across every splice. When a stationary noise needs FFT reduction, use `dialogue-nr`, which samples a fixed profile from room tone (`tn=0`). Prefer `dialogue-df` when the binary is available: it lowers the floor more with less musical noise.
4. **No gate.** A gate closes in the short room-tone gaps at splices and widens them into dead air. The expander in `dialogue` is soft (knee 6 dB, at most 6 dB of reduction, only under -45 dBFS) and is checked by the splice-dip gate.
5. **Compress gently: 2:1 from -14 dB.** Harder compression lifts the floor more than any expander can safely take back.
6. **De-ess lightly and high.** `deess_i` 0.4 with `deess_f` 1.0 leaves vowel frames untouched and cuts sibilant frames by about 2 to 4 dB at 5-10 kHz (vowel frames move 0.3 dB at most at 0.5). 0.5 for a clip whose 5-10 kHz band is above -5 dB of total speech energy, 0.6 above -3 dB. Never lower `deess_f`: at 0.5 the de-esser cuts 3-5 kHz on sibilant frames by 8 dB and the voice lisps.
7. **Never loudness-normalise the voice alone.** The voice leaves this skill un-normalised. Loudness is set once, on the final mix.
8. **Compensate filter latency.** ffmpeg `afftdn` delays audio by 1200 samples at 48 kHz and `arnndn` by 480. `apply_chain` measures each stage's delay by cross-correlation and removes it; never hand-roll a chain with a plain `ffmpeg -af`.
9. **Downmix with an average.** `-af pan=mono|c0=0.5*c0+0.5*c1`, never `-ac 1`, which sums dual mono to +3 dB on float output. The scripts average channels in numpy.
10. **Process the cut timeline in one pass.** Compressor and expander state never restarts at a splice. Per-clip settings are separate full renders switched at EDL boundaries with a 5 ms crossfade.
11. **Write float WAV** so inter-sample peaks survive to the master limiter.
12. **Control peaks here, not on the mix bus.** Every preset ends with a `peak_limit` stage: a look-ahead limiter at 4x oversampling (attack 3 ms, release 50 ms, no auto-release) whose ceiling is set from the stage's own measured loudness, so the true peak sits at most `peak_plr_db` (default 14) dB above the mono voice loudness. `mix.py` plays the voice as dual mono, which reads 3 LU louder, so the voice peaks at about -3 dBTP when the mix is at -14 LUFS and the mix-bus limiter has almost nothing left to do. Isolated consonant onsets pass a 10 ms compressor attack untouched; without this stage a close-mic voice measured 18.8 dB peak to loudness and the mix needed 3.9 dB of bus limiting. At 14 it changed 0.7 % of 10 ms speech frames by more than 2 dB (max 4 dB), lowered the loudness 0.2 dB and kept the floor gate. Going to 12 cost 0.9 dB of loudness and failed the floor gate; do not go under 13.

## Workflow

Run from the reel work folder with `SKILLS` set to this repo's `skills/` folder; call scripts as `python $SKILLS/voice-clean/scripts/<script>.py`. Scripts need Python 3.10+, ffmpeg 6+ and the repo `requirements.txt`; they run under `python -I`. Reel-specific settings live in the work folder (`voice_lab/clip_params.json`).

```bash
# 1. Diagnose each source clip (video files are fine)
python $SKILLS/voice-clean/scripts/diagnose.py clips/*.MP4 --out-dir voice_lab/diagnosis
# prints floor, SNR, LUFS, hum, sibilance, plosives, bursts, a recommendation, and suggested params
# (deess_i per clip, room_tone=<clip>@start:end for dialogue-nr). Look at the spectrum PNGs.

# 2. A/B chains on the cut voice; the source row is the floor to beat
python $SKILLS/voice-clean/scripts/ab_render.py --input voice_cut.wav \
  --presets tone-only dialogue dialogue-df --reference tone-only \
  --gate-pair dialogue:tone-only --words words.out.json \
  --spectrograms --listen-copies --out-dir voice_lab/cut_ab
# per chain: floor@-14 and vs-src (pass/FAIL), pause kurtosis, breath-level frames vs source,
# per-word level against tone-only, and expander activity (closures, speech frames attenuated)

# 3. Process the cut voice; the run fails if a gate fails
python $SKILLS/voice-clean/scripts/process_voice.py --input voice_cut.wav --output voice.wav \
  --preset dialogue --edl edl.json --clip-params voice_lab/clip_params.json \
  --words words.out.json --report voice_lab/voice.report.json

# 4. Verify splices and words
python $SKILLS/voice-clean/scripts/check_splices.py --edl edl.json --audio voice_cut.wav --audio voice.wav --out voice_lab/splices.json
python $SKILLS/voice-clean/scripts/asr_diff.py --reference voice_cut.wav --candidate voice.wav \
  --model large-v3 --prompt "Brand, jargon" --out voice_lab/asr_diff.json
```

`asr_diff.py` here only compares two audio files on the same timeline (raw cut against processed voice). Checking caption words against audio is `reel-captions/scripts/asr_diff.py`.

`clip_params.json` maps a clip's file stem to overrides, optionally with its own preset. A range's audio source is its `a_clip` when the EDL has one (J/L bridge ranges), else its `clip`:

```json
{"CLIP_A": {"deess_i": 0.5}, "CLIP_D": {"preset": "arnndn-rustle", "rnnoise_model": "/models/cb.rnnn"}}
```

Global overrides go on the command line: `--set comp_threshold_db=-16 --set expander_release_ms=40`.

`process_voice.py` refuses an input whose length is not the EDL's audio total, and writes the input and output sha256 and sample counts into the report, so the mix step can prove `voice.wav` came from the current `voice_cut.wav`.

## Decision table by noise type

| Diagnosis (from `diagnose.py`) | Treatment | Preset / params |
|---|---|---|
| Quiet room, close mic: floor at or below -55 dBFS, SNR 35 dB or more | No denoiser; expander under -45 dBFS, 2:1 compression | `dialogue` |
| Floor passes but breaths or room tone still read loud between words | Faster or deeper expander, never a gate | `--set expander_release_ms=40` or `expander_ratio=4`; keep `expander_range` at 0.5 or above |
| Floor gate fails with `dialogue` | Raise the compressor threshold before adding a denoiser | `--set comp_threshold_db=-12` |
| Steady broadband (fan, HVAC, hiss): SNR 25 to 35 dB, floor -55 to -45 | DeepFilterNet capped at 10 dB; fixed-profile afftdn only without the binary | `dialogue-df`; else `dialogue-nr --set room_tone=<clip>@start:end` |
| Loud or changing noise (traffic, wind, crowd, keyboard, water): SNR under 25 dB | Neural enhancement; listen for warbled vowels and swallowed word ends | `deepfilter-full`, then `dialogue-df --set df_atten_db=18` if it warbles |
| Mains hum: `hum_peak_above_local_db` 6 dB or more at 50/60 Hz or harmonics | Narrow notches at the fundamental and three harmonics | `dialogue-hum --set hum_hz=50` (or 60) |
| Handling, cable or clothing rustle in a kept range | Cut it out first. If it must stay, RNNoise on that clip only | `arnndn-rustle` via clip params (check the model licence) |
| Sibilance: 5-10 kHz band above -5 dB of total speech energy | Stronger de-ess on that clip only, same split | `deess_i` 0.5 (above -5 dB) or 0.6 (above -3 dB) |
| Plosive pops: low-frequency bursts in `plosive_events` | The 80 Hz high-pass in every preset; raise to 100 Hz only if still audible | `--set highpass_hz=100` |
| Clipped samples | `adeclip` as the first stage, and flag the take | add `"adeclip"` to a copy of the preset |
| Hot true peak, or peaks far above the loudness (peak to loudness over 14 dB) | The `peak_limit` stage at the end of every preset | `--set peak_plr_db=14` (default); `off` disables it |
| Reverberant room | No reliable fix in this chain; prefer another take or a closer mic | |

## Default chain: dialogue

```
highpass=f=80:poles=2,
equalizer=f=250:t=q:w=1.0:g=-2,
equalizer=f=3500:t=q:w=1.2:g=2.5,
deesser=i=0.4:m=0.5:f=1.0:s=o,
agate=threshold=-45dB:ratio=3:range=0.5:knee=6:attack=5:release=50:detection=rms,
acompressor=threshold=-14dB:ratio=2:attack=10:release=150:makeup=1:knee=6,
peak_limit: aresample=192000,alimiter=limit=<loudness + 14 dB>:attack=3:release=50:level=false:asc=0,aresample=48000
```

The `agate` here is a downward expander, not a gate: 3:1 under -45 dBFS with a 6 dB soft knee and at most 6 dB of reduction. Its fast release is what lets it work in the 50 to 200 ms gaps of a tight cut; at 250 ms it never engages. Every number is a param in `presets/dialogue.json`.

## Presets

| Preset | Use |
|---|---|
| `dialogue` | Default. No denoiser. |
| `dialogue-df` | DeepFilterNet3 capped at 10 dB in front of `dialogue`. Steady or broadband noise. Needs the binary. |
| `dialogue-nr` | afftdn with a fixed profile sampled from `room_tone` (`tn=0`) in front of `dialogue`. Steady noise when DeepFilterNet is not available. |
| `dialogue-hum` | `dialogue` with mains notches. |
| `deepfilter-full` | DeepFilterNet3 with no limit, no expander. Hard noise only. |
| `arnndn-rustle` | RNNoise in front of `dialogue`; needs `rnnoise_model=<.rnnn>`. |
| `tone-only` | `dialogue` without the expander. Reference for log-spectral distance, the per-word gate and the expander activity pair. |

Preset format (JSON or YAML): `params` holds defaults; `stages` is a list of ffmpeg filter strings with `{param}` placeholders, plus special stages:

- `{"deepfilter": {"atten_lim_db": "{df_atten_db}", "post_filter": false}}`
- `{"afftdn_profile": {"nr": "{afftdn_nr}", "nf": "{afftdn_nf}", "room_tone": "{room_tone}"}}`: the room tone (`file` or `file@start:end`, at least 0.2 s) is prepended to the whole chain, afftdn samples its profile from it, and it is cut off again at the end.
- `{"hum_notch": {"fundamental_hz": 50, "harmonics": 4, "q": 20, "gain_db": -30}}`
- `{"peak_limit": {"plr_db": "{peak_plr_db}", "attack_ms": "{peak_attack_ms}", "release_ms": "{peak_release_ms}"}}`: measures the stage input's integrated loudness, limits at loudness + `plr_db` with 4x oversampling, re-measures the true peak and lowers the ceiling by the overshoot (up to 3 passes, 0.2 dB tolerance). `plr_db` `off` or `none` skips the stage. Each pass is listed in the report under `compensated_latency_samples`.

Copy a preset to the work folder to experiment and pass it by path.

## DeepFilterNet

Use the official prebuilt `deep-filter` binary from the DeepFilterNet GitHub releases (MIT or Apache-2.0, CPU only). Pass it with `--deep-filter PATH` or `DEEP_FILTER_BIN`. It accepts 48 kHz 16-bit or float WAV only (24-bit fails with `TooWide`), writes 16-bit and returns a file 30 ms short; the scripts compensate and pad. With no attenuation limit it writes digital silence in pauses. See `references/denoisers.md`.

## Verification gates

| Gate | Tool | Pass |
|---|---|---|
| Length | `process_voice.py` report `gates.length` | output samples equal input samples; input samples equal the EDL audio total |
| Alignment | `gates.alignment` | cross-correlation lag 0 against the input (also check 3 s sections if the cut changed) |
| Floor | `gates.floor` | `floor_at_minus14_lufs_dbfs.output` at or below `.input` |
| Peaks | report `output.true_peak_dbtp - output.lufs_i` | at most `peak_plr_db` + 0.2 dB (14.2 by default) |
| Words level | `gates.words` (with `--words`) | no word more than 1 dB quieter than in `tone-only` with the same per-clip settings |
| Musical noise | `ab_render.py` `pause_kurtosis` | within about 0.15 of the source; tracking afftdn measured +1.8 to +1.9 on raw clips |
| Splices | `check_splices.py` | no curvature spike over 12 dB, no 10 ms level more than 6 dB under the file's room-tone floor within 60 ms of a splice, no peak above -25 dBFS (a word on the splice is a cut problem) |
| Expander | `ab_render.py --gate-pair dialogue:tone-only` | `speech_frames_attenuated_pct` = 0 |
| Words | `asr_diff.py` | no missing or changed words; check `confidence_drops` on brand names and sibilant words by ear |

## Human listen

Hand the user at least five timestamps with what to listen for, on the loudness-matched `.listen.wav` copies so the louder file does not win by default. `diagnose.py` and `ab_render.py` write a `listen` list per input: first speech onset (expander attack), the strongest sibilant (de-esser lisp), the strongest low burst (high-pass), the longest inner pause (floor, expander pumping) and the last tail (expander release on the decay). Add the brand name and any word in `confidence_drops`.

## References

- `references/measurements.md`: every metric, how it is computed, and the thresholds above.
- `references/denoisers.md`: afftdn, arnndn, DeepFilterNet and the expander, latency, artefacts, and how to judge "materially better".
