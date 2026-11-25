# Logo rebuild from the site header

The correct Mail Infra logo is the **website header mark**: the Lucide `mail` outline icon followed by the word "Mailinfra" in Inter Bold. The site publishes no logo file, so the mark was rebuilt as outlined SVG from the header markup. The finished files are in [`skills/mailinfra-brand/assets/logos/`](../../skills/mailinfra-brand/assets/logos) and the usage rules in the skill's [Logo usage](../../skills/mailinfra-brand/SKILL.md#logo-usage) section.

## Lesson first: rebuild from the source the owner calls the logo

Before the header mark, a different lockup had been rebuilt by measuring video frames (an envelope standing in for a letter of the name, with the rest of the wordmark in another font). It matched its source within a few pixels and was still wrong: the owner rejected it, because the brand's own logo is the one on the website. Those files were deleted and must never be reused or recreated.

Take from this:

- Ask the owner which mark is the logo before measuring anything. A careful rebuild of the wrong source is still the wrong logo.
- Prefer the most first-party source: official files, then the website's own markup, then anything else.
- When a logo is replaced, delete the old files and list the old mark under "never ship" so it cannot come back through a template or a cached render.

## What the header markup says

From the header component in the site's JS bundle (Tailwind classes resolved to CSS):

| Part | Markup | Value at the desktop breakpoint |
|---|---|---|
| Icon | Lucide `mail`, `strokeWidth 2`, `md:w-8 md:h-8` | 32 x 32 px, stroke 2 on a 24-unit grid, round caps and joins |
| Gap | `md:gap-3` | 12 px |
| Word | "Mailinfra", `md:text-2xl font-bold tracking-tight` | Inter 700, 24 px, line height 32 px, letter-spacing -0.025em (-0.6 px) |
| Colours on blue hero | `text-white` | icon and word `#FFFFFF` |
| Colours on white (scrolled) | `text-[#0000FF]`, `text-[#1A1A1A]` | icon `#0000FF`, word `#1A1A1A` |

The mobile breakpoint (`w-6 h-6`, `gap-2`, `text-xl`) has the same proportions at a smaller size; the desktop values are the reference.

## Construction

- The Lucide `mail` icon is a 20 x 16 rounded rectangle (`rx` 2) at (2, 4) on a 24 x 24 grid, plus the flap path from (22, 7) to (2, 7) through the centre. It is scaled by 32/24 = 1.333 and kept as a **stroke** (not converted to a fill), so it stays crisp at any size.
- The word is outlined from Inter's variable font instanced at **wght 700, opsz 14** (see [`fonts.md`](fonts.md#the-optical-size-axis-why-opsz-14) for why 14, not 24). Each advance gets -0.025 x 24 = -0.6 px of tracking, except after the last letter.
- Vertical placement: the icon fills the 32 px line; the word is centred on the cap height, so the baseline sits at 32/2 + cap/2 = 16 + 17.46/2 = 24.73 px. Inter's cap height is 1490/2048 em, which is 17.46 px at 24 px.
- Width: icon 32 + gap 12 + word ink width + 2 px pad = **143.71 x 32 px** viewBox.
- Icon split: the gap runs from 0.223 to 0.306 of the width; its middle is 0.264. The skill's `logoMark.iconSplit` is 0.27, inside the gap, so an animation can reveal the icon first and the word after it without cutting a shape.

## Files and colours

| File | Icon | Word | Use |
|---|---|---|---|
| `mailinfra-logo-white.svg` | `#FFFFFF` | `#FFFFFF` | footage, navy cards, the persistent top logo |
| `mailinfra-logo-color.svg` | `#0000FF` | `#1A1A1A` | cream or white backgrounds only |
| `mailinfra-logo-on-dark.svg` | `#FFFFFF` | `#FFFFFF` | same artwork as white, kept for parity with the site's two states |
| `mailinfra-icon-white.svg` | `#FFFFFF` | | icon alone, 24 x 24, for tight spots |

The colour mark never goes on footage or navy. The white mark over footage gets a soft dark drop shadow so it reads on bright backgrounds. Minimum width on a 1080 x 1920 canvas: 280 px (`logoMark.minWidthPx`).

## Rebuilding it

[`tools/build_site_logo.py`](tools/build_site_logo.py) takes the variable font and any SVG with the icon geometry, and writes `<prefix>-logo-white.svg`, `<prefix>-logo-color.svg` and `<prefix>-icon-white.svg`. With its defaults and the skill's own icon file as input, it reproduces the three skill files byte for byte.

```bash
pip install fonttools
python tools/build_site_logo.py \
  --font "Inter[opsz,wght].ttf" \
  --icon ../../skills/mailinfra-brand/assets/logos/mailinfra-icon-white.svg \
  --out out/
```

It prints `width 143.71 height 32.00 cap 17.46 icon_split 0.264`. Any icon SVG works for `--icon`, for example `icons/mail.svg` from the `lucide-static` npm package; the script copies only the geometry elements and sets the stroke itself. For another brand, change `--word`, `--prefix`, `--wght`, `--opsz`, `--font-px`, `--icon-px`, `--gap-px`, `--tracking-em` and the `--light-icon`, `--light-text`, `--dark` colours to what that site's header uses. If the font is static, the axis options are ignored.

## Verifying against the live site

A rebuild is done only when it matches the live render:

1. Screenshot the header in a headless browser at device scale factor 1 and at 2, once in each colour state (hero and scrolled).
2. Render the SVG at the same pixel size on the same background.
3. Overlay or difference the two crops. Accept when the difference shows only antialiasing noise along edges. A consistent offset or width drift means a wrong axis value, wrong tracking or a missed gap. The opsz 14 outline matched the site render pixel for pixel; an opsz 24 outline is 3.4 px narrower and shows up immediately.

## Licences and trademark

- The icon is Lucide `mail` (lucide.dev, ISC licence). The ISC text ships next to the logos as `ISC-Lucide.txt`.
- The wordmark is outlined from Inter (SIL Open Font License 1.1). Outlined glyphs in a logo are artwork, not a font, so the OFL does not travel with them, but the font source is credited.
- The logo itself is a trademark of Mail Infra and is excluded from the repo's MIT licence: see [`NOTICE.md`](../../skills/mailinfra-brand/assets/logos/NOTICE.md). For another brand, rebuild that brand's own mark; do not reuse these files.
