"""The Bradley's paint maps (see modelkit/paintmaps.py for what each image
holds): armour seams and bolt rows, the bumper codes and vehicle number,
the ramp's stencils, non-skid on the roof (the "walk" channel), mud thrown
over the skirts and running gear (the "oil" channel) and exhaust soot down
the right side - seen from the left, right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from bradley import *

RES = 0.002
Z0, Z1 = REAR_Z - 0.15, FRONT_Z + 1.2
Y0, Y1 = -0.05, SPEC["height"] + 0.15
X0, X1 = -1.9, 1.9

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
UNIT, CALLSIGN = "2-7IN", "B-23"
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
    # the armour panels' seams and their tie bolts in rows
    edges = np.linspace(FRONT_Z - 0.55, REAR_PLATE_Z + 0.12, 6)
    for k in range(5):
        a, b = edges[k] - 0.03, edges[k + 1] + 0.03
        v.line([(a, 1.5), (b, 1.5)], groove=False, pitch=0.1, offset=0.0)
        v.line([(a, 1.6), (b, 1.6)], rivets=False, width=0.0014)
    v.text(CALLSIGN, 0.3, 1.72, 0.12)
    v.text("CAUTION  STAND CLEAR OF TOW LAUNCHER", TZ, 2.1, 0.02) if left else None
    # turret side: the armour's seams, the vehicle number on the TOW box
    v.line([(TZ + 0.7, 2.05), (TZ + 0.7, 2.58)], rivets=True, pitch=0.08, offset=0.0)
    if left:
        v.text(CALLSIGN, TZ, 2.32, 0.1)
    mud(v, FRONT_Z, REAR_Z, 0.95, n=800, strength=255, along=-0.05 if left else 0.05)
    mud(v, FRONT_Z - 0.3, REAR_Z + 0.3, 1.4, n=280, strength=150)
    v.streaks("oil", FRONT_Z - 0.5, REAR_Z + 0.2, 0.75, 0.68, 140, 0.25, 0.03, 160, drift=0.0, down=False)
    if not left:  # exhaust soot streaming back from the outlet on the right
        v.blob("soot", [(1.85, 1.3), (2.35, 1.3), (2.35, 1.6), (1.85, 1.6)], 220)
        v.streaks("soot", 1.85, 2.3, 1.3, 1.6, 80, 2.4, 0.05, 170, drift=0.04, down=False)
        v.streaks("soot", 1.85, 2.3, 1.3, 1.6, 40, -1.2, 0.05, 120, drift=0.08, down=False)


def top(v):
    # roof plates and their bolts, the non-skid, the troop hatch's surround
    for sx in (1, -1):
        v.rect(sx * 0.95, sx * 1.55, REAR_PLATE_Z + 0.2, TZ - 0.9, radius=0.02, rivets=True, pitch=0.1)
        v.blob("walk", [(sx * 1.0, TZ - 0.95), (sx * 1.52, TZ - 0.95), (sx * 1.52, REAR_PLATE_Z + 0.25), (sx * 1.0, REAR_PLATE_Z + 0.25)], 130)
    v.blob("walk", [(-0.65, REAR_PLATE_Z + 0.25), (0.65, REAR_PLATE_Z + 0.25), (0.65, REAR_PLATE_Z + 0.32), (-0.65, REAR_PLATE_Z + 0.32)], 120)
    v.line([(-1.55, GLACIS_TOP_Z), (1.55, GLACIS_TOP_Z)], rivets=True, pitch=0.09, offset=0.012)
    v.rect(-0.2, -0.95, 2.1, 3.0, radius=0.02, rivets=True, pitch=0.09)
    v.text("NO STEP", -0.55, 2.0, 0.04)
    # turret roof: the armour's plates and a walkway
    v.line([(-1.0, TZ + 0.15), (1.0, TZ + 0.15)], rivets=True, pitch=0.08, offset=0.012)
    v.text(CALLSIGN, 0.0, TZ - 0.75, 0.16)
    for c in ((0.6, 1.98), (0.45, TZ - 0.18), (-0.48, TZ - 0.1), (0.0, REAR_PLATE_Z + 0.95)):
        for _ in range(30):
            a = c[0] + v.rng.uniform(-0.45, 0.45)
            b = c[1] + v.rng.uniform(-0.45, 0.45)
            x, y = v.px(a, b)
            r = v.mpx(v.rng.uniform(0.02, 0.08))
            v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(40, 110)))
    for sx in (1, -1):
        v.streaks("oil", sx * 1.4, sx * 1.8, FRONT_Z, REAR_Z, 80, 0.4, 0.03, 120, drift=0.0, down=True)
    v.streaks("soot", -1.6, -1.2, 2.2, 1.8, 30, 1.5, 0.06, 120, drift=0.0, down=True)


def front(v):
    v.text(UNIT, 1.2, 1.0, 0.07)
    v.text(CALLSIGN, -1.2, 1.0, 0.07)
    mud(v, -1.8, 1.8, 1.15, n=600, strength=250)


def back(v):
    v.text(UNIT, 1.25, 1.18, 0.065)
    v.text(CALLSIGN, -1.25, 1.18, 0.065)
    v.text("CAUTION", 0.0, 1.75, 0.045)
    v.text("STAND CLEAR OF RAMP", 0.0, 1.67, 0.035)
    v.text("NO STEP", -0.3, 0.75, 0.03)
    mud(v, -1.8, 1.8, 1.25, n=600, strength=250)


def bottom(v):
    for _ in range(800):
        a = v.rng.uniform(-1.8, 1.8)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=61)
