# Previewing one beat over the real A-roll

For component builders. You need a complete `props.json` for the reel (camera, captions, A-roll) and the reel's public dir (the folder that holds the A-roll). The examples use shell variables; set them first:

```bash
SKILL=/path/to/skills/reel-motion          # this skill
WORK=/path/to/reel-work-folder             # public dir: aroll.mp4, cues.json, words.out.json
PY=python3                                 # any Python 3.10+
BASE=$WORK/motion/preview_props.json       # full camera + captions + one beat
```

## 1. Write a beat file

One beat, in the same shape as a beat map entry. `from` and `to` may be anchors (resolved with `--cues`) or plain output seconds. Times inside `props` are seconds relative to the beat's `from`: an anchor there resolves beat-relative (`{"@rel": anchor}` is the explicit form, `{"@rel": 9.5}` converts an absolute time), and a plain number is already relative. Only `props.three` (the 3D spec of `VideoInsert`, see `../../reel-3d/SKILL.md`) stays in absolute seconds.

```json
{
  "id": "PREVIEW",
  "component": "TitleSlam",
  "mode": "card",
  "from": {"@word": "example", "offset": -0.06},
  "to": {"@cutAfter": "example"},
  "layer": 0,
  "props": {"variant": "band", "kicker": "KICKER", "title": "A SHORT TITLE", "numeral": "2"}
}
```

`mode` is `talk`, `card`, `takeover` or `hidden` and moves the captions (card: y 1060, hidden: none). The props must pass the component's `schema` (`src/components/beats/<Name>.tsx`), or the render shows a red BAD PROPS box listing the failing fields.

## 2. Swap it into the base props

```bash
$PY -I $SKILL/scripts/swap_beat.py --props $BASE --beat beat.json --cues $WORK/cues.json \
  --out $WORK/motion/preview/my_props.json            # add --guides to draw the zones
```

It prints the beat's frames and the first-frame (from + 0), entry (from + 4 frames) and exit (to - 2 frames) still times, and rejects a props time outside -0.5 s to the beat length. To keep other beats on screen as well, pass a JSON list of beats instead of one.

## 3. Render stills

```bash
cd $SKILL/remotion && npx tsc -p .
bash $SKILL/scripts/render.sh --props $WORK/motion/preview/my_props.json --public-dir $WORK \
  --still 7.40,7.60,7.92 --out $WORK/motion/preview/stills
bash $SKILL/scripts/render.sh --props $WORK/motion/preview/my_props.json --public-dir $WORK \
  --still-frames 185,189 --out $WORK/motion/preview/stills
```

Always include the first frame (from + 0): with `entranceProgress` sampling one frame ahead it must already show the first step of the entrance, never an empty frame. On a shared machine set `REEL_RENDER_LOCK=/path/to/remotion.lock` (and keep `REEL_CONCURRENCY` at 2) so stills and renders queue instead of overlapping; wrapping the call in `flock` on the same file as well is safe, since `render.sh` skips its own lock when a parent already holds it.

All stills share one bundle (about 15 s, then 1 to 2 s per still). Files are `still_<t>s.png`. Look at every one (Read the PNG): text size, zones, face and caption collisions, colour meanings.

A side-by-side sheet:

```bash
cd $WORK/motion/preview/stills
ffmpeg -v error -y -i still_7.40s.png -i still_7.60s.png -i still_7.92s.png \
  -filter_complex "[0]scale=540:-1[a];[1]scale=540:-1[b];[2]scale=540:-1[c];[a][b][c]hstack=inputs=3" sheet.jpg
```

## 4. Render a short clip

Frames are output frames (`round(t * fps)`), inclusive:

```bash
bash $SKILL/scripts/render.sh --props $WORK/motion/preview/my_props.json --public-dir $WORK \
  --frames 176-205 --out $WORK/motion/preview/clip.mp4
```

Check the motion frame by frame rather than by eye at full speed:

```bash
ffmpeg -v error -y -i $WORK/motion/preview/clip.mp4 -vf "scale=270:-1,tile=10x3" $WORK/motion/preview/clip_frames.jpg
```

## Component contract (summary)

- File `src/components/beats/<Name>.tsx`: `export const schema` (zod), `export type <Name>Props`, `export default <Name>`. The registry already maps every planned component; never edit `registry.ts` for an existing name.
- Arguments: `{ props, frame, durationInFrames, fps, toFrame, beat }`. `frame` is 0 at `beat.from`; `toFrame(t)` turns a beat-relative time from props into a local frame on the output frame grid. Never add `beat.from` yourself.
- Shared building blocks: `import { Card, Tile, Pill, Kicker, Icon, AccentText, zones, boxStyle, useEnterExit, useStamp, shakeOffset, staggerStart, toneColor } from "../ui"`, tokens from `../../theme`, brand files through `brandAsset()`/`brandLogo()` from `../../lib/brand`.
- Rail and checklist: events `{t, segment, state}` (beat-relative; earlier history may be negative) placed on the frame grid with `railEventsOnFrames(events, toFrame, fps)` and read with `railStatesAt(events, count, frame / fps)` from `../../lib/rail`; geometry from `railSegmentRect(i)` and `checklistRowRect(i, count)`, so the rail segments can travel to the checklist icon boxes at `morphIntoChecklistAt` and the `Checklist` (with `fromRail: true`) starts with its icons already in place.
- Draw order: beats draw in ascending `layer` (default 0), list order within a layer; a persistent rail usually takes `"layer": 1`.
- Shakes: `shakeOffset(frame, start, frames, amplitudePx)` is the camera kick's alternating decay; prefer a camera `kick` key (`../SKILL.md`, Kick) for an impact that should move the whole picture.
