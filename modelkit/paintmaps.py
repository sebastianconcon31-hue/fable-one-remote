"""Paint maps: a model seen from its sides, top, bottom and ends, drawn at a
couple of millimetres a pixel. paint.py projects them onto the skin.

Two images per view:
  lines  R panel-line grooves, G grime halo round them, B rivets, A per-panel paint variation (0.5 = none)
  marks  R stencils (paint), G walkway non-skid, B stains (oil, or mud), A soot
Draw each view so its text reads correctly from where you'd stand to see it."""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_NARROW = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class View:
    """One paint view: spec = dict(u=(axis, u0, u1), v=(axis, v0, v1)) places it in model space; res is metres per pixel."""

    def __init__(self, name, seed, spec, res):
        self.name = name
        self.res = res
        self.ua, self.u0, self.u1 = spec["u"]
        self.va, self.v0, self.v1 = spec["v"]
        self.w = int(round(abs(self.u1 - self.u0) / res))
        self.h = int(round(abs(self.v1 - self.v0) / res))
        self.layers = {k: Image.new("L", (self.w, self.h), 0) for k in ("line", "rivet", "mark", "walk", "oil", "soot")}
        self.tint = Image.new("L", (self.w, self.h), 128)
        self.d = {k: ImageDraw.Draw(v) for k, v in self.layers.items()}
        self.dt = ImageDraw.Draw(self.tint)
        self.rng = np.random.default_rng(seed)

    def px(self, a, b):
        """Model coordinates along the view's u and v axes -> pixel."""
        x = (a - self.u0) / (self.u1 - self.u0) * self.w
        y = (1 - (b - self.v0) / (self.v1 - self.v0)) * self.h
        return (x, y)

    def mpx(self, metres):
        return metres / self.res

    # --- drawing primitives, all in model metres ---
    def line(self, pts, width=0.0022, rivets=True, pitch=0.035, offset=0.011, groove=True):
        P = [self.px(*p) for p in pts]
        if groove:
            self.d["line"].line(P, fill=255, width=max(1, int(round(self.mpx(width)))), joint="curve")
        if rivets:
            self.rivet_row(pts, pitch, offset)

    def rivet_row(self, pts, pitch=0.035, offset=0.011, r=0.0022):
        pts = [np.asarray(p, float) for p in pts]
        acc = 0.0
        for a, b in zip(pts, pts[1:]):
            seg = b - a
            L = np.linalg.norm(seg)
            if L < 1e-6:
                continue
            t = seg / L
            n = np.array([-t[1], t[0]])
            s = (pitch - acc) % pitch
            while s < L:
                for side in ((1,) if offset == 0 else (1, -1)):
                    c = a + t * s + n * offset * side
                    x, y = self.px(*c)
                    rr = self.mpx(r)
                    self.d["rivet"].ellipse((x - rr, y - rr, x + rr, y + rr), fill=255)
                s += pitch
            acc = (acc + L) % pitch

    def panel(self, pts, tint=None, rivets=True, radius=0.02, width=0.0022, pitch=0.035):
        """A closed panel outline, filled with its own shade of paint."""
        loop = rounded(pts, radius)
        P = [self.px(*p) for p in loop]
        v = int(128 + (tint if tint is not None else self.rng.normal(0, 22)))
        self.dt.polygon(P, fill=max(0, min(255, v)))
        self.line(loop + [loop[0]], width, rivets, pitch)

    def rect(self, a0, a1, b0, b1, **kw):
        self.panel([(a0, b0), (a1, b0), (a1, b1), (a0, b1)], **kw)

    def latch(self, a, b, w=0.05, h=0.02):
        P0, P1 = self.px(a - w / 2, b + h / 2), self.px(a + w / 2, b - h / 2)
        box = (min(P0[0], P1[0]), min(P0[1], P1[1]), max(P0[0], P1[0]), max(P0[1], P1[1]))
        self.d["line"].rectangle(box, outline=255, width=max(1, int(self.mpx(0.0018))))

    def text(self, s, a, b, height, font=FONT, layer="mark", squeeze=0.9, angle=0.0):
        """Text centred on (a, b), cap height `height` metres."""
        size = max(8, int(self.mpx(height) * 1.38))
        f = ImageFont.truetype(font, size)
        l, t, r, bt = f.getbbox(s)
        tw, th = r - l, bt - t
        img = Image.new("L", (tw + 8, th + 8), 0)
        ImageDraw.Draw(img).text((4 - l, 4 - t), s, font=f, fill=255)
        img = img.resize((max(1, int(img.width * squeeze)), img.height), Image.LANCZOS)
        if angle:
            img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
        x, y = self.px(a, b)
        self.layers[layer].paste(255, (int(x - img.width / 2), int(y - img.height / 2)), img)

    def blob(self, layer, pts, value=255):
        self.d[layer].polygon([self.px(*p) for p in pts], fill=value)

    def streaks(self, layer, a0, a1, b0, b1, n, length, width, strength=255, drift=0.0, down=True):
        """Streaks starting in the box and running along -b (down) or +a, for stains and soot."""
        for _ in range(n):
            a = self.rng.uniform(min(a0, a1), max(a0, a1))
            b = self.rng.uniform(min(b0, b1), max(b0, b1))
            L = length * self.rng.uniform(0.4, 1.2)
            w = abs(width) * self.rng.uniform(0.5, 1.5)
            steps = 12
            pts = []
            for k in range(steps + 1):
                t = k / steps
                if down:
                    pts.append((a + drift * t * L, b - t * L))
                else:
                    pts.append((a + t * L, b + drift * t * L))
            val = int(strength * self.rng.uniform(0.4, 1.0))
            for k in range(steps):
                fade = 1 - k / steps
                self.d[layer].line([self.px(*pts[k]), self.px(*pts[k + 1])], fill=int(val * fade), width=max(1, int(self.mpx(w) * (0.6 + 0.4 * fade))))

    def save(self, out):
        line = self.layers["line"]
        halo = line.filter(ImageFilter.GaussianBlur(self.mpx(0.006)))
        halo = Image.eval(halo, lambda v: min(255, int(v * 2.2)))
        rivet = self.layers["rivet"].filter(ImageFilter.GaussianBlur(0.6))
        line_s = line.filter(ImageFilter.GaussianBlur(0.5))
        Image.merge("RGBA", (line_s, halo, rivet, self.tint.filter(ImageFilter.GaussianBlur(1.0)))).save(os.path.join(out, f"paint_{self.name}_lines.png"), optimize=False)
        soot = self.layers["soot"].filter(ImageFilter.GaussianBlur(self.mpx(0.03)))
        oil = self.layers["oil"].filter(ImageFilter.GaussianBlur(self.mpx(0.006)))
        walk = self.layers["walk"].filter(ImageFilter.GaussianBlur(1.0))
        mark = self.layers["mark"].filter(ImageFilter.GaussianBlur(0.5))
        Image.merge("RGBA", (mark, walk, oil, soot)).save(os.path.join(out, f"paint_{self.name}_marks.png"), optimize=False)


def rounded(pts, r, n=4):
    if r <= 0:
        return [tuple(p) for p in pts]
    from geom import fillet_path
    return [tuple(p) for p in fillet_path(pts, [r] * len(pts), arc_n=n, seg_n=0, closed=True)]


def noise_field(w, h, scale_px, rng, octaves=3):
    """Smooth random field 0..1 at the given feature size, built from blurred white noise."""
    acc = np.zeros((h, w), np.float32)
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        s = max(2, int(scale_px / (2**o)))
        small = rng.random((max(2, h // s + 2), max(2, w // s + 2))).astype(np.float32)
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += np.asarray(img, np.float32) / 255 * amp
        tot += amp
        amp *= 0.5
    return acc / tot


def draw_views(out, specs, drawers, res, seed=11):
    """Draw every view (drawers: {name: fn(view)}), break stains and soot up so they read as deposits,
    wear the stencils at their edges, and save the images."""
    os.makedirs(out, exist_ok=True)
    made = {}
    for k, name in enumerate(drawers):
        v = View(name, seed + k, specs[name], res)
        drawers[name](v)
        n = noise_field(v.w, v.h, v.mpx(0.25), v.rng)
        for layer in ("soot", "oil"):
            a = np.asarray(v.layers[layer], np.float32) * (0.45 + 0.9 * n)
            v.layers[layer] = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        wear = noise_field(v.w, v.h, v.mpx(0.02), v.rng, 2)
        a = np.asarray(v.layers["mark"], np.float32) * np.clip((wear - 0.18) * 3, 0, 1)
        v.layers["mark"] = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        v.save(out)
        made[name] = (v.w, v.h)
    return made
