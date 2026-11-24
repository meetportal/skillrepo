#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  render.sh --props props.json --public-dir DIR --out out/gfx.mp4 [--concurrency 4] [--frames 0-99] [--crf 14]
  render.sh --props props.json --public-dir DIR --still 0.0,1.0,7.3 --out out/stills [--image-format png]

Brand: $REEL_BRAND (a brand folder with brand.json and assets/) or the bundled mailinfra-brand.
A full render records the A-roll md5 before and after (<out>.aroll.md5) and fails if the
A-roll changed during the render or the frame count differs from props durationSec * fps.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$script_dir/../remotion"
props="" public_dir="" out="" stills="" concurrency=4 frames="" crf=14 image_format=png composition=Reel

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --props) props="$2"; shift 2 ;;
    --public-dir) public_dir="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --still) stills="$2"; shift 2 ;;
    --concurrency) concurrency="$2"; shift 2 ;;
    --frames) frames="$2"; shift 2 ;;
    --crf) crf="$2"; shift 2 ;;
    --image-format) image_format="$2"; shift 2 ;;
    --composition) composition="$2"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ -n "$props" && -n "$public_dir" && -n "$out" ]] || { usage >&2; exit 2; }
[[ -f "$props" ]] || { echo "props not found: $props" >&2; exit 2; }
[[ -d "$public_dir" ]] || { echo "public dir not found: $public_dir" >&2; exit 2; }

props="$(realpath "$props")"
public_dir="$(realpath "$public_dir")"
out="$(realpath -m "$out")"
if [[ -n "${REEL_BRAND:-}" ]]; then
  REEL_BRAND="$(realpath "$REEL_BRAND")"
  export REEL_BRAND
fi

[[ -d "$project_dir/node_modules" ]] || (cd "$project_dir" && npm ci --no-audit --no-fund)
bash "$script_dir/prepare_public.sh" "$public_dir" >/dev/null

prop() {
  node -e 'const p=JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"));console.log(p[process.argv[2]])' "$props" "$1"
}
fps="$(prop fps)"
aroll_rel="$(prop aroll)"
aroll_path=""
[[ -n "$aroll_rel" && "$aroll_rel" != "undefined" && ! "$aroll_rel" =~ ^https?:// ]] && aroll_path="$public_dir/$aroll_rel"

cd "$project_dir"
common=(--props="$props" --public-dir="$public_dir" --log=warn)

if [[ -n "$stills" ]]; then
  node "$script_dir/stills.mjs" --props "$props" --public-dir "$public_dir" --out "$out" --times "$stills" --image-format "$image_format" --composition "$composition"
  exit 0
fi

mkdir -p "$(dirname "$out")"
render_args=(--muted --color-space=bt709 --codec=h264 --crf="$crf" --x264-preset=medium --pixel-format=yuv420p --concurrency="$concurrency")
[[ -n "$frames" ]] && render_args+=(--frames="$frames")
md5_before=""
[[ -n "$aroll_path" && -f "$aroll_path" ]] && md5_before="$(md5sum "$aroll_path" | cut -d' ' -f1)"
start=$(date +%s)
npx remotion render src/index.ts "$composition" "$out" "${common[@]}" "${render_args[@]}"
echo "rendered $out in $(( $(date +%s) - start )) s"

if [[ -n "$md5_before" ]]; then
  md5_after="$(md5sum "$aroll_path" | cut -d' ' -f1)"
  echo "$md5_after  $aroll_rel" >"$out.aroll.md5"
  if [[ "$md5_before" != "$md5_after" ]]; then
    echo "error: the A-roll changed during the render ($md5_before -> $md5_after); re-render" >&2
    exit 1
  fi
fi
if [[ -z "$frames" ]]; then
  expected="$(node -e 'const p=JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"));console.log(Math.max(1,Math.round(p.durationSec*p.fps)))' "$props")"
  actual="$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 "$out")"
  if [[ "$expected" != "$actual" ]]; then
    echo "error: $out has $actual frames, props expect $expected" >&2
    exit 1
  fi
  echo "frame count $actual matches props; A-roll md5 recorded in $out.aroll.md5"
fi
