"""The screenshot decoder on plates drawn independently of Beacon.lua: anywhere on the screen,
in either palette, next to things that look like parts of a marker."""
import json
import pathlib
import random
import re
import sys
import tempfile
import time
import unittest
import zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "companion"))
sys.path.insert(0, str(HERE))

import render  # noqa: E402
from gnomecaster import protocol  # noqa: E402
from PIL import Image  # noqa: E402

BEACON = (HERE.parent / "addon" / "Gnomecaster" / "Beacon.lua").read_text(encoding="utf-8")


def style(name):
    m = re.search(rf"\b{name} = {{ off = ([\d.]+), on = ([\d.]+)", BEACON)
    return float(m.group(1)), float(m.group(2))


DIM, CLASSIC = style("dim"), style("classic")
GOLD = tuple(float(v) for v in re.search(r"local GOLD = \{ ([\d.]+), ([\d.]+), ([\d.]+) \}", BEACON).groups())
CELL = int(re.search(r"local CELL = (\d+)", BEACON).group(1))


def cells_of(packet):
    payload = json.dumps(packet).encode()
    data = protocol.MAGIC + bytes([protocol.PROTOCOL, len(payload) // 256, len(payload) % 256]) \
        + zlib.adler32(payload).to_bytes(4, "big") + payload
    bits = "".join(f"{b:08b}" for b in data)
    bits += "0" * (-len(bits) % 3)
    cells = [int(bits[i:i + 3], 2) for i in range(0, len(bits), 3)]
    return [protocol.ROW0] + [cells[i:i + protocol.GRID_W] for i in range(0, len(cells), protocol.GRID_W)]


def plate(packet, x0, y0, palette=DIM, framed=True, row0=None):
    """Rectangles (as in a beacon dump) for a plate whose cell grid starts at x0, y0."""
    off, on = palette
    rows = cells_of(packet)
    if row0 is not None:
        rows[0] = row0
    w, h = protocol.GRID_W * CELL, len(rows) * CELL
    rects = []
    if framed:      # gold line, off-level margin of 3 and a caption strip of 15 above
        rects += [((x0 - 4, y0 - 19, w + 8, h + 23), GOLD), ((x0 - 3, y0 - 18, w + 6, h + 21), (off,) * 3)]
    else:
        rects.append(((x0, y0, w, h), (off,) * 3))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v:
                rects.append(((x0 + c * CELL, y0 + r * CELL, CELL, CELL),
                              tuple(on if v >> s & 1 else off for s in (2, 1, 0))))
    texts = [((x0, y0 - 16), GOLD, "Gnomecaster")] if framed else []
    return rects, texts


class Decode(unittest.TestCase):
    packet = {"t": "ask", "rid": 3, "sid": "abc", "text": "where is the auction house " * 20}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)

    def shot(self, rects, texts=(), size=(1920, 1080), background=None, **how):
        img = background.copy() if background is not None else render.background(size)
        path = self.tmp / ("shot.jpg" if how.get("jpeg") else "shot.png")
        render.finish(render.draw(img, rects, list(texts)), path, **how)
        return protocol.decode_image(path)

    def test_a_dim_plate_decodes_anywhere_on_a_4k_screen(self):
        for x, y in ((4, 19), (1777, 905), (3540, 1950), (2001, 3)):
            with self.subTest(at=(x, y)):
                self.assertEqual(self.shot(*plate(self.packet, x, y), size=(3840, 2160)), self.packet)

    def test_both_palettes_decode_framed_or_not(self):
        for palette in (DIM, CLASSIC):
            for framed in (True, False):
                with self.subTest(palette=palette, framed=framed):
                    self.assertEqual(self.shot(*plate(self.packet, 640, 400, palette, framed)), self.packet)

    def test_no_plate_no_request(self):
        self.assertIsNone(self.shot([], size=(3840, 2160)))

    def test_the_frame_alone_is_never_a_marker(self):
        # The plate with its marker drawn in the frame's colours: gold, and the off level.
        fake = [5 if c in protocol.MARKER else 0 for c in protocol.ROW0]
        rects, texts = plate(self.packet, 300, 300, row0=[0] * protocol.GRID_W)
        for i, v in enumerate(fake):
            if v:
                rects.append(((300 + i * CELL, 300, CELL, CELL), GOLD))
        self.assertIsNone(self.shot(rects, texts))

    def test_gold_and_off_mixed_in_any_proportion_read_as_neither_magenta_nor_cyan(self):
        # Blur, scaling and anti-aliased caption text mix the frame's two colours; under any
        # gamma or brightness blue stays the lowest channel, or no channel is lowest.
        for off in (DIM[0], CLASSIC[0]):
            row = [tuple(round(255 * (t / 255 * g + (1 - t / 255) * off)) for g in GOLD) for t in range(256)]
            img = Image.new("RGB", (256, 1))
            img.putdata(row)
            for gamma in (0.5, 0.8, 1.0, 1.5, 2.2):
                for brightness in (-0.1, 0.0, 0.1):
                    mask = protocol._hue_mask(render.tone(img, gamma, brightness))
                    self.assertFalse({1, 2} & set(mask), (off, gamma, brightness))

    def test_things_beside_the_grid_are_ignored(self):
        # magenta, cyan and yellow cells right outside the grid, and a whole decoy marker in
        # the caption strip above it
        off, on = DIM
        rects, texts = plate(self.packet, 500, 500)
        rows = len(cells_of(self.packet))
        for i in range(rows):
            for dx, colour in ((-CELL, (on, off, on)), (protocol.GRID_W * CELL, (off, on, on))):
                rects.append(((500 + dx, 500 + i * CELL, CELL, CELL), colour))
        for i, v in enumerate(protocol.MARKER):
            rects.append(((500 + i * CELL, 485, CELL, CELL), tuple(on if v >> s & 1 else off for s in (2, 1, 0))))
        self.assertEqual(self.shot(rects, texts), self.packet)

    def test_a_decoy_that_borrows_the_markers_first_cells(self):
        # magenta, cyan and yellow blocks directly left of an unframed plate: together with the
        # plate's first magenta cells they look like a marker that overlaps the real one
        rects, _ = plate(self.packet, 400, 200, CLASSIC, framed=False)
        for i, colour in enumerate(((1, 0, 1), (0, 1, 1), (1, 1, 0))):
            rects.append(((400 - 18 + 6 * i, 200, 6, 3), colour))
        self.assertEqual(self.shot(rects), self.packet)

    def test_stray_pixels_just_after_the_left_marker(self):
        # JPEG ringing leaves isolated coloured pixels in the off stretch next to a marker; in
        # every row of row 0, though not on the pixels the decoder samples (cell centres)
        rects, _ = plate(self.packet, 400, 200, CLASSIC, framed=False)
        for y, xs in ((200, (24, 31, 37, 50)), (201, (24, 30, 36, 45)), (202, (26, 33, 39, 52))):
            for x in xs:
                rects.append(((400 + x, y, 1, 1), (0.6, 0.0, 0.5)))
        self.assertEqual(self.shot(rects), self.packet)

    def test_plates_touching_the_left_or_right_screen_edge(self):
        # magenta on the other side of the screen edge: the end of the row above, or the start
        # of the row below, must not count as part of the marker
        w = 1920
        for x, other in ((0, w - 3), (w - protocol.GRID_W * CELL, 0)):
            with self.subTest(x=x):
                rects, _ = plate(self.packet, x, 300, CLASSIC, framed=False)
                rects.append(((other, 298, 3, 7), (1, 0, 1)))
                self.assertEqual(self.shot(rects), self.packet)

    def test_large_areas_of_one_colour_are_scanned_quickly(self):
        # The panel's purple reads as magenta everywhere; dark stripes give the search an off
        # stretch after every 64 pixels of it. Backtracking through the runs took about 15 s
        # of CPU here, matching each run whole about 0.3 s.
        img = Image.new("RGB", (1920, 1080), (90, 40, 150))
        for x in range(0, 1920, 84):
            img.paste((10, 10, 10), (x, 0, x + 20, 1080))
        path = self.tmp / "purple.png"
        img.save(path)
        started = time.process_time()
        self.assertIsNone(protocol.decode_image(path))
        self.assertLess(time.process_time() - started, 5.0)

    def test_purple_touching_a_classic_plate_does_not_hide_it(self):
        # the classic plate is unframed: what is right of row 0 merges with its last magenta
        # run (found by the cross-model review, 2026-10-17; the decoder before the rework read it)
        rects, _ = plate(self.packet, 0, 0, CLASSIC, framed=False)
        purple = Image.new("RGB", (1920, 1080), (90, 40, 150))
        self.assertEqual(self.shot(rects, background=purple), self.packet)

    def test_rows_of_marker_lookalikes_are_scanned_quickly(self):
        # Every row repeats magenta, cyan, yellow, magenta runs after an off stretch: each is a
        # candidate. Checking each against all earlier ones took 109 s of CPU for this image
        # (2026-10-17); against the few above it in the same columns, 0.95 s.
        pattern = [(20, 20, 20)] * 16 + [(200, 20, 200)] * 3 + [(20, 200, 200)] * 3 + [(200, 200, 20)] * 3 + [(200, 20, 200)] * 3
        # wrapped across rows, so each row's candidates sit at new x positions
        img = Image.frombytes("RGB", (1920, 540), (b"".join(bytes(p) for p in pattern) * (1920 * 540 // len(pattern) + 1))[:1920 * 540 * 3])
        path = self.tmp / "stripes.png"
        img.save(path)
        started = time.process_time()
        self.assertIsNone(protocol.decode_image(path))
        self.assertLess(time.process_time() - started, 5.0)

    def test_full_intensity_plates_survive_jpeg(self):
        # The addon asks for PNG; if the game writes JPEG anyway, full intensity is the fallback
        # (/gc beacon classic). Measuring the on level as the mean of the marker cells, which
        # JPEG smears into their neighbours, loses some of these.
        missed = []
        for seed in range(12):
            rnd = random.Random(seed)
            packet = {"t": "ask", "text": "".join(rnd.choice("abcdefghij klmnop") for _ in range(rnd.randrange(200, 1500)))}
            rects, texts = plate(packet, rnd.randrange(8, 400), rnd.randrange(24, 60), CLASSIC)
            try:
                got = self.shot(rects, texts, size=(800, 400), background=render.background((800, 400), seed), jpeg=92)
            except ValueError:
                got = None
            if got != packet:
                missed.append(seed)
        self.assertEqual(missed, [])

    def test_a_plate_cut_off_by_the_screen_edge_is_reported(self):
        rects, texts = plate(self.packet, 700, 1080 - 30, CLASSIC, framed=False)
        with self.assertRaisesRegex(ValueError, "cut off"):
            self.shot(rects, texts)


if __name__ == "__main__":
    unittest.main()
