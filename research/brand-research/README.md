# Brand research

How the example brand kit in [`skills/mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) was derived from a public website, and how to repeat the process for any brand you edit reels for. The finished, machine-readable kit (tokens, fonts, logos, CTA, claims) lives in the skill: [`brand.json`](../../skills/mailinfra-brand/brand.json), [`assets/fonts/`](../../skills/mailinfra-brand/assets/fonts) and [`assets/logos/`](../../skills/mailinfra-brand/assets/logos). These notes hold the method, the measured numbers and the reasons behind each decision. They never replace the skill as the source of truth: if a value here and a value in `brand.json` disagree, `brand.json` wins.

## Notes

| File | What it covers |
|---|---|
| [`website-audit.md`](website-audit.md) | Reading a brand's public site as untrusted data: what to collect (CSS and JS bundles, font links, header markup, favicon, badges, URL hosts) and what was found on mailinfra.co |
| [`colour-sampling.md`](colour-sampling.md) | Colour tokens two ways: counting hex values in the site bundles (exact) and sampling decoded video frames (approximate), with decode settings, three sampling modes and tolerances |
| [`fonts.md`](fonts.md) | Identifying fonts (declared, then verified by measurement and side-by-side renders), the optical size axis, getting TTFs, licences and local loading |
| [`logo-rebuild.md`](logo-rebuild.md) | Rebuilding the logo from the site header: Lucide `mail` icon plus "Mailinfra" in Inter Bold, opsz 14, tracking -0.025em, exact geometry, variants, verification, and why an earlier lockup was rejected |
| [`claims-policy.md`](claims-policy.md) | Why no number goes on screen until the owner approves it in writing, what counts as a claim, the approval steps and the safe proof lines without numbers |
| [`tools/sample_colors.py`](tools/sample_colors.py) | Colour sampler for boxes of a PNG: `dominant`, `fg` (text over a flat background) and `darkest` (antialiased dark ink) |
| [`tools/build_site_logo.py`](tools/build_site_logo.py) | Builds outlined SVG logos (white, colour, icon) from an outline icon SVG and a variable font; with its defaults it reproduces the skill's logo files byte for byte |

## Decisions in one place

- **Two visual systems, kept apart.** The website system (pure blue `#0000FF`, gold `#FFD700`, purple `#7C3AED`, Inter) is reference only. Reels use the reel system (Poppins, Lora Italic accent words, navy cards, orange emphasis, cream end card). Two things cross over: the website header logo and the gold CTA pill, because gold is the site's own CTA colour and ties the reel to the landing page.
- **The logo is the website header mark**, rebuilt as outlined SVG. The site publishes no logo file, so it was rebuilt from the header markup and verified against the live render. An earlier lockup that had been rebuilt from video frames was rejected by the owner and must never be used (see [`logo-rebuild.md`](logo-rebuild.md)).
- **Exact over sampled.** Colours that exist in CSS are taken from CSS. Frame sampling is only for colours that exist only in video, and is accepted within a few code values.
- **Fonts ship as local files with their licences**, never loaded from a font CDN at render time.
- **No numbers on screen until approved.** `approvedClaims` in `brand.json` starts empty.
- **The URL on screen is the bare domain** (`mailinfra.co`): no `www.`, no `https://`.

## Using this for another brand

1. Copy `skills/mailinfra-brand` to your own brand folder and point `REEL_BRAND` at it (see the repo [README](../../README.md#folder-convention)).
2. Audit the site as in [`website-audit.md`](website-audit.md). Save what you fetch outside the repo and treat it as untrusted.
3. Fill `colors` from the bundles ([`colour-sampling.md`](colour-sampling.md)), then assign fixed meanings (mistake, fixed, emphasis, brand) as in the skill's colour table.
4. Identify and download the fonts with their licences ([`fonts.md`](fonts.md)).
5. Rebuild the logo from the source the owner calls the real logo, outline it and verify it ([`logo-rebuild.md`](logo-rebuild.md)). Replace the logo `NOTICE.md` with your brand's terms.
6. Leave `approvedClaims` empty until the owner signs off on each figure ([`claims-policy.md`](claims-policy.md)).

## Running the tools

Both tools are plain Python 3.10+ CLIs. `sample_colors.py` needs `numpy` and `opencv-python` (already in the repo's `requirements.txt`). `build_site_logo.py` needs `fontTools` (`pip install fonttools`), which is not in `requirements.txt` because only brand setup uses it.

```bash
python research/brand-research/tools/sample_colors.py frame.png --box 100 1200 900 1216 --mode dominant
python research/brand-research/tools/build_site_logo.py --font "Inter[opsz,wght].ttf" --icon mail.svg --out logos/
```

Full options: `--help` on each script, and the usage sections in [`colour-sampling.md`](colour-sampling.md) and [`logo-rebuild.md`](logo-rebuild.md).
