# Script brief for the speaker (before a shoot)

**Source level 4** (a written formula distilled from 20 measured animated shorts in a public MIT repo, not yet tested on our talking-head reels). Use it as a checklist for hook variants and for shoot feedback. Before any part becomes a rule: A/B two cuts of the same reel (one following the brief, one not), measure both with `beat_sheet.py` and `craft-research/scripts/measure_reference.py`, run the critic on both, and record the result in the style bible.

Hand the speaker this page with the topic, the one claim the reel makes, and the approved claims list. Never script numbers that are not in that list.

## Shape (45 to 60 s of talk)

| Part | Length | What it does | Example (mock topic) |
|---|---|---|---|
| Cold open (optional) | 1 to 2 s | Flash-forward: the strongest line of the reel, cut from later in the take, then a hard cut into the hook. A/B it; skip it when the hook is already the strongest line. | "...and that is why it lands in spam." |
| Hook | sentence 1, 10 to 16 words | A paradox stated as a fact. No setup, no greeting, no "in this video". | "Your domain can be perfect and still send every email straight to spam." |
| Setting | 1 to 2 lines | Concrete details and a named everyday person or business the viewer recognises. | "Say you run yourbrand.com: a small team, one inbox, a newsletter every Tuesday." |
| Escalation | 3 to 6 short beats, each a little bigger | What goes wrong, step by step. One idea per line, so each line can carry one graphic. | "Open rates drop. Then replies stop. Then a customer says she never got the invoice." |
| Mystery | one line | The question the viewer is now asking, said out loud. | "Wait, nothing changed, so why?" |
| Pivot | "Here is why" (or "You see,") plus one everyday analogy | The mechanism, explained through something the viewer already knows. Jargon is explained in the next clause. | "Here is why: SPF, DKIM and DMARC are your domain's ID card. Without them, the inbox is a bouncer who has never seen your face." |
| Payoff | 1 to 2 short sentences, before the CTA | A short, slightly ironic line that resolves the paradox. | "So the perfect domain was never the problem. Nobody had introduced it." |
| CTA | the last 3 s | One action, the bare domain. No 3D and no new graphic over it. | "Fix it at yourbrand.com." |

## Delivery numbers (checked after the cut)

- About **3.7 words/s** on the output timeline (`beat_sheet.py` header). Under 3.2 reads slow on a phone; over 4.2 loses the captions.
- Pauses of 0.25 s or more sum to **under 1 s per 15 s** after the cut (`beat_sheet.py` header). The cut removes most of them; a speaker who pauses mid-sentence makes the cut choppy, so ask for whole sentences per breath.
- Sentences of about 10 to 15 words, contractions, one claim per sentence.
- Say each list marker ("First,", "Second,") as its own short phrase with a small breath after it: the title slam needs about 0.28 s.
- Record two takes of the hook and of the CTA. Record the cold-open line once more on its own if you plan to use it.

## Never

- A setup before the hook ("Hey guys", "Today I want to talk about").
- Describing what the viewer already sees on screen.
- Numbers, prices or percentages outside the approved claims list.
- A second CTA, or a CTA before the payoff.

## Using it in the edit

- Write the three hook variants of stage 2 against the hook row above (paradox as fact, 10 to 16 words, from the truthful speech that was recorded).
- Map the escalation beats and the pivot to beat rows; the analogy is the usual home of a 3D moment (a physical metaphor), the escalation beats of 2D cards.
- After the cut, paste the `beat_sheet.py` header into `project.md` and compare words/s and pause totals with the numbers above. Feed the difference back to the speaker for the next shoot.
