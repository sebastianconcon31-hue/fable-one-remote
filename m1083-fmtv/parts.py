"""The M1083 FMTV's outside: the flat-fronted cab over the engine with its
split windshield, grille, brush guards and steps, doors and mirrors; the
front fenders, bumper and winch; frame, axles and the six wheels on
395/85R20 tyres; the air intake and exhaust stack behind the cab, the spare
tyre, fuel tank and battery box; the drop-side cargo body with its
tailgate; and six pallet loads of supplies.

Moving parts:
  Door_{Left,Right} swing about local Y; Tailgate drops about local X
  Wheel_{1-3}_{Left,Right} spin about local X; Steer_1_{Left,Right} steer about local Y
  Cargo_Pallet_{1-6} each load can be lifted off on its own"""
import math
import os
import sys
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm, fillet_path
from running_gear import loft, slab, bolt, tyre
from vehicle import drive
from fmtv import *

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hemtt-m977"))  # last, so this folder's markings.py wins
import truck  # the pallet and strap builders the HEMTT's loads use

deg = math.pi / 180
SIDE = Frame((0, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0))


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


# ---- cab -----------------------------------------------------------------------------------------------------------------------
def cab(M, parent):
    node = empty("Cab", (0, 2.1, 2.1), parent)
    objs = []
    m = Mesh()
    F, Bk = CAB_FRONT_Z, CAB_BACK_Z
    prof = [(F, CAB_FLOOR_Y), (F, 1.98), (F - 0.08, CAB_ROOF_Y - 0.03), (Bk + 0.05, CAB_ROOF_Y), (Bk, CAB_ROOF_Y - 0.05), (Bk, CAB_FLOOR_Y)]
    loft(m, SIDE, [(-CAB_HALF_W, prof), (CAB_HALF_W, prof)], radii=[0.02, 0.03, 0.06, 0.05, 0.03, 0.02], bevel=0.05)
    # roof hatch ring and a visor over the windshield
    lathe(m, Yframe((-0.45, CAB_ROOF_Y - 0.03, 1.7)), [(0.3, 0.0), (0.38, 0.0), (0.38, 0.025), (0.3, 0.028)], 36)  # the roof hatch, flush
    lathe(m, Yframe((-0.45, CAB_ROOF_Y - 0.035, 1.7)), [(0.0, 0.0), (0.3, 0.0), (0.3, 0.025), (0.0, 0.03)], 36)
    objs.append(m.to_object("Cab_Shell", [M["paint"]], node, sharp_angle=40))
    # windshield: two panes leaning back, their seals; the dark cab behind them
    w, g, k = Mesh(), Mesh(), Mesh()
    slope = math.atan2(0.08, CAB_ROOF_Y - 0.03 - 1.98)
    for sx in (1, -1):
        x0, x1 = sx * 0.05, sx * 1.02
        y0, y1 = 2.04, CAB_ROOF_Y - 0.12
        z0 = F - (y0 - 1.98) * math.tan(slope)
        z1 = F - (y1 - 1.98) * math.tan(slope)
        P = [np.array([x0, y0, z0 + 0.004]), np.array([x1, y0, z0 + 0.004]), np.array([x1, y1, z1 + 0.004]), np.array([x0, y1, z1 + 0.004])]
        g.face(g.verts(P))
        k.face(k.verts([p - np.array([0, 0, 0.006]) for p in P]))
        for p0, p1 in zip(P, P[1:] + P[:1]):
            tube(w, p0, p1, 0.014, 6, mat=1)
    rbox(w, Frame((0, (2.04 + CAB_ROOF_Y - 0.12) / 2, F - 0.03), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.08, CAB_ROOF_Y - 2.12, 0.04), 0.01, 1)
    # rear window
    for sx in (1, -1):
        P = [np.array([sx * 0.2, 2.25, Bk - 0.004]), np.array([sx * 0.7, 2.25, Bk - 0.004]), np.array([sx * 0.7, 2.6, Bk - 0.004]), np.array([sx * 0.2, 2.6, Bk - 0.004])]
        g.face(g.verts(P))
        k.face(k.verts([p + np.array([0, 0, 0.004]) for p in P]))
    inside = lambda p: (0.0, 2.1, 2.1)
    objs.append(w.to_object("Cab_Window_Seals", [M["paint"], M["rubber"]], node, sharp_angle=40))
    objs.append(g.to_object("Cab_Glass", [M["glass"]], node, smooth=False, per_face=inside))
    objs.append(k.to_object("Cab_Window_Backing", [M["interior"]], node, smooth=False, per_face=inside))
    # the grille below the windshield and the wipers
    gr = Mesh()
    slab(gr, Frame((0, 1.68, F + 0.012), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.7, -0.28), (0.7, -0.28), (0.7, 0.28), (-0.7, 0.28)], 0.024, 0.008)
    for j in range(8):
        box(gr, (0, 1.45 + j * 0.065, F + 0.026), (1.3, 0.025, 0.012), 0.004, 1, mat=1)
    for x0 in (0.55, -0.45):
        tube(gr, (x0, 2.05, F + 0.01), (x0 + 0.08, 2.55, F - 0.02), 0.008, 6, mat=1)
    objs.append(gr.to_object("Grille", [M["paint"], M["chassis"]], node, sharp_angle=40))
    objs += doors(M, node)
    objs += cab_trim(M, node)
    return objs


def doors(M, parent):
    objs = []
    z0, z1 = CAB_BACK_Z + 1.3, CAB_BACK_Z + 0.08
    y0, y1 = CAB_FLOOR_Y + 0.05, CAB_ROOF_Y - 0.1
    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * (CAB_HALF_W + 0.012)
        d = empty(f"Door_{side}", (x, (y0 + y1) / 2, z0), parent)
        drive(d, "a cab door: swings about local Y on its front hinges; + opens it outward (to 80 degrees)", control="hinge",
              axis=[0, -1 if sx > 0 else 1, 0], limits=[0, 1.4], group="Doors")
        m = Mesh()
        Fd = Frame((x, (y0 + y1) / 2, (z0 + z1) / 2), (0, 0, 1), (0, 1, 0), (sx, 0, 0))
        slab(m, Fd, [(-(z0 - z1) / 2, -(y1 - y0) / 2), ((z0 - z1) / 2, -(y1 - y0) / 2), ((z0 - z1) / 2, (y1 - y0) / 2), (-(z0 - z1) / 2, (y1 - y0) / 2)], 0.045, 0.012)
        wz0, wz1, wy0, wy1 = z0 - 0.1, z1 + 0.1, 2.08, y1 - 0.08
        P = [np.array([x + sx * 0.024, wy0, wz0]), np.array([x + sx * 0.024, wy0, wz1]), np.array([x + sx * 0.024, wy1, wz1]), np.array([x + sx * 0.024, wy1, wz0])]
        for p0, p1 in zip(P, P[1:] + P[:1]):
            tube(m, p0, p1, 0.011, 6, mat=2)
        tube(m, (x + sx * 0.035, 1.95, z1 + 0.1), (x + sx * 0.035, 1.95, z1 + 0.28), 0.01, 8, mat=1)
        for hy in (1.6, 2.3):
            lathe(m, Yframe((x + sx * 0.025, hy - 0.06, z0 + 0.01)), [(0.0, 0.0), (0.025, 0.0), (0.025, 0.12), (0.0, 0.12)], 10, mat=1)
        o = m.to_object(f"Door_{side}_Panel", [M["paint"], M["chassis"], M["rubber"]], None, sharp_angle=40)
        set_parent(o, d)
        gm, km = Mesh(), Mesh()
        gm.face(gm.verts([p + np.array([sx * 0.004, 0, 0]) for p in P]))
        km.face(km.verts([p - np.array([sx * 0.004, 0, 0]) for p in P]))
        inside = lambda p: (0.0, 2.1, 2.1)
        go = gm.to_object(f"Door_{side}_Glass", [M["glass"]], None, smooth=False, per_face=inside)
        bo = km.to_object(f"Door_{side}_Window_Backing", [M["interior"]], None, smooth=False, per_face=inside)
        for ob in (go, bo):
            set_parent(ob, d)
        objs += [o, go, bo]
    return objs


def cab_trim(M, parent):
    """Mirrors, grab handles and the steps up to the doors."""
    m, mg = Mesh(), Mesh()
    for sx in (1, -1):
        base = np.array([sx * (CAB_HALF_W - 0.02), 2.35, CAB_FRONT_Z - 0.1])
        head = np.array([sx * 1.44, 2.25, CAB_FRONT_Z - 0.04])
        path_tube(m, [base, base + np.array([sx * 0.12, 0.05, 0.03]), head - np.array([sx * 0.04, -0.15, 0])], 0.016, 8, mat=1)
        path_tube(m, [base - np.array([0, 0.45, 0]), base - np.array([0, 0.45, 0]) + np.array([sx * 0.14, 0.08, 0.02]), head - np.array([sx * 0.04, 0.15, 0])], 0.014, 8, mat=1)
        rbox(m, Zframe(head), (0.09, 0.42, 0.06), 0.022, 2, mat=1)
        mg.face(mg.verts([head + np.array([sx * dx, dy, -0.0305]) for dx, dy in ((-0.035, -0.18), (0.035, -0.18), (0.035, 0.18), (-0.035, 0.18))]))
        path_tube(m, [np.array([sx * (CAB_HALF_W - 0.01), 1.6, CAB_BACK_Z + 0.05]), np.array([sx * (CAB_HALF_W + 0.04), 1.62, CAB_BACK_Z + 0.05]), np.array([sx * (CAB_HALF_W + 0.04), 2.4, CAB_BACK_Z + 0.05]), np.array([sx * (CAB_HALF_W - 0.01), 2.42, CAB_BACK_Z + 0.05])], 0.014, 8, mat=1)
        for k, y in enumerate((0.75, 1.05)):
            box(m, (sx * (0.98 + 0.04 * k), y, CAB_BACK_Z + 0.65), (0.24, 0.035, 0.34), 0.008, 1, mat=1)
        for dz in (-0.16, 0.16):
            tube(m, (sx * 0.97, 0.72, CAB_BACK_Z + 0.65 + dz), (sx * 1.03, CAB_FLOOR_Y, CAB_BACK_Z + 0.65 + dz), 0.014, 8, mat=1)
    return [m.to_object("Mirrors_And_Trim", [M["paint"], M["chassis"]], parent, sharp_angle=45),
            mg.to_object("Mirror_Glass", [M["mirror"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] + 1.0))]


# ---- front end, frame, wheels ------------------------------------------------------------------------------------------------
def front(M, parent):
    node = empty("Front_End", (0, 0.9, FRONT_Z - 0.2), parent)
    objs = []
    m = Mesh()
    zf = FRONT_Z
    rbox(m, Zframe((0, 0.86, zf - 0.13)), (2.3, 0.34, 0.26), 0.03, 2)
    for sx in (1, -1):
        lathe(m, Frame((sx * 0.55, 0.7, zf - 0.08), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.035, -0.035), (0.07, -0.035), (0.07, 0.035), (0.035, 0.035), (0.035, -0.035)], 16, mat=1)
    # front fenders: flat plates over the wheels off the cab's sides, their mud flaps
    for sx in (1, -1):
        f = Mesh()
        x0, x1 = sx * 0.62, sx * (HALF_W - 0.01)
        zc, L = AXLES_Z[0] + 0.05, 1.5
        box(f, ((x0 + x1) / 2, 1.3, zc), (abs(x1 - x0), 0.03, L), 0.008, 1)
        box(f, (x1 - sx * 0.01, 1.2, zc), (0.025, 0.2, L), 0.006, 1)
        objs.append(f.to_object(f"Fender_{side_name(sx)}", [M["paint"]], node, sharp_angle=45))
        mf = Mesh()
        box(mf, (sx * 0.98, 0.82, zc - L / 2 - 0.02), (0.42, 0.62, 0.012), 0.004, 1)
        objs.append(mf.to_object(f"Mud_Flap_Front_{side_name(sx)}", [M["rubber"]], node))
    objs.append(m.to_object("Bumper", [M["paint"], M["chassis"]], node, sharp_angle=45))
    return objs


def side_name(sx):
    return "Left" if sx > 0 else "Right"


def chassis(M, parent):
    node = empty("Chassis", (0, 0.9, -0.5), parent)
    m = Mesh()
    z_hi, z_lo = FRONT_Z - 0.25, REAR_Z + 0.2
    for sx in (1, -1):
        F = Frame((sx * RAIL_X, (RAIL_Y0 + RAIL_Y1) / 2, (z_hi + z_lo) / 2), (sx, 0, 0), (0, 1, 0), (0, 0, 1) if sx > 0 else (0, 0, -1))
        h, t, fl = RAIL_Y1 - RAIL_Y0, 0.01, 0.08
        c = [(0, -h / 2), (0, h / 2), (-fl, h / 2), (-fl, h / 2 - t), (-t, h / 2 - t), (-t, -h / 2 + t), (-fl, -h / 2 + t), (-fl, -h / 2)]
        prism(m, Frame(F.o, F.x, F.y, F.z), c, z_hi - z_lo)
    for z in np.arange(z_hi - 0.2, z_lo, -1.0):
        box(m, (0, 1.06, z), (2 * RAIL_X - 0.02, 0.18, 0.07), 0.01, 1)
    for k, za in enumerate(AXLES_Z):
        tube(m, (WHEEL_X - 0.18, TYRE_R, za), (-WHEEL_X + 0.18, TYRE_R, za), 0.07, 16)
        lathe(m, Zframe((0.05, TYRE_R, za - 0.17)), [(0.0, 0.0), (0.11, 0.02), (0.18, 0.1), (0.2, 0.18), (0.18, 0.28), (0.11, 0.34), (0.0, 0.35)], 22)
        for sx in (1, -1):
            for j in range(5):
                box(m, (sx * 0.62, 0.74 + j * 0.016, za), (0.09, 0.014, 1.0 - j * 0.14), 0.004, 1)
            tube(m, (sx * 0.72, TYRE_R + 0.05, za + 0.15), (sx * 0.5, 1.0, za + 0.2), 0.032, 10)
    tube(m, (WHEEL_X - 0.22, TYRE_R + 0.12, AXLES_Z[0] - 0.15), (-WHEEL_X + 0.22, TYRE_R + 0.12, AXLES_Z[0] - 0.15), 0.022, 8)
    rbox(m, Zframe((0, 0.82, 0.6)), (0.45, 0.38, 0.45), 0.04, 2)
    for za in AXLES_Z:
        tube(m, (0.0, 0.82, 0.6), (0.05, TYRE_R + 0.05, za + (0.2 if za < 0.6 else -0.2)), 0.04, 12)
    return [m.to_object("Frame_And_Running_Gear", [M["chassis"]], node, sharp_angle=50)]


def wheels(M, parent):
    node = empty("Wheels", (0, TYRE_R, 0), parent)
    objs = []
    for i, za in enumerate(AXLES_Z):
        for side, sx in (("Left", 1), ("Right", -1)):
            c = (sx * WHEEL_X, TYRE_R, za)
            holder = node
            if i == 0:
                holder = empty(f"Steer_1_{side}", c, node)
                drive(holder, "steer about local Y; + turns left", control="steer", axis=[0, 1, 0], limits=[-0.6, 0.6])
            w = empty(f"Wheel_{i + 1}_{side}", c, holder)
            drive(w, "spin about local X; + rolls the truck forward", control="wheel", axis=[1, 0, 0], radius=round(TYRE_R, 4))
            m = Mesh()
            tyre(m, c, sx, TYRE_R, TYRE_W, 0.254, blocks=30, block=(0.4, 0.034, 0.1), chevron=20, studs=10)
            objs.append(m.to_object(f"Wheel_{i + 1}_{side}_Mesh", [M["rubber"], M["chassis"]], w, sharp_angle=60))
    return objs


# ---- behind the cab -----------------------------------------------------------------------------------------------------------
def mid_body(M, parent):
    """The air intake and exhaust stack behind the cab, the spare tyre, fuel tank and battery box."""
    node = empty("Mid_Body", (0, 1.5, 0.9), parent)
    objs = []
    m = Mesh()
    zb = (CAB_BACK_Z + BED_FRONT_Z) / 2
    rbox(m, Zframe((0.82, 2.2, zb)), (0.4, 0.9, 0.36), 0.05, 2)
    path_tube(m, [np.array([0.82, 2.6, zb]), np.array([0.82, 2.68, zb]), np.array([0.82, 2.71, zb + 0.12])], 0.1, 16)
    ex = [np.array([-0.95, 1.3, zb]), np.array([-0.95, 2.7, zb]), np.array([-0.95, 2.76, zb - 0.06]), np.array([-0.95, 2.77, zb - 0.16])]
    path_tube(m, ex, 0.06, 14, mat=2, caps=False)
    tube(m, (-0.95, 1.8, zb), (-0.95, 2.62, zb), 0.085, 18)
    objs.append(m.to_object("Intake_And_Exhaust", [M["paint"], M["chassis"], M["exhaust"]], node, sharp_angle=45))
    t = Mesh()
    rings = []
    for z in np.linspace(0.3, -0.85, 2):
        loop = fillet_path([(HALF_W - 0.06, 1.18), (HALF_W - 0.06, 0.72), (0.62, 0.72), (0.62, 1.18)], [0.18, 0.18, 0.04, 0.04], arc_n=6, seg_n=3, closed=True)
        rings.append([(x, y, z) for x, y in loop])
    ids = t.grid(rings, closed=True)
    t.cap(ids[0], flip=True)
    t.cap(ids[-1])
    lathe(t, Yframe((0.95, 1.18, 0.0)), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.07, 0.05), (0.07, 0.08), (0.0, 0.085)], 16, mat=1)
    for z in (0.15, -0.7):
        box(t, (0.9, 1.2, z), (0.6, 0.025, 0.05), 0.006, 1, mat=1)
    objs.append(t.to_object("Fuel_Tank", [M["paint"], M["chassis"]], node, sharp_angle=50))
    b = Mesh()
    rbox(b, Zframe((-0.92, 0.98, -0.25)), (0.48, 0.48, 0.9), 0.03, 2)
    for dz in (-0.25, 0.25):
        box(b, (-1.163, 1.1, -0.25 + dz), (0.012, 0.06, 0.05), 0.004, 1, mat=1)
    objs.append(b.to_object("Battery_Box", [M["paint"], M["chassis"]], node, sharp_angle=45))
    # spare tyre on its carrier between the cab and the body, upright, on the left
    sc = (0.25, BED_FLOOR_Y + 0.02 + TYRE_R, zb + 0.02)
    sp = empty("Spare_Tire", sc, node)
    s = Mesh()
    tyre(s, sc, 1, TYRE_R, TYRE_W, 0.254, blocks=30, block=(0.4, 0.034, 0.1), chevron=20, studs=10)
    objs.append(s.to_object("Spare_Tire_Mesh", [M["rubber"], M["chassis"]], sp, sharp_angle=60))
    return objs


# ---- cargo body ------------------------------------------------------------------------------------------------------------
def cargo_body(M, parent):
    zc = (BED_FRONT_Z + BED_REAR_Z) / 2
    L = BED_FRONT_Z - BED_REAR_Z
    node = empty("Cargo_Body", (0, BED_FLOOR_Y, zc), parent)
    m = Mesh()
    top = BED_FLOOR_Y + BED_SIDE_H
    rbox(m, Zframe((0, BED_FLOOR_Y - 0.03, zc)), (2 * BED_HALF_W, 0.06, L), 0.01, 1)
    for sx in (1, -1):
        box(m, (sx * RAIL_X, (RAIL_Y1 + BED_FLOOR_Y - 0.06) / 2, zc), (0.12, BED_FLOOR_Y - 0.06 - RAIL_Y1, L - 0.1), 0.005, 1)
    for z in np.arange(BED_FRONT_Z - 0.15, BED_REAR_Z, -0.55):
        box(m, (0, BED_FLOOR_Y - 0.1, z), (2 * BED_HALF_W - 0.04, 0.09, 0.07), 0.005, 1)
    # drop sides with their stake pockets and the troop seats folded up against them
    for sx in (1, -1):
        x = sx * (BED_HALF_W - 0.025)
        rbox(m, Zframe((x, BED_FLOOR_Y + BED_SIDE_H / 2, zc)), (0.04, BED_SIDE_H, L - 0.06), 0.008, 1)
        rbox(m, Zframe((x + sx * 0.01, top - 0.025, zc)), (0.06, 0.05, L - 0.02), 0.012, 1)
        for z in np.arange(BED_FRONT_Z - 0.25, BED_REAR_Z + 0.1, -0.55):
            box(m, (x + sx * 0.03, BED_FLOOR_Y + BED_SIDE_H / 2 - 0.02, z), (0.025, BED_SIDE_H - 0.1, 0.06), 0.006, 1)
            lathe(m, Zframe((x + sx * 0.02, BED_FLOOR_Y + 0.02, z - 0.22)), [(0.0, -0.05), (0.016, -0.05), (0.016, 0.05), (0.0, 0.05)], 8, mat=1)
        box(m, (x - sx * 0.05, BED_FLOOR_Y + 0.38, zc), (0.025, 0.3, L - 0.4), 0.006, 1, mat=2)
        for z in np.arange(BED_FRONT_Z - 0.4, BED_REAR_Z, -0.8):
            lathe(m, Yframe((sx * (BED_HALF_IN - 0.08), BED_FLOOR_Y, z)), [(0.022, 0.0), (0.04, 0.0), (0.04, 0.012), (0.022, 0.012), (0.022, 0.0)], 12, mat=1)
    # front bulkhead
    rbox(m, Zframe((0, BED_FLOOR_Y + 0.45, BED_FRONT_Z - 0.03)), (2 * BED_HALF_W, 0.9, 0.04), 0.01, 1)
    for x in np.linspace(-1.0, 1.0, 6):
        box(m, (x, BED_FLOOR_Y + 0.45, BED_FRONT_Z + 0.005), (0.06, 0.86, 0.03), 0.006, 1)
    objs = [m.to_object("Cargo_Body_Mesh", [M["paint"], M["chassis"], M["wood"]], node, sharp_angle=45)]
    # tailgate, hinged at its foot
    hinge = (0, BED_FLOOR_Y, BED_REAR_Z + 0.02)
    tg = empty("Tailgate", hinge, node)
    drive(tg, "the tailgate: hinged at its foot, turns about local X; + drops it open (to 90 degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, 1.57], group="Tailgate")
    t = Mesh()
    rbox(t, Zframe((0, BED_FLOOR_Y + BED_SIDE_H / 2, BED_REAR_Z + 0.02)), (2 * BED_HALF_W - 0.06, BED_SIDE_H, 0.035), 0.008, 1)
    for x in np.linspace(-0.9, 0.9, 5):
        box(t, (x, BED_FLOOR_Y + BED_SIDE_H / 2, BED_REAR_Z - 0.005), (0.06, BED_SIDE_H - 0.1, 0.02), 0.006, 1)
    for sx in (1, -1):
        box(t, (sx * (BED_HALF_W - 0.08), BED_FLOOR_Y + BED_SIDE_H - 0.06, BED_REAR_Z - 0.01), (0.06, 0.05, 0.04), 0.006, 1, mat=1)
    o = t.to_object("Tailgate_Panel", [M["paint"], M["chassis"]], None, sharp_angle=45)
    set_parent(o, tg)
    objs.append(o)
    # rear: bumper, pintle, mud flaps
    r = Mesh()
    rbox(r, Zframe((0, 0.95, REAR_Z + 0.07)), (2.1, 0.22, 0.14), 0.025, 2)
    lathe(r, Frame((0, 0.92, REAR_Z + 0.07), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.04, -0.035), (0.07, -0.035), (0.07, 0.035), (0.04, 0.035), (0.04, -0.035)], 18, mat=1)
    for sx in (1, -1):
        box(r, (sx * 0.5, 1.12, (REAR_Z + BED_REAR_Z) / 2 + 0.05), (0.1, 0.3, 0.2), 0.01, 1)
    objs.append(r.to_object("Rear_End", [M["paint"], M["chassis"]], node, sharp_angle=45))
    mf = Mesh()
    for sx in (1, -1):
        box(mf, (sx * 0.98, 0.8, AXLES_Z[2] - 0.8), (0.42, 0.66, 0.012), 0.004, 1)
    objs.append(mf.to_object("Mud_Flaps_Rear", [M["rubber"]], node))
    return objs


def cargo(M, parent):
    """Six pallet loads of supplies: fuel drums, ammunition, crates and rations."""
    node = empty("Cargo", (0, BED_FLOOR_Y, -1.5), parent)
    objs = []
    rows = [BED_FRONT_Z - 0.75 - k * 1.38 for k in range(3)]
    kinds = ["drums", "ammo", "crates", "rations", "ammo", "drums"]
    mats = [M["wood"], M["chassis"], M["drum"], M["ammo_can"], M["crate"], M["strap"], M["cardboard"]]
    slot = 0
    for z in rows:
        for x in (0.56, -0.56):
            kind = kinds[slot]
            slot += 1
            c = (x, BED_FLOOR_Y, z)
            n = empty(f"Cargo_Pallet_{slot}", c, node)
            drive(n, "a pallet load; show, hide or lift it off on its own", control="cargo")
            m = Mesh()
            truck.pallet(m, c, 0)
            y0 = BED_FLOOR_Y + 0.12
            if kind == "drums":
                for dx in (-0.25, 0.25):
                    for dz in (-0.3, 0.3):
                        p = (x + dx, y0, z + dz)
                        lathe(m, Yframe(p), [(0.0, 0.0), (0.27, 0.0), (0.29, 0.015), (0.29, 0.29), (0.3, 0.3), (0.29, 0.31), (0.29, 0.57), (0.3, 0.58), (0.29, 0.59), (0.29, 0.865), (0.27, 0.88), (0.0, 0.88)], 28, mat=2)
                        lathe(m, Yframe((p[0] + 0.15, y0 + 0.88, p[2])), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.015), (0.0, 0.015)], 10, mat=1)
                truck.strap(m, (x, y0, z), 1.0, 0.88, 1.2, 5)
            elif kind == "ammo":
                for layer in range(2):
                    for i in range(3):
                        for j in range(4):
                            p = (x - 0.32 + i * 0.32, y0 + 0.095 + layer * 0.19, z - 0.45 + j * 0.3)
                            box(m, p, (0.3, 0.18, 0.28), 0.01, 1, mat=3)
                truck.strap(m, (x, y0, z - 0.3), 0.96, 0.38, 1.2, 5)
                truck.strap(m, (x, y0, z + 0.3), 0.96, 0.38, 1.2, 5)
            elif kind == "crates":
                for dz in (-0.31, 0.31):
                    p = (x, y0 + 0.22, z + dz)
                    rbox(m, Zframe(p), (0.98, 0.44, 0.58), 0.01, 1, mat=4)
                truck.strap(m, (x, y0, z), 0.98, 0.44, 1.2, 5)
            else:
                for layer in range(2):
                    for i in range(2):
                        for j in range(3):
                            box(m, (x - 0.25 + i * 0.5, y0 + 0.12 + layer * 0.24, z - 0.4 + j * 0.4), (0.48, 0.23, 0.38), 0.006, 1, mat=6)
                truck.strap(m, (x, y0, z), 1.0, 0.48, 1.2, 5)
            objs.append(m.to_object(f"Cargo_Pallet_{slot}_Mesh", mats, n, sharp_angle=50))
    return objs


# ---- lights ----------------------------------------------------------------------------------------------------------------
def lights(M, parent):
    node = empty("Lights", (0, 1.2, 0), parent)
    objs = []
    zf = FRONT_Z - 0.26
    specs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        specs += [(f"Light_Head_{side}", M["light_white"], (sx * 0.9, 1.17, zf), (0, 0, 1), 0.085),
                  (f"Light_Turn_Front_{side}", M["light_amber"], (sx * 0.66, 1.17, zf), (0, 0, 1), 0.04),
                  (f"Light_Tail_{side}", M["light_red"], (sx * 0.9, 0.98, REAR_Z + 0.014), (0, 0, -1), 0.055),
                  (f"Light_Turn_Rear_{side}", M["light_amber"], (sx * 0.74, 0.98, REAR_Z + 0.014), (0, 0, -1), 0.04)]
    for x in (-0.3, 0.0, 0.3):
        specs.append((f"Light_Clearance_{'L' if x > 0 else 'R' if x < 0 else 'C'}", M["light_amber"], (x, CAB_ROOF_Y - 0.07, CAB_FRONT_Z - 0.07), (0, 0.3, 0.95), 0.022))
    for name, mat, c, d, r in specs:
        n = empty(name, c, node)
        m = Mesh()
        F = Frame.along(np.asarray(c, float), d)
        lathe(m, Frame(F.o - F.z * 0.05, F.x, F.y, F.z), [(0.0, 0.0), (r + 0.015, 0.0), (r + 0.015, 0.056), (r, 0.056), (r, 0.05), (0.0, 0.05)], 20, mat=1)
        lathe(m, F, [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.18), (0.0, r * 0.22)], 20, mat=0)
        if name.startswith("Light_Head"):
            for k in (-1, 0, 1):
                tube(m, np.asarray(c) + np.array([-0.1, k * 0.06, 0.04]), np.asarray(c) + np.array([0.1, k * 0.06, 0.04]), 0.006, 6, mat=1)
        objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    return objs
