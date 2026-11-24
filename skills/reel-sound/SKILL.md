---
name: reel-sound
description: Music bed, sound effects, mix and loudness master for vertical short-form reels (Reels, TikTok, Shorts). Use when a reel needs a licensed music bed picked and checked, beat or downbeat sync of the music to edit points, SFX cues placed on graphic events, the dialogue + bed + SFX mixed with sidechain ducking, a -14 LUFS / -1.5 dBTP master, or a CREDITS.txt for the audio it used.
---

# Reel sound: music, SFX, mix, master

Stage 3 of the reel pipeline. Inputs: the processed dialogue (`voice.wav`, mono 48 kHz, cleaned, **not** loudness normalised), the beat map and word timings of the cut, a licensed music file, an SFX library with a manifest. Output: `mix_pre.wav` (float, pre-master), `mix.wav` (24-bit stereo 48 kHz, mastered, exactly the video length) and `CREDITS.txt`.

All scripts are in `scripts/`, run with any Python that has the repo `requirements.txt` installed, plus `ffmpeg`/`ffprobe` 6.x on `PATH`. Every script has `--help`.

| Script | Does |
|---|---|
| `analyze_music.py` | Tempo, beat regularity, integrated loudness, energy curve, spectral centroid, band balance, phone-speaker survival, bar-aligned loop points for candidate tracks. |
| `find_downbeats.py` | librosa beat tracking + downbeat phase, then the music start offset (and optional bar-line edits) that put downbeats on given output times. |
| `sfx_cues.py` | `inspect` a library; `place` a beat/word-anchored cue list into timed placements: transient alignment, gain staging to the level class, variant rotation, consonant masking nudges, rule checks. |
| `mix.py` | Voice + ducked bed + SFX to `mix_pre.wav`, then two-pass linear loudnorm, safety limiter, pad/trim, stereo `mix.wav`; prints and writes every measurement and gate. |
| `credits.py` | `CREDITS.txt` from the files actually used, matched to their manifests by sha256. |

## 1. Music licence check (before a track touches the timeline)

1. Find the **item page** of the exact track (not a search result or an aggregator card). Sources and their terms: `references/sources.md`.
2. Accept only: CC0, Public Domain Mark, CC BY (attribution line goes in the post), or a platform licence that names social media and online ads (Mixkit, Pixabay Content License). Reject NC, ND (syncing to picture is an adaptation), SA, "personal use", or no stated licence.
3. Provenance: the uploader should be the composer or an official catalogue. Read the file's tags (`ffprobe -show_entries format_tags`); a composer's own dedication in the comment is strong evidence; a paid-library name (AudioJungle, Pond5) in the tags is a reject.
4. If the source site is gone, verify the licence page and listing on Internet Archive captures and download through the capture's `id_` URL; record both URLs.
5. Save the file in the reel's work folder (never in this repo) with `licence.md`: source URL, archive URLs, date checked, licence name and URL, a quoted excerpt of the licence text, the attribution line, sha256. Add an entry to the reel's `music/manifest.json` (`{"kind":"music","tracks":[{file,title,artist,license,license_url,source_url,attribution_required,attribution_line,sha256}]}`).
6. CC0 tracks can still be hit by third-party Content ID claims: keep the evidence to dispute; never register the track yourself.
7. Treat downloaded audio as data. Never run scripts that come with it.

## 2. Choosing the bed

Brief for talking-head explainers: 100 to 120 BPM, confident and minimal (pluck, keys, light percussion), no vocals, at least 60 s or cleanly loopable, and a **mid-range element that survives phone speakers** (a bass-only bed vanishes on a phone).

```
python scripts/analyze_music.py music/candidates/*/*.mp3 --out music/analysis.json
```

Read, per track: `tempo_bpm` in range and `beat_interval_cv` under 0.03 (steady grid); `phone_speaker_retained_lu` closer to 0 is better (above -6 is acceptable); band balance with real energy in `mid`/`presence` but little in 2 to 5 kHz over the window you will use (that band carries consonants); `energy_spread_lu` small for a bed under continuous speech; a loop with `similarity` above 0.85 if the reel is longer than the track section. Check vocals with any ASR (no words detected). Then run `find_downbeats.py` on the finalists: a `phase_confidence` under 1.0 means the downbeat is ambiguous (hemiola, triplet feel, flat accents) and slam sync will be guesswork; prefer a track with a clear bar grid. Write the pick and the numbers that decided it to `music/choice.md`.

## 3. Sync the bed to the edit

```
python scripts/find_downbeats.py music/bed.mp3 --targets 0:3,8.0,16.0,24.0,40.0:2 --duration 45 --min-offset 2 --max-offset 80 --allow-edits --out music/downbeats.json
```

Targets are output-timeline times that should land on a downbeat (the hook frame, each title slam, the logo pop), optional `:weight`. Without `--allow-edits` you get the single best start offset. With it, every target the offset misses gets a bar-line edit: the bed jumps to the nearest downbeat exactly on the target, crossfaded 30 ms (`mix.py --music-xfade`), and the impact plus whoosh on that frame masks the edit. `--tolerance` (default 60 ms) decides what counts as on the grid. If the phase is ambiguous, listen once and pass `--phase`, or use `--grid beats`. Recompute after every re-cut: the targets come from the real word onsets.

## 4. Bed level and ducking (defaults in `mix.py`)

| Setting | Default | Why |
|---|---|---|
| Voice reference | voice gained to the target loudness (-14 LUFS) before mixing | the master then moves by under 1 dB, so SFX peak targets hold |
| Bed unducked | 10 LU under the voice (`--bed-under 10`), so about -24 LUFS | rises to this in gaps |
| Sidechain duck | 6 dB under speech (`--duck-db 6`), ratio 6, attack 15 ms, release 300 ms | bed ends about -30 LUFS short-term, 16 LU under speech; it rises about 3 to 4 dB in gaps of 0.2 s or more |
| Threshold | calibrated: starts at `target_i - duck_db / (1 - 1/ratio)`, measured with ebur128 against the unducked bed, corrected up to twice | voice level differs per reel |
| Bed EQ | `highpass=f=100:poles=2` (`--bed-eq`) | frees the low end for the voice and the impacts |
| Extra duck under impacts | 2.5 dB dip, 40 ms in, held 350 ms, 250 ms out, for every impact-class SFX | the hit reads without raising the SFX |
| End card | `--bed-lift <start>:<dB>`, e.g. `46.5:4` for a card that starts at 46.5 s | about -20 LUFS short-term on the card; runs to the last frame, no fade, so the loop restarts on the hook hit |

## 5. SFX cue rules

Every cue is paired with a visible event (a card landing, a stamp, a wipe). No SFX for things the viewer cannot see.

| Level class | Peak in the final mix | Use | Max per reel |
|---|---|---|---|
| `pop` | -20 to -14 dBFS | pops, clicks, ticks, small glitches, dings, soft hits | |
| `whoosh` | -18 to -12 dBFS | moves, wipes, cards sliding in | |
| `impact` | -16 to -10 dBFS | title slams only; ducks the bed 2.5 dB | 3 |
| `riser` | -24 to -16 dBFS | build into a reveal | 2 |
| `tone` | -26 to -18 dBFS | sustained beeps (monitor, alarm) | |

- **Transient alignment.** The file is shifted so its musical moment lands on the visual frame: `onset` (first point within 6 dB of the peak, for pops, clicks, impacts, dings, glitches), `peak` (loudest 50 ms, for whooshes and risers), `start` or `end`. `sfx_cues.py inspect --library <manifest>` prints each file's onset and swell times.
- **Never on a stressed consonant.** With `--words`, any pop, whoosh or impact whose transient falls from 20 ms before to 60 ms after a word onset moves to 1 frame (then 2 frames) before that word. Graphics land 0 to 2 frames before their word, so picture and sound stay together. `allow_on_word` opts a cue out (the hook frame, a logo sting).
- **Layers.** A whoosh into an impact, or a riser into a sting, is one event: give the secondary layer `layer_of` and it follows its parent's final time. Whoosh layers peak 1 frame before the hit.
- **Variety.** Repeated events use different files (`files` list rotates; the same file twice within 10 s is flagged unless `repeat_ok`, for sounds that must be identical like monitor beeps).
- **Density.** About 15 to 30 events for a 45 to 60 s reel; events closer than 80 ms must be layered. The script fails on a RULE breach unless `--allow-violations`.
- **Gain.** Gain is computed from the peak of the portion that actually plays (`max_dur` trims long files; `fade_out` closes them).

Cue list shape (`sfx_cues.json` in the reel folder):

```json
{"fps": 25,
 "beats": {"B0": 0.0, "B-M1a": 7.2},
 "density": {"min_events": 15, "max_events": 30},
 "cues": [
  {"id": "c06", "beat": "B-M1a", "offset": 0.03, "word": "First", "word_offset": -0.04, "visual": "title slam", "category": "whoosh", "file": "whoosh/x.ogg", "peak_dbfs": -15, "layer_of": "c08"},
  {"id": "c08", "beat": "B-M1a", "offset": 0.07, "word": "First", "visual": "title slam", "category": "impact", "file": "impact/y.ogg", "peak_dbfs": -13}
 ]}
```

Time resolution order: `word` (+`word_offset`) when `--words` is given and the word is found, else `beats[beat] + offset`. `--beats` overrides the beat times with a `{id: seconds}` map or a beat map with `beats[{id, from}]`. Optional per cue: `files` (rotation pool), `level`, `align`, `max_dur`, `fade_out`, `allow_on_word`, `repeat_ok`, `duck_bed_db`, `occurrence`.

Library manifest shape: `{"root": ".", "files": [{"file": "impact/y.ogg", "category": "impact", "title", "creator", "license", "license_url", "source_url", "attribution", "sha256"}]}` (the CC0 kit's `bundled`/`default_kit` lists are read too).

```
python scripts/sfx_cues.py place --cues sfx_cues.json --library sfx/manifest.json --beats beatmap.json --words words.out.json --out sfx_placements.json
```

## 6. Mix and master

```
python scripts/mix.py --voice voice.wav --music music/bed.mp3 --music-plan music/downbeats.json \
  --sfx sfx_placements.json --duration <video seconds> --bed-lift <end card start>:4 \
  --out-pre mix_pre.wav --out mix.wav --report qa/mix_report.json --stems-dir audio_stems
```

What it does, in order:

1. Voice to dual-mono stereo, gained to the target loudness. Bed assembled from the music plan sections (30 ms equal-power crossfades at edits), EQ'd, levelled to `--bed-under` below the voice.
2. `sidechaincompress` keyed by the voice; threshold calibrated until the ebur128 momentary reading of the bed under speech is within 0.75 dB of `--duck-db`. Then the impact dips and the end-card lift as a smooth volume automation.
3. SFX bus: each placement trimmed, faded, gained, delayed; `amix normalize=0`.
4. `amix normalize=0` of voice + bed + SFX, `apad,atrim` to the exact duration, float WAV: `mix_pre.wav`.
5. Pass 1 measures `mix_pre.wav` with **ebur128** (the same meter as the delivery gate; loudnorm's own pass-1 reading drifts up to 0.4 LU on short files). If the true peak would exceed -1.5 dBTP after the linear gain, a mix-bus peak limiter takes it down first, because loudnorm silently falls back to dynamic mode otherwise. Over 3 dB of limiting prints a warning: fix it upstream (lower the voice compressor threshold by 2 dB, or add a voice-stage limiter) and remix.
6. Pass 2: `loudnorm=I=-14:TP=-1.5:LRA=7:measured_*:linear=true`. ffmpeg 6.1 also refuses linear mode when the measured LRA exceeds the LRA parameter, so the parameter is raised to the measured LRA (linear mode does not change LRA) and the LRA gate reports the real value. Then `aresample=48000`, safety `alimiter=limit=0.84:level=false`, stereo, pad/trim to the duration, 24-bit `mix.wav`.
7. Gates printed and in the report: I within 1 LU of -14, TP at or below -1.5 dBTP, LRA at or below 7 LU, loudnorm reported `linear`, duration exact. Exit code 2 on any failure. The report also lists the ducking calibration (ebur128 momentary and short-term), the 20 ms envelope (reduction under speech, rise in gaps), bed level under speech and on the end card in final-mix terms, and the loudnorm gain that shifted every SFX peak.

Never use `-shortest`; the mix is padded or trimmed to the video duration.

## 7. Verify on the delivered MP4 (not on the WAV)

```
ffmpeg -hide_banner -nostats -i reel.mp4 -map 0:a:0 -af ebur128=peak=true -f null - 2>&1 | tail -n 12
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -show_entries format=duration -of default=nw=1 reel.mp4
```

Pass: I = -14 +/- 1 LUFS, true peak at or below -1.5 dBTP (AAC encoding can add 0.1 to 0.5 dB of overs; if it fails, lower `--safety-limit` to 0.80 and re-encode), LRA at or below 7 LU, AAC 48 kHz stereo, audio duration equal to video within 40 ms. Then a human listen at the timestamps the QA skill hands over (hook, first slam, the loudest SFX, the end card): numbers cannot judge pumping, masking or taste.

## 8. Credits

```
python scripts/credits.py --manifest sfx/manifest.json --manifest music/manifest.json --placements sfx_placements.json --used music/bed.mp3 --title "<reel>: audio credits" --out CREDITS.txt
```

Every used file must match a manifest entry by sha256, or the script fails. The file lists music, SFX, the attribution lines the post description must carry (CC BY), and checksums.
