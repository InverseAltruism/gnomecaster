"""The screenshot channel: decoding requests the addon draws into screenshots.

Layout (protocol v1), drawn by addon/Gnomecaster/Beacon.lua:
  row 0      : marker M M C C Y Y M M (magenta, cyan, yellow) at both ends; the distance
               between the two markers gives the cell size
  rows 1..n  : data, 3 bits per cell (red, green, blue on/off), GRID_W cells per row
  data bytes : MAGIC, version, length (2 bytes), adler32 (4 bytes), JSON payload
The constants below must match the addon; tests/test_contract.py compares them.
"""
from __future__ import annotations

import json
import pathlib
import sys
import zlib

GRID_W = 96
NUM_SLOTS = 60
PROTOCOL = 1
MAGIC = b"GC"                       # first two bytes of every packet
MARKER = [5, 5, 3, 3, 6, 6, 5, 5]   # colour index = r*4 + g*2 + b
HEADER_LEN = 9                      # MAGIC, version, length(2), adler32(4)
SCREENSHOT_EXT = {".png", ".jpg", ".jpeg", ".tga"}


def require_pillow():
    try:
        from PIL import Image
    except ImportError:
        requirements = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
        sys.exit(f'Pillow is missing. Install it with:  "{sys.executable}" -m pip install -r "{requirements}"')
    return Image


def _cls(p) -> int:
    return (4 if p[0] >= 128 else 0) | (2 if p[1] >= 128 else 0) | (1 if p[2] >= 128 else 0)


def _marker_at(px, w, h, x, y, cell) -> bool:
    cy = int(y + cell / 2)
    if cy >= h:
        return False
    for i, want in enumerate(MARKER):
        cx = int(x + (i + 0.5) * cell)
        if cx >= w or _cls(px[cx, cy]) != want:
            return False
    return True


def find_markers(img, limit: int = 640):
    """Yield (x, y, cell_size) for each place that looks like a beacon's first row.
    A candidate needs the marker at both ends of row 0, so noise can't fake one."""
    w, h = img.size
    px = img.load()
    span = GRID_W - len(MARKER)
    for y in range(min(h, limit)):
        for x in range(min(w, limit)):
            if _cls(px[x, y]) != 5:
                continue
            if (x > 0 and _cls(px[x - 1, y]) == 5) or (y > 0 and _cls(px[x, y - 1]) == 5):
                continue
            run = 1
            while x + run < w and run < 64 and _cls(px[x + run, y]) == 5:
                run += 1
            if run < 2:
                continue
            # the run length is only accurate to about a pixel: try nearby cell sizes
            rough = None
            for k in range(-4, 5):
                c = run / 2.0 + k * 0.125
                if c >= 1 and _marker_at(px, w, h, x, y, c):
                    rough = c
                    break
            if rough is None:
                continue
            # the same marker ends row 0; the distance between the two gives the exact size
            cy = int(y + rough / 2)
            lo, hi = int(x + span * (rough - 0.6)), min(w - 1, int(x + span * (rough + 0.6)))
            for x2 in range(max(lo, x + 1), hi):
                if _cls(px[x2, cy]) == 5 and _cls(px[x2 - 1, cy]) != 5:
                    cell = (x2 - x) / span
                    if _marker_at(px, w, h, x2, y, cell):
                        yield x, y, cell
                        break


def _cells_to_bytes(cells, nbytes: int) -> bytes:
    bits = []
    for c in cells:
        bits.extend(((c >> 2) & 1, (c >> 1) & 1, c & 1))
    out = bytearray()
    for i in range(nbytes):
        v = 0
        for b in bits[i * 8:(i + 1) * 8]:
            v = (v << 1) | b
        out.append(v)
    return bytes(out)


def decode_image(path) -> dict | None:
    """Decode a Gnomecaster request from a screenshot. None if there is no beacon."""
    image = require_pillow()
    with image.open(path) as im:
        img = im.convert("RGB")
    px = img.load()
    w, h = img.size
    problem = None
    for x0, y0, cell in find_markers(img):
        try:
            packet = _decode_at(px, w, h, x0, y0, cell)
        except ValueError as e:
            problem = problem or e
            continue
        if packet is not None:
            return packet
    if problem:
        raise problem
    return None


def _decode_at(px, w, h, x0, y0, cell):
    def read(n):
        cells = []
        for i in range(n):
            r, c = 1 + i // GRID_W, i % GRID_W
            x, y = int(x0 + (c + 0.5) * cell), int(y0 + (r + 0.5) * cell)
            if x >= w or y >= h:
                raise ValueError("beacon is cut off at the screen edge")
            cells.append(_cls(px[x, y]))
        return cells

    head = _cells_to_bytes(read(-(-HEADER_LEN * 8 // 3)), HEADER_LEN)
    if head[:2] != MAGIC:
        return None
    if head[2] != PROTOCOL:
        raise ValueError(f"addon speaks protocol {head[2]}, companion speaks {PROTOCOL}")
    length = head[3] * 256 + head[4]
    checksum = int.from_bytes(head[5:9], "big")
    total = HEADER_LEN + length
    data = _cells_to_bytes(read(-(-total * 8 // 3)), total)
    payload = data[HEADER_LEN:]
    if zlib.adler32(payload) != checksum:
        raise ValueError("checksum mismatch (screenshot scaled, filtered or JPEG-compressed?)")
    return json.loads(payload.decode("utf-8", errors="replace"))
