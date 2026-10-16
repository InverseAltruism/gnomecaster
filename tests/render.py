"""Turn a beacon dump (rectangles in physical pixels) into a fake WoW screenshot."""
import random
import sys

from PIL import Image, ImageDraw


def render(dump_path, out_path, jpeg=None, scale=1.0, size=(1920, 1080), seed=7):
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    px = img.load()
    # noisy "game world" background, with some magenta specks to tempt the decoder
    for y in range(0, size[1], 4):
        for x in range(0, size[0], 4):
            c = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
            if rnd.random() < 0.01:
                c = (255, 0, 255)
            for dy in range(4):
                for dx in range(4):
                    px[x + dx, y + dy] = c
    d = ImageDraw.Draw(img)
    with open(dump_path) as f:
        w, h = map(int, f.readline().split())
        d.rectangle([0, 0, w - 1, h - 1], fill=(0, 0, 0))
        for line in f:
            x, y, rw, rh, r, g, b = line.split()
            x, y, rw, rh = float(x), float(y), float(rw), float(rh)
            d.rectangle([round(x), round(y), round(x + rw) - 1, round(y + rh) - 1],
                        fill=(int(r) * 255, int(g) * 255, int(b) * 255))
    if scale != 1.0:
        img = img.resize((int(size[0] * scale), int(size[1] * scale)), Image.BILINEAR)
    if jpeg:
        img.save(out_path, "JPEG", quality=jpeg)
    else:
        img.save(out_path, "PNG")


if __name__ == "__main__":
    args = sys.argv[1:]
    jpeg = int(args[2]) if len(args) > 2 and args[2] != "-" else None
    scale = float(args[3]) if len(args) > 3 else 1.0
    render(args[0], args[1], jpeg, scale)
