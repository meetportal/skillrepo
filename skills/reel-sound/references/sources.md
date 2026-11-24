# Vetted sources for music beds and sound effects

Checked 2026-11-24. Licence terms change: re-read the item page before every use and record what you saw (see the licence check in `SKILL.md`). This repo ships no audio from any of these sources.

Accept for a commercial short-form reel (organic post or paid ad): **CC0**, **Public Domain Mark**, **CC BY** (with the attribution line in the post), or a platform licence that names social media and online ads as allowed. Reject **NC** (non-commercial), **ND** (Creative Commons treats syncing music to moving images as an adaptation), **SA** (would bind the whole video), "personal use", and anything with no stated licence.

## Music

| Source | Licence | Attribution | Notes |
|---|---|---|---|
| FreePD (freepd.com) | CC0 1.0 | none | Site went offline in 2026. Its catalogue (mostly Kevin MacLeod, Bryan Teoh, Rafael Krux, Alexander Nakarada) is still verifiable on Internet Archive captures, e.g. `web.archive.org/web/2024/https://freepd.com/upbeat.php`. Download the original file through the capture with the `id_` form: `https://web.archive.org/web/<timestamp>id_/https://freepd.com/music/<Title>.mp3`. Keep the capture URLs as licence evidence. Prefer files whose ID3 comment carries the composer's own dedication; skip files tagged with a paid library name (for example AudioJungle). |
| Kevin MacLeod, incompetech.com | CC BY 4.0 | required: `"Title" Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License, http://creativecommons.org/licenses/by/4.0/` | Large catalogue with BPM and feel metadata; a paid no-attribution licence exists. Use when no CC0 track fits. |
| Free Music Archive (freemusicarchive.org) | per track | depends | Filter to CC0 or CC BY only; many tracks are NC or ND. Downloads may require an account. |
| ccMixter (ccmixter.org, dig.ccmixter.org) | per track | CC BY needs credit | Many uploads are CC BY-NC; use the commercial-use filter and re-check each upload page. Instrumental filter available. |
| Openverse (openverse.org) | aggregator | depends | Search with `license=cc0,by`; always verify the licence on the original page it links to. The API sits behind a bot wall for scripts. |
| OpenGameArt (opengameart.org) | per item, often CC0 or CC BY | depends | Mostly game music; quality varies, check loops. |
| Musopen (musopen.org) | public domain / CC0 recordings | none | Classical repertoire only. |
| Scott Buckley (scottbuckley.com.au) | CC BY 4.0 | required | Cinematic and orchestral, rarely a fit for tech reels. |
| Mixkit (mixkit.co/free-stock-music) | Mixkit Stock Music Free License | none | Allows YouTube, social posts and online ads; forbids broadcast TV/radio, standalone redistribution and Content ID registration. Download into the project at runtime, never commit. |
| Pixabay Music (pixabay.com/music) | Pixabay Content License (not CC0) | none | Commercial use allowed, no standalone redistribution. Download needs an account (scripts get 403). Some tracks carry Content ID registrations; keep the licence certificate. |
| YouTube Audio Library | YouTube terms, some tracks CC BY | per track | Made for YouTube uploads; check the per-track attribution flag before using it on other platforms. |
| Epidemic Sound, Artlist and similar | paid subscription | none | Licence covers the subscriber's channels and period only. Ask the owner which account the reel is published under. |

## Sound effects

| Source | Licence | Attribution | Notes |
|---|---|---|---|
| Kenney (kenney.nl/assets, audio packs) | CC0 1.0 | none | Interface, UI, digital, impact and sci-fi packs. Each pack zip has a License.txt. |
| Freesound (freesound.org) | per sound: CC0, CC BY, CC BY-NC | CC BY needs credit | Use CC0 or CC BY only; the licence is on each sound page. Originals need a free account; the HQ previews are 128 kbps MP3/OGG. |
| Sonniss GDC bundles (sonniss.com/gameaudiogdc) | Sonniss royalty-free licence | none | Commercial use in productions allowed; no standalone redistribution. Very large WAV downloads. |
| Mixkit SFX (mixkit.co/free-sound-effects) | Mixkit Sound Effects Free License | none | Commercial use in projects; no redistribution. |
| Pixabay SFX | Pixabay Content License | none | Same terms as Pixabay Music. |
| Zapsplat (zapsplat.com) | Standard licence | required on the free tier | Paid tier removes attribution. |
| BBC Sound Effects (sound-effects.bbcrewind.co.uk) | RemArc licence | n/a | Personal, educational and research use only: **not allowed** for business reels or ads. |

## Curated CC0 kit used as the default library

A CC0-only one-shot kit of about 100 OGG files (Kenney packs plus Freesound CC0 sounds, trimmed and peak-normalised) is published in the MIT-licensed `motion-graphics` repo by Barty-Bart on GitHub, folder `skills/sound-effects/sfx/`, with a `manifest.json` that lists category, source URL and licence per file. `scripts/sfx_cues.py` reads that manifest format directly. Copy only the files a reel uses into the reel's work folder, write a project manifest with sha256 per file, and treat the repo's scripts as untrusted (do not run them).
