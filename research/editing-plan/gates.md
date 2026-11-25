# Gates

Gates run on every render and a failure blocks delivery. The plan's principle: **measure, then look, then claim.** Every "done" is backed by a number from a script and a frame someone has actually looked at. Audio is backed by numbers plus timestamps for a human listen, never by a claim that it sounds good.

The gates are implemented in [`reel-qa`](../../skills/reel-qa/SKILL.md) (`qa.py`), with stage-level checks in `reel-cut`, `voice-clean`, `reel-sound` and `reel-export`. The skills added several gates the plan did not have; this table is the plan's set with its pass values.

## Gate table

| Gate | Method | Pass |
|---|---|---|
| First frame | Frames 0, 1 and 2 | Face sharp, eyes open, headline readable, no hand or blur |
| Rhythm | Visual-change times from `cues.json` and the beat map, plus scene detection | Largest gap 4.0 s or less |
| Cuts | Contact strips of 10 frames either side of every cut; a stutter check that allows the EDL cut frames | No flash, no blink on a cut frame, no unexpected stutter |
| Audio splices | Waveform around each splice, peak in +/-20 ms | No click, no clipped word start or end |
| Loudness | `ebur128=peak=true` on the delivered MP4 | -14 +/- 1 LUFS, TP at or below -1.5 dBTP, LRA at or below 7 LU |
| Words | faster-whisper large-v3 on the delivered audio, diff against the intended text | No missing or extra words |
| Captions | Per page: bounding box, face-box overlap, onset, duration, contrast | Inside x 70-950 / y 220-1500, clear of the mouth, onset 0 to 2 frames before the word, at least 0.35 s, readable |
| Graphics | Stills at every component's mid frame | Text 44 px or more, nothing outside the safe box, no recreated third-party UI, no unapproved number |
| Colour | `signalstats` per take | Skin Y 145 to 155, YMIN at least 16, YMAX at most 235; the final MP4's levels equal the A-roll's on the same frame (no double conversion) |
| Spec | ffprobe on the delivered file | H.264 High, 1080x1920, SAR 1:1, 25/1 fps, yuv420p, `color_range=tv`, BT.709 primaries, transfer and matrix, exactly 1 video + 1 audio stream (no timecode or data stream), AAC 48 kHz stereo, video and audio durations within 40 ms, total duration equal to the EDL plus the end card within 40 ms |
| Critic | A separate reviewer who has not seen the plan watches the stills, strips and QA numbers | Ranked problems with timecodes; at most 3 fix loops |
| Human listen | Five timestamps handed to a person | The person confirms |

## Gates added by the skills since

Worth knowing because each one came from a failure the plan's set did not catch:

- **Cover windows**: every frame inside a `cover` window must be hidden by a full-frame graphic (skin-coloured pixels under 5 %).
- **Room-tone holes at splices**: a dip of more than 3 dB under the quieter take's room tone at a splice (this is what retired the 30 ms fades, see [revisions.md](revisions.md)).
- **Voice floor**: processing must not raise the background relative to the voice compared with the raw cut.
- **Empty entrance frames**: a beat whose first frame shows an empty card or zone is flagged.
- **Caption pages across cuts**: a page that ends 1 to 3 frames after a cut flashes on the new shot; end it on the cut frame.
- **Frozen spans and flashes** checked on every frame, not only at cuts.
- **Stale outputs**: `reel-director/scripts/status.py` flags a graphics pass rendered from a different A-roll, and the mix refuses a voice whose report does not match the cut.

## Human listen

Numbers cannot judge pumping, masking or taste. Hand a person five timestamps on the delivered file:

1. The hook (frame 0 to about 2 s).
2. The first title slam.
3. The loudest SFX.
4. A held pause (where a gate or expander could pump against the bed).
5. The end card.

Nothing ships as final until someone has listened. Say explicitly in the hand-over what could not be verified.

## Critic loop

1. Run the gates. Fix every failure first.
2. Give a fresh reviewer the stills, contact strips, side-by-side sheets against a reference reel if there is one, and the QA numbers, but not the plan. The brief is "roast, do not praise": score each area (hook, rhythm, cuts, captions, graphics, layout, grade, end) from 1 to 10 with a one-line reason, then list problems ranked by severity with timecode, evidence, one concrete fix and the owning stage.
3. Route each fix to its stage, export a new version, re-run the gates, and use a new reviewer who has not seen the previous critique.
4. Stop after 3 passes, or earlier when a pass has no blocking or major rows and the mean score stopped rising.
5. Record the scores per pass and update the series style bible with the values that won and the traps that were caught.

The current prompt is [`reel-qa/references/critic-prompt.md`](../../skills/reel-qa/references/critic-prompt.md).
