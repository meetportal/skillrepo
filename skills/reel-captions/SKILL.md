---
name: reel-captions
description: Burned-in caption text and rendering for vertical talking-head reels. Use when turning ASR word timings into on-screen captions, correcting caption text (brand names, acronyms, spelling) without touching timings, choosing accent words and the accent style, tuning caption pages (words per page, pauses, line limits, timing across cuts), fixing caption contrast on bright walls, or checking a delivered reel for missing or ghost words with an ASR diff.
---

# Reel captions

Captions are rendered by the `reel-motion` Remotion project (`src/components/Captions.tsx`, page rules in `src/lib/captionPages.ts`), always as the last layer. This skill owns the text that goes in, the page rules, and the checks that come out.

## Conventions

Run from the reel work folder with `SKILLS` set to this repo's `skills/` folder; call scripts as `python $SKILLS/reel-captions/scripts/<script>.py`. Reel-specific files live in the work folder's `config/`.

## 1. Correction layer (the only place caption text changes; timings never change)

There is one correction format and one script. `reel-cut` never edits text: it writes `words.retimed.json` (Remotion `Caption[]` with the transcribed text on the output timeline). This skill turns it into `words.out.json`, which everything downstream reads (`cues.json`, Remotion, SFX, QA).

Exact order in a reel:

1. `reel-cut/scripts/retime_words.py` writes `words.retimed.json`.
2. `apply_corrections.py` (below) writes `words.out.json`: reel corrections first, then the brand dictionary, then the never-show check.
3. `reel-cut/scripts/build_cues.py` reads `words.out.json` and writes `cues.json`.

```bash
python $SKILLS/reel-captions/scripts/apply_corrections.py --words words.retimed.json --corrections config/corrections.json \
  --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --out words.out.json
```

`config/corrections.json` (reel-specific):

```json
{"corrections": [
  {"match": "analyse", "text": "analyze", "required": true},
  {"match": "example, and", "text": "example and"},
  {"index": 42, "text": "API"},
  {"index": 57, "text": ""},
  {"match": "thank you for watching", "text": ""}
]}
```

- `match` compares lowercase tokens without punctuation and replaces every occurrence (`occurrence: n` for the nth only, `required: true` to stop when it is absent). `index` refers to the input word list (`words.retimed.json` order) and is applied first, highest index first; `count` widens it to several words.
- Empty `text` deletes the words. The leading and trailing punctuation of the replaced span is kept unless the replacement brings its own.
- Equal token counts keep each word's timing; a different count divides the span's time evenly (two words merged into one take the whole span).
- The brand dictionary (`{"phrases": {"spoken form": "Caption Form"}, "neverShow": [...]}`, owned by the brand skill) is applied the same way, longest phrases first. The script exits non-zero if a `neverShow` phrase survives (ASR hallucinations on hum, wrong URLs).

Rules for the text layer:

- Never rewrite the speaker. Fix only spelling, brand names, acronyms, and clear slips where the intended word is unambiguous. Record each edit with its reason in the reel's `project.md`.
- One spelling convention (US by default) and one brand spelling everywhere.
- Acronyms in caps (API, SDK, CRM). No Oxford comma added.
- Strip words with no energy under them (phantoms) and anything inside a non-speech event.
- Sentence case. All caps belongs to title slams and the hook headline only.

## 2. Page rules (implemented in `captionPages.ts`)

1. Tokens come from `createTikTokStyleCaptions` (`@remotion/captions`).
2. Split into phrases at punctuation (`, . ? ! ; :`), at pauses of `mergeAcrossPauseSec` (0.25 s) or more, and at the end of the hook (the first cut).
3. Split each phrase into scored pages: at most `hookMaxWords` (**3**) before the first cut (hook), at most `bodyMaxWords` (**4**) after it; body pages under `bodyMinWords` (**2**) cost extra.
4. Never split an accent phrase across pages.
5. At most **2 lines** of at most **22 characters**; the split that minimises the longest line wins. If a page still measures wider than the safe width (880 px), its font scales down to fit.
6. No page shorter than **0.35 s** (from its first word to the next page): merge with the next page, else the previous one.
7. A page shows from 1 frame before its first word until the next page starts, or 0.6 s after its last word, whichever comes first.
8. A page that would end 1 to 3 frames after a cut (`cues.cuts`) ends on the cut frame instead, so the old page never flashes on the new shot (`timePages()` in `captionPages.ts`; the case is in `captionPages.test.ts`).

### Caption options

Set them per reel in the beat map source (`"captions": {...}`) or in a file passed to `reel-motion/scripts/build_props.py --captions-config captions.json` (the file wins key by key). `build_props.py` and the zod schema validate them; the props carry them as `captionOptions`. The defaults give exactly the pages and look described above.

| Key | Default | Range | Effect |
|---|---|---|---|
| `style` | `standard` | `standard`, `kinetic` | the look and the defaults of the page keys below (see Kinetic captions) |
| `hookMaxWords` | 3 | 1 to 6 | words per page before the first cut |
| `bodyMinWords` | 2 (kinetic 1) | 1 to 6 | body pages shorter than this cost extra (one-word pages are rare) |
| `bodyMaxWords` | 4 (kinetic 3) | 1 to 6 | words per page after the first cut (at least `bodyMinWords`) |
| `maxLines` | 2 (kinetic in framed layout 1) | 1 to 2 | lines per page |
| `maxCharsPerLine` | 22 (kinetic 14) | 8 to 30 | characters per line when choosing breaks (a single longer word still fits by scaling) |
| `mergeAcrossPauseSec` | 0.25 | 0 to 1 | a pause shorter than this stays inside a phrase; raising it also discounts every pause by the same amount when scoring a break, so "First" + 0.3 s pause + "warm every inbox." becomes one page at 0.5 |
| `accentStyle` | `serif` | see below | how the accent word is drawn |
| `localScrim` | 0 | 0 to 0.4 | opacity of a soft dark rounded shape behind the page |
| `centerY` | none | `{talk?, card?}`, y 220 to 1500 | caption centre per mode; overrides the style and layout defaults |
| `kinetic` | see below | object | kinetic look options (ignored by `standard`) |

Punctuation still ends a phrase: "First," with a comma stays its own phrase whatever the pause. Use 3 for `bodyMaxWords` on a fast speaker and 0.4 to 0.5 for `mergeAcrossPauseSec` when list markers ("First", "Second") come out as one-word pages.

Reveal: the page layout is reserved for all its words from the first frame (lines never re-centre). Each word fades in and rises 6 px over 4 frames; its first visible frame is 1 frame (40 ms) before its onset. No grey preview of unspoken words, no active-word colour.

Style: Poppins Bold 700, 68 px, `#F8FCFC`, shadow `0 4px 16px rgba(0,0,0,0.6)`, no box. Position: centre x 510 (middle of the x 70 to 950 safe band), centre y 1180 in Talk and Takeover, y 1060 in Card, suppressed in `hidden`. In the framed layout of `reel-motion` (`layout.mode: "framed"`) captions are centred on the window (x 540, max width 820) at y 1418 and kept inside the band from the window bottom + 14 to y 1500.

Every page, standard or kinetic, is kept inside its band: y 220 (below the top logo zone) to 1500 (above the bottom 420 px) in full frame, window bottom + 14 to 1500 in framed layout. A page taller than the band scales down; a page that would cross an edge moves inside it.

### Kinetic captions

`"captions": {"style": "kinetic"}` draws big centred pages instead of the standard line: Poppins ExtraBold 800 at `kinetic.fontPx` (100), 1 to 3 words per page, at most 2 lines (1 in framed layout), centred on x 540 (max width 820). The page rules above are unchanged (scored breaks, accent phrases never split, cut-edge snap, hold breaks at takeover and hidden windows); only the defaults differ (`bodyMinWords` 1, `bodyMaxWords` 3, `maxCharsPerLine` 14).

```json
"captions": {"style": "kinetic", "kinetic": {"fontPx": 100, "highlight": "pill", "popFrames": 4, "popFromScale": 0.85}, "centerY": {"talk": 1240, "card": 1010}}
```

- Word pop: every word has its place on the page from the first frame (lines never re-centre) and appears on its own onset: opacity 0 to 1 from 2 frames before the onset to the onset, scale `popFromScale` (0.85) to 1 over `popFrames` (4) frames from 2 frames before the onset, ease-out, no overshoot. So it is partly visible 1 frame before its onset and settled 2 frames after.
- Active word: the word being spoken (from 1 frame before its onset until the next word takes over; the last word keeps it until the page ends) is highlighted. `highlight: "pill"` (default) puts an accent-orange rounded pill (radius 0.2 em, 0.16 em side padding) behind it with ink `#141828` text; the pill slides to the next word on the same line over 3 frames and pops with the first word of a line. `highlight: "text"` turns the active word accent orange over 2 frames instead. Compared on reel 24 footage (beige wall, warm skin): the pill reads at a glance on every shot, orange text loses edge on the wall and against the accent serif, so pill is the default; use `text` on dark, busy footage where a solid shape would be heavy.
- Accent words keep a distinct face: Lora Bold Italic at 1.06x in accent orange when not active, ink Lora on the pill when active (in `text` mode they stay orange Lora).
- Legibility: white words carry a 0.075 em dark navy stroke (`paint-order: stroke fill`) and a soft shadow stack; on the pill the stroke and shadow fade out with the ink.
- Position: full frame defaults are centre y 1240 in talk and y 1010 in card (two lines then end above the card zone at 1150 and start below the chin); framed layout uses its `captionY` (1418) and one line. `centerY` overrides both. Check the band rules above with stills over the busiest shots and with `render.sh --caption-boxes`.
- `localScrim` works with kinetic pages too.

## 3. Accent selection

- Exactly one accent word or phrase per page, styled by `accentStyle`. If a page holds two candidates, only the first is styled.
- Pick the word that carries the meaning of the beat: the mistake, the consequence, the fix, the brand. Usually one per sentence, about 15 for a 45 s reel.
- Prefer nouns and strong verbs; never function words; never two accents in a row on consecutive pages unless both are essential.
- Multi-word accents (a two-word consequence, the brand name) are listed as phrases; the page builder keeps them together.
- The accent list lives in the beat map (`accents`), next to the beats it supports.

### Accent styles

| `accentStyle` | Look | Use |
|---|---|---|
| `serif` (default) | Lora Italic 600 at 1.08x, accent orange, 6 px dark stroke | dark or mid walls, the house look |
| `serifHeavy` | Lora Italic 700 at 1.08x, accent orange, 9 px dark stroke | bright or busy walls where the thin serif loses its edge |
| `sansUnderline` | the accent word in the base white Poppins, with a 6 px accent-orange underline (8 px below the baseline, through descenders) | beige or orange-ish walls where orange text itself has no contrast |

`localScrim` (0.25 to 0.4 when used) draws a blurred dark pill behind the whole page, sized to the page box; it combines with any style. Pick the lightest fix that works: `serif`, then `serifHeavy`, then `sansUnderline`, then add `localScrim`. Render one accent page in each candidate over the brightest shot and look at the stills before choosing.

## 4. ASR diff (one script, two modes)

```bash
python $SKILLS/reel-captions/scripts/asr_diff.py --mode cut --media voice_cut.wav --words words.out.json --edl edl.json \
  --corrections config/corrections.json --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --prompt "Brand. Acronyms." \
  --out qa/stage1/asr_diff.json
python $SKILLS/reel-captions/scripts/asr_diff.py --mode final --media out/reel.mp4 --words words.out.json \
  --corrections config/corrections.json --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --out qa/asr_diff_delivered.json
```

- `cut` (Stage 1): transcribes the cut dialogue in chunks of at most 20 s split at the EDL audio splices (whisper invents words at its own 30 s window edges).
- `final` (after the mix or on the delivered file): chunks end in the middle of a gap of 120 ms or more between two words of `words.out.json`, else in the middle of a run of 8 or more quiet 10 ms frames (at or under the 15th energy percentile), else at a word end; a bound never falls inside a word (`cut` mode drops EDL splices that fall inside a word the same way). `--chunks-only` prints the bounds without transcribing. `--heard transcript.json` diffs an existing `[{text, start, end}]` list instead of running a model.
- `--threads N` sets faster-whisper's CPU threads (default 2 for a shared machine; 0 lets it pick).
- `python -I scripts/test_asr_chunks.py` checks the chunker on synthetic reels with soft word interiors: no bound inside a word, chunks at most 20 s, word gaps used first. On the same reels the old quietest-point rule cut 9 words in half.
- faster-whisper large-v3 int8 on CPU, audio decoded by ffmpeg (mono fold with `pan`), aligned to the intended words with `difflib`. Lists `missing` (clipped by a cut), `extra` (ghost words or an uncut retake) and `changed` words with their times. Every correction pair and dictionary phrase is accepted in both directions, as are contraction spellings; `--allow "intended>heard"` adds more. Exit code 1 means a blocking difference.
- The diff is a text check. Onset accuracy is gated by `reel-ingest/scripts/check_onsets.py`.

## 5. QA per page

- Bounding box inside x 70 to 950, y 220 to 1500, clear of the mouth region of the face box (framed layout: below the window bottom, y 1344 to 1500; kinetic pill pages include the pill padding in their box).
- First visible frame 0 to 2 frames before the word onset; page duration at least 0.35 s.
- Contrast: the mean luma behind the text leaves white readable (check bright walls); if an accent fades into the wall, switch `accentStyle` or add `localScrim` (section 3).
- Cuts: no page ends 1 to 3 frames after a cut (the renderer snaps these to the cut frame; `reel-qa` warns if one slips through).
- Spot-check frames at 5 to 6 onsets across the reel and read them against the audio.
