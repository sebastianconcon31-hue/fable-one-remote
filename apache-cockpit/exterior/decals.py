"""Paint maps: the aircraft seen from the left, the right, above and below,
drawn at about 2 mm a pixel. The paint shader projects them onto the skin.

Two images per view:
  lines  R panel-line grooves, G grime halo round them, B rivets, A per-panel paint variation (0.5 = none)
  marks  R stencils (black paint), G walkway non-skid, B oil and hydraulic stains, A exhaust soot
Each view is drawn so its text reads correctly from where you'd stand to see it."""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import airframe as af
from ah64 import TAIL_Z, WING_TIP_X, PYLON_INBOARD_X, PYLON_OUTBOARD_X

RES = 0.0022  # metres per pixel
Z0, Z1 = -13.5, 2.7
Y0, Y1 = -0.7, 2.95
X0, X1 = -2.8, 2.8
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_NARROW = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SERIAL = "05-07015"

# where each view sits in model space (the shader uses the same numbers)
VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
}


class View:
    def __init__(self, name, seed):
        self.name = name
        spec = VIEWS[name]
        self.ua, self.u0, self.u1 = spec["u"]
        self.va, self.v0, self.v1 = spec["v"]
        self.w = int(round(abs(self.u1 - self.u0) / RES))
        self.h = int(round(abs(self.v1 - self.v0) / RES))
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
        return metres / RES

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


# ---- the side views ------------------------------------------------------------------------------------------------------------
def body_extent(z):
    """Top and bottom of the fuselage side at station z (roughly)."""
    L = af.LOWER(z)
    if z < -1.84:
        top = af.AFT_TOP(z)["u"][1] if z > -4.6 else af.AFT_TOP(z)["t"] - 0.05
    elif z <= 0.98:
        top = af.sill_at(z)[1]
    else:
        top = af.NOSE_TOP(z)["k"][1]
    return L["lc"][1] - 0.05, top


def side(v, sx):
    left = sx > 0
    # --- nose ---
    v.line([(1.62, -0.3), (1.62, 0.64)])
    v.rect(2.08, 1.72, 0.02, 0.4, radius=0.03)
    v.latch(1.9, 0.02)
    # --- avionics bay: three big doors hinged along the top, with latches along the bottom ---
    for z0, z1 in ((1.42, 0.52), (0.46, -0.52), (-0.58, -1.72)):
        v.rect(z0, z1, -0.12, 0.5, radius=0.035)
        v.line([(z0 - 0.04, 0.47), (z1 + 0.04, 0.47)], rivets=False, width=0.0015)
        for k in range(3):
            v.latch(z0 + (z1 - z0) * (k + 1) / 4, -0.1)
    # louvred cooling grille on the forward bay
    for i in range(14):
        z = 1.2 - i * 0.018
        v.line([(z, 0.18), (z, 0.34)], rivets=False, width=0.004)
    v.rect(1.215, 0.94, 0.165, 0.355, rivets=False, tint=0, radius=0.01)
    # --- cockpit wall above the bays ---
    v.rect(0.9, 0.08, 0.6, 0.74, radius=0.02, tint=v.rng.normal(0, 12))
    v.rect(-0.5, -1.8, 0.62, 1.08, radius=0.02, tint=v.rng.normal(0, 12))
    # --- centre fuselage: frames, bays below the wing, survival-kit door ---
    for z in (-1.95, -3.35, -4.1):
        b, t = body_extent(z)
        v.line([(z, b), (z, t)])
    v.rect(-2.0, -3.3, -0.3, 0.42, radius=0.03)
    v.rect(-3.42, -4.0, -0.1, 0.45, radius=0.03)
    if left:
        v.rect(-2.25, -3.05, 0.86, 1.24, radius=0.03)
        for k in range(3):
            v.latch(-2.35 - k * 0.3, 0.87)
    else:
        v.rect(-2.2, -2.9, 0.84, 1.2, radius=0.03)
    # --- rotor pylon side panels ---
    v.line([(-1.9, 1.96), (-4.5, 1.96)])
    v.rect(-2.12, -2.78, 2.0, 2.27, radius=0.02)
    v.rect(-2.95, -3.9, 2.0, 2.28, radius=0.02)
    # --- engine nacelle: intake ring, the big cowling door, rear ring ---
    v.line([(-2.12, 1.1), (-2.12, 1.83)])
    v.rect(-2.28, -3.72, 1.14, 1.78, radius=0.06)
    for k in range(4):
        v.latch(-2.45 - k * 0.38, 1.76, 0.06, 0.018)
    v.line([(-2.28, 1.3), (-3.72, 1.3)], rivets=False, width=0.0014)
    v.line([(-3.88, 1.1), (-3.88, 1.82)])
    v.rect(-3.92, -4.02, 1.25, 1.62, radius=0.01)
    v.line([(-4.12, 1.2), (-4.12, 1.7)])
    # --- tail boom: splices, frames (rivet lines), stringers, access panels ---
    for z in np.arange(-4.9, -10.3, -0.55):
        b = af.LOWER(z)["bot"] + 0.02
        t = af.AFT_TOP(z)["t"] - 0.02
        groove = z in (-4.9,) or abs(z + 7.1) < 0.2 or abs(z + 9.3) < 0.2
        v.line([(z, b), (z, t)], groove=groove, pitch=0.03, offset=0.0 if not groove else 0.011)
    zs = np.linspace(-4.7, -10.4, 30)
    v.line([(z, af.AFT_TOP(z)["t"] - 0.1) for z in zs], pitch=0.04)
    v.line([(z, af.LOWER(z)["bot"] + 0.13) for z in zs], pitch=0.04)
    v.line([(z, (af.AFT_TOP(z)["t"] + af.LOWER(z)["bot"]) / 2 + 0.03) for z in zs], groove=False, pitch=0.04, offset=0.0)
    for z0, z1 in ((-5.95, -6.3), (-8.15, -8.45), (-9.9, -10.2)):
        yc = (af.AFT_TOP(z0)["t"] + af.LOWER(z0)["bot"]) / 2
        v.rect(z0, z1, yc - 0.12, yc + 0.1, radius=0.02)
    # --- fin ---
    ys = np.linspace(1.6, 2.62, 12)
    v.line([(af.FIN(y)["le"] - 0.16, y) for y in ys], pitch=0.03)
    v.line([(-12.3, 0.6), (-12.3, 2.12)], pitch=0.03)
    v.line([(-11.3, 2.07), (-12.36, 2.07)])
    v.line([(-11.25, 1.07), (-12.4, 1.07)])
    v.rect(-11.6, -12.12, 2.14, 2.5, radius=0.03)
    v.rect(-11.55, -12.2, 0.52, 0.98, radius=0.02)
    # --- stencils ---
    v.text("U.S. ARMY", -6.35, 1.26, 0.19)
    v.text(SERIAL, -11.78, 1.86, 0.07, squeeze=0.95)
    v.text("DANGER", -11.8, 1.36, 0.035)
    v.text("KEEP CLEAR OF TAIL ROTOR", -11.8, 1.3, 0.022)
    v.text("NO STEP", -3.0, 1.7, 0.03)
    v.text("NO STEP", -2.5, 2.2, 0.025)
    if left:
        v.text("JP-8", -3.1, 0.95, 0.03)
    else:
        v.text("CANOPY JETTISON", -0.8, 0.67, 0.024)
        # rescue arrow pointing at the external canopy jettison handle
        v.blob("mark", [(-0.62, 0.64), (-0.52, 0.66), (-0.52, 0.645), (-0.46, 0.645), (-0.46, 0.635), (-0.52, 0.635), (-0.52, 0.62)])
        v.text("RESCUE", -0.35, 0.64, 0.024)
    v.text("GROUND HERE", -1.7, -0.05, 0.018)
    v.text("JACK POINT", -3.2, -0.2, 0.018)
    v.text("HOIST", -2.9, 2.25, 0.02)
    # --- weathering painted in ---
    # exhaust soot: on the suppressor round the exit, and a plume trailing along the boom
    v.blob("soot", [(-4.35, 1.2), (-4.75, 1.18), (-4.8, 1.62), (-4.4, 1.66)], 210)
    v.streaks("soot", -4.7, -5.2, 1.3, 1.72, 90, -2.4, 0.05, 150, drift=0.02, down=False)
    v.streaks("soot", -5.2, -6.8, 1.4, 1.72, 60, -1.6, 0.04, 70, drift=0.03, down=False)
    # oil and hydraulic weeping below the transmission deck, the nacelle drains and the tail gearbox
    v.streaks("oil", -2.4, -3.7, 1.8, 1.95, 26, 0.7, 0.012, 200, drift=-0.12)
    v.streaks("oil", -2.6, -3.6, 1.05, 1.12, 14, 0.5, 0.01, 180, drift=-0.2)
    v.streaks("oil", -11.7, -12.05, 2.1, 2.2, 10, 0.6, 0.008, 170, drift=-0.05)
    v.streaks("oil", 0.6, -0.2, -0.12, -0.1, 6, 0.2, 0.008, 120, drift=-0.1)


# ---- top and bottom -------------------------------------------------------------------------------------------------------------
def top(v):
    for sx in (1, -1):
        # wings: spars, ribs, root walkway, NO STEP out by the tips
        w = lambda x: af.WING(abs(x))
        xs = np.linspace(0.55, 2.52, 20)
        v.line([(sx * x, w(x)["le"] - 0.2 * w(x)["c"]) for x in xs], pitch=0.03)
        v.line([(sx * x, w(x)["le"] - 0.64 * w(x)["c"]) for x in xs], pitch=0.03)
        for x in (0.95, 1.35, 1.7, 2.05, 2.35):
            v.line([(sx * x, w(x)["le"] - 0.2 * w(x)["c"]), (sx * x, w(x)["le"] - 0.64 * w(x)["c"])], groove=False, offset=0.0, pitch=0.03)
        v.line([(sx * 2.5, w(2.5)["le"] - 0.02), (sx * 2.5, w(2.5)["le"] - w(2.5)["c"] + 0.02)])
        wl = [(sx * 0.6, -2.27), (sx * 1.02, -2.28), (sx * 1.02, -2.95), (sx * 0.6, -2.96)]
        v.blob("walk", wl)
        v.text("NO STEP", sx * 2.2, -2.62, 0.04, angle=0)
        v.text("WALKWAY", sx * 0.81, -2.62, 0.028, angle=90 * sx)
        # nacelle tops: cowling door edges and the rings
        for dx in (-0.24, 0.24):
            v.line([(sx * (0.82 + dx), -2.28), (sx * (0.82 + dx), -3.72)])
        v.line([(sx * 0.55, -2.12), (sx * 1.1, -2.12)])
        v.line([(sx * 0.55, -3.88), (sx * 1.1, -3.88)])
        v.text("NO STEP", sx * 0.82, -3.0, 0.028, angle=90 * sx)
        # stabilator
        xs = np.linspace(0.12, 1.65, 12)
        v.line([(sx * x, -11.52 - 0.08 * x / 1.7 - 0.12) for x in xs], pitch=0.03)
        v.line([(sx * x, -11.52 - 0.08 * x / 1.7 - 0.62) for x in xs], pitch=0.03)
        v.text("NO STEP", sx * 1.0, -11.9, 0.03)
        # avionics bay tops
        v.line([(sx * 0.42, 1.5), (sx * 0.42, -1.9)], pitch=0.035)
        v.rect(sx * 0.44, sx * 0.6, 1.3, 0.2, radius=0.02)
        v.rect(sx * 0.44, sx * 0.6, -0.1, -1.6, radius=0.02)
    # nose top
    v.rect(0.3, -0.3, 1.1, 1.95, radius=0.05)
    v.line([(-0.36, 1.62), (0.36, 1.62)])
    # pylon top and the drive-shaft cover segments
    v.rect(0.22, -0.22, -2.0, -2.5, radius=0.03)
    v.rect(0.22, -0.22, -3.2, -4.3, radius=0.03)
    for z in np.arange(-5.3, -10.4, -0.9):
        v.line([(0.09, z), (-0.09, z)], pitch=0.02)
    v.line([(0.0, -4.8), (0.0, -10.4)], groove=False, offset=0.0, pitch=0.04)
    # soot on top behind the engines
    for sx in (1, -1):
        v.streaks("soot", sx * 0.95, sx * 1.1, -4.55, -4.7, 30, 0.6, 0.05, 160, drift=0, down=True)
    v.streaks("oil", 0.2, -0.2, -2.6, -3.3, 12, 0.3, 0.01, 150, drift=0.0)


def bottom(v):
    # belly: gun bay, forward avionics, fuel cells, the aft equipment bays
    v.rect(0.2, -0.2, 1.9, 1.1, radius=0.03)
    v.rect(0.2, -0.2, 0.95, -0.25, radius=0.03)
    v.rect(0.2, -0.2, -0.4, -1.75, radius=0.03)
    v.rect(0.22, -0.22, -1.95, -3.1, radius=0.03)
    v.rect(0.2, -0.2, -3.25, -4.0, radius=0.03)
    for z in np.arange(-4.4, -10.5, -0.55):
        v.line([(0.08, z), (-0.08, z)], groove=False, offset=0.0, pitch=0.025)
    for sx in (1, -1):
        v.line([(sx * 0.24, 1.9), (sx * 0.24, -3.4)], pitch=0.035)
        # wing undersides
        w = lambda x: af.WING(abs(x))
        xs = np.linspace(0.55, 2.52, 20)
        v.line([(sx * x, w(x)["le"] - 0.2 * w(x)["c"]) for x in xs], pitch=0.03)
        v.line([(sx * x, w(x)["le"] - 0.64 * w(x)["c"]) for x in xs], pitch=0.03)
        xs = np.linspace(0.12, 1.65, 12)
        v.line([(sx * x, -11.52 - 0.08 * x / 1.7 - 0.12) for x in xs], pitch=0.03)
    for z in (0.5, -1.0, -2.5, -3.6):
        x, y = v.px(0.0, z)
        r = v.mpx(0.008)
        v.d["line"].ellipse((x - r, y - r, x + r, y + r), fill=255)
    v.text("NO STEP", 0.0, -8.0, 0.03)
    # grime and fluids collect underneath
    v.streaks("oil", 0.25, -0.25, 0.8, -3.6, 40, 0.5, 0.012, 150, drift=0.0)


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


def draw_all(out):
    os.makedirs(out, exist_ok=True)
    made = {}
    for name, fn, seed in (("left", lambda v: side(v, 1), 11), ("right", lambda v: side(v, -1), 12), ("top", top, 13), ("bottom", bottom, 14)):
        v = View(name, seed)
        fn(v)
        # break the soot and stains up so they read as deposits, not shapes
        n = noise_field(v.w, v.h, v.mpx(0.25), v.rng)
        for k in ("soot", "oil"):
            a = np.asarray(v.layers[k], np.float32) * (0.45 + 0.9 * n)
            v.layers[k] = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        # stencils wear at the edges
        wear = noise_field(v.w, v.h, v.mpx(0.02), v.rng, 2)
        a = np.asarray(v.layers["mark"], np.float32) * np.clip((wear - 0.18) * 3, 0, 1)
        v.layers["mark"] = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        v.save(out)
        made[name] = (v.w, v.h)
    return made


if __name__ == "__main__":
    import sys
    print(draw_all(sys.argv[1] if len(sys.argv) > 1 else "decals"))
