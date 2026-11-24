---
name: mailinfra-brand
description: Mail Infra brand kit as code and rules for short-form vertical reels. Use whenever a reel, caption, card, end card, thumbnail or any on-screen text is made for Mail Infra (mailinfra.co), when picking colours, fonts, logos or CTA copy for it, or when checking a render for brand or claims violations.
---

# Mail Infra brand (reel system)

The reels use the **reel system**: Poppins plus Lora Italic accent words, navy cards, orange emphasis, cream end card, the two-tone envelope logo. The website system (pure blue `#0000FF`, purple `#7C3AED`, Inter) is never used in reels. The only website element borrowed is the gold `#FFD700` CTA pill on the end card.

Machine-readable source of truth: `brand.json` in this folder. Caption spelling rules (brand name, acronyms, US spelling, phrases never to show) live in `caption-dictionary.json`, used by the `reel-captions` scripts. Code (for example the `reel-motion` Remotion theme) reads tokens from it; do not retype hex values by hand.

## Colour tokens and fixed meanings

| Token | Hex | Meaning (fixed, never reuse for something else) |
|---|---|---|
| navyTop / navyBottom | `#141C38` / `#081024` | card and takeover background gradient |
| navyPanel | `#101C34` | flat panel |
| navyTile | `#18243C` | tiles and inner rows |
| border | `#2C3450` | 1 px card border |
| accent | `#F09C48` | emphasis, active state, the accent word in a caption |
| brandOrange | `#E88838` | logo orange, accent on cream |
| brandBlue | `#2870BC` | Mail Infra itself (logo, brand moments) |
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

- Files in `assets/logos/` are outlined recreations (no font needed): `logo.svg` (lockup with descriptor), `logo-horizontal.svg`, `logo-horizontal-on-dark.svg` (navy backgrounds), `logo-icon.svg` (envelope only). `logo-live-text.svg` needs Poppins installed; prefer the outlined files.
- On footage, place the logo on a cream `#F4F0E8` rounded card; on navy use the on-dark variant; on cream use `logo.svg`.
- No persistent logo bug in any corner (the top right collides with platform camera and search icons). The brand appears in slam styling, the logo pop on the spoken brand name, and the end card.
- Never recolour, stretch, outline or add effects to the logo. Minimum width 280 px on a 1080 px canvas.

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

End card layout: cream background with a blue glow near the top right and a peach glow near the bottom left; logo about 760 px wide near y 420; headline Poppins Bold 64 px ink; gold URL pill; "Link in bio". Content inside x 70 to 950, y 300 to 1450. Music runs to the last frame so the loop is clean.

## Never ship

- `www.mailinfra.co`, or any URL form other than `mailinfra.co`
- any number not in `approvedClaims` (no "USD 2/mo", "250+", "99 %", "40-120/day", website template stats)
- website palette or Inter in a reel
- a persistent logo bug or a watermark
- the Google Workspace logo without the "authorized reseller" wording beside it; any recreated Google UI
- scene counters ("01/11"), timecodes, "n/3" labels
- card text under 44 px
- copy that disparages competitors or vendors by name
