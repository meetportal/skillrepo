---
name: reel-sound
description: Music bed, sound effects, mix and loudness master for vertical short-form reels (Reels, TikTok, Shorts). Use when a reel needs a licensed music bed picked and checked, beat or downbeat sync of the music to edit points, SFX cues placed on graphic or 3D events and levelled in LU against the voice, a generated licence-free SFX kit, the dialogue + bed + SFX mixed with a word-keyed duck, rides, dropouts and room tone fills, a stale-voice check, a cue sheet, a -14 LUFS / -1.5 dBTP master, or a CREDITS.txt for the audio it used.
---

# Reel sound: music, SFX, mix, master

Stage 3 of the reel pipeline. Inputs: the processed dialogue (`voice.wav`, mono 48 kHz, cleaned, **not** loudness normalised) with its voice-clean report, the beat map and word timings of the cut, the `3d/*.json` event files when the reel has 3D beats, a licensed music file, an SFX library with a manifest (or the generated kit). Output: `mix_pre.wav` (float, pre-master), `mix.wav` (24-bit stereo 48 kHz, mastered, exactly the video length), `qa/mix_report.json`, `qa/cue_sheet.md` and `CREDITS.txt`.

All scripts are in `scripts/`, run with any Python that has the repo `requirements.txt` installed, plus `ffmpeg`/`ffprobe` 6.x on `PATH`. Every script has `--help`.

| Script | Does |
|---|---|
| `analyze_music.py` | Tempo, beat regularity, integrated loudness, energy curve, spectral centroid, band balance, phone-speaker survival, bar-aligned loop points for candidate tracks. |
| `find_downbeats.py` | librosa beat tracking + downbeat phase, then the music start offset (and optional bar-line edits) that put downbeats on given output times. |
| `sfx_cues.py` | `inspect` a library; `place` a beat, word or 3D-event anchored cue list into timed placements: transient alignment, LU levels against the voice (or peak classes), variant rotation, consonant masking nudges, rule and 3D event checks. |
| `sfx_synth.py` | Seeded generator for a licence-free SFX kit (whooshes, impacts, pops, ticks, riser, tone) with a manifest. |
| `mix.py` | Stale-voice guard, voice + word-keyed (or sidechain) ducked bed with rides, dropouts and room tone + SFX to `mix_pre.wav`, then two-pass linear loudnorm, safety limiter, pad/trim, stereo `mix.wav`; writes every measurement, a per-beat table and a cue sheet. |
| `credits.py` | `CREDITS.txt` from the files actually used, matched to their manifests by sha256. |
| `selftest.py` | End-to-end check of the scripts above on generated mock audio. |

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

## 4. Bed level, ducking, rides and dropouts (defaults in `mix.py`)

| Setting | Default | Why |
|---|---|---|
| Voice reference | voice gained to the target loudness (-14 LUFS) before mixing | the master then moves by under 1 dB, so SFX levels hold |
| Bed unducked | 10 LU under the voice (`--bed-under 10`), so about -24 LUFS | the level in gaps |
| Duck mode | `--duck-mode words` (needs `--words words.out.json`) | the bed moves on the word timings, not on the signal: no pumping, no opening in breaths |
| Word-keyed duck | words merged into spans across gaps under 0.3 s; the gain opens 80 ms before each span and holds 120 ms after it; one-pole attack 70 ms, release 450 ms at a 1 kHz control rate; depth `--duck-db 6`; applied as sample gain on the bed stem | the bed is already down when the first consonant lands and stays down for the whole sentence |
| Sidechain duck | `--duck-mode sidechain`: `sidechaincompress` keyed by the voice, ratio 6, attack 15 ms, release 300 ms, threshold calibrated until the ebur128 momentary reduction under speech is within 0.75 dB of `--duck-db` | fallback without word timings; `--duck-hold 150 --duck-ratio 3 --duck-release 600` keeps it steadier |
| Bed EQ | `highpass=f=100:poles=2` (`--bed-eq`) | frees the low end for the voice and the impacts |
| Impact dip | 2.5 dB, 40 ms in, held 350 ms, 250 ms out, for every impact-class SFX | the hit reads without raising the SFX |
| Rides | `--auto-ride-min-margin 10` (0 turns them off, needs `--words`) | any word whose voice-to-bed RMS margin is under 10 dB gets the bed dipped by the shortfall, clamped to 2 to 6 dB, 60 ms ramps outside the word; quiet sentence-final words stay on top |
| Bed dips | `--bed-dip <start>:<end>:<dB>`, repeatable | a manual cut where the rides are not enough (50 ms ramps outside) |
| Dropouts | `--dropout <start>:<end>`, repeatable | a hard stop of the bed for a dead-stop line: 15 ms fade out ending at start, silent to end, 30 ms fade in; listed in the report and the cue sheet |
| End card | `--bed-lift <start>:<dB>`, e.g. `46.5:4` | about -20 LUFS short-term on the card; runs to the last frame, no fade, so the loop restarts on the hook hit |
| Tail fade | `--tail-fade 0.5` (s, default 0) | fades the bed and SFX to silence over the last N seconds; the voice is untouched |

Order on the bed stem: duck (words envelope or sidechain), then impact dips, bed dips, lift, dropouts and tail fade, then the rides, which are measured against that bed. All gain curves run at 1 kHz and are interpolated to samples. Words that start after `--duration` are dropped and words that run past it are clipped (the count is printed), so a trimmed mix can reuse the full `words.out.json`.

The report (`ducking.envelope`) gives the reduction under speech, the gain range inside each merged word span (`span_gain_range_db_max`: the bed moving inside a sentence, the pumping number; the word-keyed duck keeps it under about 2 dB, the sidechain path typically shows 5 to 10 dB) and the rise in gaps of 0.2 s or more. `word_margins` gives the per-word voice to bed + SFX RMS margin (median, p10, min, every word under 8 dB). Aim for a median of 15 dB or more and nothing under about 8 dB. Small ASR models also mistake an SFX transient right after a soft last word for a consonant: keep whooshes and swipes 60 ms or more clear of the end of the last word.

### Voice clip gain and room tone

- `--voice-gain <start>:<end>:<dB>` (repeatable): clip gain on the voice stem with 20 ms ramps outside the window, for one word that came out of voice-clean too soft or too hot.
- `--room-tone-src FILE:<start>:<end>` plus one or more `--room-tone-at <start>:<end>`: the source region (a clean pause of 0.1 s or more, always from `voice.wav`, the processed voice that is mixed) is looped with 20 ms equal-power crossfades, held at the region's own RMS, given the same gain as the voice and laid under each hole with 20 ms fades. A region from `voice_cut.wav` is not denoised or compressed, so its floor and timbre would not match the voice around the hole; `mix.py` warns when the source is not the `--voice` file. Use it for the splice holes the QA `splices` gate flags (room tone drops 10 dB or more). Every fill is listed in the cue sheet.

### Stale-voice guard

```
python scripts/mix.py --voice voice.wav --voice-report voice_lab/voice.report.json --voice-cut voice_cut.wav ...
```

`mix.py` exits 2 before mixing when sha256(`--voice`) is not the report's `output.sha256`, when sha256(`--voice-cut`) is not its `input.sha256` (without `--voice-cut` the input path recorded in the report is checked; when that path no longer exists, for example after the work folder moved, it exits 2 and asks for `--voice-cut`), or when any gate in the report is false. Each problem prints a `VOICE GUARD:` line. Always pass `--voice-report` in a real reel; without it the report carries a warning.

## 5. SFX cue rules

Every cue is paired with a visible event (a card landing, a stamp, a wipe, a 3D land). No SFX for things the viewer cannot see.

### Levels in LU (default when `--voice` is given)

`sfx_cues.py place --voice voice.wav` levels each cue by loudness, not by peak: the gain puts the cue's momentary maximum (400 ms window, BS.1770 K-weighting, of the portion that actually plays) a class offset under the voice's integrated loudness.

| Class | Target LU vs voice | Allowed range | Peak ceiling (safety cap) | Use | Max per reel |
|---|---|---|---|---|---|
| `impact` | -8 | -11 to -6 | -3 dBFS | title slams, 3D lands, logo hit; ducks the bed 2.5 dB | 3 |
| `pop` | -14 | -16 to -12 | -4 dBFS | pops, clicks, ticks, small glitches, dings; 3D glints at -16 at most | |
| `whoosh` | -17 | -19 to -15 | -8 dBFS | moves, wipes, cards sliding in, swells | |
| `riser` | -18 | -20 to -16 | -10 dBFS | build into a reveal | 2 |
| `tone` | -20 | -22 to -18 | -12 dBFS | sustained beeps (monitor, alarm) | |

- With the voice at -14 LUFS an impact sits at about -22 LUFS momentary max, a whoosh at about -31.
- `level_lu` on a cue overrides the class target; outside the range it warns. `peak_ceiling_dbfs` overrides the cap. When the cap bites, the gain is lowered, a warning names the cue and the cue sheet shows the shortfall.
- The ceilings are a safety cap, not the level. The old peak table (pop -14, impact -10 dBFS) put short sounds 5 to 6 LU under their loudness target: a 30 ms pop or a 0.35 s impact has a large peak-to-loudness ratio, so a peak target makes it sound weak.
- `--level-mode peak` (or no `--voice`) keeps the peak-dBFS classes: pop -20 to -14, whoosh -18 to -12, impact -16 to -10, riser -24 to -16, tone -26 to -18 (`peak_dbfs` per cue).
- `mix.py` recomputes the gain of every LU cue from its stored momentary max and the voice level it actually mixes at, so a remix after a voice change keeps the LU targets; it warns when the placements were made against another `voice.wav` (sha256).

### Timing

- **Transient alignment.** The file is shifted so its musical moment lands on the visual frame: `onset` (first point within 6 dB of the peak, for pops, clicks, impacts, dings, glitches), `peak` (the loudest 10 ms inside the loudest 50 ms, for whooshes and risers), `start` or `end`. A manifest entry with `anchor_s` and `align` (the generated kit has both) uses that exact anchor. `sfx_cues.py inspect --library <manifest>` prints each file's onset, swell, anchor and momentary max.
- **Never on a stressed consonant.** With `--words`, any pop, whoosh or impact whose transient falls from 20 ms before to 60 ms after a word onset moves to 1 frame (then 2 frames) before that word. Graphics land 0 to 2 frames before their word, so picture and sound stay together. `allow_on_word` opts a cue out (the hook frame, a logo sting). 3D event cues are never moved: they warn instead, because the sound must stay on the rendered land.
- **Layers.** A whoosh into an impact, or a riser into a sting, is one event: give the secondary layer `layer_of` and it follows its parent's final time. Whoosh layers peak 1 frame before the hit.
- **Variety.** Repeated events use different files (`files` list rotates; the same file twice within 10 s is flagged unless `repeat_ok`, for sounds that must be identical like monitor beeps).
- **Density.** About 15 to 30 events for a 45 to 60 s reel; events closer than 80 ms must be layered. The script fails on a RULE breach unless `--allow-violations`.

### 3D events (reel-3d)

`reel-3d/scripts/render3d.py` writes `3d/<beatId>.json` with `events: [{id, t, kind}]` (`t` in output seconds, `kind` one of `whoosh`, `impact`, `pop`, `glint`). Pass `--events "3d/*.json"` and anchor cues with `"event": "<beatId>.<eventId>"` (plus optional `event_offset` in seconds). Event time wins over `word` and `beat`. A cue that names a missing event stops the script: render the 3D beat first.

- One impact on the land frame (`kind: impact`), never two; the script flags a second impact or one off the land frame.
- The whoosh into a land peaks 1 frame before it: `{"event": "spam3d.land", "event_offset": -0.04, "category": "whoosh", "layer_of": "<impact cue>"}` at 25 fps.
- A glint gets a pop at -16 LU at most; a louder `level_lu` on a glint cue is lowered with a warning.
- An `impact` or `whoosh` event without a cue is listed as `EVENT:` so nothing that moves on screen is silent by accident.

Cue list shape (`sfx_cues.json` in the reel folder):

```json
{"fps": 25,
 "beats": {"B0": 0.0, "B-M1a": 7.2},
 "density": {"min_events": 15, "max_events": 30},
 "cues": [
  {"id": "c06", "beat": "B-M1a", "offset": 0.03, "word": "First", "word_offset": -0.04, "visual": "title slam", "category": "whoosh", "layer_of": "c08"},
  {"id": "c08", "beat": "B-M1a", "offset": 0.07, "word": "First", "visual": "title slam", "category": "impact"},
  {"id": "c11", "event": "spam3d.land", "visual": "3D envelope lands in spam", "category": "impact"},
  {"id": "c12", "event": "spam3d.glint", "visual": "spam badge glint", "category": "pop", "level_lu": -16}
 ]}
```

Time resolution order: `event` (+`event_offset`) when the event exists, else `word` (+`word_offset`) when `--words` is given and the word is found, else `beats[beat] + offset`. `--beats` overrides the beat times with a `{id: seconds}` map or a beat map with `beats[{id, from}]`. Optional per cue: `files` (rotation pool), `level`, `level_lu`, `level_mode`, `peak_dbfs` (peak mode), `peak_ceiling_dbfs`, `align`, `max_dur`, `fade_out`, `allow_on_word`, `repeat_ok`, `duck_bed_db`, `occurrence`.

Library manifest shape: `{"root": ".", "files": [{"file": "impact/y.ogg", "category": "impact", "title", "creator", "license", "license_url", "source_url", "attribution", "sha256", "align"?, "anchor_s"?}]}` (the CC0 kit's `bundled`/`default_kit` lists are read too). `--library` is repeatable, so a vetted CC0 kit and the generated kit can be used together.

```
python scripts/sfx_cues.py place --cues sfx_cues.json --library sfx/manifest.json --library sfx/generated/manifest.json \
  --beats beatmap.json --words words.out.json --events "3d/*.json" --voice voice.wav --out sfx_placements.json
```

### Generated SFX kit (licence-free)

```
python scripts/sfx_synth.py --out-dir sfx/generated --seed 7
python scripts/sfx_synth.py --list
```

Seeded numpy generators write 48 kHz 24-bit WAVs to `<category>/<preset>-NN.wav` plus `manifest.json` entries with `category`, `license: "original"`, `creator: "generated"`, `sha256`, `align`, `anchor_s` and `params` (preset numbers, seed, variant). The same seed gives byte-identical files. `credits.py` accepts `original` and needs no attribution for it.

| Preset | Category | Sound | Variants |
|---|---|---|---|
| `whoosh-move` | `whoosh` | 0.6 s, peak at 0.09 s, band 330 to 2000 Hz, 0.8 octave wide, tail 0.18 s, air 0.15; for camera moves and cards | 3 |
| `whoosh-transition` | `transition` | 0.8 s, peak at 0.32 s, 300 to 1600 Hz, tail 0.25 s; for a takeover or wipe | 2 |
| `whoosh-swell` | `swell` | reversed whoosh 500 to 4200 Hz, peak at 0.78 s; for a reveal or a flash | 1 |
| `impact` | `impact` | sine sweep 120 to 45 Hz, lightly saturated so it survives phone speakers, with a noise click, 0.35 s | 3 |
| `pop` | `pop` | 30 ms band burst 2 to 6 kHz plus a falling sine blip | 3 |
| `tick` | `tick` | 3.2 kHz ping with a click, 60 ms | 2 |
| `riser` | `riser` | 1.5 s noise band rising 300 to 3500 Hz, anchor at its end | 1 |
| `tone` | `tone` | 880 Hz beep, 0.3 s | 1 |

The noise sounds are flattened to a smooth power envelope before the preset envelope is applied, so the measured swell lands within about 3 ms of `anchor_s` at seed 7 (up to about 10 ms on other seeds, the noise itself); alignment uses `anchor_s`, which is exact. The whoosh generator is adapted from an MIT project, see `NOTICE`. Treat the kit as a fallback and a placeholder: a vetted CC0 kit with recorded sounds is still the first choice for impacts.

## 6. Mix and master

```
python scripts/mix.py --voice voice.wav --voice-report voice_lab/voice.report.json --voice-cut voice_cut.wav \
  --music music/bed.mp3 --music-plan music/downbeats.json --sfx sfx_placements.json --words words.out.json \
  --beats beatmap.json --duration <video seconds> --bed-lift <end card start>:4 \
  --out-pre mix_pre.wav --out mix.wav --report qa/mix_report.json --cue-sheet qa/cue_sheet.md --stems-dir audio_stems
```

What it does, in order:

1. Stale-voice guard (section 4). Voice to dual-mono stereo, gained to the target loudness, then clip gains and room tone fills. Bed assembled from the music plan sections (30 ms equal-power crossfades at edits), EQ'd, levelled to `--bed-under` below the voice.
2. Duck (words envelope or calibrated sidechain), then the bed automation and the rides (section 4).
3. SFX bus in numpy, sample-exact: each placement trimmed, faded, gained (LU cues re-levelled against the mixed voice) and placed.
4. Sum of voice + bed + SFX, exactly the duration, float WAV: `mix_pre.wav`. With `--stems-dir` the stems stay: `voice_ref.wav`, `bed_unducked.wav`, `bed_ducked.wav`, `bed_final.wav`, `sfx_bus.wav`.
5. Pass 1 measures `mix_pre.wav` with **ebur128** (the same meter as the delivery gate; loudnorm's own pass-1 reading drifts up to 0.4 LU on short files). If the true peak would exceed -1.5 dBTP after the linear gain, a mix-bus peak limiter takes it down first (up to 3 passes, because limiting lowers the loudness and raises the gain), since loudnorm silently falls back to dynamic mode otherwise. Over 3 dB of limiting prints a warning: fix it upstream (the voice should come from `voice-clean` with its `peak_limit` stage, which holds the voice 14 dB peak to loudness) and remix.
6. Pass 2: `loudnorm=I=-14:TP=-1.5:LRA=7:measured_*:linear=true`. ffmpeg 6.1 also refuses linear mode when the measured LRA exceeds the LRA parameter, so the parameter is raised to the measured LRA (linear mode does not change LRA) and the LRA gate reports the real value. Then `aresample=48000`, safety `alimiter=limit=0.84:level=false:latency=1`, stereo, pad/trim to the duration, 24-bit `mix.wav`. Both limiters run with `latency=1`: without it each `alimiter` delays the audio by its attack (5 ms), and the master came out 10 ms late against the picture.
7. Gates printed and in the report: I within 1 LU of -14, TP at or below -1.5 dBTP, LRA at or below 7 LU, loudnorm reported `linear`, duration exact. Exit code 2 on any failure.

The report (`--report`) also carries: the voice guard result, the duck settings and envelope numbers, every bed event (`bed_events`, `dropouts`, `rides`), the bed level under speech and on the end card in final-mix terms, word margins, and per SFX cue the target and the measured LU (`sfx.cues`, `sfx.lu_delta_max`). Measured LU is the cue's momentary max on the isolated SFX stem at the master gain, so it checks the placement math, not the limiters; `limiter_db` per cue is the gain change the two limiters made to the whole mix over the cue's loudest 400 ms (mix.wav against mix_pre.wav at the master gain), and `sfx.limited_over_1_db` lists the cues where it is more than 1 dB, with a warning.

### Per-beat table and cue sheet

- `--beats beatmap.json` adds `beats`: per beat the voice, bed and SFX loudness in the final mix (LUFS, gated, over the beat window) and the speech margin median and p10 over 400 ms windows centred on each word (voice momentary loudness minus bed + SFX momentary loudness). A p10 under about 6 LU in a beat means the bed or an SFX competes with the words there.
- `--cue-sheet qa/cue_sheet.md`: one table with every SFX (time, frame, cue id, visual, class, target LU, measured LU (stem at master gain), delta, limiter dB, peak, file, layer or 3D event) and one with every bed event (word duck spans, impact dips, bed dips, rides with the word and its margin, dropouts, lift, tail fade, voice gains, room tone fills), plus the per-beat table. Read it before the listening pass; the QA skill reads the dropouts from the report.

Never use `-shortest`; the mix is padded or trimmed to the video duration.

### Self test

```
python scripts/selftest.py
```

Builds mock audio in a temporary folder (a synthetic voice on mock word times, a generated bed, the generated kit, a mock `3d/*.json`) and checks: same seed gives the same kit, whoosh swell within 5 ms of its preset, event cues on the land frame, the glint cap, both duck modes pass the loudness gates, the word-keyed duck moves under 3 dB inside word spans, every LU cue within 1 LU of its target, and the voice guard exits 2 on a mismatched voice. Run it after changing any script here.

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

Every used file must match a manifest entry by sha256, or the script fails. The file lists music, SFX, the attribution lines the post description must carry (CC BY), and checksums. Add `--manifest sfx/generated/manifest.json` when the generated kit was used: its files are credited as original sounds and need no attribution.
