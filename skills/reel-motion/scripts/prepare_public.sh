#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: prepare_public.sh <public-dir> [brand-skill-dir]" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
public_dir="$1"
brand_dir="${2:-$script_dir/../../mailinfra-brand}"

if [[ ! -d "$brand_dir/assets/fonts" ]]; then
  echo "brand assets not found in $brand_dir/assets" >&2
  exit 1
fi

mkdir -p "$public_dir/brand"
for sub in fonts logos; do
  rm -rf "$public_dir/brand/$sub"
  cp -r "$brand_dir/assets/$sub" "$public_dir/brand/$sub"
done
echo "brand assets copied to $public_dir/brand"
