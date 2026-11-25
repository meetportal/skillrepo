# Colour sampling

Brand colours come from two kinds of source, and they are not equally good:

1. **Site bundles (exact).** A hex value written in CSS or JS is the designer's value. Count it, do not sample it.
2. **Decoded video frames (approximate).** Colours that exist only in video (a card navy, an accent orange used on captions) have to be measured from frames. Chroma subsampling, the YUV to RGB matrix and compression move them by a few code values.

Use 1 wherever it exists. Use 2 only for what 1 cannot give, and record the result rounded, not to the last bit.

## 1. Counting hex values in the bundles

```bash
cat site/*.css site/*.js | grep -oiE '#[0-9a-f]{6}\b' | tr a-f A-F | sort | uniq -c | sort -rn | head -40
```

Then read each frequent value in context (`grep -o '.\{80\}#0000FF.\{80\}' site/*.js`) to give it a role: hero background, button, hover, link, body text, border, surface, footer. Frequency says what matters; context says what it means. Hover shades (`#0000CC` next to `#0000FF`) and gradient ends (`#4040FF`) are not separate brand colours.

Website system found on mailinfra.co (reference only, not used in reels except as noted):

| Role | Hex | Count |
|---|---|---|
| Primary blue: hero, default button, links | `#0000FF` | 13 in JS, 9 in CSS |
| Primary hover | `#0000CC` | |
| Blue light, gradient end | `#4040FF` | |
| CTA gold, main button | `#FFD700` (hover `#FFC700`) | 14 |
| Purple accent | `#7C3AED`, dark `#5B21B6`, tint `#F5F3FF` | 14 |
| Ink text | `#1A1A1A` | 25 |
| Gray text | `#6B7280` | 23 |
| Border | `#E5E7EB` | |
| Surface | `#F8F9FA` | |
| Footer navy | `#0F172A` | |

Two of these cross into reels: the header logo keeps its own colours (`#0000FF` icon, `#1A1A1A` text on light), and `#FFD700` with `#1A1A1A` ink is the single CTA pill on the end card. Both sit in [`brand.json`](../../skills/mailinfra-brand/brand.json) as `ctaGold` / `ctaInk` and in `logoMark`.

## 2. Sampling decoded frames

### Decode a frame correctly

Check the stream first, then convert with the matrix and range it declares. Most phone and editor exports are BT.709, limited (tv) range. ffmpeg's default RGB conversion can assume BT.601, which shifts saturated blues and oranges visibly.

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=color_space,color_range,color_primaries -of default=nw=1 input.mp4
ffmpeg -ss 3 -i input.mp4 -frames:v 1 -vf "scale=in_color_matrix=bt709:in_range=tv,format=rgb24" frame.png
```

Pick frames where the element is fully on screen and still (not mid-fade, not motion-blurred). Sample a flat interior at least 4 px from any edge: 4:2:0 chroma is stored at half resolution, so colour bleeds across edges.

### Three modes

[`tools/sample_colors.py`](tools/sample_colors.py) takes a PNG and one or more boxes (`--box X0 Y0 X1 Y1`, pixel coordinates, end exclusive) and prints the top colours per box.

| Mode | What it does | Use for |
|---|---|---|
| `dominant` (default) | quantises every pixel to steps of `--quant` (4) and ranks them | flat fills: card backgrounds, tiles, pills, glows |
| `fg` | finds the background as the most common colour at a coarse step of 8, keeps only pixels farther than `--thresh` (110, Euclidean RGB) from it, then ranks those | text or thin strokes on a flat background: caption accent words, kickers, ticks. Lower `--thresh` (40 to 60) for low-contrast gray text |
| `darkest` | takes the `--darkest` (200) darkest pixels of the box and ranks them | dark antialiased ink on a light background, where most text pixels are blended edges |

```bash
python tools/sample_colors.py frame.png --box 100 1200 900 1216 --box 100 1400 900 1416
python tools/sample_colors.py frame.png --box 120 1240 600 1300 --mode fg --thresh 110
python tools/sample_colors.py frame.png --box 120 400 960 470 --mode darkest --json
```

### Tolerances and rounding

- Quantising to 4 means each channel is within 2 of the bin, before decode error. Expect values a few units from the original design value. Rounding to a nearby clean value, or to a near Tailwind value (a sampled navy panel `#101C34` sits next to slate-900 `#0F172A`), is fine.
- A gradient needs two samples (top and bottom strips), not one average.
- Translucent borders: a 1 px border that samples as `#2C3450` on navy is most likely white at about 12% opacity. Either value works; pick one and use it everywhere.
- Never sample over a moving face, a watermark or an overlay you do not own. Sample the brand element only.

### From samples to tokens

Sampled values become named tokens in `brand.json` with one fixed meaning each. The meaning matters more than the third hex digit: in the skill, red (`danger`) always means a mistake, green (`success`) always means fixed or safe, orange (`accent`) always means emphasis, blue (`brandBlue`) always means the brand. A colour without a meaning does not get a token.

When an accent colour has to work on two backgrounds, keep two tokens. On navy the accent is the lighter `#F09C48`; on cream the slightly deeper `#E88838` holds contrast better. Similarly a brand blue lifted for dark backgrounds (`brandBlueOnDark` `#4A8EDB`) is a separate token, not an opacity trick.

## Swatch check

Before locking the palette, render every token as a labelled swatch on both the navy and the cream backgrounds and look at it on a phone screen. Any pair that reads as the same colour at phone size (two oranges, two grays) should collapse into one token.
