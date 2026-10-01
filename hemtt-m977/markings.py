"""The HEMTT's paint maps (see modelkit/paintmaps.py for what each image
holds): panel seams, stencils (black on the CARC green), yellow hazard
stripes (the "walk" channel is the yellow here), mud splashed up from the
wheels (the "oil" channel is mud) and exhaust soot - seen from the left,
right, top, front, back and underneath."""
import numpy as np

from paintmaps import draw_views
from m977 import *

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
REGISTRATION = "NL 21 3478"
BUMPER = ("3-4ID", "B-17")


def hazard(v, a0, a1, b0, b1, stripe=0.06):
    """Yellow-and-black diagonal hazard stripes over a rectangle."""
    v.blob("walk", [(a0, b0), (a1, b0), (a1, b1), (a0, b1)])
    span = abs(a1 - a0) + abs(b1 - b0)
    lo, hi = min(a0, a1), max(a0, a1)
    blo, bhi = min(b0, b1), max(b0, b1)
    k = 0
    t = -span
    while t < span:
        if k % 2 == 0:
            quad = [(lo + t, blo), (lo + t + stripe, blo), (lo + t + stripe + (bhi - blo), bhi), (lo + t + (bhi - blo), bhi)]
            clipped = [(min(max(a, lo), hi), b) for a, b in quad]
            v.blob("mark", clipped)
        t += stripe
        k += 1


def mud_low(v, a0, a1, top, n=140, strength=210, along=0.0):
    """Mud thrown up by the wheels: splashes low down, thinning out with height."""
    for _ in range(n):
        a = v.rng.uniform(min(a0, a1), max(a0, a1))
        b = v.rng.uniform(0.15, top) ** 1.0
        r = v.rng.uniform(0.015, 0.09) * (1.3 - b / max(top, 1e-3))
        val = int(strength * v.rng.uniform(0.4, 1.0) * max(0.15, 1 - b / top))
        x, y = v.px(a, b)
        rr = v.mpx(max(r, 0.008))
        v.d["oil"].ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=val)
    v.streaks("oil", a0, a1, top * 0.5, top, 40, top * 0.45, 0.02, 120, drift=along)


def side(v, sx):
    left = sx > 0
    # cab: seams round the side panel, the step well, the rear corner
    v.line([(4.06, 1.43), (2.74, 1.43)], rivets=False)
    v.line([(2.7, 1.43), (2.7, 2.8)], rivets=False)
    v.line([(4.2, 1.43), (4.2, 2.78)], rivets=False)
    v.rect(2.66, 2.36, 1.5, 2.4, radius=0.03, rivets=False)
    # door stencils: registration and the weight class
    v.text(REGISTRATION, 3.42, 1.72, 0.05)
    v.text("MAX SPEED 62 MPH", 3.42, 1.58, 0.022)
    # front fender and engine bay
    v.line([(4.0, 1.38), (1.25, 1.38)], rivets=False, width=0.003)
    v.rect(2.22, 1.25, 1.42, 2.22, radius=0.04, rivets=True, pitch=0.08)
    v.text("NO STEP", 1.75, 2.15, 0.03)
    # fuel tank or boxes
    if left:
        v.rect(1.05, -0.32, 0.75, 1.26, radius=0.18, rivets=False)
        v.text("JP-8", 0.35, 1.1, 0.06)
        v.text("NO SMOKING WITHIN 50 FT", 0.35, 0.98, 0.025)
    else:
        v.rect(1.05, 0.39, 0.76, 1.24, radius=0.02, rivets=False)
        v.rect(0.28, -0.52, 0.76, 1.2, radius=0.02, rivets=False)
        v.text("BATTERIES", 0.72, 1.1, 0.03)
        v.text("24 V", 0.72, 1.04, 0.025)
    # cargo body: the side panel seams every 0.6 m, bolts along the top rail
    for z in np.arange(BED_FRONT_Z - 0.6, BED_REAR_Z, -0.6):
        v.line([(z, BED_FLOOR_Y + 0.03), (z, BED_FLOOR_Y + BED_SIDE_H - 0.06)], rivets=False, width=0.0015)
    v.line([(z, BED_FLOOR_Y + BED_SIDE_H - 0.07) for z in (BED_FRONT_Z, BED_REAR_Z)], groove=False, pitch=0.15, offset=0.0)
    v.text("TIE DOWN", BED_FRONT_Z - 0.5, BED_FLOOR_Y - 0.06, 0.02)
    v.text("CTIS  TIRE PRESSURE: HWY 45 / CROSS-COUNTRY 25 / MUD-SAND-SNOW 12 PSI", -0.9, BED_FLOOR_Y + 0.14, 0.022)
    v.text("GVW 64,500 LB   PAYLOAD 21,561 LB", -2.4, BED_FLOOR_Y + 0.14, 0.022)
    # crane: capacity and a warning on the boom, hazard stripes at its tip
    if not left:
        v.text("CRANE CAPACITY 4500 LB AT 9 FT / 2500 LB AT 19 FT", CRANE[2] + 1.9, CRANE[1] + 0.86, 0.022)
        hazard(v, CRANE[2] + 3.5, CRANE[2] + 3.75, CRANE[1] + 0.7, CRANE[1] + 1.0)
        v.text("DANGER  STAND CLEAR OF LOAD", CRANE[2], CRANE[1] + 0.7, 0.018)
    # mud: thrown up round every wheel and along the lower body
    for za in AXLES_Z:
        mud_low(v, za + 0.8, za - 1.0, 1.5, n=320, strength=255, along=-0.05 if left else 0.05)
    mud_low(v, FRONT_Z, REAR_Z, 1.1, n=500, strength=200)
    # exhaust soot round the stack and the cab's rear corner (right side)
    if not left:
        v.blob("soot", [(2.05, 2.75), (2.32, 2.75), (2.3, 3.0), (2.06, 3.0)], 200)
        v.streaks("soot", 2.0, 2.1, 2.85, 2.95, 40, -0.9, 0.03, 120, drift=0.0, down=False)


def top(v):
    # cab roof seams, the engine cover's access panels, the bed floor plates
    v.line([(-CAB_HALF_W + 0.05, 3.4), (CAB_HALF_W - 0.05, 3.4)], rivets=False)
    v.rect(0.8, -0.8, 1.3, 2.15, radius=0.05, rivets=True, pitch=0.1)
    for z in np.arange(BED_FRONT_Z - 0.6, BED_REAR_Z, -0.6):
        v.line([(-BED_HALF_W + 0.06, z), (BED_HALF_W - 0.06, z)], rivets=True, pitch=0.12, offset=0.012)
    v.line([(0.0, BED_FRONT_Z - 0.05), (0.0, BED_REAR_Z + 0.05)], rivets=True, pitch=0.12, offset=0.012)
    # boot and pallet scuffs and caked dirt on the floor
    for _ in range(90):
        a = v.rng.uniform(-1.1, 1.1)
        b = v.rng.uniform(BED_REAR_Z + 0.1, BED_FRONT_Z - 0.1)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.04, 0.2))
        v.d["oil"].ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=int(v.rng.uniform(40, 130)))
    v.text("NO STEP", 0.0, 1.45, 0.04)
    v.text("NO STEP", 0.0, 2.0, 0.03)
    # soot drifting back from the exhaust over the right of the headboard
    v.streaks("soot", -1.12, -1.0, 2.0, 1.9, 40, 0.8, 0.04, 140, drift=0.02, down=True)
    # mud splashed onto the fender tops and the rear deck
    for sx in (1, -1):
        v.streaks("oil", sx * 0.85, sx * 1.2, 4.2, 1.2, 50, 0.15, 0.02, 110, drift=0.0, down=True)


def front(v):
    # bumper codes either side of the winch, a warning above the fairlead
    v.text(BUMPER[0], 0.66, 0.84, 0.07)
    v.text(BUMPER[1], -0.66, 0.84, 0.07)
    v.text("CAUTION  WINCH", 0.0, 0.99, 0.02)
    # yellow and black on the bumper ends
    hazard(v, 1.0, 1.16, 0.66, 1.02)
    hazard(v, -1.16, -1.0, 0.66, 1.02)
    # mud on the bumper and lower cab
    mud_low(v, -1.2, 1.2, 1.3, n=420, strength=240)


def back(v):
    v.text(BUMPER[0], 0.55, 0.92, 0.06)
    v.text(BUMPER[1], -0.55, 0.92, 0.06)
    hazard(v, 0.98, 1.1, 0.78, 1.06)
    hazard(v, -1.1, -0.98, 0.78, 1.06)
    v.text("CAUTION  CRANE IN USE", 0.0, BED_FLOOR_Y + 0.4, 0.03)
    v.text("KEEP BACK 50 FT", 0.0, BED_FLOOR_Y + 0.33, 0.025)
    mud_low(v, -1.2, 1.2, 1.5, n=480, strength=250)


def bottom(v):
    # underneath is mud, everywhere
    for _ in range(600):
        a = v.rng.uniform(-1.25, 1.25)
        b = v.rng.uniform(REAR_Z, FRONT_Z)
        x, y = v.px(a, b)
        r = v.mpx(v.rng.uniform(0.03, 0.25))
        v.d["oil"].ellipse((x - r, y - r, x + r, y + r), fill=int(v.rng.uniform(80, 230)))


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom, "front": front, "back": back}, RES, seed=31)
