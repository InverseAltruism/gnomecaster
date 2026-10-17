"""Renders one beacon dump the ways a screenshot may come out and decodes each with the
companion's own decoder.

usage: beacon_matrix.py <dump> <expected.json> <label> [--jpeg | --plain]

Conditions: gamma 0.5 to 2.2 with brightness -0.1 to +0.1, and the screenshot scaled by 1.25.
--jpeg adds JPEG quality 92, which only the classic plate is expected to survive; --plain
renders only the untouched screenshot.
Prints one PASS line, or a FAIL line per condition that did not decode; exits 1 on failure.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = pathlib.Path(os.environ.get("GNOMECASTER_COMPANION")
                     or HERE.parent / "companion" / "gnomecaster_companion.py")
sys.path.insert(0, str(ENTRY.parent))
sys.path.insert(0, str(HERE))

import render  # noqa: E402
from gnomecaster import protocol  # noqa: E402

GAMMAS = (0.5, 0.8, 1.0, 1.5, 2.2)
BRIGHTNESS = (-0.1, 0.0, 0.1)


def conditions(jpeg, plain=False):
    if plain:
        yield "no changes", {}
        return
    for g in GAMMAS:
        for b in BRIGHTNESS:
            yield f"gamma {g} brightness {b:+.1f}", {"gamma": g, "brightness": b}
    yield "scaled 1.25", {"scale": 1.25}
    if jpeg:
        yield "JPEG 92", {"jpeg": 92}


def main(dump, expected_path, label, jpeg=False, plain=False):
    expected = json.loads(pathlib.Path(expected_path).read_text(encoding="utf-8"))
    size, rects, texts = render.read_dump(dump)
    failed, n = [], 0
    for name, how in conditions(jpeg, plain):
        n += 1
        out = f"{dump}.{n}.{'jpg' if how.get('jpeg') else 'png'}"
        render.finish(render.draw(render.background(size, seed=n), rects, texts), out, **how)
        try:
            got = protocol.decode_image(out)
        except ValueError as e:
            got = f"error: {e}"
        if got != expected:
            failed.append(f"{name}: {'no beacon found' if got is None else str(got)[:80]}")
    for f in failed:
        print(f"FAIL {label} decodes under {f}")
    if not failed and plain:
        print(f"PASS {label} decodes")
    elif not failed:
        print(f"PASS {label} decodes under all {n} conditions (gamma {GAMMAS[0]}..{GAMMAS[-1]} x brightness "
              f"{BRIGHTNESS[0]:+.1f}..{BRIGHTNESS[-1]:+.1f}, scaled 1.25{', JPEG 92' if jpeg else ''})")
    return 1 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(args[0], args[1], args[2], "--jpeg" in args[3:], "--plain" in args[3:]))
