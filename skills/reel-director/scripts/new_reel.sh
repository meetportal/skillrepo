#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage: new_reel.sh <work-dir> [--series-root DIR]

Creates the reel work folder layout (config/, ingest/, voice_lab/, music/, sfx/, 3d/, out/, qa/)
and copies the reel-director templates into it without overwriting anything that exists:
  config/   cutlist.json grade.json cues_config.json corrections.json shots.json beatmap.src.json sfx_cues.json
  music/manifest.json  sfx/manifest.json  project.md
The series style bible (style-bible.md) goes to the series root, by default the parent of <work-dir>,
and is only created when the series has none yet.
EOF
}

work="" series_root=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --series-root) series_root="$2"; shift 2 ;;
    -*) usage >&2; exit 2 ;;
    *) [[ -z "$work" ]] || { usage >&2; exit 2; }; work="$1"; shift ;;
  esac
done
[[ -n "$work" ]] || { usage >&2; exit 2; }

templates="$(cd "$(dirname "${BASH_SOURCE[0]}")/../templates" && pwd)"
mkdir -p "$work"
work="$(cd "$work" && pwd)"
series_root="${series_root:-$(dirname "$work")}"
mkdir -p "$series_root"

for sub in config ingest voice_lab music sfx 3d out qa; do
  mkdir -p "$work/$sub"
done

copy() {
  local src="$1" dest="$2"
  if [[ -e "$dest" ]]; then
    echo "kept     $dest"
  else
    cp -p "$src" "$dest"
    echo "created  $dest"
  fi
}

for file in "$templates"/config/*.json; do
  copy "$file" "$work/config/$(basename "$file")"
done
copy "$templates/music/manifest.json" "$work/music/manifest.json"
copy "$templates/sfx/manifest.json" "$work/sfx/manifest.json"
copy "$templates/project.md" "$work/project.md"
copy "$templates/style-bible.md" "$series_root/style-bible.md"

echo "next: fill config/cutlist.json with the raw clip paths, then follow reel-director/references/runbook.md"
echo "      python \$SKILLS/reel-director/scripts/status.py   (prints what is missing or stale and the next command)"
