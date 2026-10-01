"""The Apache's paint maps: panel lines, rivets, stencils, walkways, soot and
stains, drawn on the aircraft seen from the left, the right, above and below
(see modelkit/paintmaps.py for what each image holds)."""
import numpy as np

from paintmaps import View, draw_views, rounded, FONT, FONT_NARROW
import airframe as af
from ah64 import TAIL_Z, WING_TIP_X, PYLON_INBOARD_X, PYLON_OUTBOARD_X

RES = 0.0022  # metres per pixel
Z0, Z1 = -13.5, 2.7
Y0, Y1 = -0.7, 2.95
X0, X1 = -2.8, 2.8
SERIAL = "05-07015"

# where each view sits in model space (the shader uses the same numbers)
VIEWS = {
    "left": dict(u=("z", Z1, Z0), v=("y", Y0, Y1)),
    "right": dict(u=("z", Z0, Z1), v=("y", Y0, Y1)),
    "top": dict(u=("x", X1, X0), v=("z", Z0, Z1)),
    "bottom": dict(u=("x", X0, X1), v=("z", Z0, Z1)),
}


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


def draw_all(out):
    return draw_views(out, VIEWS, {"left": lambda v: side(v, 1), "right": lambda v: side(v, -1), "top": top, "bottom": bottom}, RES)


if __name__ == "__main__":
    import sys
    print(draw_all(sys.argv[1] if len(sys.argv) > 1 else "decals"))
