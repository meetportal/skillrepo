#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  -h|--help) echo "usage: test_captions.sh   (bundles and runs remotion/src/lib/captionPages.test.ts)"; exit 0 ;;
esac
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$script_dir/../remotion"
[[ -d "$project_dir/node_modules" ]] || (cd "$project_dir" && npm ci --no-audit --no-fund)
out_dir="$(mktemp -d)"
trap 'rm -rf "$out_dir"' EXIT
"$project_dir/node_modules/.bin/esbuild" "$project_dir/src/lib/captionPages.test.ts" --bundle --platform=node --log-level=warning --outfile="$out_dir/test.cjs"
node "$out_dir/test.cjs"
