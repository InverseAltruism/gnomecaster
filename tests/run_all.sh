#!/usr/bin/env bash
# Runs every simulated scenario and the Python unit tests.
# Needs: a Lua 5.1 interpreter (LUA=path/to/lua5.1), python3, Pillow.
# Exits non-zero when any scenario or unit test fails.
set -uo pipefail
LUA="${LUA:-lua5.1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export GNOMECASTER_COMPANION="$HERE/../companion/gnomecaster_companion.py"
# Tests never reach a real model or read the player's own settings.
unset GNOMECASTER_BASE_URL GNOMECASTER_API_KEY GNOMECASTER_MODEL
export GNOMECASTER_CONFIG="$WORK/no-config.json"
export PYTHONDONTWRITEBYTECODE=1

failed=()
cp "$HERE"/wowmock*.lua "$HERE"/wow_api_methods.lua "$HERE"/render.py "$HERE"/driver.py "$HERE"/run_tests.lua "$HERE"/run_places.lua "$WORK"/
for sc in macro noevents noprobe fontcache secret combat jpeg scaled actions ui places conversation; do
	rm -rf "$WORK/AddOns" && mkdir -p "$WORK/AddOns" && cp -r "$HERE"/../addon/* "$WORK/AddOns/"
	echo "=== $sc"
	if ! (cd "$WORK" && "$LUA" run_tests.lua "$sc" "$WORK/AddOns" "$WORK") >"$WORK/$sc.log" 2>&1; then
		failed+=("$sc")
	fi
	grep -E "^(PASS|FAIL)|Round trip OK" "$WORK/$sc.log" || true
	if [[ " ${failed[*]} " == *" $sc "* ]] && ! grep -q "^FAIL" "$WORK/$sc.log"; then
		tail -n 15 "$WORK/$sc.log"
	fi
done

echo "=== python unit tests"
if ! python3 -m unittest discover -s "$HERE" -p 'test_*.py'; then
	failed+=("python")
fi

if [ ${#failed[@]} -gt 0 ]; then
	echo "FAILED: ${failed[*]}"
	exit 1
fi
echo "all suites passed"
