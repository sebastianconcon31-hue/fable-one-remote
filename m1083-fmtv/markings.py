"""The FMTV's paint maps (see modelkit/paintmaps.py for what each image
holds): cab seams, the registration and bumper codes, the body's stencils,
yellow and black hazard stripes on the bumpers (the "walk" channel), mud
thrown up by the wheels (the "oil" channel) and soot round the exhaust -
seen from the left, right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from fmtv import *

RES = 0.002
Z0, Z1 = REAR_Z - 0.15, FRONT_Z + 0.15
Y0, Y1 = -0.05, SPEC["height"] + 0.15
X0, X1 = -1.6, 1.6

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
REGISTRATION = "NL 07 2265"
BUMPER = ("2-3BSB", "A-14")


def hazard(v, a0, a1, b0, b1, stripe=0.05):
    v.blob("walk", [(a0, b0), (a1, b0), (a1, b1), (a0, b1)])
    lo, hi = min(a0, a1), max(a0, a1)
    blo, bhi = min(b0, b1), max(b0, b1)
    span = (hi - lo) + (bhi - blo)
    t, k = -span, 0
    while t < span:
        if k % 2 == 0:
            quad = [(lo + t, blo), (lo + t + stripe, blo), (lo + t + stripe + (bhi - blo), bhi), (lo + t + (bhi - blo), bhi)]
            v.blob("mark", [(min(max(a, lo), hi), b) for a, b in quad])
        t += stripe
        k += 1


def mud(v, a0, a1, top, n=200, strength=230, along=0.0):
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.12, top)
        r = v.rng.uniform(0.015, 0.08) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.008))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.5, top, 40, top * 0.45, 0.02, 120, drift=along)


def side(v, sx):
    left = sx > 0
    zc = (CAB_BACK_Z + 1.3 + CAB_BACK_Z + 0.08) / 2
    v.text(REGISTRATION, zc, 1.62, 0.05)
    v.text("MAX SPEED 58 MPH", zc, 1.5, 0.02)
    v.line([(CAB_FRONT_Z - 0.05, 1.36), (CAB_BACK_Z + 0.05, 1.36)], rivets=False, width=0.0016)
    for z in np.arange(BED_FRONT_Z - 0.55, BED_REAR_Z, -0.55):
        v.line([(z, BED_FLOOR_Y + 0.03), (z, BED_FLOOR_Y + BED_SIDE_H - 0.06)], rivets=False, width=0.0015)
    v.text("TROOP SEATS  12 PERSONNEL", (BED_FRONT_Z + BED_REAR_Z) / 2, BED_FLOOR_Y + 0.12, 0.022)
    v.text("CTIS  HWY 60 / XC 30 / MSS 12 PSI", -0.9, BED_FLOOR_Y - 0.09, 0.02)
    if left:
        v.text("DIESEL", 0.0, 1.05, 0.05)
    for za in AXLES_Z:
        mud(v, za + 0.75, za - 0.9, 1.4, n=300, strength=255, along=-0.05 if left else 0.05)
    mud(v, FRONT_Z, REAR_Z, 1.1, n=450, strength=200)
    if not left:
        zb = (CAB_BACK_Z + BED_FRONT_Z) / 2
        v.blob("soot", [(zb - 0.15, 2.7), (zb + 0.15, 2.7), (zb + 0.15, 2.9), (zb - 0.15, 2.9)], 200)


def top(v):
    v.line([(-CAB_HALF_W + 0.06, CAB_BACK_Z + 0.5), (CAB_HALF_W - 0.06, CAB_BACK_Z + 0.5)], rivets=False)
    v.text("NO STEP", 0.4, CAB_BACK_Z + 1.2, 0.04)
    for z in np.arange(BED_FRONT_Z - 0.55, BED_REAR_Z, -0.55):
        v.line([(-BED_HALF_IN + 0.05, z), (BED_HALF_IN - 0.05, z)], rivets=True, pitch=0.12, offset=0.012)
    for _ in range(70):
        a = v.rng.uniform(-1.1, 1.1)
        b = v.rng.uniform(BED_REAR_Z + 0.1, BED_FRONT_Z - 0.1)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.04, 0.18))
        v.d["oil"].ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=int(v.rng.uniform(40, 120)))
    v.streaks("soot", -1.05, -0.85, 0.95, 0.85, 30, 0.7, 0.04, 120, drift=0.0, down=True)


def front(v):
    v.text(BUMPER[0], 0.6, 0.86, 0.065)
    v.text(BUMPER[1], -0.6, 0.86, 0.065)
    hazard(v, 1.0, 1.15, 0.7, 1.02)
    hazard(v, -1.15, -1.0, 0.7, 1.02)
    mud(v, -1.2, 1.2, 1.3, n=380, strength=240)


def back(v):
    v.text(BUMPER[0], 0.5, 0.95, 0.055)
    v.text(BUMPER[1], -0.5, 0.95, 0.055)
    hazard(v, 0.96, 1.05, 0.85, 1.05)
    hazard(v, -1.05, -0.96, 0.85, 1.05)
    mud(v, -1.2, 1.2, 1.5, n=420, strength=250)


def bottom(v):
    for _ in range(500):
        a = v.rng.uniform(-1.2, 1.2)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.22))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=101)
