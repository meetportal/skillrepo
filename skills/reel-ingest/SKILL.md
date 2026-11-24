---
name: reel-ingest
description: Probe and analyse raw talking-head clips before editing a short-form vertical reel. Use when new footage arrives for a reel (Reels, TikTok, Shorts), when you need stream facts (range, rotation, timecode/data tracks, dual-mono audio), the right rotation filter, per-frame sharpness, motion, face boxes, blinks and soft windows, or an accurate word-level transcript with energy-snapped word edges and hallucinations stripped.
---

# reel-ingest

Stage 1a of the reel pipeline. Everything here only reads the raw clips; never write next to them. All outputs go to the reel work folder (for example `work/<reel>/ingest/`).

Run every script with a Python that has the packages in the repo `requirements.txt` (opencv-python, numpy, scipy, soundfile, faster-whisper). Scripts take input paths and an output path; they contain no project paths.

## Steps

1. **Probe** every clip.
   ```
   python scripts/probe.py RAW/*.MP4 --out work/<reel>/ingest/probe.json
   ```
   Reports codec, size, fps, frame count, `pix_fmt`, range (`full` for `yuvj*` or `color_range=pc`), rotation metadata (displaymatrix side data or `rotate` tag), data/timecode tracks, and whether the stereo audio is dual-mono (L-R difference at least 30 dB under L). It prints the input flags to use: `-map 0:v:0 -map 0:a:0 -map_metadata -1` plus `-write_tmcd 0` when a tmcd/data track exists and `-ac 1` for dual-mono.

2. **Rotation.** Camera bodies often record vertical shoots as landscape pixels with no rotation tag.
   ```
   python scripts/rotation_check.py RAW/*.MP4 --out work/<reel>/qa/rotation_check.jpg
   ```
   One row per clip with `none, 1, 2, 180, hflip`. Read the sheet: pick the option where the subject is upright and background text reads left to right (a mirrored image needs `hflip` or transpose 0/3). `transpose=1` is 90 degrees clockwise, `transpose=2` is 90 degrees counter-clockwise. If the probe shows rotation metadata, ffmpeg already auto-rotates; do not add a transpose on top.

3. **Frame metrics** (sharpness, motion, face box, landmarks, blinks, soft and sway windows).
   ```
   python scripts/frame_metrics.py RAW/*.MP4 --model MODELS/face_detection_yunet_2023mar.onnx --rotate 2 --out work/<reel>/ingest/frame_metrics.json
   ```
   - `--rotate` must match the edit's rotation so the face boxes are in final pixel space.
   - Per frame: luma, Laplacian variance on a quarter-size frame (`sharp`), mean absolute frame difference (`motion`), largest YuNet face `[x, y, w, h, score]` and 5 landmarks (right eye, left eye, nose, mouth right, mouth left).
   - Per clip: `blinks` (eye patch darkness spikes against a 15-frame median, robust threshold), `soft` (sharpness under 45 % of the clip median: AF hunt, motion blur), `motion` (sway, gestures), `no_face` (hand over lens) and a `face` summary (centre, width, chin) for framing and caption placement.
   - Blink detection is tuned for recall: it also flags half-closed eyes. Treat it as a list of frames that must not sit on a cut, and frame-step anything that matters.

4. **Transcribe** with faster-whisper.
   ```
   python scripts/transcribe.py RAW/*.MP4 --prompt "Brand Name. Product terms. SPF, DKIM, DMARC." --out work/<reel>/ingest/words_raw.json
   ```
   - Default model `large-v3`, `int8` on CPU, beam 5, word timestamps, no VAD, `condition_on_previous_text=False`.
   - Audio is decoded by ffmpeg to a 16 kHz float32 numpy array and passed in directly. Do not pass a file path: some PyAV builds break `faster_whisper.decode_audio` (`metadata_errors` keyword).
   - The prompt is a short keyterm list (brand spelling, acronyms, jargon). It biases spelling; it will not change what was actually said.
   - small/base models absorb leading silence into word starts (onsets 0.3 to 0.6 s early). Never cut from small-model timings.

5. **Snap and clean the words.**
   ```
   python scripts/snap_words.py work/<reel>/ingest/words_raw.json --resegment --frame-metrics work/<reel>/ingest/frame_metrics.json --out work/<reel>/ingest/transcript.json
   ```
   - 10 ms RMS envelope (30 ms window), noise floor = 5th percentile, voiced segments by hysteresis (open at floor + 18 dB, close at floor + 10 dB), gaps under 150 ms merged, except that weak runs (peak under floor + 24 dB: hum, breaths, lip noise) are never merged into speech. Without that exception a faint hum 100 ms after the last word gets absorbed and the last word's end runs into it.
   - Whisper hallucinates on weak runs ("Thank you.", "In.", repeated "It"). Words in a weak segment survive only when they also appear, in order, in the full-clip pass; otherwise the segment becomes a `non_speech_events` entry.
   - `--cache FILE` stores every per-segment transcription, so re-running with different thresholds costs no ASR time.
   - `--resegment` re-transcribes every voiced segment in isolation, which settles which words sit on each side of a pause. Word text is then taken from the full-clip pass wherever the two passes align (it has the right punctuation and casing), timings from the segment pass.
   - The first word of a segment starts at the segment's energy onset, the last word ends at its energy offset (accurate to about 10 ms, decay included). Internal boundaries keep whisper DTW (about +/-60 ms).
   - Stripped: words with no voiced energy within 100 ms (phantoms), and whole segments whose text matches a hallucination phrase (`thank you for watching`, `subscribe`, `www.` and so on; add more with `--hallucination`). They are kept in `non_speech_events` so the cutter stays out of them.
   - Output schema (what `reel-cut` reads): `{"clips": {"<clip stem>": {"file", "words": [{"word", "start", "end", "prob"}], "voiced_segments", "pauses_gt_250ms", "non_speech_events", "blinks", "soft"}}}`.

## Checks before moving on

- Read the rotation sheet and at least one frame per clip.
- Look at `no_face`, `soft` and `motion` windows near the first spoken word of every clip (hand over lens, focus hunt, lean-in at the start of a take).
- Diff the transcript against the script if one exists. Spoken slips (the speaker says a different word) are fixed in the caption layer only, never in audio.
- Words with low `prob` near pauses are the usual hallucination suspects: listen to them.

## Face model (not bundled)

YuNet from the OpenCV model zoo (MIT licence). Download the ONNX file once and pass its path with `--model`:

```
curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

It is loaded with `cv2.FaceDetectorYN.create`. Some OpenCV builds ship no Haar cascades, so YuNet is the face detector here.

## Known gotchas

- Full-range (`yuvj420p`) sources: any filter chain that does not pin the format lets ffmpeg convert to `yuv420p` implicitly at the input. A later explicit `scale=in_range=full` then compresses the range twice. See `reel-grade`.
- Dual-mono audio counts double in loudness meters if left as stereo. Fold it to mono once.
- Timecode (tmcd) and data tracks break some muxers and players: map only `v:0` and `a:0`.
