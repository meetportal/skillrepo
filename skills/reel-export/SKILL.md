---
name: reel-export
description: Delivery encode for vertical short-form reels (Instagram Reels, TikTok, YouTube Shorts). Use when the graphics pass (gfx.mp4) and the mastered mix (mix.wav) are ready and need to become the final upload MP4, when checking a file against the upload spec with ffprobe, when exporting a cover image and checking the grid crop, when writing an SRT for platform captions, or when naming and versioning deliveries.
---

# reel-export

Stage between the mix and QA. Inputs: `out/gfx.mp4` (muted, 1080x1920, 25 fps, tv range, BT.709, from `reel-motion`) and `mix.wav` (mastered, from `reel-sound`). Output: `out/<name>_vN.mp4` plus a sidecar `out/<name>_vN.json`, and optionally `_cover.jpg`, `_cover_4x5.jpg`, `_cover_check.jpg` and `.srt`.

```bash
python $SKILLS/reel-export/scripts/export.py --video out/gfx.mp4 --audio mix.wav \
  --out-dir out --name reel --edl edl.json --extra-sec 2.5 \
  --cover-time 0.40 --keep-box 70,300,950,520 --srt words.out.json
```

Run from the reel work folder. `--dry-run` prints the ffmpeg command and the version it would write. Exit 1 when the spec gate fails. `--threads N` caps the x264 and filter threads (for a shared machine); without it ffmpeg uses every core.

## The encode (fixed spec)

```
ffmpeg -i gfx.mp4 -i mix.wav \
  -filter_complex "[1:a]apad,atrim=end=<V>,aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]" \
  -map 0:v:0 -map "[a]" \
  -c:v libx264 -preset slow -profile:v high -level:v 4.2 -crf 18 -maxrate 16M -bufsize 32M \
  -g 50 -keyint_min 25 -bf 2 -pix_fmt yuv420p -r 25 -fps_mode cfr \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
  -c:a aac -profile:a aac_low -b:a 256k -ar 48000 -ac 2 \
  -map_metadata -1 -map_chapters -1 -movflags +faststart out/reel_vN.mp4
```

- `<V>` is the video length from its packet count (frames / fps). The audio is padded with silence or trimmed to exactly that. **Never `-shortest`**: it hides drift and can drop the last frames.
- No scale and no range conversion here. The A-roll was converted to tv range once, in `reel-cut`; a second conversion lifts blacks by about 10 codes and dulls whites. The script rejects a graphics pass that is not 1080x1920, not 25 fps, or tagged full range.
- The graphics pass is re-encoded (not stream-copied) so profile, level, GOP and colour tags are ours: Remotion's own output is level 4.0 with its own GOP.
- CRF 18 with a 16 Mbit/s cap: a 50 s reel with graphics lands at about 10 Mbit/s, 60 MB. Platforms re-encode everything; a clean high-bitrate upload survives that better than a 3 to 5 Mbit/s file.
- `--preset` faster than `slow` is for drafts only. A 49 s reel at `slow` takes about 60 s on 8 cores.
- Loudness is not touched here (the mix is mastered in `reel-sound`). The script measures it on the output and prints it; `reel-qa` gates it. AAC encoding can add 0.1 to 0.5 dB of true peak.

## Spec gate (ffprobe, `scripts/delivery_spec.py`)

Run automatically after the encode, and by `reel-qa`:

| Check | Expected |
|---|---|
| streams | exactly 1 video + 1 audio; no tmcd or data track |
| video | h264, profile High, level 42, 1080x1920, SAR 1:1, `r_frame_rate` 25/1 equal to `avg_frame_rate` (CFR), yuv420p |
| colour | `color_range=tv`, `color_space`, `color_transfer`, `color_primaries` all bt709 |
| audio | aac, profile LC, 48000 Hz, 2 channels |
| durations | video vs audio within 40 ms; video vs expected (`--expected-duration`, or `--edl` duration + `--extra-sec`) within 40 ms |
| faststart | top-level `moov` atom before `mdat` |

A warning before the encode ("graphics pass is X s but the expected duration is Y s") almost always means a stale graphics render: re-render it, do not export.

## Versioning

- Never overwrite a delivery. Without `--out`, the script writes `<out-dir>/<name>_v(N+1).mp4`, where N is the highest existing version. With `--out`, an existing file is refused.
- Every version gets `<name>_vN.json`: input paths and md5s, duration, the ffmpeg command, the spec gate result, measured loudness, cover and SRT paths. That is how you prove which mix and which graphics pass a delivery came from.
- A failed gate still leaves the file (for inspection) and consumes the number. The next export is N+1.
- Hand over the version number, not "the final file". Record it in `project.md` with the QA verdict.

## Cover image

`--cover-time T` (output seconds) writes:

- `<name>_vN_cover.jpg`: 1080x1920, the frame at T, for the Reels cover and TikTok cover picker.
- `<name>_vN_cover_4x5.jpg`: the 1080x1350 centre crop (y 285 to 1635), the Instagram feed preview.
- `<name>_vN_cover_check.jpg`: the frame at half size with the 4:5 crop in yellow and the 3:4 profile-grid crop (1080x1440, y 240 to 1680) in cyan.
- `--keep-box x0,y0,x1,y1` (for example the hook headline's box) fails the export when the box leaves the 1080x1350 crop. Headlines placed from y 220 (the top of the reel safe zone) do not survive the 4:5 crop: either start the cover text at y 300 or later, or design a separate cover frame.

Pick a frame where the face is sharp, eyes open, mouth closed or mid-vowel, and the hook text fully on screen. Read the check image before using it.

## SRT

`--srt words.out.json` writes `<name>_vN.srt` from the corrected caption words (Remotion `Caption[]`): a new cue at sentence ends, at pauses of 0.5 s or more, or when a cue would pass 32 characters (`--srt-max-chars`) or 4 s; each cue ends 0.2 s after its last word (never past the next cue) and lasts at least 0.7 s. Upload it as the subtitle track on YouTube Shorts for accessibility and search; the burned-in captions stay as they are. Instagram and TikTok generate their own auto-captions; turn those off on the post if they duplicate the burned-in ones.

## Platform notes (check each platform's help page before relying on limits; they change)

| | Instagram Reels | TikTok | YouTube Shorts |
|---|---|---|---|
| Frame | 9:16, 1080x1920 | 9:16, 1080x1920 | 9:16 (or square), 1080x1920 |
| Frame rate | 23 to 60 fps accepted; keep the source rate (25) | 24 to 60 accepted; keep 25 | any common rate; keep 25 |
| Length | up to 3 min | up to 10 min in app | up to 3 min |
| UI overlap (1080x1920) | top 210, bottom 310 (more with a long audio title), right about 90 | top 108 plus tabs, bottom 320 (370 for ads), right 120 | top 120, bottom 300 (360 with description), right 96 |
| Cover | picked from a frame or uploaded; profile grid shows a 3:4 centre crop, feed shows 4:5 | picked in the upload flow | thumbnail picked from a frame in the app |
| Captions | burned-in; platform auto-captions optional | burned-in; auto-captions optional | burned-in plus an uploaded SRT |

The universal safe box for text and logos is x 70 to 950, y 220 to 1500 (bottom 420 px and right 130 px kept clear). One master file serves all three platforms; do not make per-platform encodes unless a platform rejects the file.
