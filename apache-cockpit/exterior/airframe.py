"""The airframe: fuselage, avionics bays, rotor pylon, engine nacelles and
exhausts, stub wings and pylons, fin, stabilator and the canopy.

Surfaces are lofted from cross-sections given at key stations (tables below)
and interpolated smoothly in between; every chine is a real fillet, so the
skin shades like the aircraft's does, with no faceting."""
import math
import bpy
import numpy as np
from geom import Mesh, fillet_path, table, spacing, airfoil, Frame, lathe, tube, rbox, prism, empty, norm, set_parent
from ah64 import CAN, SILL, sill_at, mir, TAIL_Z, TAIL_HUB, WING_TIP_X, WING_Z, WING_Y, PYLON_INBOARD_X, PYLON_OUTBOARD_X


def mirror2(half, closed=True):
    """Left half (x >= 0) from top centre to bottom centre -> the full loop (or the open U for the cockpit)."""
    if closed:
        return half + [(-x, y) for x, y in reversed(half[1:-1])]
    return half + [(-x, y) for x, y in reversed(half[:-1])]


def ring3(pts2, z):
    return [(x, y, z) for x, y in pts2]


# ---- fuselage ------------------------------------------------------------------------------------------------------------------
# The lower body - the side below the sill, the chine and the belly - runs the full length (z: corner (x, y, r)).
LOWER = table([
    (2.18, dict(lc=(0.20, 0.0, 0.05), bc=(0.12, -0.235, 0.06), bot=-0.245)),
    (2.05, dict(lc=(0.25, -0.02, 0.06), bc=(0.15, -0.28, 0.08), bot=-0.29)),
    (1.85, dict(lc=(0.31, -0.04, 0.07), bc=(0.18, -0.33, 0.10), bot=-0.34)),
    (1.55, dict(lc=(0.37, -0.07, 0.07), bc=(0.21, -0.38, 0.11), bot=-0.385)),
    (1.25, dict(lc=(0.41, -0.09, 0.06), bc=(0.23, -0.41, 0.12), bot=-0.41)),
    (0.98, dict(lc=(0.43, -0.10, 0.06), bc=(0.24, -0.42, 0.12), bot=-0.42)),
    (0.0, dict(lc=(0.46, -0.10, 0.06), bc=(0.25, -0.42, 0.12), bot=-0.42)),
    (-1.0, dict(lc=(0.49, -0.10, 0.06), bc=(0.26, -0.42, 0.12), bot=-0.42)),
    (-1.84, dict(lc=(0.52, -0.10, 0.07), bc=(0.27, -0.42, 0.12), bot=-0.42)),
    (-2.5, dict(lc=(0.54, -0.08, 0.08), bc=(0.28, -0.41, 0.12), bot=-0.41)),
    (-3.1, dict(lc=(0.53, -0.02, 0.10), bc=(0.27, -0.34, 0.13), bot=-0.35)),
    (-3.7, dict(lc=(0.49, 0.12, 0.12), bc=(0.24, -0.16, 0.14), bot=-0.18)),
    (-4.3, dict(lc=(0.42, 0.38, 0.14), bc=(0.20, 0.18, 0.12), bot=0.14)),
    (-5.0, dict(lc=(0.33, 0.62, 0.12), bc=(0.16, 0.48, 0.10), bot=0.45)),
    (-5.8, dict(lc=(0.27, 0.80, 0.10), bc=(0.13, 0.68, 0.08), bot=0.64)),
    (-7.0, dict(lc=(0.23, 0.95, 0.09), bc=(0.11, 0.84, 0.07), bot=0.80)),
    (-8.5, dict(lc=(0.20, 1.06, 0.08), bc=(0.10, 0.96, 0.06), bot=0.92)),
    (-10.3, dict(lc=(0.17, 1.14, 0.07), bc=(0.08, 1.05, 0.05), bot=1.01)),
    (-11.6, dict(lc=(0.12, 1.20, 0.05), bc=(0.06, 1.13, 0.04), bot=1.09)),
    (-12.25, dict(lc=(0.05, 1.30, 0.02), bc=(0.03, 1.25, 0.015), bot=1.22)),
], ["lc", "bc", "bot"])

NOSE_TOP = table([
    (0.98, dict(t=0.800, k=(0.395, 0.788, 0.004))),
    (1.25, dict(t=0.760, k=(0.370, 0.742, 0.030))),
    (1.55, dict(t=0.680, k=(0.330, 0.655, 0.060))),
    (1.85, dict(t=0.580, k=(0.270, 0.552, 0.070))),
    (2.05, dict(t=0.500, k=(0.220, 0.468, 0.070))),
    (2.18, dict(t=0.440, k=(0.180, 0.410, 0.060))),
], ["t", "k"])

AFT_TOP = table([
    (-1.84, dict(t=2.020, k=(0.280, 2.018, 0.010), u=(0.485, 1.168, 0.010))),
    (-2.10, dict(t=2.010, k=(0.330, 2.000, 0.060), u=(0.530, 1.000, 0.120))),
    (-2.60, dict(t=2.000, k=(0.360, 1.980, 0.080), u=(0.560, 0.850, 0.150))),
    (-3.30, dict(t=1.980, k=(0.360, 1.950, 0.100), u=(0.550, 0.850, 0.180))),
    (-4.00, dict(t=1.900, k=(0.320, 1.860, 0.100), u=(0.470, 1.000, 0.200))),
    (-4.60, dict(t=1.830, k=(0.270, 1.800, 0.090), u=(0.360, 1.200, 0.180))),
    (-5.20, dict(t=1.780, k=(0.240, 1.750, 0.080), u=(0.290, 1.300, 0.150))),
    (-6.50, dict(t=1.710, k=(0.210, 1.680, 0.070), u=(0.250, 1.380, 0.120))),
    (-8.50, dict(t=1.640, k=(0.180, 1.610, 0.060), u=(0.210, 1.400, 0.100))),
    (-10.30, dict(t=1.580, k=(0.160, 1.550, 0.050), u=(0.180, 1.400, 0.080))),
    (-11.60, dict(t=1.550, k=(0.110, 1.520, 0.040), u=(0.120, 1.420, 0.050))),
    (-12.25, dict(t=1.480, k=(0.045, 1.460, 0.020), u=(0.052, 1.400, 0.020))),
], ["t", "k", "u"])

LOWER_ARCS = [5, 5, 1]
LOWER_SEGS = [8, 4, 3]


def lower_corners(z):
    L = LOWER(z)
    lc, bc = L["lc"], L["bc"]
    return [(lc[0], lc[1]), (bc[0], bc[1]), (0.0, L["bot"])], [lc[2], bc[2], 0.0]


def nose_ring(z):
    N = NOSE_TOP(z)
    k = N["k"]
    pts, rs = lower_corners(z)
    half = fillet_path([(0.0, N["t"]), (k[0], k[1])] + pts, [0, k[2]] + rs, arc_n=[1, 6] + LOWER_ARCS, seg_n=[6] + LOWER_SEGS)
    return mirror2(half)


def cockpit_ring(z):
    xs, ys = sill_at(z)
    pts, rs = lower_corners(z)
    half = fillet_path([(xs + 0.015, ys - 0.012)] + pts, [0] + rs, arc_n=[1] + LOWER_ARCS, seg_n=LOWER_SEGS)
    return mirror2(half, closed=False)


def aft_ring(z):
    A = AFT_TOP(z)
    k, u = A["k"], A["u"]
    pts, rs = lower_corners(z)
    half = fillet_path([(0.0, A["t"]), (k[0], k[1]), (u[0], u[1])] + pts, [0, k[2], u[2]] + rs, arc_n=[1, 6, 6] + LOWER_ARCS, seg_n=[6, 8] + LOWER_SEGS)
    return mirror2(half)


def fuselage(M, parent):
    """Three pieces meeting at the canopy's front and rear frames: the closed nose, the open cockpit section, the closed aft body and tail boom."""
    objs = []
    # nose
    m = Mesh()
    zs = spacing(2.18, 0.98, 0.035)
    ids = m.grid([ring3(nose_ring(z), z) for z in zs], closed=True)
    m.cap(ids[0], flip=True)
    objs.append(m.to_object("Fuselage_Nose", [M["paint"]], parent, outward=lambda p: (0, 0.2, p[2])))
    # cockpit section, open at the top for the canopy
    m = Mesh()
    zs = sorted(set(spacing(0.98, -1.84, 0.04) + [-0.14, -0.46]), reverse=True)
    m.grid([ring3(cockpit_ring(z), z) for z in zs], closed=False)
    objs.append(m.to_object("Fuselage_Cockpit", [M["paint"]], parent, outward=lambda p: (0, 0.25, p[2])))
    # aft body and tail boom; the first ring leans forward above the sill to meet the canopy's slanted back
    m = Mesh()
    zs = spacing(-1.84, -5.6, 0.05) + spacing(-5.6, -12.25, 0.12)[1:]
    rings = []
    for i, z in enumerate(zs):
        r = ring3(aft_ring(z), z)
        if i == 0:
            # 5 mm behind the cockpit's rear bulkhead, so the two never fight for the same pixels
            ys = 1.168
            r = [(x, y, z - 0.005 + max(0.0, (y - ys) / (2.02 - ys)) * 0.12) for x, y, _ in r]
        rings.append(r)
    ids = m.grid(rings, closed=True)
    m.cap(ids[0], flip=True)
    m.cap(ids[-1])
    def axis(p):
        z = p[2]
        A, L = AFT_TOP(z), LOWER(z)
        return (0, (A["t"] + L["bot"]) / 2, z)
    objs.append(m.to_object("Fuselage_Aft", [M["paint"]], parent, outward=axis))
    return objs


# ---- extended forward avionics bays (the Longbow's "cheeks") -------------------------------------------------------------
EFAB = table([
    (1.78, dict(top=0.552, bot=0.420, xo=0.400)),
    (1.74, dict(top=0.560, bot=0.300, xo=0.520)),
    (1.66, dict(top=0.560, bot=0.140, xo=0.590)),
    (1.56, dict(top=0.560, bot=-0.030, xo=0.620)),
    (1.46, dict(top=0.560, bot=-0.150, xo=0.628)),
    (1.00, dict(top=0.560, bot=-0.180, xo=0.630)),
    (-1.00, dict(top=0.560, bot=-0.180, xo=0.630)),
    (-1.70, dict(top=0.560, bot=-0.160, xo=0.620)),
    (-1.95, dict(top=0.540, bot=-0.050, xo=0.580)),
    (-2.08, dict(top=0.500, bot=0.100, xo=0.520)),
], ["top", "bot", "xo"])


def efab(M, parent):
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        m = Mesh()
        rings = []
        for z in spacing(1.76, -2.08, 0.04):
            e = EFAB(z)
            xi = 0.37
            pts = [(xi, e["top"]), (e["xo"], e["top"] - 0.008), (e["xo"] - 0.025, e["bot"] + 0.02), (xi, e["bot"] + 0.05)]
            loop = fillet_path(pts, [0.01, 0.03, 0.05, 0.01], arc_n=5, seg_n=[6, 8, 6, 3], closed=True)
            rings.append([(sx * x, y, z) for x, y in loop])
        ids = m.grid(rings, closed=True)
        m.cap(ids[0], flip=True)
        m.cap(ids[-1])
        objs.append(m.to_object(f"Avionics_Bay_{side}", [M["paint"]], parent, outward=lambda p, sx=sx: (sx * 0.5, 0.2, p[2])))
    return objs


# ---- rotor pylon (transmission fairing) --------------------------------------------------------------------------------------------
PYLON = table([
    (-1.72, dict(xt=0.235, yt=2.040, xb=0.280, yb=1.920)),
    (-2.00, dict(xt=0.260, yt=2.180, xb=0.330, yb=1.900)),
    (-2.30, dict(xt=0.270, yt=2.290, xb=0.350, yb=1.900)),
    (-2.60, dict(xt=0.270, yt=2.340, xb=0.360, yb=1.900)),
    (-3.20, dict(xt=0.270, yt=2.350, xb=0.360, yb=1.900)),
    (-3.70, dict(xt=0.250, yt=2.320, xb=0.340, yb=1.880)),
    (-4.20, dict(xt=0.210, yt=2.200, xb=0.300, yb=1.820)),
    (-4.70, dict(xt=0.160, yt=2.000, xb=0.250, yb=1.760)),
    (-5.10, dict(xt=0.120, yt=1.830, xb=0.200, yb=1.720)),
], ["xt", "yt", "xb", "yb"])


def pylon_top(z):
    return PYLON(z)["yt"]


def pylon(M, parent):
    m = Mesh()
    rings = []
    for z in spacing(-1.72, -5.1, 0.04):
        p = PYLON(z)
        loop = fillet_path([(p["xt"], p["yt"]), (p["xb"], p["yb"]), (-p["xb"], p["yb"]), (-p["xt"], p["yt"])], [0.1, 0.02, 0.02, 0.1], arc_n=6, seg_n=[8, 6, 8, 8], closed=True)
        rings.append(ring3(loop, z))
    ids = m.grid(rings, closed=True)
    m.cap(ids[0], flip=True)
    m.cap(ids[-1])
    obj = m.to_object("Rotor_Pylon", [M["paint"]], parent, outward=lambda p: (0, 2.1, p[2]))
    # cooling air grilles either side of the mast (a louvred panel set into each side)
    g = Mesh()
    for sx in (1, -1):
        for i in range(7):
            z = -2.45 - i * 0.07
            p = PYLON(z)
            x = sx * (p["xt"] + 0.035)
            y = p["yt"] - 0.13
            F = Frame((x, y, z), (0, 0, 1), (0, 1, 0), (sx, 0, 0))
            rbox(g, Frame(F.o, F.x, F.y, F.z), (0.045, 0.16, 0.012), 0.004, 1, mat=0)
    grille = g.to_object("Rotor_Pylon_Louvres", [M["dark"]], parent)
    return [obj, grille]


# ---- engine nacelles and the IR-suppressing exhausts -----------------------------------------------------------------------
NAC_X, NAC_Y = 0.82, 1.45
NACELLE = table([
    (-1.92, dict(w=0.262, h=0.262, rt=0.262, rb=0.262)),
    (-2.02, dict(w=0.300, h=0.315, rt=0.270, rb=0.260)),
    (-2.30, dict(w=0.335, h=0.395, rt=0.220, rb=0.170)),
    (-3.00, dict(w=0.345, h=0.405, rt=0.200, rb=0.150)),
    (-3.60, dict(w=0.335, h=0.395, rt=0.200, rb=0.150)),
    (-4.05, dict(w=0.310, h=0.360, rt=0.200, rb=0.140)),
], ["w", "h", "rt", "rb"])


def rrect(cx, cy, w, h, rt, rb, segs=6, arc=6):
    return fillet_path([(cx + w, cy + h), (cx + w, cy - h), (cx - w, cy - h), (cx - w, cy + h)], [rt, rb, rb, rt], arc_n=arc, seg_n=segs, closed=True)


def nacelles(M, parent):
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        node = empty(f"Nacelle_{side}", (sx * NAC_X, NAC_Y, -3.0), parent)
        m = Mesh()
        rings = []
        for z in spacing(-1.92, -4.05, 0.035):
            n = NACELLE(z)
            loop = rrect(sx * NAC_X, NAC_Y, n["w"], n["h"], n["rt"], n["rb"])
            rings.append(ring3(loop, z))
        ids = m.grid(rings, closed=True)
        m.cap(ids[-1])
        objs.append(m.to_object(f"Nacelle_{side}_Skin", [M["paint"]], node, outward=lambda p, sx=sx: (sx * NAC_X, NAC_Y, p[2])))
        # intake: the lip rolls in to a round duct, with the engine's front frame and nose cone inside
        F = Frame((sx * NAC_X, NAC_Y, -1.92), (-1, 0, 0), (0, 1, 0), (0, 0, -1))
        li = Mesh()
        prof = [(0.262, 0.0), (0.261, -0.013), (0.252, -0.026), (0.239, -0.03), (0.226, -0.024), (0.22, -0.008), (0.218, 0.02), (0.216, 0.12), (0.21, 0.3), (0.19, 0.42)]
        lathe(li, F, prof, 40, mat=0)
        lip = li.to_object(f"Nacelle_{side}_Intake", [M["paint"]], node, probe=((sx * NAC_X, NAC_Y + 0.262, -1.93), (0, 1, 0.3)))
        du = Mesh()
        # the duct's back: stator ring and the engine nose cone
        lathe(du, F, [(0.0, 0.27), (0.05, 0.3), (0.07, 0.36), (0.075, 0.43), (0.19, 0.43), (0.19, 0.42)], 32, mat=0)
        for i in range(18):
            a = 2 * math.pi * i / 18
            d = np.array([math.cos(a), math.sin(a), 0.0])
            p0 = F.p(d * 0.078 + np.array([0, 0, 0.415]))
            p1 = F.p(d * 0.186 + np.array([0, 0, 0.415]))
            t = np.cross(d, (0, 0, 1))
            G = Frame(F.p(d * 0.132 + np.array([0, 0, 0.415])), F.d(t * 0.6 + np.array([0, 0, 0.8])), F.d(d), F.d(np.cross(t * 0.6 + np.array([0, 0, 0.8]), d)))
            rbox(du, G, (0.05, 0.108, 0.006), 0.002, 1, mat=0)
        duct = du.to_object(f"Nacelle_{side}_Engine_Face", [M["engine"]], node)
        objs += [lip, duct]
        # nacelle mount: a fairing from the nacelle's inboard underside to the fuselage shoulder
        fm = Mesh()
        rings = []
        for z in spacing(-2.2, -3.9, 0.1):
            w = 0.1 if -3.7 < z < -2.4 else 0.05
            loop = fillet_path([(0.72, 1.18), (0.44, 1.26), (0.44, 1.02), (0.70, 1.06)], [0.05, 0.02, 0.02, 0.05], arc_n=4, seg_n=3, closed=True)
            rings.append([(sx * x, y + (0.1 - w) * 0.3, z) for x, y in loop])
        ids = fm.grid(rings, closed=True)
        fm.cap(ids[0], flip=True)
        fm.cap(ids[-1])
        objs.append(fm.to_object(f"Nacelle_{side}_Mount", [M["paint"]], node, outward=lambda p, sx=sx: (sx * 0.58, 1.13, p[2])))
        objs += exhaust(M, node, side, sx)
    return objs


def bez(p0, p1, p2, t):
    p0, p1, p2 = map(np.asarray, (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2


def exhaust(M, node, side, sx):
    """The "Black Hole" suppressor: the duct leaves the nacelle's tail and turns outboard, its exit facing out and aft."""
    p0, p1, p2 = (sx * 0.82, 1.45, -4.02), (sx * 0.85, 1.44, -4.36), (sx * 1.05, 1.39, -4.67)
    n = 16
    rings, frames = [], []
    for i in range(n + 1):
        t = i / n
        c = bez(p0, p1, p2, t)
        tan = norm(bez(p0, p1, p2, min(1, t + 0.01)) - bez(p0, p1, p2, max(0, t - 0.01)))
        F = Frame.along(c, tan, (0, 1, 0))
        hw, hh = 0.245 - 0.07 * t, 0.29 - 0.07 * t
        r = 0.12 - 0.05 * t
        loop = fillet_path([(hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)], [r] * 4, arc_n=5, seg_n=4, closed=True)
        rings.append([F.p((x, y, 0)) for x, y in loop])
        frames.append((F, hw, hh, r))
    m = Mesh()
    m.grid(rings, closed=True, mat=0)
    # the exit: a lip, then the sooty inside
    F, hw, hh, r = frames[-1]
    # counter-clockwise about the exit, so the lip faces out and the walls face in
    inner = []
    for inset, back in ((0.0, 0.0), (0.018, 0.0), (0.022, 0.02), (0.022, 0.18)):
        loop = fillet_path([(hw - inset, hh - inset), (hw - inset, -hh + inset), (-hw + inset, -hh + inset), (-hw + inset, hh - inset)], [max(0.01, r - inset)] * 4, arc_n=5, seg_n=4, closed=True)[::-1]
        inner.append([F.p((x, y, -back)) for x, y in loop])
    ids = m.grid(inner, closed=True, mat=1, orient=False)
    m.cap(ids[-1], mat=1)
    duct = m.to_object(f"Exhaust_{side}", [M["paint"], M["exhaust"]], node)
    # cooling-air scoop on top of the suppressor
    sm = Mesh()
    c = bez(p0, p1, p2, 0.35)
    G = Frame.along(c + np.array([0, 0.22, 0]), (sx * 0.12, -0.06, -1.0), (0, 1, 0))
    rbox(sm, G, (0.2, 0.07, 0.3), 0.025, 2, mat=0)
    rbox(sm, Frame(G.p((0, 0.0, 0.14)), G.x, G.y, G.z), (0.17, 0.045, 0.02), 0.005, 1, mat=1)
    scoop = sm.to_object(f"Exhaust_{side}_Scoop", [M["paint"], M["exhaust"]], node)
    return [duct, scoop]


# ---- stub wings, weapon pylons ------------------------------------------------------------------------------------------------------
WING = table([
    (0.45, dict(c=1.06, le=-2.150, y=0.645, t=0.160)),
    (1.20, dict(c=0.99, le=-2.180, y=0.628, t=0.150)),
    (2.00, dict(c=0.92, le=-2.200, y=0.612, t=0.135)),
    (2.556, dict(c=0.86, le=-2.220, y=0.600, t=0.120)),
], ["c", "le", "y", "t"])
INCIDENCE = math.radians(2.5)


def wing_section(x, sx=1):
    w = WING(x)
    c = w["c"]
    pts = []
    for u, v in airfoil(w["t"] / c, 18):
        z = w["le"] - u * c
        y = w["y"] + v * c
        # nose-up incidence about the quarter chord
        zq = w["le"] - 0.25 * c
        dz, dy = z - zq, y - w["y"]
        z2 = zq + dz * math.cos(INCIDENCE) - dy * math.sin(INCIDENCE)
        y2 = w["y"] + dz * math.sin(INCIDENCE) + dy * math.cos(INCIDENCE)
        pts.append((sx * x, y2, z2))
    return pts


def wing_lower_y(x, z):
    """y of the wing's lower surface at (x, z), roughly - for hanging things under it."""
    w = WING(x)
    u = (w["le"] - z) / w["c"]
    t = w["t"] / w["c"]
    yt = 5 * t * (0.2969 * math.sqrt(max(u, 0)) - 0.126 * u - 0.3516 * u**2 + 0.2843 * u**3 - 0.1036 * u**4)
    return w["y"] - yt * w["c"] + (w["le"] - 0.25 * w["c"] - z) * math.sin(INCIDENCE)


def wings(M, parent):
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        node = empty(f"Wing_{side}", (sx * 1.5, WING_Y, WING_Z), parent)
        m = Mesh()
        ids = m.grid([wing_section(x, sx) for x in spacing(0.45, 2.556, 0.08)], closed=True)
        m.cap(ids[0], flip=True)
        m.cap(ids[-1])
        objs.append(m.to_object(f"Wing_{side}_Skin", [M["paint"]], node, outward=lambda p, sx=sx: (p[0], WING_Y, -2.62)))
        # wingtip station: the launcher rail fairing, which carries the navigation light
        tm = Mesh()
        F = Frame((sx * (WING_TIP_X - 0.03), 0.6, -2.62), (sx, 0, 0), (0, 1, 0), (0, 0, 1))
        rbox(tm, Frame(F.o, (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.06, 0.13, 0.9), 0.025, 3)
        rbox(tm, Frame(F.p((0, -0.085, -0.05)), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.035, 0.05, 0.62), 0.01, 2)
        objs.append(tm.to_object(f"Wing_{side}_Tip_Station", [M["paint"]], node))
        objs += weapon_pylons(M, node, side, sx)
    return objs


def weapon_pylons(M, node, side, sx):
    objs = []
    for where, px in (("Inboard", PYLON_INBOARD_X), ("Outboard", PYLON_OUTBOARD_X)):
        m = Mesh()
        top = wing_lower_y(px, -2.62) + 0.03
        bot = 0.36
        secs = []
        for y in np.linspace(bot, top, 6):
            c, le, t = 0.86, -2.2, 0.085
            loop = airfoil(t / c, 14)
            secs.append([(sx * px + v * c, y, le - u * c) for u, v in loop])
        ids = m.grid(secs, closed=True)
        m.cap(ids[0], flip=True)
        m.cap(ids[-1])
        # ejector rack along the bottom, with sway-brace pads
        rbox(m, Frame((sx * px, 0.345, -2.63)), (0.09, 0.05, 0.78), 0.012, 2, mat=1)
        for dz in (-0.25, 0.25):
            for dx in (-0.055, 0.055):
                tube(m, (sx * px + dx, 0.34, -2.63 + dz), (sx * px + dx * 1.6, 0.30, -2.63 + dz), 0.009, 8, mat=1)
        objs.append(m.to_object(f"Pylon_{side}_{where}", [M["paint"], M["mech"]], node, outward=None))
    return objs


# ---- tail: fin, stabilator, drive-shaft cover, tail rotor gearbox fairing -------------------------------------------------
FIN = table([
    (0.46, dict(le=-11.62, te=-12.35, t=0.100)),
    (0.80, dict(le=-11.42, te=-12.43, t=0.110)),
    (1.05, dict(le=-11.20, te=-12.43, t=0.118)),
    (1.30, dict(le=-10.80, te=-12.43, t=0.124)),
    (1.60, dict(le=-10.40, te=-12.43, t=0.130)),
    (2.00, dict(le=-10.78, te=-12.43, t=0.122)),
    (2.30, dict(le=-11.07, te=-12.37, t=0.110)),
    (2.55, dict(le=-11.31, te=-12.27, t=0.098)),
    (2.68, dict(le=-11.43, te=-12.20, t=0.088)),
], ["le", "te", "t"])


def fin_section(y, shrink=1.0):
    f = FIN(y)
    c = f["le"] - f["te"]
    return [(v * c * shrink, y, f["le"] - (u * c)) for u, v in airfoil(f["t"] / c, 20)]


def tail(M, parent):
    node = empty("Tail", (0, 1.5, -11.8), parent)
    objs = []
    m = Mesh()
    ys = list(np.linspace(0.46, 2.68, 26))
    secs = [fin_section(y) for y in ys]
    # round the tip over
    f = FIN(2.68)
    top = [(x * 0.55, 2.705, z * 0.98 + f["le"] * 0.02) for x, _, z in secs[-1]]
    secs.append(top)
    ids = m.grid(secs, closed=True)
    m.cap(ids[0], flip=True)
    m.cap(ids[-1])
    objs.append(m.to_object("Fin", [M["paint"]], node, outward=lambda p: (0, p[1], -11.9)))
    # stabilator: all-moving, through the lower fin
    sm = Mesh()
    secs = []
    for x in np.linspace(-1.70, 1.70, 21):
        a = abs(x) / 1.70
        c = 0.86 - 0.16 * a
        le = -11.52 - 0.08 * a
        t = 0.11 - 0.02 * a
        secs.append([(x, 0.72 + v * c, le - u * c) for u, v in airfoil(t / c, 16)])
    ids = sm.grid(secs, closed=True)
    sm.cap(ids[0], flip=True)
    sm.cap(ids[-1])
    objs.append(sm.to_object("Stabilator", [M["paint"]], node, outward=lambda p: (p[0], 0.72, -11.9)))
    # tail rotor gearbox fairing, on the fin's left at the top
    gm = Mesh()
    F = Frame((0.02, TAIL_HUB[1], TAIL_HUB[2]), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    lathe(gm, F, [(0.0, 0.0), (0.16, 0.0), (0.17, 0.05), (0.15, 0.13), (0.10, 0.19), (0.06, 0.215), (0.0, 0.22)], 28)
    rbox(gm, Frame((0.03, TAIL_HUB[1] + 0.2, TAIL_HUB[2] + 0.08), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.12, 0.3, 0.42), 0.05, 3)
    objs.append(gm.to_object("Tail_Rotor_Gearbox_Fairing", [M["paint"]], node))
    # tail rotor drive-shaft cover along the top of the boom, and the intermediate gearbox fairing at the fin
    dm = Mesh()
    rings = []
    for z in spacing(-4.75, -10.45, 0.1):
        t = AFT_TOP(z)["t"]
        loop = fillet_path([(0.075, t + 0.055), (0.085, t - 0.02), (-0.085, t - 0.02), (-0.075, t + 0.055)], [0.03, 0.005, 0.005, 0.03], arc_n=4, seg_n=2, closed=True)
        rings.append(ring3(loop, z))
    ids = dm.grid(rings, closed=True)
    dm.cap(ids[0], flip=True)
    dm.cap(ids[-1])
    rbox(dm, Frame.along((0, 1.66, -10.42), (0, 0.55, -1)), (0.2, 0.16, 0.42), 0.06, 3)
    objs.append(dm.to_object("Drive_Shaft_Cover", [M["paint"]], node, outward=lambda p: (0, 1.5, p[2])))
    return objs


# ---- canopy -------------------------------------------------------------------------------------------------------------------------
def Lf(k):
    return np.asarray(CAN[k], float)


def Rt(k):
    return np.asarray(mir(CAN[k]), float)


PANES = {
    "windscreen": ["A", "A'", "B'", "B"],
    "frontRoof": ["B", "B'", "C'", "C"],
    "pilotScreen": ["C", "C'", "D'", "D"],
    "rearRoof": ["D", "D'", "E'", "E"],
    "frontLeft": ["A", "B", "C", "Q"],
    "rearLeft": ["Q", "C", "D", "E", "R2", "R1"],
    "frontRight": ["A'", "B'", "C'", "Q'"],
    "rearRight": ["Q'", "C'", "D'", "E'", "R2'", "R1'"],
}


def P(k):
    return Rt(k[:-1]) if k.endswith("'") else Lf(k)


CAN_CTR = np.array([0, 1.05, -0.4])


def pane_normal(name):
    pts = [P(k) for k in PANES[name]]
    c = np.mean(pts, axis=0)
    n = norm(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
    return n if np.dot(n, c - CAN_CTR) > 0 else -n


# frame members: (from, to, panes it borders)
MEMBERS = [
    ("A", "A'", ["windscreen"]), ("A", "B", ["windscreen", "frontLeft"]), ("A'", "B'", ["windscreen", "frontRight"]),
    ("B", "B'", ["windscreen", "frontRoof"]), ("B", "C", ["frontRoof", "frontLeft"]), ("B'", "C'", ["frontRoof", "frontRight"]),
    ("C", "C'", ["frontRoof", "pilotScreen"]), ("C", "Q", ["frontLeft", "rearLeft"]), ("C'", "Q'", ["frontRight", "rearRight"]),
    ("C", "D", ["pilotScreen", "rearLeft"]), ("C'", "D'", ["pilotScreen", "rearRight"]), ("D", "D'", ["pilotScreen", "rearRoof"]),
    ("D", "E", ["rearRoof", "rearLeft"]), ("D'", "E'", ["rearRoof", "rearRight"]), ("E", "E'", ["rearRoof"]),
    ("E", "R2", ["rearLeft"]), ("E'", "R2'", ["rearRight"]),
    ("A", "Q", ["frontLeft"]), ("Q", "R1", ["rearLeft"]), ("R1", "R2", ["rearLeft"]),
]
DOOR_SILLS = {"Canopy_Door_CPG": [("A'", "Q'")], "Canopy_Door_Pilot": [("Q'", "R1'"), ("R1'", "R2'")]}
FW, FT = 0.058, 0.042  # frame member width and depth


def member(m, a, b, n, w=FW, t=FT, extend=0.03, mat_out=0, mat_in=1):
    """A canopy frame member from a to b, its depth along n (outward): painted outside, dark inside."""
    d = norm(b - a)
    y = norm(n - d * np.dot(n, d))
    x = np.cross(y, d)
    c = (a + b) / 2 + y * 0.004
    F = Frame(c, x, y, d)
    tmp = Mesh()
    rbox(tmp, F, (w, t, np.linalg.norm(b - a) + extend * 2), 0.008, 2)
    # outer-facing faces take the paint
    for f in range(len(tmp.f)):
        vs = [np.asarray(tmp.v[i]) for i in tmp.f[f]]
        fn = np.cross(vs[1] - vs[0], vs[2] - vs[0])
        tmp.fm[f] = mat_out if np.dot(fn, y) > -1e-9 else mat_in
    m.extend(tmp)


def canopy(M, parent):
    node = empty("Canopy", (0, 1.4, -0.4), parent)
    N = {k: pane_normal(k) for k in PANES}
    glass = Mesh()
    for k in ["windscreen", "frontRoof", "pilotScreen", "rearRoof", "frontLeft", "rearLeft"]:
        ids = glass.verts([P(p) for p in PANES[k]])
        glass.face(ids)
    g = glass.to_object("Canopy_Glass", [M["glass"]], node, smooth=False, per_face=lambda p: CAN_CTR)
    fr = Mesh()
    sills = {s for v in DOOR_SILLS.values() for s in v}
    for a, b, ps in MEMBERS:
        if (a, b) in sills:
            continue
        n = norm(sum(N[p] for p in ps))
        member(fr, P(a), P(b), n)
    frame = fr.to_object("Canopy_Frame", [M["paint"], M["interior"]], node, smooth=True, sharp_angle=40)
    objs = [g, frame]
    doors = {}
    for name, fn, pane, ha, hb in (("Canopy_Door_CPG", "doorCpg", "frontRight", "B'", "C'"), ("Canopy_Door_Pilot", "doorPilot", "rearRight", "C'", "E'")):
        a, b = P(ha), P(hb)
        x = norm(b - a)
        z = norm(np.cross(x, N[pane]))
        y = np.cross(z, x)
        F = Frame((a + b) / 2, x, y, z)
        d = empty(name, F.o, node)
        # orient the pivot so its local axes are the hinge frame (local X along the hinge; +angle opens it up and out)
        from mathutils import Matrix
        from geom import B
        mat = Matrix.Identity(4)
        # Blender's local +Y and +Z are glTF's -Z and +Y: columns chosen so the exported node's axes are the hinge frame
        for col, v in enumerate((F.x, -F.z, F.y)):
            bv = B(v)
            for row in range(3):
                mat[row][col] = bv[row]
        bo = B(F.o)
        for row in range(3):
            mat[row][3] = bo[row]
        d.matrix_world = mat
        bpy.context.view_layer.update()
        gm = Mesh()
        ids = gm.verts([P(p) for p in PANES[pane]])
        gm.face(ids)
        dg = gm.to_object(f"{name}_Glass", [M["glass"]], None, smooth=False, per_face=lambda p: CAN_CTR)
        set_parent(dg, d)
        fm = Mesh()
        for a2, b2 in DOOR_SILLS[name]:
            member(fm, P(a2), P(b2), N[pane], w=FW * 0.95)
        # latch handle outside, and the jettison marking panel is painted on
        s0, s1 = P(DOOR_SILLS[name][-1][0]), P(DOOR_SILLS[name][-1][1])
        hp = (s0 + s1) / 2 + N[pane] * 0.03 + np.array([0, 0.07, 0])
        tube(fm, hp + np.array([0, 0, -0.06]), hp + np.array([0, 0, 0.06]), 0.009, 10, mat=2)
        df = fm.to_object(f"{name}_Frame", [M["paint"], M["interior"], M["mech"]], None, smooth=True, sharp_angle=40)
        bpy.context.view_layer.update()
        set_parent(df, d)
        doors[name] = d
        objs += [dg, df]
    # upper wire-strike cutter above the front roof, and wipers on both windscreens
    wm = Mesh()
    prism(wm, Frame((0, 1.52, 0.05), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(-0.2, -0.07), (0.16, -0.07), (0.28, 0.02), (0.1, 0.1), (-0.16, 0.06)], 0.012)
    for base, top in ((np.array([0.12, 0.85, 0.955]), np.array([0.02, 1.25, 0.72])), (np.array([0.1, 1.52, -0.19]), np.array([0.02, 1.88, -0.45]))):
        tube(wm, base, top, 0.006, 8, mat=0)
        tube(wm, base + np.array([-0.012, 0, 0.006]), top + np.array([-0.012, 0, 0.006]), 0.004, 6, mat=1)
    objs.append(wm.to_object("Wire_Cutter_Upper", [M["mech"], M["rubber"]], node))
    return objs, doors
