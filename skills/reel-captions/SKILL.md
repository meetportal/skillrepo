---
name: reel-captions
description: Burned-in caption text and rendering for vertical talking-head reels. Use when turning ASR word timings into on-screen captions, correcting caption text (brand names, acronyms, spelling) without touching timings, choosing accent words, tuning caption pages (words per page, line limits, timing), or checking a delivered reel for missing or ghost words with an ASR diff.
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
2. Split into phrases at punctuation (`, . ? ! ; :`), at pauses of 0.25 s or more, and at the end of the hook (the first cut).
3. Split each phrase into near-equal pages: at most **3 words** before the first cut (hook), at most **4 words** after it.
4. Never split an accent phrase across pages.
5. At most **2 lines** of at most **22 characters**; the split that minimises the longest line wins. If a page still measures wider than the safe width (880 px), its font scales down to fit.
6. No page shorter than **0.35 s** (from its first word to the next page): merge with the next page, else the previous one.
7. A page shows from 1 frame before its first word until the next page starts, or 0.6 s after its last word, whichever comes first.

Reveal: the page layout is reserved for all its words from the first frame (lines never re-centre). Each word fades in and rises 6 px over 4 frames; its first visible frame is 1 frame (40 ms) before its onset. No grey preview of unspoken words, no active-word colour.

Style: Poppins Bold 700, 68 px, `#F8FCFC`, shadow `0 4px 16px rgba(0,0,0,0.6)`, no box. Position: centre x 510 (middle of the x 70 to 950 safe band), centre y 1180 in Talk and Takeover, y 1060 in Card, suppressed in `hidden`.

## 3. Accent selection

- Exactly one accent word or phrase per page, in Lora Italic 600 at 1.08x, accent orange. If a page holds two candidates, only the first is styled.
- Pick the word that carries the meaning of the beat: the mistake, the consequence, the fix, the brand. Usually one per sentence, about 15 for a 45 s reel.
- Prefer nouns and strong verbs; never function words; never two accents in a row on consecutive pages unless both are essential.
- Multi-word accents (a two-word consequence, the brand name) are listed as phrases; the page builder keeps them together.
- The accent list lives in the beat map (`accents`), next to the beats it supports.

## 4. ASR diff (one script, two modes)

```bash
python $SKILLS/reel-captions/scripts/asr_diff.py --mode cut --media voice_cut.wav --words words.out.json --edl edl.json \
  --corrections config/corrections.json --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --prompt "Brand. Acronyms." \
  --out qa/stage1/asr_diff.json
python $SKILLS/reel-captions/scripts/asr_diff.py --mode final --media out/reel.mp4 --words words.out.json \
  --corrections config/corrections.json --dictionary $SKILLS/<brand-skill>/caption-dictionary.json --out qa/asr_diff_delivered.json
```

- `cut` (Stage 1): transcribes the cut dialogue in chunks of at most 20 s split at the EDL audio splices (whisper invents words at its own 30 s window edges).
- `final` (after the mix or on the delivered file): chunks split at the quietest points. `--heard transcript.json` diffs an existing `[{text, start, end}]` list instead of running a model.
- faster-whisper large-v3 int8 on CPU, audio decoded by ffmpeg (mono fold with `pan`), aligned to the intended words with `difflib`. Lists `missing` (clipped by a cut), `extra` (ghost words or an uncut retake) and `changed` words with their times. Every correction pair and dictionary phrase is accepted in both directions, as are contraction spellings; `--allow "intended>heard"` adds more. Exit code 1 means a blocking difference.
- The diff is a text check. Onset accuracy is gated by `reel-ingest/scripts/check_onsets.py`.

## 5. QA per page

- Bounding box inside x 70 to 950, y 220 to 1500, clear of the mouth region of the face box.
- First visible frame 0 to 2 frames before the word onset; page duration at least 0.35 s.
- Contrast: the mean luma behind the text leaves white readable (check bright walls).
- Spot-check frames at 5 to 6 onsets across the reel and read them against the audio.
