---
name: mailinfra-brand
description: Mail Infra brand kit as code and rules for short-form vertical reels. Use whenever a reel, caption, card, end card, thumbnail or any on-screen text is made for Mail Infra (mailinfra.co), when picking colours, fonts, logos or CTA copy for it, or when checking a render for brand or claims violations.
---

# Mail Infra brand (reel system)

The reels use the **reel system**: Poppins plus Lora Italic accent words, navy cards, orange emphasis, cream end card. The logo is the **website header mark** (mail outline icon plus "Mailinfra" in Inter Bold), the only correct Mail Infra logo. Apart from that mark, the website system (pure blue `#0000FF`, purple `#7C3AED`, Inter) is never used in reels. The only other website element borrowed is the gold `#FFD700` CTA pill on the end card.

Machine-readable source of truth: `brand.json` in this folder. Caption spelling rules (brand name, acronyms, US spelling, phrases never to show) live in `caption-dictionary.json`, used by the `reel-captions` scripts. Code (for example the `reel-motion` Remotion theme) reads tokens from it; do not retype hex values by hand.

## Colour tokens and fixed meanings

| Token | Hex | Meaning (fixed, never reuse for something else) |
|---|---|---|
| navyTop / navyBottom | `#141C38` / `#081024` | card and takeover background gradient |
| navyPanel | `#101C34` | flat panel |
| navyTile | `#18243C` | tiles and inner rows |
| border | `#2C3450` | 1 px card border |
| accent | `#F09C48` | emphasis, active state, the accent word in a caption |
| brandOrange | `#E88838` | accent on cream (end card kicker and accent word) |
| brandBlue | `#2870BC` | Mail Infra itself (brand moments in graphics; the logo keeps its own colours) |
| danger | `#F05468` | mistake, failure, burned, marked |
| success / successFill | `#30C898` / `#143C40` | fixed, safe, done |
| warning | `#F4C424` | not set, risky, pending |
| text / muted | `#F8FCFC` / `#94A0B8` | primary and secondary text on navy |
| cream, glows | `#F4F0E8`, `#C8D4EC`, `#F4D8BC` | end card only |
| ink | `#141828` | headline text on cream |
| ctaGold / ctaInk | `#FFD700` / `#1A1A1A` | the single CTA pill, nothing else |

Red always means a mistake, green always means fixed or safe, orange always means emphasis or the active item, blue always means Mail Infra. A red element that is not a mistake, or a green one that is not a fix, is a bug.

## Typography

- Captions: Poppins Bold 700, 68 px, `#F8FCFC`, shadow `0 4px 16px rgba(0,0,0,0.6)`, sentence case, no box.
- Accent word: Lora Italic 600 at 1.08x the caption size, `#F09C48`. One word or phrase per caption page.
- Title slams: Poppins ExtraBold 800, 76 px, all caps. Hook headline: Poppins ExtraBold 800, 120 px, all caps. Slams and the hook are the only all-caps text.
- Kickers: Poppins Medium 500, 36 px, tracking 0.2em, all caps, accent orange.
- Card text at least 44 px; numerals at least 140 px; a mono DNS line may be 36 px.
- Fonts live in `assets/fonts/` (SIL OFL 1.1, licences `OFL-Poppins.txt` and `OFL-Lora.txt` must ship with them). Load them from local files at render time, never from a font CDN.

## Logo usage

The only correct logo is the mailinfra.co website header mark: the Lucide `mail` outline icon (stroke 2, round caps and joins) followed by the wordmark "Mailinfra" in Inter Bold 700, tracking -0.025em, icon height equal to the line height, 12 px gap at the 24 px source size. The old "envelope as M + ail Infra" lockup is wrong and must never appear.

Files in `assets/logos/` (outlined, no font needed; `brand.json` keys in brackets):

| File | Use |
|---|---|
| `mailinfra-logo-white.svg` (`white`) | footage, navy cards, navy takeovers, the persistent top logo |
| `mailinfra-logo-on-dark.svg` (`onDark`) | same artwork as `white`, kept for parity with the website export |
| `mailinfra-logo-color.svg` (`color`) | light backgrounds: icon `#0000FF`, text `#1A1A1A` (cream end card, cream logo pop card) |
| `mailinfra-icon-white.svg` (`iconWhite`) | icon only, white, for tight spots |

`brand.json` `logoMark.iconSplit` (0.27) is the horizontal fraction between icon and wordmark, used to animate the icon first and the wordmark after it.

- White mark on dark or footage, colour mark on cream or white. Never put the colour mark on footage or navy.
- **Top logo**: every reel shows the white mark persistently at top-center (`TopLogo` in `reel-motion`, about 320 px wide, centred at y 170, zone y 120 to 220) for the whole talking section, including over navy takeovers, with a soft dark drop shadow so it reads on bright walls. It is hidden while the end card shows (the big logo takes over). Nothing else is placed in the top logo zone; hook headline, progress rail and graphics start at y 236 or lower.
- The logo pop on the spoken brand name and the end card use the same mark.
- No logo bug in a corner (the top right collides with platform camera and search icons).
- Never recolour, stretch, outline or add effects to the logo, except the soft drop shadow of the top logo. Minimum width 280 px on a 1080 px canvas.
- The icon is Lucide's `mail` (ISC, `assets/logos/ISC-Lucide.txt`); the wordmark glyphs are outlined from Inter (OFL). To regenerate the files, outline "Mailinfra" from Inter at wght 700 with -0.025em tracking and place it 12 px after a 32 px icon (source units), baseline at half height plus half the cap height.

## 3D (reel-3d)

The `three` block in `brand.json` holds every 3D token; the `reel-3d` compositions read it from input props, so nothing is retyped in code.

| Key | Value | Use |
|---|---|---|
| `backdrop` | `navyTop` to `navyBottom`, spot `#DFE5FF` at 0.18 | the same navy gradient as 2D takeovers and cards, with a soft light spot behind the object |
| `fill` | hemisphere `#DFE5FF` / `#2A3050`, 1.0 | soft sky and ground light |
| `key` | from (-4, 5, 8), 3.0, 2048 PCF shadow, bias -0.0004, normal bias 0.02 | the only shadow caster |
| `rim` | from (4.5, 3.5, -4), 4.0, colour by `meaning` | the single coloured light |
| `rim.meaning` | `danger`, `success`, `accent`, `brand` (= `brandBlueOnDark`), `warning` | the rim, base glow and label plate always carry the meaning of the moment: red mistake, green fixed, orange emphasis, blue Mail Infra, yellow pending |
| `shadow` | `#060B1C` at 0.35 | floor shadow, stays navy |
| `baseGlowOpacity` | 0.35 | additive glow under the object in the meaning colour |
| `materials` | clay roughness 0.55, tile roughness 0.3 | matte objects and glossy plates |
| `envelope` | body `cream`, flap `#E4DDCF`, seal `brandBlueOnDark` | the one envelope model used in every 3D moment |
| `burnt` | `#3A1E24` | a burned domain ends dark red-brown, never black |
| `darkest` | `#1A2038` | emissive floor of every 3D material; nothing on an object renders darker |
| `camera` | fov 32 (vertical), near 0.1, far 200 | all 3D cameras |

Rules:

- The canvas renders without tone mapping, so unlit brand colours are exact (a `brandBlueOnDark` or `navyPanel` patch renders within 1 code of its hex). Lit surfaces shade, so a brand colour is judged on flat plates, not on shaded faces.
- No bloom, no lens effects. Glow only on fire, the shield edge and a glint.
- The 3D logo is the website header mark extruded from `logos.white` (or `logos.color` on cream), never a remodelled mark. `LogoExtrude3D` always ends on the exact flat mark: the same SVG at the same width and centre as the 2D `LogoPop` mark that follows it (same `card`, `widthPx` and `centerY`), so the 2D card takes over without a jump. It marks a brand moment earlier in the reel, never the last 3 s before the end card.
- Labels on 3D objects use Poppins Bold from `fonts.sans`, at least 56 px cap height (44 px card text minimum when three labels share a card row).

## CTA rules

- The URL is always **mailinfra.co**. Never `www.`, never `https://` on screen.
- One CTA per reel, on the end card, in the gold pill (`#FFD700`, radius 28, ink `#1A1A1A`, Poppins ExtraBold 80 px), with "Link in bio" under it in Poppins Medium 36 px `#4C4C54`.

## Claims

`approvedClaims` in `brand.json` is **empty**. Until the owner adds entries there, a reel shows no prices, percentages, client counts, volume limits, ratings or certifications. To add one: get the exact wording and figure approved by the owner in writing, add it verbatim to `approvedClaims` with the approval date and source, and only then use it. Figures seen on the website or in older reels conflict with each other (price, client count, deliverability) and are not approved by being public.

Safe proof lines without numbers are in `endCardCopy.proofLinesWithoutNumbers`.

## End card copy bank

Headlines (accent word in Lora Italic, `*like this*`):

- "Stop burning domains." / "Start scaling *safely.*"
- "Safe domains." / "Scalable *sending.*"
- "Cold email," / "set up *right.*"

Kicker: "SAFE DOMAINS. SCALABLE SENDING." CTA: "mailinfra.co", or "Scale cold email safely at mailinfra.co". Any offer line needs owner approval before use.

End card layout: cream background with a blue glow near the top right and a peach glow near the bottom left; colour logo about 640 px wide above the headline; headline Poppins Bold 64 px ink; gold URL pill; "Link in bio". Content inside x 70 to 950, y 300 to 1450. Music runs to the last frame so the loop is clean.

## Never ship

- `www.mailinfra.co`, or any URL form other than `mailinfra.co`
- any number not in `approvedClaims` (no "USD 2/mo", "250+", "99 %", "40-120/day", website template stats)
- website palette or Inter in a reel outside the logo mark
- the old envelope-as-M lockup; a logo bug in a corner; a watermark
- the Google Workspace logo without the "authorized reseller" wording beside it; any recreated Google UI
- scene counters ("01/11"), timecodes, "n/3" labels
- card text under 44 px
- copy that disparages competitors or vendors by name
