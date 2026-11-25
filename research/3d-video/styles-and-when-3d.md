# 3D styles, and when 3D beats 2D in a talking-head reel

What makes 3D shorts hold viewers, how B2B and SaaS brands use 3D, what the evidence says about cutaways in talking-head video, and how that turned into a 3D budget for a 45 to 60 s talking-head reel. The shipped rules are in [`reel-3d/references/when-3d.md`](../../skills/reel-3d/references/when-3d.md); this note keeps the sources and the reasoning.

Evidence grades: **[M]** measured (frame analysis), **[T]** a controlled-ish test, **[P]** practitioner or vendor opinion, **[O]** our own inference for the format.

## 1. Why 3D story shorts retain viewers [M]

From the plugin's study of 20 reference shorts (details in [reference-and-plugin.md](reference-and-plugin.md)). f = frame at 30 fps, px at 720x1280 (x1.5 for 1080x1920).

**Script and voice.** Voice starts at frame 1 to 4; no intro, logo, outro or CTA; median length about 60 s. Narration 3.5 to 4.1 words/s; total pauses over 0.25 s under 1 s per video. -14 LUFS, bed 5 to 10 dB under speech. Hook = a paradox stated as fact; one mystery question; a pivot into an everyday analogy; an ironic payoff; ends on the last word. Every sentence illustrated literally.

**Camera** (the part that transfers best).
- Almost never dead still: 65 % of frames move, about 10 % are true holds. About 6 moves per 10 s.
- Moves are symmetric ease-in-out glides: about 10 f in, 10 f out, 23 f total; median peak 14 px/f (p75 25) at 720p. Smootherstep over 18 to 40 f; keep duration >= 0.075 x distance in 720p px.
- Snappy 3-frame ease-out moves read as wrong (the plugin's first version peaked 8x too fast).
- Anything bigger than half a frame width or 40 % zoom is a hard cut, not a move.
- Holds creep: median 0.14 %/f (p75 0.34); emphasis push-ins 0.6 %/f for about 35 f. Push-ins outnumber pull-outs 2 to 1.
- Rolls 3.2 per 10 s, median 3.6 degrees over 18 f. No hand-held float.
- Impacts: a 6 to 7 f kick whose offset flips sign every frame, about 3 px per unit at 720p, roll 0.1 to 0.35 degrees, decay `(1 - n/7)^1.5`; the push stops on the hit.
- Hard cuts rare (0 to 1 per video in 12 of 20); a 4 f white flash after the hook.

**Acting and timing.** Every visual reaction lands 0 to 3 f before its word; swaps are instant. A short wind-up, about 6 f held, a 1-frame strike on the word onset. No squash and stretch, no busy idle loops.

**Look.** No pure blacks (non-ink p5 about 0.23, warm-lifted black point); saturation high; gentle vignette. Coloured shadows (violet-blue under warm key). Bloom only on true emissives. No film grain. Specular only on metal.

## 2. How B2B and SaaS brands use 3D [P]

- **An email API brand working in Spline** ([customer story](https://spline.design/customers/resend), [launch week write-up](https://www.resend.com/blog/launch-week-behind-the-scenes)), the closest analogue: a dark backdrop with a soft spotlight, **one coloured rim or edge light per object**, a glow at the base to anchor it, glossy or textured tiles, frosted glass only for large abstract forms, slow motion only (tumble, rotate, gentle rock), one unique 3D object per launch video, paired with animated text. Their launch feature videos themselves were simple talking heads, with 3D carrying the brand around them.
- **3D explainer roundups** ([B2W](https://www.b2w.tv/blog/best-3d-explainer-video-examples)): abstract spheres moving through pipelines and gates with protective layers, a hero object travelling a path and merging into a larger structure, isometric process flows, a dark warehouse that brightens once the solution appears. Repeated rule: **the palette warms or brightens at the transformation beat**.
- **Icon trends 2026**: soft 3D or clay is most adopted in consumer apps; developer tools still lean minimal; glass gets muddy at small sizes. Most SaaS 3D is "flat design plus one layer of depth or motion".
- **Product reveal craft**: always eased (linear reads cheap); every camera move uncovers something (an edge, a face, a glint); during orbits the lights follow the camera so the look holds, and the rim becomes a glint sweep.
- **Isometric**: true isometric = orthographic camera, yaw 45 degrees, pitch 35.264 degrees (atan(1/sqrt 2)); the classic "2:1 pixel" look is dimetric at 26.565 degrees. Orthographic keeps object size constant, so racks and flows read as diagrams rather than scenes.

## 3. Cutaways and interrupts in talking-head video

- **[T] One controlled-ish test** ([source](https://www.opus.pro/blog/does-b-roll-increase-watch-time)): an 8-minute video in three versions with the same script. No cutaways 66 % completion, about 40 % cutaway coverage 84 %, about 70 % coverage 74 %. At 70 % the drop-offs lined up with cutaway transitions. Cutaways that literally illustrate the sentence gained 3 to 7 % retention at that moment. An emotional anecdote kept 12 % more viewers on camera than over cutaways; a CTA over cutaways converted 40 % worse than a CTA to camera.
- **[P] Short-form cadence**: most sources cluster at a visual change every 2 to 6 s, denser in the first 15 to 25 s; an uninterrupted talking head for 10 to 15 s is widely reported to sag (unverified).
- **[P] The first 3 seconds** decide distribution; 30 to 60 s B2B feed videos with the hook in 3 s and burned-in captions are the consensus. **No source measured 3D against flat graphics for retention**: treat 3D as novelty and clarity, not magic.
- **[M] Rewatch**: a 31 s short watched 1.4 times beats a 60 s short abandoned halfway.

Conclusion: illustrate, do not cover. Moderate coverage beats none and beats heavy; keep the face for stories and the CTA.

## 4. When 3D beats 2D [O]

| Use 3D | Use 2D |
|---|---|
| a physical metaphor the viewer follows with their eyes: the email that lands in spam, the domain that burns, the shield that closes, the logo that turns to face them | text, numbers, lists, comparisons, charts, anything the viewer reads |
| one object, one action, at most one short label | several labels, a sentence, a checklist |
| a moment the script lingers on for at least 1 s | a word or phrase that passes in under 0.6 s |

If the idea still reads when the object is drawn flat, draw it flat: 2D renders in a fraction of the time and stays sharp at caption size. 3D text is avoided (flat text is crisper and keeps the 44 px minimum); a 3D label is at most one short word on an unlit plate.

## 5. Transfer to a 45 to 60 s talking-head reel [O]

### 5.1 Budget

- **2 or 3 3D moments per reel**, total 3D time **4 to 8 s** (about 10 to 15 %), inside an overall graphics coverage of 35 to 50 % (in line with the cutaway test above).
- **At most one full-frame 3D takeover per 15 s**, each **1.0 to 1.5 s** (the general takeover limit stays 1.5 s). Other 3D moments are card-zone objects of 1.5 to 2.5 s with the face still on screen.
- Never in the first second: the face and the hook own frame 0.
- Never over the CTA (it is to camera) and never over an emotional or personal line.
- At least 2 s of face between takeovers.
- The same object model throughout a reel, so the story is "this email" travelling, like the faceless channels' follow-the-object transitions.

`reel-director/scripts/beat_audit.py` now enforces the first-second, CTA window, takeover density, total time and takeover length rules.

### 5.2 Where on screen (1080x1920)

- **Takeover**: object in the band y 380 to 1060, centre about (510, 700), 420 to 560 px tall; captions at y 1180 on the dark band below.
- **Card zone**: inside x 70 to 950, y 1150 to 1480; object 260 to 300 px tall with a 44 px+ label; the face keeps the top two thirds; captions move up to y 1060.
- Nothing in the top logo zone (y 120 to 220), the bottom 420 px or the right 130 px (platform UI).
- An inset beside the head on wide shots was considered (a 280 to 340 px object at x 640 to 900) but not built.

### 5.3 Motion recipe per moment

- Entrance 10 to 14 f: from 1.15 scale or a 40 px offset plus a 20 to 35 degree yaw that resolves to a three-quarter view; never from scale 0. Smootherstep for 3D paths; the 8 f cubic stays for flat UI.
- Landing 0 to 3 f before the stressed word (the skill lands 1 frame before), one kick, one SFX hit; any creep stops on the hit.
- Hold 0.6 to 1.2 s with a creeping push of 0.15 to 0.35 %/f and a slow yaw of 0.2 to 0.4 degrees/f, so no 12-frame span is frozen (a QA failure inside a 3D window).
- Exit by hard cut back to the face (preferred after a takeover) or 5 to 6 f.
- At most one spring or overshoot per moment (6 % max).

### 5.4 Look in brand terms

Mapped onto the example brand in [`mailinfra-brand`](../../skills/mailinfra-brand/SKILL.md) (its `three` token block):

- Navy takeover gradient as the backdrop with a soft spot behind the object; lifted, coloured darks, nothing below the darkest token.
- Soft key from top-left (matches a typical A-roll key), cool fill, **one rim light in the meaning colour**: danger for failure, success for fixed, accent for emphasis, brand blue for the brand itself, warning for pending. A base glow in the same colour at 20 to 35 % opacity.
- Matte clay materials (roughness 0.55 to 0.8), one glossier part per object; glass only on large shapes.
- Glow only on emissive meaning elements (fire, the shield edge, a glint). No grain. No depth of field on card objects.
- The logo extrude must rest on the exact flat mark: the final frame equals the 2D logo card that follows it.

### 5.5 Moment library (deliverability vocabulary, mock text)

| Moment | Trigger words (example) | Mode, length | Built |
|---|---|---|---|
| Envelope falls into the spam folder | "spam", "junk" | takeover 1.2 to 1.5 s | yes, `EnvelopeToSpam3D` |
| Domain block catches fire | "burned", "blacklisted" | card 1.5 to 2.0 s | yes, `DomainBurn3D` |
| Shield closes around SPF, DKIM, DMARC | "authentication", the record names | card 2.0 to 2.5 s or takeover 1.0 to 1.5 s | yes, `AuthShield3D` |
| Logo turns to face the viewer | the first time the brand is named | takeover 0.8 to 1.0 s, hands off to a flat logo card | yes, `LogoExtrude3D` |
| Isometric server rack, LEDs cascading on the word | "infrastructure", "sending servers" | takeover 1.5 s | no |
| Warm-up ramp of stacked envelopes | "warm up", "ramp" | card 2.0 s | no |
| Envelope lands in the inbox (mirror of the spam drop, success rim, no kick, palette warms) | "lands in the inbox" | card 1.5 s | no |

Labels are our own text, never a real mail client's UI; no invented counts or numbers on any object.

The logo turn was first planned as the lead-in to the end card. It moved to "a brand moment earlier in the reel" because the CTA window (the last 3 s before the end card) must stay on the face, and `beat_audit.py` fails any 3D there.

### 5.6 Sample spacing

Face and hook headline own the first second. Place the first 3D moment as a card once the hook has landed, one takeover in each of the middle thirds at least 15 s apart, and card moments of 1.5 to 2.5 s between them, with at least 2 s of face around every takeover. The CTA and the last 3 s before the end card stay on the face. That gives 2 or 3 moments, 4 to 8 s of 3D, and all graphics at 35 to 50 % of the reel.

### 5.7 Sound for 3D moments

One SFX per 3D event: the whoosh peaks 1 frame before the land, one impact on the land frame, a glint gets a pop at -16 LU at most. Duck the bed, never the voice. The 3D renderer writes the event times (`3d/<beat>.json`) and [`reel-sound`](../../skills/reel-sound/SKILL.md) places cues on them.

## 6. What does not transfer

- 2D cartoon characters in a 3D town, ink-outlined worlds, one-word hard-swap captions, story narration with no face: the reel is a person talking; 3D is punctuation.
- "Hard cuts almost never": a talking head cuts often; only the 3D shots follow the glide grammar.
- Faceless-niche packaging and the "no CTA" rule.
- Transfers well: the paradox hook, the pivot into an analogy, the ironic payoff, reactions 0 to 3 f early, creeping holds, flip-sign impact kicks, lifted coloured blacks, bloom only on emissives, no grain, one meaning colour per rim.

## Sources

- Plugin (MIT, read only): mromidev's animated-shorts plugin (`gh repo list mromidev`): README, skill file, style bible, motion, depth, grade, lighting and outline reports.
- Faceless channel breakdown: https://danielrusnok.substack.com/p/how-a-faceless-channel-engineered
- B-roll coverage test: https://www.opus.pro/blog/does-b-roll-increase-watch-time
- Remotion: https://www.remotion.dev/docs/three-canvas, https://remotion.dev/docs/three, https://github.com/remotion-dev/template-three, https://github.com/remotion-dev/glb-example
- Spline customer story and launch write-up: https://spline.design/customers/resend, https://www.resend.com/blog/launch-week-behind-the-scenes
- 3D explainer examples: https://www.b2w.tv/blog/best-3d-explainer-video-examples
- Icon trends: https://iconly.ai/blog/icon-trends-2026/, https://www.creativebloq.com/3d/the-critical-3d-art-trends-that-will-impact-2026
- Isometric projection: https://pikuma.com/blog/isometric-projection-in-games, https://threejs.org/docs/pages/OrthographicCamera.html
- Text extrusion: https://threejs.org/docs/pages/TextGeometry.html, https://tympanus.net/codrops/2020/06/02/kinetic-typography-with-three-js/
- Pacing and hooks (low confidence): https://hailuoai.video/knowledge/youtube-shorts-pacing-camera-speed, https://www.capcut.com/create/pattern-interrupt-technique-short-form-video, https://www.opus.pro/blog/ideal-linkedin-video-length-format-for-retention
- Overlay placement: https://hera.video/blog/overlay-motion-graphics-generator-for-talking-head-videos
