#!/usr/bin/env python3
"""Generates every icon file from the one vector source, assets/brand/gnomecaster-icon.svg.

  python3 tools/make_icons.py           regenerate
  python3 tools/make_icons.py --check   exit 1 if a generated file is out of date

Needs resvg 0.48.1 (`cargo install resvg --version 0.48.1 --locked`) on PATH or in RESVG,
and Pillow. Each size is rendered from the vector source rather than scaled from a large
bitmap, so small icons stay crisp. Outputs:
  assets/brand/png/icon-<size>.png         app, installer and web use
  assets/brand/gnomecaster.ico             Windows (16 to 256 px, each size rendered)
  assets/brand/gnomecaster.icns            macOS
  addon/Gnomecaster/Media/icon.tga         the AddOns list and the panel's title (shown at 16-20 px)
  addon/Gnomecaster/Media/spark.tga        the panel's busy indicator, from spark.svg
  desktop/ui/icon.png                      the desktop app's own interface
  assets/brand/installer/side-<w>.png      the installer's welcome and finish pages, from
                                           installer-side.svg, one per screen scaling
  assets/brand/installer/small-<s>.png     the installer's page header
"""
from __future__ import annotations

import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "brand" / "gnomecaster-icon.svg"
PNG_DIR = ROOT / "assets" / "brand" / "png"
SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 512, 1024]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
GAME_SIZE = 64                      # WoW textures want power-of-two sides
SIDE = ROOT / "assets" / "brand" / "installer-side.svg"
SPARK = ROOT / "assets" / "brand" / "spark.svg"
# Inno Setup's image areas at 100, 125, 150, 175, 200 and 250 % scaling (its WizardImageFile
# and WizardSmallImageFile help pages); Setup picks the file that fits best.
SIDE_SIZES = [(202, 386), (269, 515), (336, 643), (403, 772), (430, 824), (534, 1022)]
SMALL_SIZES = [58, 77, 97, 116, 124, 159]


def resvg() -> str:
    exe = os.environ.get("RESVG") or shutil.which("resvg")
    if not exe:
        sys.exit("resvg not found: cargo install resvg --version 0.48.1 --locked (or set RESVG)")
    return exe


def render(size: int, tmp: pathlib.Path, source: pathlib.Path = SOURCE, height: int | None = None) -> Image.Image:
    out = tmp / f"{source.stem}-{size}.png"
    subprocess.run([resvg(), "-w", str(size), "-h", str(height or size), str(source), str(out)], check=True)
    with Image.open(out) as im:
        return im.convert("RGBA").copy()


def build() -> dict[pathlib.Path, bytes]:
    """Every generated file as bytes, keyed by its path."""
    files: dict[pathlib.Path, bytes] = {}
    with tempfile.TemporaryDirectory() as tmp:
        images = {s: render(s, pathlib.Path(tmp)) for s in sorted(set(SIZES + SMALL_SIZES))}
        sides = {w: render(w, pathlib.Path(tmp), SIDE, h).convert("RGB") for w, h in SIDE_SIZES}
        spark = render(GAME_SIZE // 2, pathlib.Path(tmp), SPARK)

    def encode(image: Image.Image, fmt: str, **kw) -> bytes:
        buf = io.BytesIO()
        image.save(buf, fmt, **kw)
        return buf.getvalue()

    for s in SIZES:
        files[PNG_DIR / f"icon-{s}.png"] = encode(images[s], "PNG", optimize=True)
    largest = images[max(ICO_SIZES)]
    files[ROOT / "assets" / "brand" / "gnomecaster.ico"] = encode(
        largest, "ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=[images[s] for s in ICO_SIZES if s != max(ICO_SIZES)])
    files[ROOT / "assets" / "brand" / "gnomecaster.icns"] = encode(images[1024], "ICNS")
    files[ROOT / "addon" / "Gnomecaster" / "Media" / "icon.tga"] = encode(images[GAME_SIZE], "TGA", compression=None)
    files[ROOT / "desktop" / "ui" / "icon.png"] = encode(images[128], "PNG", optimize=True)
    files[ROOT / "addon" / "Gnomecaster" / "Media" / "spark.tga"] = encode(spark, "TGA", compression=None)
    installer = ROOT / "assets" / "brand" / "installer"
    for w, im in sides.items():
        files[installer / f"side-{w}.png"] = encode(im, "PNG", optimize=True)
    for s in SMALL_SIZES:
        files[installer / f"small-{s}.png"] = encode(images[s], "PNG", optimize=True)
    return files


def main() -> None:
    check = "--check" in sys.argv[1:]
    stale = []
    for path, data in build().items():
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if check:
        if stale:
            sys.exit("out of date: " + ", ".join(map(str, stale)) + " (run tools/make_icons.py)")
        print("icons up to date")
    else:
        print(f"wrote {len(SIZES)} PNGs, gnomecaster.ico, gnomecaster.icns, the game icon and "
              f"{len(SIDE_SIZES) + len(SMALL_SIZES)} installer images")


if __name__ == "__main__":
    main()
