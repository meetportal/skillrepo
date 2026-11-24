#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage:
  render.sh --props props.json --public-dir DIR --out out/gfx.mp4 [--concurrency 4] [--frames 0-99] [--crf 14]
  render.sh --props props.json --public-dir DIR --still 0.0,1.0,7.3 --out out/stills [--image-format png]
EOF
  exit 2
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$script_dir/../remotion"
props="" public_dir="" out="" stills="" concurrency=4 frames="" crf=14 image_format=png composition=Reel

while [[ $# -gt 0 ]]; do
  case "$1" in
    --props) props="$2"; shift 2 ;;
    --public-dir) public_dir="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --still) stills="$2"; shift 2 ;;
    --concurrency) concurrency="$2"; shift 2 ;;
    --frames) frames="$2"; shift 2 ;;
    --crf) crf="$2"; shift 2 ;;
    --image-format) image_format="$2"; shift 2 ;;
    --composition) composition="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$props" && -n "$public_dir" && -n "$out" ]] || usage

props="$(realpath "$props")"
public_dir="$(realpath "$public_dir")"
out="$(realpath -m "$out")"

[[ -d "$project_dir/node_modules" ]] || (cd "$project_dir" && npm ci --no-audit --no-fund)
bash "$script_dir/prepare_public.sh" "$public_dir" >/dev/null

cd "$project_dir"
common=(--props="$props" --public-dir="$public_dir" --log=warn)

if [[ -n "$stills" ]]; then
  mkdir -p "$out"
  fps="$(node -e 'console.log(JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).fps)' "$props")"
  IFS=',' read -r -a times <<<"$stills"
  for t in "${times[@]}"; do
    frame="$(node -e 'console.log(Math.round(Number(process.argv[1]) * Number(process.argv[2])))' "$t" "$fps")"
    npx remotion still src/index.ts "$composition" "$out/still_${t}s.${image_format}" "${common[@]}" --frame="$frame" --image-format="$image_format"
    echo "still $t s (frame $frame) -> $out/still_${t}s.${image_format}"
  done
  exit 0
fi

mkdir -p "$(dirname "$out")"
render_args=(--muted --color-space=bt709 --codec=h264 --crf="$crf" --x264-preset=medium --pixel-format=yuv420p --concurrency="$concurrency")
[[ -n "$frames" ]] && render_args+=(--frames="$frames")
start=$(date +%s)
npx remotion render src/index.ts "$composition" "$out" "${common[@]}" "${render_args[@]}"
echo "rendered $out in $(( $(date +%s) - start )) s"
