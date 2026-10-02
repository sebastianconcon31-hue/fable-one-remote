"""A sample picture for the helmet display: a green night-vision view with the flight symbology over it, drawn at the
display's 4:3. A game replaces it by rendering its own into the HDU_Display material."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1024, 768
GREEN = (60, 255, 110)


def font(size, bold=False):
    for f in ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(os.path.join("/usr/share/fonts/truetype/dejavu", f), size)
        except OSError:
            pass
    return ImageFont.load_default()


def scene(seed=7):
    """A thermal view: warm ground under a darker sky, a ridge line, noise and scan lines."""
    rng = np.random.default_rng(seed)
    base = np.zeros((H, W))
    for scale, amp in ((220, 0.5), (90, 0.25), (30, 0.15), (9, 0.08)):
        n = rng.random((H // scale + 2, W // scale + 2))
        im = Image.fromarray((n * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        base += np.asarray(im) / 255.0 * amp
    base = (base - base.min()) / (base.max() - base.min())
    y = np.linspace(0, 1, H)[:, None]
    horizon = 0.46 + 0.05 * np.sin(np.linspace(0, 7, W))[None, :] + 0.02 * np.sin(np.linspace(0, 31, W))[None, :]
    ground = (y > horizon).astype(float)
    img = 0.16 + 0.22 * base * (0.4 + 0.6 * ground) + 0.2 * ground * (y - horizon).clip(0, 1) ** 0.6
    img += rng.normal(0, 0.012, (H, W))
    img *= 1 - 0.18 * (np.arange(H)[:, None] % 3 == 0)  # scan lines
    vig = 1 - 0.55 * (((np.arange(W)[None, :] - W / 2) / (W / 2)) ** 2 + ((np.arange(H)[:, None] - H / 2) / (H / 2)) ** 2) ** 1.2
    img = (img * vig).clip(0, 1)
    rgb = np.stack([img * GREEN[0] * 0.5, img * GREEN[1] * 0.95, img * GREEN[2] * 0.55], -1)
    return Image.fromarray(rgb.astype(np.uint8))


def symbology(im):
    d = ImageDraw.Draw(im)
    g = GREEN
    f, fb = font(28), font(34, True)
    cx = W // 2
    # heading tape across the top
    heading = 75
    d.line([(150, 70), (W - 150, 70)], fill=g, width=2)
    for k in range(-30, 31, 5):
        x = cx + k * 11.5
        v = (heading + k) % 360
        d.line([(x, 70), (x, 70 - (22 if k % 10 == 0 else 12))], fill=g, width=2)
        if k % 10 == 0:
            t = f"{v:03d}"
            w = d.textlength(t, font=f)
            d.text((x - w / 2, 18), t, fill=g, font=f)
    d.polygon([(cx, 74), (cx - 10, 94), (cx + 10, 94)], outline=g, fill=None, width=2)
    d.rectangle([cx - 44, 96, cx + 44, 132], outline=g, width=2)
    d.text((cx - 36, 98), f"{heading:03d}", fill=g, font=fb)
    # the horizon and pitch ladder, banked a little
    bank = math.radians(3)
    def rot(x, y):
        return (cx + x * math.cos(bank) - y * math.sin(bank), 384 + x * math.sin(bank) + y * math.cos(bank))
    for pitch in (-10, -5, 0, 5, 10):
        y = -pitch * 14 + 22
        half = 230 if pitch == 0 else 70
        gap = 36 if pitch == 0 else 0
        for s in (-1, 1):
            a = rot(s * half, y)
            b = rot(s * (gap if gap else 14), y)
            d.line([a, b], fill=g, width=3)
        if pitch:
            t = f"{abs(pitch)}"
            p = rot(-half - 28, y - 12)
            d.text(p, t, fill=g, font=f)
    # the line-of-sight reticle
    d.ellipse([cx - 22, 384 - 22, cx + 22, 384 + 22], outline=g, width=2)
    d.line([(cx - 44, 384), (cx - 22, 384)], fill=g, width=2)
    d.line([(cx + 22, 384), (cx + 44, 384)], fill=g, width=2)
    d.line([(cx, 384 + 22), (cx, 384 + 44)], fill=g, width=2)
    # airspeed on the left, altitude on the right, with their ticks
    for side, label, value in ((-1, "KTS", 85), (1, "RAD ALT", 150)):
        x0 = cx + side * 340
        d.line([(x0, 250), (x0, 520)], fill=g, width=2)
        for k in range(-5, 6):
            y = 384 - k * 24
            d.line([(x0, y), (x0 - side * (16 if k % 5 == 0 else 9), y)], fill=g, width=2)
        bx = x0 + side * 12
        d.rectangle([min(bx, bx + side * 112), 364, max(bx, bx + side * 112), 404], outline=g, width=2)
        d.text((bx + (6 if side > 0 else -104), 366), f"{value:03d}", fill=g, font=fb)
        d.text((x0 - (40 if side > 0 else 40), 530), label, fill=g, font=font(22))
    # the lower field: torque, the active sensor, the mode
    d.text((60, 690), "PNVS", fill=g, font=fb)
    d.text((cx - 70, 690), "FLT   TRQ 62", fill=g, font=f)
    d.text((W - 190, 690), "HMD", fill=g, font=f)
    d.rectangle([4, 4, W - 5, H - 5], outline=(30, 120, 60), width=2)
    return im


def draw(path):
    im = symbology(scene())
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(path)
    return path


if __name__ == "__main__":
    import sys
    print(draw(sys.argv[1] if len(sys.argv) > 1 else "display.png"))
