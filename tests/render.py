"""Turn a beacon dump (wowmock.lua DumpBeacon) into a fake WoW screenshot.

usage: render.py <dump> <out> [jpeg quality|-] [scale] [gamma] [brightness]

The picture passes through what the game and the screenshot may do to it: a gamma curve
(each channel v -> v ** gamma, on 0..1), a brightness offset (added after the curve), a
resize and JPEG compression.
"""
import random
import sys

from PIL import Image, ImageDraw


def read_dump(path):
    with open(path) as f:
        size = tuple(map(int, f.readline().split()))
        rects, texts = [], []
        for line in f:
            kind, rest = line.rstrip("\n").split(" ", 1)
            if kind == "rect":
                x, y, w, h, r, g, b = map(float, rest.split())
                rects.append(((x, y, w, h), (r, g, b)))
            elif kind == "text":
                x, y, r, g, b, text = rest.split(" ", 5)
                texts.append(((float(x), float(y)), (float(r), float(g), float(b)), text))
    return size, rects, texts


def background(size, seed=7):
    """A noisy "game world" in 4 px blocks, with some magenta specks to tempt the decoder."""
    rnd = random.Random(seed)
    bw, bh = -(-size[0] // 4), -(-size[1] // 4)
    data = bytearray(rnd.randbytes(bw * bh * 3))
    for i in rnd.sample(range(bw * bh), bw * bh // 100):
        data[3 * i:3 * i + 3] = b"\xff\x00\xff"
    return Image.frombytes("RGB", (bw, bh), bytes(data)).resize((bw * 4, bh * 4), Image.NEAREST).crop((0, 0) + size)


def draw(img, rects, texts):
    d = ImageDraw.Draw(img)
    for (x, y, w, h), colour in rects:
        d.rectangle([round(x), round(y), round(x + w) - 1, round(y + h) - 1],
                    fill=tuple(round(c * 255) for c in colour))
    for (x, y), colour, text in texts:
        d.text((round(x), round(y)), text, fill=tuple(round(c * 255) for c in colour))
    return img


def tone(img, gamma=1.0, brightness=0.0):
    if gamma == 1.0 and brightness == 0.0:
        return img
    lut = [max(0, min(255, round(255 * ((v / 255) ** gamma + brightness)))) for v in range(256)]
    return img.point(lut * 3)


def finish(img, out_path, jpeg=None, scale=1.0, gamma=1.0, brightness=0.0):
    img = tone(img, gamma, brightness)
    if scale != 1.0:
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.BILINEAR)
    if jpeg:
        img.save(out_path, "JPEG", quality=jpeg)
    else:
        img.save(out_path, "PNG", compress_level=1)     # lossless at any level; 1 is fastest


def render(dump_path, out_path, jpeg=None, scale=1.0, gamma=1.0, brightness=0.0, seed=7):
    size, rects, texts = read_dump(dump_path)
    finish(draw(background(size, seed), rects, texts), out_path, jpeg, scale, gamma, brightness)


if __name__ == "__main__":
    args = sys.argv[1:]
    jpeg = int(args[2]) if len(args) > 2 and args[2] != "-" else None
    scale = float(args[3]) if len(args) > 3 else 1.0
    gamma = float(args[4]) if len(args) > 4 else 1.0
    brightness = float(args[5]) if len(args) > 5 else 0.0
    render(args[0], args[1], jpeg, scale, gamma, brightness)
