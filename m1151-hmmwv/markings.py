"""The HMMWV's paint maps (see modelkit/paintmaps.py for what each image
holds): the hood's and body's panel seams, the bumper codes and stencils,
mud thrown up by the wheels (the "oil" channel) - seen from the left,
right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from hmmwv import *

RES = 0.0015
Z0, Z1 = REAR_Z - 0.15, FRONT_Z + 0.15
Y0, Y1 = -0.05, 3.0
X0, X1 = -1.35, 1.35

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
UNIT, CALLSIGN = "1-23IN", "HHC-14"


def mud(v, a0, a1, top, n=300, strength=230, along=0.0):
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.1, top)
        r = v.rng.uniform(0.012, 0.07) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.006))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.6, top, 50, top * 0.45, 0.015, 130, drift=along)


def side(v, sx):
    left = sx > 0
    v.line([(HOOD_FRONT_Z - 0.02, 1.08), (HOOD_BACK_Z + 0.02, 1.2)], rivets=False, width=0.0016)
    v.line([(CAB_BACK_Z - 0.03, 0.8), (CAB_BACK_Z - 0.03, 1.58)], rivets=False, width=0.0016)
    v.line([(CAB_BACK_Z - 0.06, 1.3), (REAR_Z + 0.2, 1.3)], rivets=True, pitch=0.08, offset=0.0)
    v.text("NO STEP", 1.75, 1.2, 0.025)
    v.text(CALLSIGN, -1.65, 1.2, 0.07)
    for za in AXLES_Z:
        mud(v, za + 0.65, za - 0.8, 1.25, n=320, strength=255, along=-0.05 if left else 0.05)
    mud(v, FRONT_Z, REAR_Z, 1.0, n=420, strength=210)


def top(v):
    # the hood's centre seam and its latches, the roof's armour plate, dirt on the hood
    v.line([(0.0, HOOD_FRONT_Z - 0.05), (0.0, HOOD_BACK_Z + 0.05)], rivets=False, width=0.0016)
    for sx in (1, -1):
        v.latch(sx * 0.95, HOOD_FRONT_Z - 0.25)
        v.latch(sx * 0.95, HOOD_BACK_Z + 0.2)
    v.rect(-1.0, 1.0, CAB_BACK_Z + 0.05, HOOD_BACK_Z - 0.2, radius=0.03, rivets=True, pitch=0.1)
    v.text("NO STEP", 0.5, 1.7, 0.04)
    for _ in range(60):
        a = v.rng.uniform(-1.0, 1.0)
        b = v.rng.uniform(HOOD_BACK_Z, HOOD_FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.02, 0.1))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(30, 90)))


def front(v):
    v.text(UNIT, 0.82, 0.6, 0.055)
    v.text(CALLSIGN, -0.82, 0.6, 0.055)
    mud(v, -1.15, 1.15, 1.0, n=380, strength=240)


def back(v):
    v.text(UNIT, 0.6, 0.98, 0.05)
    v.text(CALLSIGN, -0.6, 0.98, 0.05)
    v.text("CAUTION  GUNNER IN TURRET", 0.0, 1.4, 0.03)
    mud(v, -1.15, 1.15, 1.1, n=420, strength=250)
    v.streaks("soot", 0.55, 0.8, 0.5, 0.6, 20, 0.3, 0.03, 100, drift=0.0, down=False)


def bottom(v):
    for _ in range(500):
        a = v.rng.uniform(-1.15, 1.15)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.2))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=91)
