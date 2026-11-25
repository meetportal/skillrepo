---
name: reel-ingest
description: Probe and analyse raw talking-head clips before editing a short-form vertical reel. Use when new footage arrives for a reel (Reels, TikTok, Shorts), when you need stream facts (range, rotation, timecode/data tracks, dual-mono audio), the right rotation filter, per-frame sharpness, motion, face boxes, blinks and soft windows, or a word-level transcript whose onsets are accurate to one video frame (ASR, energy snapping, hallucination stripping, then CTC forced alignment).
---

# reel-ingest

Stage 1a of the reel pipeline. Everything here only reads the raw clips; never write next to them.

## Conventions

- Run every command from the reel work folder (for example `work/<reel>/`). Outputs go to `ingest/` and `qa/stage1/` inside it.
- `SKILLS` points at the `skills/` folder of this repo: `export SKILLS=/path/to/repo/skills`. Scripts are called as `python $SKILLS/reel-ingest/scripts/<script>.py`.
- `RAW` is the folder of camera files, `MODELS` a folder for downloaded models.
- Use a Python with the repo `requirements.txt` installed (opencv-python, numpy, scipy, soundfile, faster-whisper, torch and torchaudio CPU builds). Every script runs under `python -I`; scripts add their own folder to `sys.path`.
- Scripts take paths as arguments and contain no project paths.

## Steps

1. **Probe** every clip.
   ```
   python $SKILLS/reel-ingest/scripts/probe.py "$RAW"/*.MP4 --out ingest/probe.json
   ```
   Reports codec, size, fps, frame count, `pix_fmt`, range (`full` for `yuvj*` or `color_range=pc`), rotation metadata (displaymatrix side data or `rotate` tag), data/timecode tracks, and whether stereo audio is dual-mono (L-R difference at least 30 dB under L). It prints the flags to use: `-map 0:v:0 -map 0:a:0 -map_metadata -1`, `-write_tmcd 0` when a tmcd/data track exists, and for dual-mono `-af pan=mono|c0=0.5*c0+0.5*c1`. Never fold dual-mono with `-ac 1`: it sums the two identical channels and comes out up to 3 dB hot on float pipelines.

2. **Rotation.** Camera bodies often record vertical shoots as landscape pixels with no rotation tag.
   ```
   python $SKILLS/reel-ingest/scripts/rotation_check.py "$RAW"/*.MP4 --out qa/stage1/rotation_check.jpg
   ```
   One row per clip with `none, 1, 2, 180, hflip`. Read the sheet: pick the option where the subject is upright and background text reads left to right. `transpose=1` is 90 degrees clockwise, `transpose=2` is 90 degrees counter-clockwise. If the probe shows rotation metadata, ffmpeg already auto-rotates; do not add a transpose on top.

3. **Frame metrics** (sharpness, motion, face box, landmarks, blinks, soft and sway windows).
   ```
   python $SKILLS/reel-ingest/scripts/frame_metrics.py "$RAW"/*.MP4 --model "$MODELS"/face_detection_yunet_2023mar.onnx --rotate 2 --out ingest/frame_metrics.json
   ```
   - `--rotate` must match the edit's rotation so face boxes are in final pixel space.
   - Per frame: luma, Laplacian variance on a quarter-size frame (`sharp`), mean absolute frame difference (`motion`), largest YuNet face `[x, y, w, h, score]` and 5 landmarks (right eye, left eye, nose, mouth right, mouth left).
   - Per clip: `blinks`, `soft` (sharpness under 45 % of the clip median), `motion`, `no_face` and a `face` summary.
   - Whole-frame sharpness misses a soft face on a sharp background. For any frame that will be a thumbnail, a loop frame or a cut frame, measure the Laplacian variance of the face box crop at full resolution and look at the crop.

4. **Transcribe** with faster-whisper.
   ```
   python $SKILLS/reel-ingest/scripts/transcribe.py "$RAW"/*.MP4 --prompt "Brand Name. Product terms. Acronyms." --out ingest/words_raw.json
   ```
   - Default model `large-v3`, `int8` on CPU, beam 5, word timestamps, no VAD, `condition_on_previous_text=False`. Audio is decoded by ffmpeg (mono fold with `pan`) into a 16 kHz numpy array.
   - The prompt is a short keyterm list. It biases spelling; it does not change what was said.

5. **Snap and clean the words** (text and segment membership).
   ```
   python $SKILLS/reel-ingest/scripts/snap_words.py ingest/words_raw.json --resegment --cache ingest/segment_cache.json \
     --frame-metrics ingest/frame_metrics.json --out ingest/words_snapped.json
   ```
   - 10 ms RMS envelope, noise floor = 5th percentile, voiced segments by hysteresis (open at floor + 18 dB, close at floor + 10 dB), short gaps merged except into weak runs (hum, breaths).
   - `--resegment` re-transcribes every voiced segment in isolation; text comes from the full-clip pass wherever the passes agree.
   - Strips phantom words and hallucinated segments (`thank you for watching`, `subscribe`, `www.` and so on; add more with `--hallucination`) into `non_speech_events`.
   - Whisper word times inside continuous speech are off by up to 0.5 s, and a breath before a phrase is often counted as its first word. This step is for text only; step 6 sets the times.

6. **Force-align the words** (the timing every later stage uses).
   ```
   python $SKILLS/reel-ingest/scripts/align_words.py ingest/words_snapped.json \
     --pronunciations config/pronunciations.json --overrides config/word_overrides.json --out ingest/transcript.json
   ```
   - torchaudio `MMS_FA` (wav2vec2 CTC forced aligner, CPU, model downloaded once by torchaudio) aligns the snapped text against the audio in windows split at gaps over 1.2 s. A wildcard token sits at every pause over 0.2 s so breaths and stray sounds do not drag words.
   - Text is turned into spoken letters first: numbers become words (`2026` to `twenty twenty six`), all-caps tokens of 2 to 5 letters are spelled as letter names. Acronyms said as words go in `--pronunciations`, for example `{"SQL": "sequel", "NASA": "nasa"}`.
   - Onsets are then refined on a 10 ms window, 5 ms hop envelope: after silence the onset is where the envelope climbs above room tone + 20 dB (breaths stay under it, nasal and glide onsets clear it); inside continuous speech it moves to the deepest envelope dip in the 120 ms before the aligner's start when that dip is 6 dB under the word. Phrase-final words end where the envelope falls to floor + 10 dB (decay included).
   - `--overrides` is a short list of onsets set by ear and envelope where the aligner is wrong, usually vowel-to-vowel or glide joins: `[{"clip": "CLIP_A", "word": "example", "near": 6.0, "start": 5.905}]`. Every override needs a reason in the reel notes.
   - Output schema (what `reel-cut` reads): `{"clips": {"<clip stem>": {"file", "words": [{"word", "start", "end", "prob", "ctc_start", "ctc_end", "align_score", "onset_method"}], "voiced_segments", "pauses_gt_250ms", "non_speech_events", "blinks", "soft"}}}`.

7. **Onset gate.**
   ```
   python $SKILLS/reel-ingest/scripts/check_onsets.py --transcript ingest/transcript.json --out ingest/onsets_energy.json
   python $SKILLS/reel-ingest/scripts/check_onsets.py --transcript ingest/transcript.json --asr-every 1 --model medium.en --threads 2 --out ingest/onsets_asr.json
   ```
   - Energy test: every word that follows a quiet frame (within 10 dB of room tone in the 80 ms before it) is measured against the energy rise (the point where a 5 ms window stays 12 dB above that quiet frame for 20 ms). Gate: every one within one video frame.
   - ASR leak test: the audio from each onset to three words later is transcribed. If it starts with the previous word, the onset sits early, inside the previous word. Gate: no leaks.
   - Both must pass before `reel-cut` runs. On the cut audio, the same script takes `--words words.out.json --audio voice_cut.wav`. `--threads` (default 2) caps the faster-whisper CPU threads of the ASR test on a shared machine.

## Checks before moving on

- Read the rotation sheet and at least one frame per clip.
- Look at `no_face`, `soft` and `motion` windows near the first spoken word of every clip.
- Diff the transcript against the script if one exists. Spoken slips are fixed in the caption layer (`reel-captions`), never in audio.

## Face model (not bundled)

YuNet from the OpenCV model zoo (MIT licence). Download the ONNX file once and pass its path with `--model`:

```
curl -L -o "$MODELS"/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

## Known gotchas

- Full-range (`yuvj420p`) sources: any filter chain that does not pin the format lets ffmpeg convert to `yuv420p` implicitly at the input, and a later explicit `scale=in_range=full` compresses the range twice. See `reel-grade`.
- Dual-mono audio counts double in loudness meters if left as stereo. Fold it to mono once, with `pan`.
- Timecode (tmcd) and data tracks break some muxers and players: map only `v:0` and `a:0`.
- Energy snapping alone cannot place onsets inside continuous speech, and a breath before a phrase reads as speech to it. Always run the forced alignment.
