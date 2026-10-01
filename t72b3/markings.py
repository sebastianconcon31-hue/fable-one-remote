"""The T-72B3's paint maps (see modelkit/paintmaps.py for what each image
holds): weld seams, the white tactical number on the turret and the
stencils (the stencil colour is white here), mud thrown up by the tracks
(the "oil" channel) and exhaust soot along the left side - seen from the
left, right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from t72 import *

RES = 0.002
Z0, Z1 = REAR_Z - 0.15, MUZZLE_Z + 0.15
Y0, Y1 = -0.05, 3.0
X0, X1 = -1.95, 1.95

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
NUMBER = "211"
TZ = TURRET_Z


def mud(v, a0, a1, top, n=300, strength=230, along=0.0):
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.1, top)
        r = v.rng.uniform(0.015, 0.1) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.008))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.6, top, 60, top * 0.5, 0.02, 140, drift=along)


def side(v, sx):
    left = sx > 0
    # the tactical number on the turret's side stowage, and on the fender boxes
    v.text(NUMBER, TZ - 0.6, 1.86, 0.17)
    v.text(NUMBER, -0.65, FENDER_Y + 0.22, 0.12)
    # fender tanks: seams and filler warnings
    for z0, z1 in ((1.93, 0.97), (-1.22, -2.18)):
        v.line([(z0, FENDER_Y + 0.38), (z1, FENDER_Y + 0.38)], rivets=False, width=0.0014)
    v.text("ДТ", 1.45, FENDER_Y + 0.26, 0.06) if not left else None
    # mud, thick on the skirts and the fenders' undersides
    mud(v, FRONT_Z, REAR_Z, 0.95, n=800, strength=255, along=-0.05 if left else 0.05)
    mud(v, FRONT_Z - 0.3, REAR_Z + 0.3, 1.25, n=280, strength=160)
    v.streaks("oil", FRONT_Z - 0.4, REAR_Z + 0.2, 0.7, 0.63, 140, 0.25, 0.03, 160, drift=0.0, down=False)
    if left:  # the exhaust on the left fender blackens the side behind it
        v.blob("soot", [(-1.0, 1.15), (-1.62, 1.15), (-1.62, 1.38), (-1.0, 1.38)], 230)
        v.streaks("soot", -1.6, -1.0, 1.1, 1.4, 90, -2.0, 0.06, 180, drift=0.02, down=False)


def top(v):
    # weld seams of the hull roof and the turret's cast joint lines; dirt and soot
    v.line([(-1.4, GLACIS_TOP_Z), (1.4, GLACIS_TOP_Z)], rivets=False, width=0.002)
    v.line([(-1.4, -1.45), (1.4, -1.45)], rivets=True, pitch=0.1, offset=0.012)
    v.text(NUMBER, 0.0, TZ - 0.5, 0.25)
    for sx in (1, -1):
        v.streaks("oil", sx * 1.42, sx * 1.75, FRONT_Z, REAR_Z, 90, 0.4, 0.03, 120, drift=0.0, down=True)
    v.streaks("soot", 1.3, 1.75, -1.0, -1.6, 60, 1.6, 0.06, 150, drift=0.0, down=True)
    for c in ((0.0, GLACIS_TOP_Z - 0.22), (0.48, TZ - 0.18), (-0.52, TZ - 0.25)):
        for _ in range(30):
            a = c[0] + v.rng.uniform(-0.45, 0.45)
            b = c[1] + v.rng.uniform(-0.45, 0.45)
            x, y = v.px(a, b)
            r = v.mpx(v.rng.uniform(0.02, 0.08))
            v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(40, 110)))


def front(v):
    mud(v, -1.8, 1.8, 1.1, n=650, strength=250)


def back(v):
    v.text(NUMBER, 0.0, 1.25, 0.12)
    mud(v, -1.8, 1.8, 1.2, n=600, strength=250)
    v.streaks("soot", 0.8, 1.6, 1.0, 1.3, 40, 0.3, 0.05, 120, drift=0.0, down=False)


def bottom(v):
    for _ in range(800):
        a = v.rng.uniform(-1.8, 1.8)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=71)
