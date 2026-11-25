# Open gaps

When the plan was written, these items were missing, unverified or needed a decision only the owner could make. They are generalised here as a checklist for any new reel or series, with a note on where each one stands in the skills.

## Owner decisions

Ask these in one message at the start and keep working with the safe default. The current table of questions and defaults is in [`reel-director`](../../skills/reel-director/SKILL.md#when-to-ask-the-owner-and-keep-working-meanwhile).

| Gap | Why it blocks | Safe default |
|---|---|---|
| Rendering licence | Remotion is free for individuals and companies of up to 3 people; larger for-profit companies need a company licence. Headcount is often unknown to the editor | Do not render client work with Remotion until confirmed; the fallback is ffmpeg with ASS subtitles and PNG overlays (other frameworks were not tested) |
| Claims | On the first reel the brand's own sources gave conflicting prices, client counts, deliverability rates and offers | Ship with no numbers until the owner approves a claims list; any graphic label with a figure (for example a daily sending limit) needs the same approval |
| Brand system | The website and the existing reels used different colours and fonts | The system the existing reels use |
| Music | No licensed track existed; free-licence libraries need a check for commercial social use | Now covered: `reel-sound` has a licence check procedure and a generated SFX kit; without a track, SFX plus room tone is weaker but shippable |
| CTA destination | "Link in bio" assumes a profile link exists and someone knows where it points | The bare domain, no `www.` |
| Series scope | Whether the new template applies only to new reels or the back catalogue is re-edited | None: the owner decides; the style bible makes the template reusable either way |
| Shoot feedback | Recurring capture problems (handheld mic instead of a lav, a hand over the lens at the start, swaying on list items) had no owner | Partly covered: [`reel-director/references/script-brief.md`](../../skills/reel-director/references/script-brief.md) is a script and hook brief for the speaker; capture notes (a lav on the collar, no hand over the lens at the start, holding still on list items) still have no home |

## Unverified when planned (check on the first render of any new setup)

| Gap | What to check | Status in the skills |
|---|---|---|
| Nobody had listened | Every denoise, de-ess, gate and bed choice was numeric. A gate can pump against the bed; bed-level advice spans 10 to 28 dB across sources | Still a human job: the five-timestamp listen in [gates.md](gates.md) |
| Upscale sharpness at 1.18 to 1.20 | Stills at 1.00, 1.12 and the ceiling, compared | `reel-motion` warns above 1.20 and asks for stills per camera body |
| Levels through the whole chain | Whether Chromium decode plus x264 in Remotion keeps the A-roll's tv-range levels, and whether an RGB filter such as `colortemperature` inside the chain shifts range before the explicit conversion. Measure the same frame in raw, A-roll, graphics pass and final | Covered by the `levels` gate in `reel-qa` and the working-format rules in `reel-grade` |
| Per-take grade values | Starting points from measurements, not yet checked on a waveform after application | `reel-grade` verifies on cheek patches after the render |
| Planned output timings | Computed from the transcript and the cut list, not from a render | Rule: recompute every graphic and SFX time from `words.out.json` after each cut; the beat map anchors to words |
| J/L cuts around blinks | Planned offsets, not frame-stepped | `reel-cut` searches offsets and guards 3 frames around blinks; still frame-step the cut strips |
| Caption contrast and mouth overlap | Not measured for each caption position on every take, especially a bright wall on one side or a close-up with a low chin | Covered by the caption gates in `reel-qa` |
| Full-length render time and memory | Extrapolated from 10 s benchmarks (about 9.5 fps after a 7 s startup); memory with 15 or more components untested | Open; measure on the target machine and use `REEL_CONCURRENCY` on a shared one |
| First frame | Whether the speaker's face is acceptable at frame 0 at the hook scale while focus is still settling | Covered: `first_frame` gate and held frames in `reel-cut` |
| Heavy weight of the display font | Title slams wanted an ExtraBold weight that was not downloaded | Check the brand folder holds every weight the components use, and load fonts from local files only (see the brand skill) |
| Tutorial transcripts | Video tutorials could not be fetched (bot wall), so the craft numbers rest on written guides and repo defaults | `craft-research` has the fetch recipe (throwaway-account cookies, sequential, slow); reference reels can now be measured directly |
| Framing drift | A slow reframe inside a take (about 100 px of background drift over a few seconds) shows under a static crop | Open: a smoothed face-tracking crop was suggested and not built |
| Music sync | Downbeat alignment to slams depends on the track tempo | Covered once a track exists: `reel-sound/scripts/find_downbeats.py` |

## Missing from every source

| Gap | Status in the skills |
|---|---|
| Cover image for the profile grid (and whether the grid crop keeps the headline) | Covered by `reel-export` (cover JPGs and the grid crop check) |
| Platform post copy and hashtags | Out of scope of these skills |
| Burned-in captions vs an uploaded subtitle file | Covered: `reel-export` writes an SRT for YouTube Shorts; burned-in captions stay |
| Licence of the `arnndn` model files (the model repo states none) | Open: check before using `arnndn` in production; the default chain does not use it |
| How one reel's decisions carry to the rest of a series | Covered by the series style bible in `reel-director` (standing rules, values that won, traps caught) |
