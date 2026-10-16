#!/usr/bin/env bash
# Runs every simulated scenario. Needs: a Lua 5.1 interpreter (LUA=path/to/lua5.1), python3, Pillow.
set -e
LUA="${LUA:-lua5.1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
export WOWPILOT_COMPANION="$HERE/../companion/wowpilot_companion.py"
cp "$HERE"/wowmock.lua "$HERE"/render.py "$HERE"/driver.py "$HERE"/run_tests.lua "$WORK"/
for sc in macro noevents noprobe fontcache secret combat jpeg scaled; do
  rm -rf "$WORK/AddOns" && mkdir -p "$WORK/AddOns" && cp -r "$HERE"/../addon/* "$WORK/AddOns/"
  echo "=== $sc"
  (cd "$WORK" && "$LUA" run_tests.lua "$sc" "$WORK/AddOns" "$WORK") | grep -E "^(PASS|FAIL)|Round trip OK"
done
