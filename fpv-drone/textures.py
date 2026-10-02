"""The two images the quad uses, drawn in code so the repo holds no binary assets:
a 2x2 twill carbon weave for the frame plates, and a plain, generic label for
the battery. Both are written as PNGs by make(dir)."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WEAVE_SIZE = 512
WEAVE_YARNS = 16  # yarns across one tile (the tile covers 24 mm, so a yarn is 1.5 mm wide: a 3K twill)


def carbon(path):
    n = WEAVE_SIZE
    cell = n // WEAVE_YARNS
    yy, xx = np.mgrid[0:n, 0:n]
    cx, cy = xx // cell, yy // cell
    u = (xx % cell) / cell  # across the cell, 0..1
    v = (yy % cell) / cell
    warp_on_top = ((cx + cy) // 2) % 2 == 0  # 2x2 twill: warp (vertical) yarns over, then weft
    # a yarn is a rounded ridge: bright along its crown, dark at its edges, and dark where it dives under a crossing yarn
    ridge_u = np.sin(np.pi * u) ** 0.6
    ridge_v = np.sin(np.pi * v) ** 0.6
    dive_v = 1.0 - 0.55 * np.clip(1 - np.minimum(v, 1 - v) * 7, 0, 1)
    dive_u = 1.0 - 0.55 * np.clip(1 - np.minimum(u, 1 - u) * 7, 0, 1)
    shade = np.where(warp_on_top, ridge_u * dive_v, ridge_v * dive_u)
    # warp and weft catch the light differently, which is what makes a twill read
    tint = np.where(warp_on_top, 1.0, 0.82)
    grey = 0.03 + 0.17 * shade * tint
    rgb = np.stack([grey * 0.96, grey * 0.99, grey * 1.06], -1)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def battery_label(path, w=1024, h=512):
    """The top of a 6S 1300 mAh pack: a charcoal wrap with a plain generic label. The border is the colour the
    pack's sides use, so the label's edge meets them cleanly."""
    base = (24, 26, 30)
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    m = 34
    d.rounded_rectangle((m, m, w - m, h - m), radius=26, fill=(36, 39, 45))
    d.rectangle((m, h - m - 120, w - m, h - m), fill=(176, 62, 14))  # the orange band along one edge
    d.text((m + 36, m + 28), "LiPo", font=font(120), fill=(235, 235, 232))
    d.text((m + 36, m + 168), "6S  22.2V", font=font(88), fill=(205, 207, 205))
    d.text((m + 36, m + 276), "1300mAh  100C", font=font(66), fill=(150, 154, 156))
    d.text((w - m - 300, h - m - 100), "XT60", font=font(70), fill=(20, 20, 20))
    for i in range(6):  # six cell marks
        x = w - m - 330 + i * 52
        d.rectangle((x, m + 40, x + 36, m + 76), outline=(120, 124, 126), width=3)
    img.save(path)


def make(out):
    os.makedirs(out, exist_ok=True)
    paths = {"carbon": os.path.join(out, "carbon_weave.png"), "battery": os.path.join(out, "battery_label.png")}
    carbon(paths["carbon"])
    battery_label(paths["battery"])
    return paths
