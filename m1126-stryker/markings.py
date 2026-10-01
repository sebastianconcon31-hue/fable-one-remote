"""The Stryker's paint maps (see modelkit/paintmaps.py for what each image
holds): the armour tiles' bolts, bumper codes and vehicle number, the ramp's
stencils, non-skid on the roof (the "walk" channel), mud thrown up by the
wheels (the "oil" channel) and exhaust soot down the right side - seen from
the left, right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from stryker import *

RES = 0.002
Z0, Z1 = REAR_Z - 0.15, FRONT_Z + 0.15
Y0, Y1 = -0.05, SPEC["height"] + 0.15
X0, X1 = -1.5, 1.5

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
UNIT, CALLSIGN = "1-23IN", "C-21"


def mud(v, a0, a1, top, n=300, strength=230, along=0.0):
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.1, top)
        r = v.rng.uniform(0.015, 0.09) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.008))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.6, top, 50, top * 0.45, 0.02, 130, drift=along)


def tile_bolts(v, z0, z1, y0, y1):
    """Four bolts in each tile's corners."""
    for z in np.arange(z0, z1, 0.44):
        for yy in (y0, y1):
            for dz in (-0.17, 0.17):
                x, y = v.px(z + dz, yy)
                r = v.mpx(0.012)
                v.d["rivet"].ellipse((x - r, y - r, x + r, y + r), fill=255)


def side(v, sx):
    left = sx > 0
    tile_bolts(v, RAMP_Z + 0.32, GLACIS_TOP_Z - 0.05, SHELF_Y + 0.08, 1.59)
    v.text(CALLSIGN, -0.5, 1.33, 0.1)
    v.text("CAUTION  STAND CLEAR OF WEAPON STATION", 0.9, 1.56, 0.02) if not left else None
    for za in AXLES_Z:
        mud(v, za + 0.75, za - 0.9, 1.5, n=280, strength=255, along=-0.05 if left else 0.05)
    mud(v, FRONT_Z, REAR_Z, 1.2, n=500, strength=200)
    if not left:
        v.blob("soot", [(1.85, 1.42), (2.35, 1.42), (2.35, 1.62), (1.85, 1.62)], 220)
        v.streaks("soot", 1.85, 2.3, 1.42, 1.62, 70, 2.2, 0.05, 170, drift=0.04, down=False)


def top(v):
    for sx in (1, -1):
        v.blob("walk", [(sx * 0.12, -0.9), (sx * 0.95, -0.9), (sx * 0.95, RAMP_Z + 0.15), (sx * 0.12, RAMP_Z + 0.15)], 130)
    v.line([(-1.06, GLACIS_TOP_Z), (1.06, GLACIS_TOP_Z)], rivets=True, pitch=0.09, offset=0.012)
    v.line([(-1.06, 0.95 - 0.5), (1.06, 0.95 - 0.5)], rivets=False, width=0.0016)
    v.text(CALLSIGN, 0.0, -0.4, 0.18)
    for k in range(3):
        z = GLACIS_TOP_Z + 0.3 + k * 0.42
        for x in (-0.66, -0.22, 0.22, 0.66):
            for dx in (-0.17, 0.17):
                for dz in (-0.16, 0.16):
                    px, py = v.px(x + dx, z + dz)
                    r = v.mpx(0.012)
                    v.d["rivet"].ellipse((px - r, py - r, px + r, py + r), fill=255)
    for c in ((0.6, 1.62), (-0.3, 0.3), (0.45, -1.75), (-0.45, -1.75)):
        for _ in range(30):
            a = c[0] + v.rng.uniform(-0.45, 0.45)
            b = c[1] + v.rng.uniform(-0.45, 0.45)
            x, y = v.px(a, b)
            r = v.mpx(v.rng.uniform(0.02, 0.08))
            v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(40, 110)))
    v.streaks("soot", -1.3, -1.0, 2.3, 1.8, 30, 1.5, 0.06, 120, drift=0.0, down=True)


def front(v):
    v.text(UNIT, 0.75, NOSE_TOP_Y - 0.06, 0.06)
    v.text(CALLSIGN, -0.75, NOSE_TOP_Y - 0.06, 0.06)
    mud(v, -1.36, 1.36, 1.2, n=500, strength=250)


def back(v):
    v.text(UNIT, 1.1, 1.05, 0.06)
    v.text(CALLSIGN, -1.1, 1.05, 0.06)
    v.text("CAUTION  STAND CLEAR OF RAMP", 0.0, 1.9, 0.035)
    mud(v, -1.36, 1.36, 1.3, n=520, strength=250)


def bottom(v):
    for _ in range(700):
        a = v.rng.uniform(-1.36, 1.36)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=81)
