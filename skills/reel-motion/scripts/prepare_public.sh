#!/usr/bin/env bash
set -euo pipefail

owned_name=".reel-motion-brand"
marker=".owned-by-reel-motion"

usage() {
  cat <<EOF
usage: prepare_public.sh <public-dir> [brand-dir]

Copies the brand's brand.json, assets/fonts and assets/logos into
<public-dir>/$owned_name/ (fonts/, logos/, brand.json). Nothing else in
<public-dir> is touched. The folder carries a marker file; a folder of that name
without the marker is never overwritten.

brand-dir defaults to \$REEL_BRAND, then to the bundled mailinfra-brand skill.
It must contain brand.json and assets/fonts.
EOF
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") usage >&2; exit 2 ;;
  -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
esac
[[ $# -le 2 ]] || { echo "too many arguments" >&2; usage >&2; exit 2; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
public_dir="$1"
brand_dir="${2:-${REEL_BRAND:-$script_dir/../../mailinfra-brand}}"

[[ -d "$public_dir" ]] || { echo "public dir not found: $public_dir" >&2; exit 2; }
[[ -f "$brand_dir/brand.json" && -d "$brand_dir/assets/fonts" ]] || { echo "brand.json or assets/fonts not found in $brand_dir" >&2; exit 2; }

target="$(cd "$public_dir" && pwd)/$owned_name"
if [[ -e "$target" && ! -f "$target/$marker" ]]; then
  echo "$target exists and was not created by prepare_public.sh; move it away first" >&2
  exit 1
fi

staging="$(mktemp -d "$(dirname "$target")/.reel-motion-brand.tmp.XXXXXX")"
trap 'rm -rf "$staging"' EXIT
cp "$brand_dir/brand.json" "$staging/brand.json"
cp -r "$brand_dir/assets/fonts" "$staging/fonts"
[[ -d "$brand_dir/assets/logos" ]] && cp -r "$brand_dir/assets/logos" "$staging/logos"
touch "$staging/$marker"
chmod 755 "$staging"

if [[ -d "$target" ]] && diff -rq "$staging" "$target" >/dev/null 2>&1; then
  echo "brand assets in $target are up to date"
  exit 0
fi
if [[ -d "$target" ]]; then
  rm -rf "$target"
fi
mv "$staging" "$target"
trap - EXIT
echo "brand assets copied to $target"
