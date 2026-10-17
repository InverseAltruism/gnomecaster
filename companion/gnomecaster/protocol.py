"""The screenshot channel: decoding requests the addon draws into screenshots.

Layout (protocol v1), drawn by addon/Gnomecaster/Beacon.lua:
  row 0      : marker M M C C Y Y M M (magenta, cyan, yellow) at both ends, off cells between;
               the distance between the two markers gives the cell size
  rows 1..n  : data, 3 bits per cell (red, green, blue on/off), GRID_W cells per row
  data bytes : MAGIC, version, length (2 bytes), adler32 (4 bytes), JSON payload
The levels a channel has when off and on are not fixed: the addon draws a dim plate or the
classic full-intensity one, and the game's gamma and brightness move both. Every channel is
on and off somewhere in the marker, so the decoder measures the two levels there and splits
each channel at their midpoint. The plate may be anywhere in the screenshot.
The constants below must match the addon; tests/test_contract.py compares them.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import zlib

GRID_W = 96
NUM_SLOTS = 20
PROTOCOL = 1
MAGIC = b"GC"                       # first two bytes of every packet
MARKER = [5, 5, 3, 3, 6, 6, 5, 5]   # colour index = r*4 + g*2 + b
HEADER_LEN = 9                      # MAGIC, version, length(2), adler32(4)
SCREENSHOT_EXT = {".png", ".jpg", ".jpeg", ".tga"}

SPAN = GRID_W - len(MARKER)         # cells from the start of one marker to the start of the other
ROW0 = MARKER + [0] * (SPAN - len(MARKER)) + MARKER
MARGIN = 8                          # of 255: the least difference that counts (lowest channel, on vs off)
# The search runs on one byte per pixel: 1 where green is clearly the lowest channel (magenta),
# 2 for red (cyan), 3 for blue (yellow), else 0. A marker is then a byte pattern: four runs of
# two cells each, with up to 3 blended pixels between them. Positions are taken from the
# boundaries inside a marker, never from its outer edges, which can merge with what is next to it.
# Every run is matched whole (the lookarounds), so a large area of one class costs one attempt
# per run instead of backtracking through it.
_RUNS = (rb"(?<!\x01)(\x01{3,64})(?!\x01)[^\x01\x02]{0,3}(\x02{3,64})(?!\x02)[^\x02\x03]{0,3}"
         rb"(\x03{3,64})(?!\x03)[^\x03\x01]{0,3}(\x01{3,64})(?!\x01)")
_MARKER = re.compile(_RUNS, re.S)
_MARKER_LEN = 4 * 64 + 9            # the longest match of _RUNS
# Row 0 has 80 off cells after the left marker. JPEG ringing can break them up next to the
# marker, so a clean stretch of _OFF_RUN must only start within _REACH pixels of it.
_OFF_RUN = b"\x00" * 16
_REACH = 120
_NOT_OFF = re.compile(rb"[^\x00]")


def require_pillow():
    try:
        from PIL import Image
    except ImportError:
        requirements = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
        sys.exit(f'Pillow is missing. Install it with:  "{sys.executable}" -m pip install -r "{requirements}"')
    return Image


def _hue_mask(img) -> bytes:
    """One byte per pixel, row by row: which channel is clearly the lowest (see _RUNS). Each
    row ends with an extra 0, so no run or lookaround reaches into the next row: the mask is
    img.width + 1 bytes per row."""
    from PIL import Image, ImageChops
    padded = Image.new("RGB", (img.width + 1, img.height))
    padded.paste(img, (0, 0))
    r, g, b = padded.split()
    mask = None
    for value, low, one, two in ((1, g, r, b), (2, r, g, b), (3, b, r, g)):
        gap = ImageChops.subtract(ImageChops.darker(one, two), low)
        part = gap.point([0] * (MARGIN + 1) + [value] * (255 - MARGIN))
        mask = part if mask is None else ImageChops.add(mask, part)
    return mask.tobytes()


def _cls(p, levels) -> int:
    return (4 if p[0] >= levels[0] else 0) | (2 if p[1] >= levels[1] else 0) | (1 if p[2] >= levels[2] else 0)


def _calibrate(samples):
    """Per channel, the midpoint between its off and on levels measured in row 0. Off is the
    median of the off cells, most of which are the uniform stretch between the markers. On
    is the upper quartile of the marker cells where the channel is on: those are two cells
    wide, and blur or JPEG pulls them towards their neighbours. None unless the levels are
    clearly apart and every cell of row 0 reads as drawn."""
    levels = []
    for k in range(3):
        on = sorted(p[k] for p, want in samples if want >> (2 - k) & 1)
        off = sorted(p[k] for p, want in samples if not want >> (2 - k) & 1)
        low, high = off[len(off) // 2], on[3 * len(on) // 4]
        if high - low < MARGIN:
            return None
        levels.append((low + high) / 2)
    if any(_cls(p, levels) != want for p, want in samples):
        return None
    return tuple(levels)


def _left_markers(mask: bytes, stride: int):
    """Matches of _RUNS that a stretch of off pixels follows in the same row. The stretches
    are found with bytes.find, so the pixel-by-pixel work stays in C."""
    pos = mask.find(_OFF_RUN)
    while pos != -1:
        start = max(pos - pos % stride, pos - _REACH - _MARKER_LEN)
        m = _MARKER.search(mask, start, pos) if mask.find(b"\x01", start, pos) != -1 else None
        while m:
            if pos - m.end() <= _REACH:
                yield m
            # matches may overlap: noise next to the plate can borrow the marker's first run
            m = _MARKER.search(mask, m.start(2), pos)
        nxt = _NOT_OFF.search(mask, pos + len(_OFF_RUN))
        if not nxt:
            return
        pos = mask.find(_OFF_RUN, nxt.start())


def _marker_at(mask: bytes, row: int, w: int, lo: int, hi: int):
    """The match of _RUNS in the row starting at `row` whose cyan run starts at x lo to hi."""
    end = row + min(w, hi + 3 * 64 + 6)
    m = _MARKER.search(mask, row + max(0, lo - 64 - 3), end)
    while m and m.start(2) - row <= hi:
        if m.start(2) - row >= lo:
            return m
        m = _MARKER.search(mask, m.start(2), end)
    return None


def find_markers(img):
    """Yield (x, y, cell_size, levels) for each place that looks like a beacon's first row.
    A candidate needs the marker at both ends of row 0 and off cells between, so noise can't
    fake one; `levels` are the channel thresholds measured from its marker."""
    w, h = img.size
    mask, stride = _hue_mask(img), w + 1
    px = img.load()
    seen = []                                       # (x, first row, last row) of marker rows tried
    for m in _left_markers(mask, stride):
        y, inner = divmod(m.start(2), stride)      # inner: where cyan starts, two cells in
        if any(abs(inner - sx) <= 4 and top <= y <= bottom + 1 for sx, top, bottom in seen):
            continue
        rough = (m.end(4) - m.start(2)) / 6
        if not all(rough < m.end(i) - m.start(i) < 3 * rough for i in (2, 3, 4)):
            continue                                # each run is two cells long
        # the marker row's height: down from here while magenta, cyan and yellow stay in place
        probes = [(int(inner + (i - 1.5) * rough), i // 2 + 1) for i in (0, 2, 4)]
        rows = 0
        while y + rows < h and rows < 64 and all(mask[(y + rows) * stride + cx] == v for cx, v in probes):
            rows += 1
        seen.append((inner, y, y + rows))
        if rows == 0 or rows > 1.5 * rough + 2:
            continue
        cy = int(y + rows / 2)                      # the middle row; the first may be blended
        row = cy * stride
        left = _marker_at(mask, row, w, inner - 3, inner + 3)
        if not left:
            continue
        inner = left.start(2) - row
        # the same marker ends row 0; the distance between the two gives the exact size
        right = _marker_at(mask, row, w, inner + int(SPAN * (rough - 0.6)) - 2, inner + int(SPAN * (rough + 0.6)) + 2)
        if not right:
            continue
        cell = (right.start(2) - row - inner) / SPAN
        if not 0.75 * rough <= cell <= 1.25 * rough:
            continue
        x = inner - 2 * cell
        if x < -0.5 or x + GRID_W * cell > w + 0.5:
            continue
        levels = _calibrate([(px[int(x + (i + 0.5) * cell), cy], want) for i, want in enumerate(ROW0)])
        if levels is None:
            continue
        yield max(0.0, x), cy + 0.5 - cell / 2, cell, levels


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
    for x0, y0, cell, levels in find_markers(img):
        try:
            packet = _decode_at(px, w, h, x0, y0, cell, levels)
        except ValueError as e:
            problem = problem or e
            continue
        if packet is not None:
            return packet
    if problem:
        raise problem
    return None


def _decode_at(px, w, h, x0, y0, cell, levels):
    def read(n):
        cells = []
        for i in range(n):
            r, c = 1 + i // GRID_W, i % GRID_W
            x, y = int(x0 + (c + 0.5) * cell), int(y0 + (r + 0.5) * cell)
            if x >= w or y >= h:
                raise ValueError("beacon is cut off at the screen edge")
            cells.append(_cls(px[x, y], levels))
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
