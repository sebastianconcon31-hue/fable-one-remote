"""The Abrams' paint maps (see modelkit/paintmaps.py for what each image
holds): armour seams and bolt rows, the turret's blow-out panels, bumper
codes and the gun tube's name, non-skid on the walking areas (the "walk"
channel), mud thrown over the skirts and running gear (the "oil" channel)
and exhaust soot over the rear grille - seen from the left, right, top,
front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from abrams import *

RES = 0.002
Z0, Z1 = HULL_REAR_Z - 0.15, MUZZLE_Z + 0.15
Y0, Y1 = -0.05, 3.2
X0, X1 = -1.95, 1.95

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
UNIT, CALLSIGN, NAME = "1-66AR", "A-12", "AMBUSH"
TZ = TURRET_Z


def mud(v, a0, a1, top, n=300, strength=230, along=0.0):
    """Mud thrown up by the tracks: thick low down, thinning out with height."""
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
    # skirts: bolt rows along their tops and the armoured panels' bolted faces
    edges = np.linspace(HULL_FRONT_Z - 0.38, REAR_PLATE_Z + 0.05, 8)
    for k in range(7):
        z0, z1 = edges[k] - 0.05, edges[k + 1] + 0.05
        v.line([(z0, 1.48), (z1, 1.48)], groove=False, pitch=0.12, offset=0.0)
        if k < 3:
            v.line([(z0, 0.68), (z1, 0.68)], groove=False, pitch=0.12, offset=0.0)
            v.line([(z0 - 0.02, 1.2), (z1 + 0.02, 1.2)], rivets=False, width=0.0016)
    # turret side: the cheek module's seam, the bustle's welds, the number on the box
    v.line([(TZ + 0.66, 1.7), (TZ + 0.66, 2.4)], rivets=True, pitch=0.09, offset=0.0)
    v.line([(TZ + 0.66, 2.36), (TZ - 1.1, 2.36)], rivets=False, width=0.0016)
    v.line([(TZ - 1.1, 1.7), (TZ - 1.1, 2.4)], rivets=False, width=0.0016)
    v.text(CALLSIGN, TZ - 2.1, 2.1, 0.11)
    v.text("NO HANDHOLD", TZ + 0.4, 1.78, 0.022)
    # the gun tube's name, near the shield, on the thermal sleeve
    v.text(NAME, TZ + 2.55, TRUNNION[1] + 0.005, 0.075)
    # mud: thick over the lower skirts and running gear, splashed up the hull
    mud(v, HULL_FRONT_Z, HULL_REAR_Z, 1.0, n=900, strength=255, along=-0.05 if left else 0.05)
    mud(v, HULL_FRONT_Z - 0.3, HULL_REAR_Z + 0.3, 1.5, n=300, strength=150)
    # dust drawn into the skirts' lower edges by the tracks
    v.streaks("oil", HULL_FRONT_Z - 0.5, HULL_REAR_Z + 0.2, 0.7, 0.62, 160, 0.25, 0.03, 160, drift=0.0, down=False)


def top(v):
    # hull: the front deck plates and the engine deck's access plates, bolted
    v.rect(-0.9, 0.9, 2.95, 3.95, radius=0.02, rivets=True, pitch=0.1)
    for sx in (1, -1):
        v.rect(sx * 1.0, sx * 1.7, 1.3, 2.6, radius=0.02, rivets=True, pitch=0.1)
        v.rect(sx * 1.25, sx * 1.7, -1.6, REAR_PLATE_Z + 0.08, radius=0.02, rivets=True, pitch=0.1)
    v.line([(-1.7, -1.6), (1.7, -1.6)], rivets=True, pitch=0.1, offset=0.012)
    # non-skid on the walking areas: the deck either side of the turret and over the engine
    for sx in (1, -1):
        v.blob("walk", [(sx * 1.08, 2.0), (sx * 1.7, 2.0), (sx * 1.7, -0.55), (sx * 1.08, -0.55)])
    v.blob("walk", [(-1.2, -1.7), (1.2, -1.7), (1.2, REAR_PLATE_Z + 0.1), (-1.2, REAR_PLATE_Z + 0.1)], 120)
    # turret roof: the front armour's plate, the blow-out panels over the bustle's ammunition, a walkway
    v.line([(-1.4, TZ + 0.2), (1.4, TZ + 0.2)], rivets=True, pitch=0.08, offset=0.012)
    for sx in (1, -1):
        v.rect(sx * 0.08, sx * 1.36, TZ - 1.55, TZ - 2.7, radius=0.03, rivets=True, pitch=0.07)
        v.text("BLOW-OUT PANEL", sx * 0.72, TZ - 2.05, 0.04)
        v.text("NO STEP", sx * 0.72, TZ - 2.2, 0.05)
    v.blob("walk", [(0.15, TZ - 0.2), (1.35, TZ - 0.2), (1.35, TZ - 1.15), (0.15, TZ - 1.15)], 140)
    v.text(CALLSIGN, 0.0, TZ - 0.9, 0.2)
    # soot blown up over the rear deck, dirt kicked onto the fenders, scuffs round the hatches
    v.streaks("soot", -1.0, 1.0, REAR_PLATE_Z + 0.05, REAR_PLATE_Z + 0.2, 60, 0.6, 0.06, 140, drift=0.0, down=False)
    for sx in (1, -1):
        v.streaks("oil", sx * 1.4, sx * 1.8, HULL_FRONT_Z, HULL_REAR_Z, 90, 0.4, 0.03, 120, drift=0.0, down=True)
    for c in ((-0.6, TZ - 0.42), (0.62, TZ - 0.48), (0.0, 2.44)):
        for _ in range(30):
            a = c[0] + v.rng.uniform(-0.5, 0.5)
            b = c[1] + v.rng.uniform(-0.5, 0.5)
            x, y = v.px(a, b)
            r = v.mpx(v.rng.uniform(0.02, 0.08))
            v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(40, 110)))


def front(v):
    # bumper codes on the front fenders
    v.text(UNIT, 1.36, 1.0, 0.075)
    v.text(CALLSIGN, -1.36, 1.0, 0.075)
    v.text("120MM", 0.0, TRUNNION[1] - 0.22, 0.04)
    mud(v, -1.85, 1.85, 1.2, n=600, strength=250)


def back(v):
    v.text(UNIT, 1.36, 1.32, 0.075)
    v.text(CALLSIGN, -1.36, 1.32, 0.075)
    v.text("CAUTION  HOT EXHAUST  STAND CLEAR", 0.0, 1.58, 0.028)
    # soot over the exhaust grille and the rear plate, and the bustle rack's back
    v.blob("soot", [(-1.0, 0.95), (1.0, 0.95), (1.0, 1.55), (-1.0, 1.55)], 230)
    v.streaks("soot", -1.0, 1.0, 1.5, 1.55, 80, 0.5, 0.05, 160, drift=0.0, down=False)
    v.streaks("soot", -1.4, 1.4, 1.9, 2.0, 30, 0.3, 0.05, 90, drift=0.0, down=False)
    mud(v, -1.85, 1.85, 1.3, n=600, strength=250)


def bottom(v):
    for _ in range(900):
        a = v.rng.uniform(-1.85, 1.85)
        b = v.rng.uniform(HULL_REAR_Z, HULL_FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=51)
