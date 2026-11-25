import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soundlib import load_json

ATTRIBUTION_FREE = ("cc0", "public domain", "pdm", "mixkit", "pixabay", "original")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest_entries(path):
    manifest = load_json(path)
    root = Path(path).resolve().parent / manifest.get("root", ".")
    kind = manifest.get("kind")
    entries = []
    for key in ("files", "bundled", "default_kit", "tracks"):
        for entry in manifest.get(key, []):
            if not entry.get("file"):
                continue
            file_path = root / entry["file"]
            digest = entry.get("sha256") or (sha256(file_path) if file_path.exists() else None)
            entries.append({**entry, "kind": entry.get("kind") or kind or ("music" if key == "tracks" else "sfx"), "sha256": digest, "path": str(file_path.resolve())})
    return entries


def used_files(args):
    files = list(args.used or [])
    for placements_path in args.placements or []:
        files += [p["file"] for p in load_json(placements_path)["placements"]]
    unique = []
    for path in files:
        resolved = str(Path(path).resolve())
        if resolved not in unique:
            unique.append(resolved)
    return unique


def needs_attribution(entry):
    licence = (entry.get("license") or "").lower()
    if entry.get("attribution_required") is not None:
        return bool(entry["attribution_required"])
    return not any(token in licence for token in ATTRIBUTION_FREE)


def credit_line(entry):
    if entry.get("attribution_line"):
        return entry["attribution_line"]
    if (entry.get("license") or "").lower() == "original":
        params = entry.get("params") or {}
        seed = f", seed {params['seed']}" if "seed" in params else ""
        return f'"{entry.get("title") or Path(entry["file"]).stem}" generated with sfx_synth.py{seed}, original sound, no licence needed'
    title = entry.get("title") or Path(entry["file"]).stem
    creator = entry.get("creator") or entry.get("artist") or "unknown"
    licence = entry.get("license") or "licence unknown"
    source = entry.get("source_url") or ""
    return f'"{title}" by {creator} ({source}), {licence}'.replace(" ()", "")


def main():
    parser = argparse.ArgumentParser(description="Write CREDITS.txt for every music and SFX file a mix used, from the files' manifests (matched by sha256).")
    parser.add_argument("--manifest", action="append", required=True, help="manifest json with files[] or tracks[] (repeatable)")
    parser.add_argument("--placements", action="append", help="sfx_cues.py placements json; every file it places counts as used (repeatable)")
    parser.add_argument("--used", action="append", help="another used file, e.g. the music bed (repeatable)")
    parser.add_argument("--title", default="Audio credits")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    entries = [e for path in args.manifest for e in manifest_entries(path)]
    by_hash = {e["sha256"]: e for e in entries if e["sha256"]}
    by_path = {e["path"]: e for e in entries}
    matched, missing = [], []
    for path in used_files(args):
        entry = by_path.get(path) or by_hash.get(sha256(path))
        (matched if entry else missing).append(entry or path)
    if missing:
        raise SystemExit("no licence record for: " + ", ".join(missing))

    music = [e for e in matched if e["kind"] == "music"]
    sfx = sorted({e["file"]: e for e in matched if e["kind"] != "music"}.values(), key=lambda e: e["file"])
    required = [e for e in music + sfx if needs_attribution(e)]
    lines = [args.title, "", "MUSIC"]
    lines += [f"- {credit_line(e)}" + (f" [{e['license_url']}]" if e.get("license_url") else "") for e in music] or ["- none"]
    lines += ["", "SOUND EFFECTS"]
    lines += [f"- {credit_line(e)}" for e in sfx] or ["- none"]
    lines += ["", "ATTRIBUTION REQUIRED IN THE POST DESCRIPTION"]
    lines += [f"- {credit_line(e)}" for e in required] or ["- none (every file is CC0 / public domain or under a no-credit licence; the credits above are given voluntarily)"]
    lines += ["", "FILE CHECKSUMS (sha256)"]
    lines += [f"- {e['file']}  {e['sha256']}" for e in music + sfx]
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"{len(music)} music, {len(sfx)} SFX files credited; {len(required)} need attribution -> {args.out}")


if __name__ == "__main__":
    main()
