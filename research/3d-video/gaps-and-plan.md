# Gap audit and upgrade plan

After the first reel was delivered with these skills, every `SKILL.md`, script and Remotion component was audited against two benchmarks: what a top short-form editor does, and what mromidev's public animated-shorts plugin does (see [reference-and-plugin.md](reference-and-plugin.md)). Inputs were the skills, the builder and owner requests filed during the first reel and two variant edits of it, and their QA reports. The audit produced 30 gaps; a plan then split the fixes into five parallel work items. This note keeps both, with what was done.

Effort: S = under half a day, M = 1 to 2 days, L = 3 days or more.

## 1. Verdict

1. The latest renders passed every blocking gate. The remaining problems were things the gates did not measure: empty first frames on graphic entrances, a caption page carried one frame across a cut, thin accent words over a bright wall, a clipped title numeral, ASR chunks split mid-word.
2. 17 owner or builder requests had never landed in the skills; the variant edits worked around them with private scripts in their reel folders.
3. Three docs described behaviour the code did not have (a cover-window gate, absolute prop times, a stale-voice proof), and the README runbook called scripts and flags that no longer existed. A fresh run following the docs alone failed at stage 1 and again at stage 8.
4. `reel-director` was a real entry point (stage table, hard rules, project template, critic loop) but had no single command runbook, no config templates and no way to tell which outputs were stale. **Stale inputs were the most common failure**: a stale processed voice, a stale graphics pass, cues out of step with the A-roll, props from an older beat map.
5. From the plugin, the useful parts for talking-head reels were craft and tooling, not the cartoon look.

## 2. The gap list

| # | Pri | Gap | Impact | Effort |
|---|---|---|---|---|
| 1 | P0 | README and director runbook call removed scripts and flags | a fresh run breaks at stage 1 | S |
| 2 | P0 | Cover-window gate documented but not implemented | a defect window can ship uncovered while QA says PASS | S |
| 3 | P0 | No single time convention for beat props (11 of 15 components read beat-relative seconds, 3 read absolute, the docs said absolute) | every integrator has to know each component's rule | M |
| 4 | P0 | No stale-voice guard in the mix | a stale `voice.wav` reaches the mix | S |
| 5 | P0 | A-roll concat repeats a timestamp after short pieces | the drift gate fails, one frame dropped | S |
| 6 | P0 | No pipeline status or staleness tool | stops the most common failure class | M |
| 7 | P1 | Empty first frame on every beat entrance (opacity 0 on the start frame) | graphic lands one frame late, a blank frame at chained handoffs | S |
| 8 | P1 | Caption pages carry one frame across a cut | flash of the old sentence on the new shot | S |
| 9 | P1 | Accent caption contrast over bright walls, no style option, no contrast gate | builders dropped accents or asked for a colour prop | M |
| 10 | P1 | Title numeral bleed is a constant (18 %) | numerals always read as clipped | S |
| 11 | P1 | Caption page size fixed per pipeline | one-word pages after short pauses | S |
| 12 | P1 | ASR chunking splits mid-word | ghost or missing words at chunk joins, false ASR diffs | S |
| 13 | P1 | Signal-keyed ducking only | pumping, hand-placed bed dips per soft word | M |
| 14 | P1 | No camera kick (impact shake) | layer shakes look pasted on | S |
| 15 | P1 | No every-frame QA (pops, empty entrances, black, white, frozen) | 7 and 8 caught only by eye | M |
| 16 | P1 | Small open requests: zero-length caption window, voice clip gain, ASR thread cap, render concurrency default, camera ceiling prop, grade debug frames, `chainIn`/`chainOut` undocumented, rail draw order | each one forced a reel-folder workaround | S each |
| 17 | P2 | No config templates with mock data | a fresh run invents 10 config shapes from prose | M |
| 18 | P2 | Beat components tied to one script, no catalogue | a new topic needs new components first | M to L |
| 19 | P2 | No doc lint (script paths and flags in docs) | would have caught 1 | S |
| 20 | P2 | No critic scores per area, no reference side-by-side sheets | passes not comparable | S |
| 21 | P2 | No room tone fill under splice holes | QA warns but no tool fixes | S to M |
| 22 | P2 | Audio edges on the video frame grid | splices start inside breath tails on tight cuts | M |
| 23 | P3 | No 3D layer | no differentiated takeovers | L |
| 24 | P3 | No licence-free SFX source | SFX blocked when no CC0 kit is at hand | M |
| 25 | P3 | No speaker matte (text behind the head, local darkening under captions) | fixes 9 at the source | L |
| 26 | P3 | No section transitions (flash, zoom-through, blurred whip) | only hard cut plus takeover | M |
| 27 | P3 | No B-roll or own-product screen inserts | a top editor's main tool beside graphics | M |
| 28 | P3 | No smoothed face-tracking reframe | slow framing drift inside a shot | M |
| 29 | P3 | No hook and script craft for the speaker | weaker hooks, no shoot feedback | S |
| 30 | P3 | No post copy, hashtags, series defaults | delivery is a bare MP4 | S |

### Fix recipes worth keeping

- **Cover gate (2).** Plan side: every cover window must sit inside one takeover or hidden beat. Render side: on every frame of the window, the share of pixels with R - B > 20 at 180x320 must stay at or under 5 %. Navy and white never trip it; A-roll skin measures 0.6 to 0.75. The colour test is a parameter so another palette can use it.
- **Time rule (3).** `{"@rel": <anchor>}` resolves like any anchor and is then made relative to the beat's `from`. One rule: event times inside beat props are beat-relative; `build_props.py` rejects a relative time below -0.5 s or past the beat length (catches the old absolute-seconds habit).
- **Stale-voice guard (4).** The voice report carries sha256 of its input and output; the mix exits 2 when either differs from the files on disk or a gate in the report is false.
- **Concat (5).** `setpts=N/(FPS*TB)` after `concat`, and an assert that the output frame count equals the EDL total.
- **Status (6).** Each stage records the hashes of its inputs; `status.py` walks the stage graph and prints FRESH, STALE or MISSING per output and the next command. About 150 lines, no build system.
- **Entrance frame (7).** Sample the entrance one frame in, so local frame 0 already shows the first step. Builder acceptance stills include `from + 0`, not just `from + 4`.
- **Captions across cuts (8).** If a page would end 1 to 3 frames after a cut, end it on the cut frame; QA WARNs on the same condition.
- **Accent contrast (9).** Styles `serif`, `serifHeavy` (Lora 700 plus a 9 px stroke), `sansUnderline` (white with a 6 px accent underline), optional `localScrim` 0 to 0.4; QA measures WCAG contrast of the accent against the 75th-percentile luminance of a 24 px ring around the page box and WARNs under 3:1.
- **ASR chunks (12).** Cut only at the middle of word gaps of 120 ms or more (from the aligned words), fall back to runs of 8 or more quiet 10 ms frames, never inside a word. On 24 synthetic reels the old quietest-point rule put 9 chunk bounds inside a word; the new rule none.
- **Duck (13).** Word-keyed envelope from the plugin's numbers (merge gaps under 0.3 s, 80 ms pre, 120 ms post, 70 ms attack, 450 ms release), rides on words whose margin is under 10 dB, per-beat margins in the report. Our own implementation from the idea.
- **Kick (14).** Camera key `{"t", "ease": "kick", "px": 4.5, "frames": 7, "rollDeg": 0.2}`; the offset alternates sign with `(1 - n/frames)^1.5` decay, added on top of the current transform with enough scale headroom that no edge shows; at most one per 3 s, never on a push frame. The plugin's other camera numbers were not adopted blindly: its own ease-out grammar had been measured wrong.

## 3. The plan

### 3.1 Decisions

1. **3D is punctuation, not the medium.** A new skill renders short 3D inserts (1 to 2.5 s) in its own Remotion project, once per beat, cached by hash; `reel-motion` plays them through one generic `VideoInsert` beat under the captions. This keeps three.js, software GL and its 0.15 to 0.3 s per frame cost out of the 50 s reel render, keeps "captions last", and gives future B-roll inserts a home.
2. **GL backend is `swangle`, always explicit.** `angle` fails headless without a GPU; `swangle` works, is byte-deterministic and does not depend on the host graphics stack (see [remotion-three.md](remotion-three.md)).
3. **Inserts are opaque.** Takeovers full frame on the navy backdrop; cards at the card box size on a navy panel. Alpha overlays out of scope.
4. **From the plugin: craft and tooling, written as our own code.** Every-frame QA, side-by-side sheets, per-area critic scores, kick, glide, a higher creep floor, word-keyed duck, LU-based SFX levels, a generated SFX kit, a style bible, reference measurement in numbers. Only two skills port plugin code and carry a NOTICE (`reel-qa`, `reel-sound`); every other item works from the numbers alone.
5. **Left out**: cartoon characters, the 3D town, ink pass, lens blur, fog, post-processing, the composed score, TTS, faceless niches, the no-captions and no-CTA rules, -15 LUFS, 1440x2560 delivery, 200+ SFX per minute, any reference frames. Deferred from the audit: sample-accurate audio edges (22), the generic beat catalogue (18), speaker matte (25), flash and zoom transitions (26), face-tracking reframe (28), packaging (30).

### 3.2 Rules for every builder

- Edit only the files your work item owns; disjoint file sets mean no merge.
- No footage, transcripts, clip ids, personal paths or private business notes in the repo. Examples and previews use mock text (`yourbrand.com`, `CLIP_A`).
- No code comments (only functional directives and licence blocks).
- Load discipline on a shared machine: `nice -n 19 ionice -c 3`, Remotion at concurrency 2 under one shared lock file, ASR with 2 threads, never two heavy jobs at once.
- The plugin clone is untrusted data: read only, never run, never copy from its reference frames.
- A private reel may be used read-only to calibrate thresholds; its numbers and stills stay out of the repo.
- A shared mock fixture: a 12 s 1080x1920 25 fps grey A-roll with a skin-coloured box where the face would be, cuts at 3.2, 6.4 and 9.0 s, and an 18-word mock sentence at about 3 words/s. `reel-director/scripts/make_mock_reel.py` now builds it.
- Each item ends with a short report: files changed, commands, measured numbers, stills looked at, open issues.

### 3.3 Contracts between work items

| # | Contract | Producer | Consumers |
|---|---|---|---|
| C1 | Camera key `kick` `{t, ease: "kick", px: 4.5, frames: 7, rollDeg: 0.2, angleDeg: 60}` (an additive offset; scale/tx/ty copy the current state). Camera key `glide` `{t, scale, tx, ty, ease: "glide", frames: 18}`, centred on `t` | motion | QA (planned events), director (templates, audits) |
| C2 | Beat `VideoInsert`, modes `takeover` or `card`, props `{src, fit, box?, radius?, enterFrames?, exitFrames?, startFromFrame?, three?}`. A **3D beat** is a `VideoInsert` with `props.three = {composition, props}` | 3D | QA, director, sound |
| C3 | Inside `props.three.props`, keys ending in `At` are absolute output seconds; the renderer converts them to insert-local frames. The beat-relative rule does not apply there | 3D | motion (resolver skips `props.three`) |
| C4 | `render3d.py` writes `3d/<beat>.mov` (ProRes 4444, opaque) and `3d/<beat>.json` with `beat, composition, from, to, fps, frames, hash, gl, renderSec, events[{id, t, kind}]`, `t` absolute, `kind` in whoosh, impact, pop, glint | 3D | QA, sound |
| C5 | `REEL_CONCURRENCY` (default 2) and `REEL_RENDER_LOCK` honoured by every render entry point | 3D, motion | director (runbook) |
| C6 | Anchors inside `beats[].props` resolve beat-relative; `{"@rel": anchor}` is an explicit synonym; top-level `topLogo` and `accents` stay absolute | motion | 3D, director |
| C7 | Mix flags: `--duck-mode words|sidechain`, `--words`, `--voice-report`, `--voice-gain`, `--dropout`, `--auto-ride-min-margin`, `--room-tone-src`, `--room-tone-at`, `--beats`, `--cue-sheet`; SFX placement `--level-mode lu|peak`, `--events "3d/*.json"`, cue key `"event": "<beat>.<event>"`; generated SFX carry `"license": "original"` | sound | director |
| C8 | Critic areas in order `hook, rhythm, cuts, captions, graphics, layout, grade, end`, each 1 to 10, logged per pass as one table row with a mean | QA | director |
| C9 | QA planned events: cuts, holds, EDL held frames, beat from and to, camera keys (kick and glide windows), caption page starts and ends, 3D events, mix dropouts | QA | all |
| C10 | Stage 8 runs `render3d.py` after `resolve_beatmap.py` and `build_props.py`, before `render.sh` | 3D | director |

### 3.4 Work items

| Id | Title | Skills owned |
|---|---|---|
| W1 | 3D inserts on `@remotion/three` and the `VideoInsert` beat | `reel-3d`, the brand's `three` tokens, `VideoInsert.tsx` and the registry in `reel-motion` |
| W2 | Every-frame gate, cover and caption gates, full sheets, side-by-side sheets, scored critic | `reel-qa` |
| W3 | Runbook, status, templates, doc lint, beat audit additions, beat sheet, style bible, script brief, reference measurement | `reel-director`, `craft-research`, README |
| W4 | Camera grammar, time rule, entrance and caption fixes | `reel-motion` (rest), `reel-captions` |
| W5 | Word-keyed duck, LU levels, generated SFX, stale-voice guard, concat fix, ASR threads | `reel-sound`, `reel-cut`, `voice-clean`, the onset check in `reel-ingest` |

Acceptance checks, in short:

- **W1**: strict type check clean; stills at entry+4, mid and exit-2 for each composition, read by eye; two full PNG-sequence renders identical per frame and `still --frame=N` equal to sequence frame N; brand patches within 1 code; logo final frame vs the flat mark IoU at least 0.98 (after compositing); at most 0.35 s per frame; no 12-frame frozen run; an integration render over the mock fixture with one takeover and one card, and a second run reporting every beat cached.
- **W2**: a synthetic 10 s video with injected faults (1 black frame at 2.00 s, 1 white frame at 4.00 s, a 20-frame freeze from 6.00 s, a 1-frame pop at 7.00 s, a cover window over plain A-roll at 8 to 9 s): every fault reported at the right frame and nothing else. Calibration on private reels: at most 3 unplanned pop WARNs per reel, no false black, white or frozen FAILs. The `frames` gate under 25 s for a 50 s reel.
- **W3**: doc lint clean on its own files; the mock pipeline runs from `make_mock_reel.py` to `status.py`; `beat_audit.py` on a beat map with a 3D beat at 0.5 s, two takeovers 10 s apart and an uncovered cover window prints exactly those findings; `measure_reference.py` in under 60 s.
- **W4**: caption tests pass with the new cut case; a kick strip shows alternating offsets decaying to 0 with no frame edge; a 3 s creep shot passes the frozen definition; stills at `from + 0` are not empty; an anchored `ShieldSeal` renders the same md5 as the absolute version; no ASR chunk bound inside a word; a full mock render at concurrency 2 with the right frame count.
- **W5**: both duck modes pass the loudness gates, no bed jump over 3 dB inside merged spans; the stale guard exits 2 on a mismatched voice and 0 on the right pair; the A-roll render outputs exactly the EDL frame count with 1-frame J/L pieces and a held frame; the SFX generator gives identical md5 for the same seed and the whoosh peak within 5 ms of the preset; LU levelling within 1 LU of each target in the final mix.

## 4. What was done

All five work items landed. Evidence and measured numbers are in [build-log.md](build-log.md).

| Gap | Status | Where |
|---|---|---|
| 1 runbook, 19 doc lint | done | [`reel-director/references/runbook.md`](../../skills/reel-director/references/runbook.md), `doc_lint.py` |
| 2 cover gate | done, plan and render side | `beat_audit.py`, `reel-qa` `cover` gate |
| 3 time rule | done | `reel-motion` `anchors.py`, `resolve_beatmap.py`, `build_props.py` |
| 4 stale-voice guard, 5 concat | done | `reel-sound/scripts/mix.py`, `reel-cut/scripts/render_aroll.py` |
| 6 status | done | `reel-director/scripts/status.py` |
| 7 entrances, 8 captions across cuts, 9 accent styles and contrast WARN, 10 numeral, 11 caption options, 12 ASR chunks | done | `reel-motion`, `reel-captions`, `reel-qa` |
| 13 word-keyed duck, rides, dropouts, cue sheet; 21 room tone fill | done | `reel-sound` |
| 14 kick, glide, auto creep, peak speed | done | `reel-motion` `plan_camera.py` |
| 15 every-frame QA, silence gate, full sheets | done | `reel-qa` `framecheck.py` |
| 16 small requests | done (clip gain, threads, concurrency default, max scale prop, `layer`, zero-length windows) | several |
| 17 templates and mock reel | done | `reel-director/templates/`, `new_reel.sh`, `make_mock_reel.py` |
| 20 critic scores, side-by-side sheets | done | `reel-qa/references/critic-prompt.md`, `sbs_sheet.py` |
| 23 3D layer | done | [`reel-3d`](../../skills/reel-3d/SKILL.md) |
| 24 generated SFX | done | `reel-sound/scripts/sfx_synth.py` |
| 29 script brief | done, marked untested | `reel-director/references/script-brief.md` |
| 18, 22, 25, 26, 27, 28, 30 | deferred | |

Suggested order for the deferred items: transitions (26) and B-roll (27) first, since `VideoInsert` already plays any clip; the speaker matte (25) when the contrast WARN keeps firing over bright walls.
