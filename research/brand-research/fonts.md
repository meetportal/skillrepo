# Fonts

## Identify: declared first, then verified

1. **Declared fonts.** The site's font `<link>` and CSS `font-family` give the web font for certain. mailinfra.co loads one family from Google Fonts:
   `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap`
2. **Fonts that only exist in video or print** have to be identified by eye and then proven by measurement:
   - Shortlist by tell-tale glyphs: single-story or double-story `a` and `g`, the shape of `G`, `R`, `k`, `y`, the terminals, geometric or humanist `o`.
   - **Size fit**: measure the cap height and the width of a known word in pixels, solve for the font size from each (`size = cap_px / (sCapHeight / unitsPerEm)`, and the width from the advance widths), and accept the font only when both give the same size within about 1%. A wrong family fits one measurement and misses the other.
   - **Side-by-side render**: render the candidate at the solved size next to a crop of the original and compare stroke contrast, joins and spacing. For an italic, compare the `g`, `b`, `d`, `k` and the contrast.
3. Write down close alternatives in case a font cannot be licensed, but use the exact match when it exists.

Results for the example brand:

| Role | Font | How it was confirmed |
|---|---|---|
| Logo wordmark | **Inter Bold 700**, opsz 14 | declared on the site; outline at opsz 14 matched the live header render (see below and [`logo-rebuild.md`](logo-rebuild.md)) |
| Captions, headlines, labels, kickers | **Poppins** 400 to 900 | geometric `o`, single-story `a`; cap height and word width gave the same size |
| Accent words (1 to 3 per caption) | **Lora Italic** 600 (500 to 700 acceptable) | side-by-side render: single-story `g`, `b/d/k` shapes and contrast matched |
| Website UI | Inter 400 to 800 | declared; reference only, never used in reels outside the logo |

Alternatives if needed: Montserrat or Outfit for Poppins, Source Serif 4 Italic or Literata Italic for Lora Italic. The skill pins the exact sizes and weights per role in [`brand.json`](../../skills/mailinfra-brand/brand.json) `type`.

## The optical size axis (why opsz 14)

Inter 4 is a variable font with two axes: `opsz` 14 to 32 (default 14) and `wght` 100 to 900. At larger optical sizes the letters get tighter and the details finer. Outlining "Mailinfra" at 24 px gives:

| opsz | Word lockup width (icon + gap + word) |
|---|---|
| 14 | 143.71 px |
| 24 | 140.28 px (2.4% narrower) |

The site's Google Fonts request names only the `wght` axis, so the served font most likely carries only the default `opsz` 14 even though the text is 24 px. Either way, the opsz 14 outline is the one that matched the live render. General rule: when rebuilding text from a web page, instance the variable font at the axis values the page actually receives, not at the values that "should" apply to the size. Check by overlaying, not by reasoning.

## Get the files

- Download TTFs, not WOFF2, so the same file works in Remotion, libass and ffmpeg `drawtext`. Two ways:
  - the font's official repository or the `google/fonts` GitHub repository (variable TTFs with the licence next to them);
  - the Google Fonts CSS2 API: a request with a non-browser User-Agent returns `src: url(...ttf)` instead of WOFF2.
- Static instances (for example `Poppins-Bold.ttf`, `Lora-SemiBoldItalic.ttf`) are easier for libass and `drawtext`, which do not select variable axes. Keep the variable file as well when you need an in-between weight in Remotion.
- Ship each family's licence next to the files. Poppins, Lora and Inter are all SIL Open Font License 1.1; the skill ships `OFL-Poppins.txt` and `OFL-Lora.txt` in [`assets/fonts/`](../../skills/mailinfra-brand/assets/fonts). Inter is not shipped as a font because the logo is outlined.

## Load locally, never from a CDN

- Render from local files (`@remotion/fonts` `loadFont({ family, url: staticFile(...), weight })`). A CDN font fetch at render time makes renders depend on the network and can silently fall back to a system font.
- Machines often have only DejaVu or Liberation installed. A missing font does not error; it substitutes. Check a still after any font change.
- libass `fontsdir` tries to load every file in the folder. Keep font folders to font files and licence texts only; a stray `.css` there causes load errors.
- Outline logo text to paths (see [`logo-rebuild.md`](logo-rebuild.md)) so the logo never depends on a font being installed.
