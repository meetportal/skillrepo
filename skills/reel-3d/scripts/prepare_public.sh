#!/usr/bin/env bash
set -euo pipefail

owned_name=".reel-3d-brand"
marker=".owned-by-reel-3d"

usage() {
  cat <<EOF2
usage: prepare_public.sh [brand-dir]

Copies the brand's brand.json, assets/fonts and assets/logos into
remotion/public/$owned_name/ of the reel-3d skill (fonts/, logos/, brand.json).
The folder carries a marker file; a folder of that name without the marker is
never overwritten. Nothing else in public/ is touched.

brand-dir defaults to \$REEL_BRAND, then to the bundled mailinfra-brand skill.
It must contain brand.json, assets/fonts and assets/logos.
EOF2
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "too many arguments" >&2; usage >&2; exit 2; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
public_dir="$script_dir/../remotion/public"
brand_dir="${1:-${REEL_BRAND:-$script_dir/../../mailinfra-brand}}"

mkdir -p "$public_dir"
[[ -f "$brand_dir/brand.json" && -d "$brand_dir/assets/fonts" && -d "$brand_dir/assets/logos" ]] || {
  echo "brand.json, assets/fonts or assets/logos not found in $brand_dir" >&2
  exit 2
}

target="$(cd "$public_dir" && pwd)/$owned_name"
if [[ -e "$target" && ! -f "$target/$marker" ]]; then
  echo "$target exists and was not created by prepare_public.sh; move it away first" >&2
  exit 1
fi

staging="$(mktemp -d "$(dirname "$target")/.reel-3d-brand.tmp.XXXXXX")"
trap 'rm -rf "$staging"' EXIT
cp "$brand_dir/brand.json" "$staging/brand.json"
cp -r "$brand_dir/assets/fonts" "$staging/fonts"
cp -r "$brand_dir/assets/logos" "$staging/logos"
touch "$staging/$marker"
chmod 755 "$staging"

if [[ -d "$target" ]] && diff -rq "$staging" "$target" >/dev/null 2>&1; then
  echo "brand assets in $target are up to date"
  exit 0
fi
[[ -d "$target" ]] && rm -rf "$target"
mv "$staging" "$target"
trap - EXIT
echo "brand assets copied to $target"
