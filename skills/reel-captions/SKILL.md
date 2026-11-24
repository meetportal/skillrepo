---
name: reel-captions
description: Burned-in caption text and rendering for vertical talking-head reels. Use when turning ASR word timings into on-screen captions, correcting caption text (brand names, acronyms, spelling) without touching timings, choosing accent words, tuning caption pages (words per page, line limits, timing), or checking a delivered reel for missing or ghost words with an ASR diff.
---

# Reel captions

Captions are rendered by the `reel-motion` Remotion project (`src/components/Captions.tsx`, page rules in `src/lib/captionPages.ts`), always as the last layer. This skill owns the text that goes in, the page rules, and the checks that come out.

## 1. Correction layer (text only, timings never change)

Input: Remotion `Caption[]` on the output timeline (`[{"text": " word", "startMs", "endMs", "timestampMs", "confidence"}]`, leading space kept).

Two kinds of corrections, applied in this order by `scripts/apply_corrections.py`:

1. **Index edits** (`edits.json`): `[{"i": 41, "text": "deliverability"}, {"i": 57, "drop": true}]`, keyed by word index in the input file. Use for spoken slips the caption tidies, merged consonants ("a damage sender" to "damaged"), contractions, and dropping phantom words.
2. **Brand dictionary** (`caption-dictionary.json`, owned by the brand skill): `{"phrases": {"mail infra": "Mail Infra", "gtm": "GTM"}, "neverShow": ["thank you for watching"]}`. Matching ignores case and punctuation; punctuation and the leading space of the original are kept. A multi-word source mapping to a different word count merges the words into one token spanning their times.

```bash
python scripts/apply_corrections.py --words words.json --edits edits.json \
  --dictionary ../mailinfra-brand/caption-dictionary.json --out words.out.json
```

It exits non-zero if a `neverShow` phrase survives (ASR hallucinations on music or hum, wrong URLs).

Rules for the text layer:

- Never rewrite the speaker. Fix only spelling, brand names, acronyms, and clear slips where the intended word is unambiguous. Record each edit with its reason in the reel's `project.md`.
- One spelling convention (US by default) and one brand spelling everywhere.
- Acronyms in caps (SPF, DKIM, DMARC, GTM). No Oxford comma added.
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
- Multi-word accents ("too soon", "lose trust", the brand name) are listed as phrases; the page builder keeps them together.
- The accent list lives in the beat map (`accents`), next to the beats it supports.

## 4. ASR diff check (after the final mix)

```bash
python scripts/asr_diff.py --intended words.out.json --media final.mp4 \
  --prompt "Brand. Acronym list." --dictionary ../mailinfra-brand/caption-dictionary.json \
  --allow "deliverability>deliverable" --out qa/asr_diff.json
```

It transcribes the delivered audio with faster-whisper (large-v3, int8, CPU; audio decoded by ffmpeg into numpy), aligns it to the intended words with `difflib`, and lists `missing` (clipped by a cut), `extra` (ghost words or an uncut retake) and `changed` words with their times. Pairs in `--allow` are intentional text edits. Exit code 1 means a blocking difference: fix the cut or the text, then re-run. Use `--heard transcript.json` to diff against an existing transcript without running a model.

## 5. QA per page

- Bounding box inside x 70 to 950, y 220 to 1500, clear of the mouth region of the face box.
- First visible frame 0 to 2 frames before the word onset; page duration at least 0.35 s.
- Contrast: the mean luma behind the text leaves white readable (check bright walls).
- Spot-check frames at 5 to 6 onsets across the reel and read them against the audio.
