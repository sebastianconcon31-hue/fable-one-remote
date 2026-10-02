"""The M978A4's paint maps (see modelkit/paintmaps.py for what each image
holds): the cab's seams and stencils as on the M977, the tank's welded sheet
seams, fuel stencils, red FLAMMABLE placards (the "walk" channel is the
placard red here), mud thrown up by the wheels (the "oil" channel) and soot
round the exhaust - seen from the left, right, top, front, back and
underneath."""
import numpy as np

from paintmaps import draw_views
from m978 import *

RES = 0.002
Z0, Z1 = REAR_Z - 0.15, FRONT_Z + 0.15
Y0, Y1 = -0.05, SPEC["height"] + 0.15
X0, X1 = -1.65, 1.65

VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
    "front": dict(u=("x", X0, X1), v=("y", Y0, Y1)),
    "back": dict(u=("x", X1, X0), v=("y", Y0, Y1)),
}
REGISTRATION = "NL 21 5112"
BUMPER = ("3-4ID", "F-23")


def placard(v, a, b, size=0.27, number="1863"):
    """A red flammable-liquid placard on its point: the diamond in the placard red, the UN number and a border in black."""
    s = size / 2
    v.blob("walk", [(a, b + s), (a + s, b), (a, b - s), (a - s, b)])
    v.text(number, a, b - s * 0.15, size * 0.16)
    v.text("3", a, b - s * 0.72, size * 0.1)
    v.line([(a, b + s), (a + s, b), (a, b - s), (a - s, b), (a, b + s)], rivets=False, width=0.004, groove=False)
    v.d["mark"].line([v.px(*p) for p in [(a, b + s * 0.93), (a + s * 0.93, b), (a, b - s * 0.93), (a - s * 0.93, b), (a, b + s * 0.93)]], fill=255, width=max(1, int(v.mpx(0.006))))
    v.d["mark"].line([v.px(a - s * 0.62, b + s * 0.05), v.px(a + s * 0.62, b + s * 0.05)], fill=255, width=max(1, int(v.mpx(0.004))))
    # the flame at the top
    v.blob("mark", [(a, b + s * 0.75), (a + s * 0.17, b + s * 0.42), (a + s * 0.08, b + s * 0.3), (a - s * 0.08, b + s * 0.3), (a - s * 0.17, b + s * 0.42)])


def mud_low(v, a0, a1, top, n=140, strength=210, along=0.0):
    """Mud thrown up by the wheels: splashes low down, thinning out with height."""
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.15, top)
        r = v.rng.uniform(0.015, 0.09) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.008))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.5, top, 40, top * 0.45, 0.02, 120, drift=along)


def side(v, sx):
    left = sx > 0
    # cab, as on the M977
    v.line([(4.06, 1.43), (2.74, 1.43)], rivets=False)
    v.line([(2.7, 1.43), (2.7, 2.8)], rivets=False)
    v.line([(4.2, 1.43), (4.2, 2.78)], rivets=False)
    v.rect(2.66, 2.36, 1.5, 2.4, radius=0.03, rivets=False)
    v.text(REGISTRATION, 3.42, 1.72, 0.05)
    v.text("MAX SPEED 62 MPH", 3.42, 1.58, 0.022)
    v.line([(4.0, 1.38), (1.25, 1.38)], rivets=False, width=0.003)
    v.rect(2.22, 1.25, 1.42, 2.22, radius=0.04, rivets=True, pitch=0.08)
    v.text("NO STEP", 1.75, 2.15, 0.03)
    if left:
        v.rect(1.05, -0.32, 0.75, 1.26, radius=0.18, rivets=False)
        v.text("JP-8", 0.35, 1.1, 0.06)
    # tank: sheet seams, the stencils and a placard
    zc = (TANK_FRONT_Z + TANK_REAR_Z) / 2
    for z in (TANK_FRONT_Z - 1.4, TANK_REAR_Z + 1.4):
        v.line([(z, TANK_Y - TANK_B + 0.05), (z, TANK_Y + TANK_B - 0.05)], rivets=False, width=0.0015)
    v.line([(TANK_FRONT_Z - 0.2, TANK_Y + 0.3), (TANK_REAR_Z + 0.2, TANK_Y + 0.3)], rivets=False, width=0.0015)
    v.text("FLAMMABLE", zc + 0.9, TANK_Y + 0.05, 0.11)
    v.text("JP-8", zc - 0.75, TANK_Y + 0.05, 0.12)
    v.text("NO SMOKING WITHIN 50 FEET", zc, TANK_Y - 0.25, 0.045)
    v.text("CAPACITY 2500 GALLONS", zc + 0.9, TANK_Y + 0.26, 0.035)
    placard(v, TANK_REAR_Z + 0.55, TANK_Y + 0.02)
    v.text("BOND BEFORE FUELING", TANK_REAR_Z + 0.55, TANK_Y - 0.33, 0.022)
    # pump module: the side door's outline, its latches and instructions
    zp = (PUMP_FRONT_Z + PUMP_REAR_Z) / 2
    L = PUMP_FRONT_Z - PUMP_REAR_Z - 0.26
    v.rect(zp + L / 2, zp - L / 2, PUMP_BOTTOM_Y + 0.25, PUMP_TOP_Y - 0.12, radius=0.02, rivets=False)
    v.text("EMERGENCY SHUT-OFF", zp, PUMP_BOTTOM_Y + 0.85, 0.035)
    v.text("PULL", zp, PUMP_BOTTOM_Y + 0.78, 0.03)
    v.text("CTIS  TIRE PRESSURE: HWY 45 / CROSS-COUNTRY 25 / MUD-SAND-SNOW 12 PSI", -0.3, 1.32, 0.02)
    v.text("GVW 64,800 LB", -2.2, 1.32, 0.02)
    for za in AXLES_Z:
        mud_low(v, za + 0.8, za - 1.0, 1.5, n=320, strength=255, along=-0.05 if left else 0.05)
    mud_low(v, FRONT_Z, REAR_Z, 1.1, n=500, strength=200)
    # fuel stains: drips down from the manholes and round the pump module's doors
    v.streaks("oil", TANK_FRONT_Z - 0.6, TANK_FRONT_Z - 1.3, TANK_Y + TANK_B, TANK_Y + TANK_B - 0.05, 18, 0.5, 0.012, 90, drift=0.0)
    v.streaks("oil", TANK_REAR_Z + 0.7, TANK_REAR_Z + 1.4, TANK_Y + TANK_B, TANK_Y + TANK_B - 0.05, 18, 0.5, 0.012, 90, drift=0.0)
    if not left:
        v.blob("soot", [(2.05, 2.75), (2.32, 2.75), (2.3, 3.0), (2.06, 3.0)], 200)
        v.streaks("soot", 2.0, 2.1, 2.85, 2.95, 40, -0.9, 0.03, 120, drift=0.0, down=False)


def top(v):
    v.line([(-CAB_HALF_W + 0.05, 3.4), (CAB_HALF_W - 0.05, 3.4)], rivets=False)
    v.rect(0.8, -0.8, 1.3, 2.15, radius=0.05, rivets=True, pitch=0.1)
    v.text("NO STEP", 0.0, 1.45, 0.04)
    v.text("NO STEP", 0.0, 2.0, 0.03)
    # the tank's top sheet seams and stains round the manholes
    v.line([(-TANK_A + 0.1, TANK_FRONT_Z - 1.4), (TANK_A - 0.1, TANK_FRONT_Z - 1.4)], rivets=False, width=0.0015)
    v.line([(-TANK_A + 0.1, TANK_REAR_Z + 1.4), (TANK_A - 0.1, TANK_REAR_Z + 1.4)], rivets=False, width=0.0015)
    for z in (TANK_FRONT_Z - 0.95, TANK_REAR_Z + 1.05):
        for _ in range(30):
            a = v.rng.uniform(-0.5, 0.5)
            b = z + v.rng.uniform(-0.5, 0.5)
            x, y = v.px(a, b)
            r = v.mpx(v.rng.uniform(0.02, 0.1))
            v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(40, 120)))
    zp = (PUMP_FRONT_Z + PUMP_REAR_Z) / 2
    v.text("NO STEP", 0.0, zp, 0.05)
    v.streaks("soot", -1.12, -1.0, 2.0, 1.9, 40, 0.8, 0.04, 140, drift=0.02, down=True)
    for sx in (1, -1):
        v.streaks("oil", sx * 0.85, sx * 1.2, 4.2, 1.2, 50, 0.15, 0.02, 110, drift=0.0, down=True)


def front(v):
    v.text(BUMPER[0], 0.66, 0.84, 0.07)
    v.text(BUMPER[1], -0.66, 0.84, 0.07)
    v.text("CAUTION  WINCH", 0.0, 0.99, 0.02)
    mud_low(v, -1.2, 1.2, 1.3, n=420, strength=240)


def back(v):
    v.text(BUMPER[0], 0.55, 0.92, 0.06)
    v.text(BUMPER[1], -0.55, 0.92, 0.06)
    placard(v, 0.0, PUMP_TOP_Y - 0.45, 0.3)
    v.text("FLAMMABLE", 0.0, PUMP_TOP_Y - 0.12 - 0.04, 0.05)
    v.text("NO SMOKING WITHIN 50 FEET", 0.0, PUMP_BOTTOM_Y + 0.3, 0.035)
    v.text("CAUTION  STAY BACK 100 FT", 0.0, 1.0, 0.025)
    mud_low(v, -1.2, 1.2, 1.5, n=480, strength=250)


def bottom(v):
    for _ in range(600):
        a = v.rng.uniform(-1.25, 1.25)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=41)
