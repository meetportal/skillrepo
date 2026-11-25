# Claims policy

A reel shows **no prices, percentages, client counts, volume limits, ratings or certifications** until the owner has approved the exact wording and figure in writing. In the skill this is enforced by data: [`brand.json`](../../skills/mailinfra-brand/brand.json) `approvedClaims` starts as an empty list, and anything not in it does not ship.

## Why

- **Public is not approved.** A brand's own pages and older videos can carry different figures for the same claim (a price, a customer count, a rate). A number on screen is a promise in an ad; picking one of two conflicting public figures is guessing.
- **Templates leak.** Site themes ship with placeholder stats, review ratings, compliance badges and testimonials. Repeating one in a reel would turn a placeholder into a claim made on camera.
- **Numbers age.** Prices and counts change; a reel stays online. The approval date in `approvedClaims` tells a later editor whether to ask again.
- **Reels without numbers lose little.** The proof that carries a short reel is concrete and checkable (authorized reseller, records configured, warmed inboxes), not a percentage the viewer cannot verify.

## What counts as a claim

Anything a viewer could hold the brand to:

- any figure about the business: price, discount, trial length, client or customer count, volume, rate, percentage, rating, time to set up;
- a certification or compliance badge (SOC 2, GDPR and the like);
- a named customer, testimonial or logo of a customer;
- a superlative ("lowest", "best", "fastest", "#1");
- a partner status beyond what the partner's own rules allow (the Google Workspace logo only with "authorized reseller" wording beside it).

Teaching numbers that are not about the brand (for example "three mistakes", a generic DNS record name) are content, not claims, and do not need approval. When in doubt, treat it as a claim.

## Approval steps

1. Collect every figure you want to use into a private list for the owner, with where each one was seen. Keep this list out of the repo.
2. Get the exact wording and figure confirmed in writing.
3. Add it verbatim to `approvedClaims` with the approval date and the source of the approval.
4. Only then use it, word for word. A rounded or rephrased figure needs a new approval.

## What to say instead

Proof lines without numbers, already in `brand.json` `endCardCopy.proofLinesWithoutNumbers`:

- "Authorized Google Workspace reseller"
- "Warmed inboxes and domains, set up for you"
- "SPF, DKIM and DMARC configured"
- "Safe sending limits per inbox"

Note the last line: the concept of a per-inbox limit is a proof point, the number range is a claim. Say the first, hold the second until it is approved.

## Related rules in the skill

- The CTA URL is always the bare domain (`mailinfra.co`), one CTA per reel, in the gold pill on the end card.
- No copy that disparages competitors or vendors by name.
- Any offer line (free accounts, trial terms) needs owner approval like any other figure.

Full list: the skill's [Claims](../../skills/mailinfra-brand/SKILL.md#claims) and [Never ship](../../skills/mailinfra-brand/SKILL.md#never-ship) sections.
