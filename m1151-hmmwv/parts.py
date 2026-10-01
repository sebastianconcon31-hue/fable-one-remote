"""The M1151A1 HMMWV's outside: the wide hood over the engine and front
wheels with its slotted grille and headlights, the armoured cab with four
heavy doors and their thick windows, the windshield, the rear cargo shell
and its deck lid, the gunner's turret (O-GPK shields round an M2), mirrors,
lights, frame and portal-hub axles, and four wheels on 37 x 12.50 R16.5
tyres and beadlock rims.

Moving parts:
  Door_{Front,Rear}_{Left,Right} swing about local Y; Cargo_Lid hinges up about local X
  Turret (traverse, local Y), Gun (elevate, axis -X: + raises it)
  Wheel_{1,2}_{Left,Right} spin about local X; Steer_1_{Left,Right} steer about local Y"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm
from running_gear import loft, slab, bolt, tyre
from vehicle import drive
from hmmwv import *

deg = math.pi / 180
SIDE = Frame((0, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0))  # side profiles (z, y), lofted across x
ZF = Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))  # cross-sections (x, y), lofted along z


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def hood_y(z):
    return HOOD_Y_FRONT + (HOOD_FRONT_Z - z) / (HOOD_FRONT_Z - HOOD_BACK_Z) * (HOOD_Y_BACK - HOOD_Y_FRONT)


def arch(zc, yc, r, y_cut, n=14):
    """The top of a wheel arch: points over the wheel from back to front where the arc meets y_cut."""
    a = math.asin(min(1.0, (y_cut - yc) / r))
    return [(zc + r * math.cos(t), yc + r * math.sin(t)) for t in np.linspace(math.pi - a, a, n)]


def body(M, parent):
    node = empty("Body", (0, 1.2, 0.2), parent)
    objs = []
    m = Mesh()
    # the hood: a thick fibreglass shell over the engine bay and both front wheels
    hood = [(HOOD_FRONT_Z, HOOD_Y_FRONT - 0.09), (HOOD_FRONT_Z, HOOD_Y_FRONT), (HOOD_BACK_Z, HOOD_Y_BACK), (HOOD_BACK_Z, HOOD_Y_BACK - 0.09)]
    loft(m, SIDE, [(-BODY_HALF_W, hood), (BODY_HALF_W, hood)], radii=[0.01, 0.04, 0.02, 0.01], bevel=0.02)
    # its side panels with the wheel arches cut in
    zc = AXLES_Z[0]
    for sx in (1, -1):
        poly = [(HOOD_FRONT_Z, hood_y(HOOD_FRONT_Z) - 0.02), (HOOD_BACK_Z, hood_y(HOOD_BACK_Z) - 0.02), (HOOD_BACK_Z, 0.78)] + arch(zc, TYRE_R, 0.56, 0.78) + [(HOOD_FRONT_Z, 0.78)]
        slab(m, Frame((sx * (BODY_HALF_W - 0.015), 0, 0), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), poly, 0.03, 0.006)
    # the front: grille panel between the headlight panels
    slab(m, Frame((0, 0.97, HOOD_FRONT_Z - 0.012), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-BODY_HALF_W + 0.01, -0.19), (BODY_HALF_W - 0.01, -0.19), (BODY_HALF_W - 0.01, 0.19), (-BODY_HALF_W + 0.01, 0.19)], 0.024, 0.006)
    for k in range(13):
        x = -0.54 + k * 0.09
        box(m, (x, 0.98, HOOD_FRONT_Z + 0.004), (0.035, 0.28, 0.012), 0.004, 1, mat=1)
    # the cab: lower body to the belt line, the armoured upper cab, roof
    lower = [(HOOD_BACK_Z, SILL_Y), (HOOD_BACK_Z, 1.38), (CAB_BACK_Z, 1.38), (CAB_BACK_Z, SILL_Y)]
    loft(m, SIDE, [(-BODY_HALF_W + 0.02, lower), (BODY_HALF_W - 0.02, lower)], radii=0.01, bevel=0.01)
    # the upper cab: its front section is low, so the windshield leans back to the roof
    upper = lambda ytop: [(1.06, 1.36), (1.02, ytop), (-1.02, ytop), (-1.06, 1.36)]
    sections = [(HOOD_BACK_Z - 0.02, upper(1.42)), (HOOD_BACK_Z - 0.14, upper(ROOF_Y - 0.06)), (CAB_BACK_Z, upper(ROOF_Y - 0.06))]
    loft(m, ZF, sections[::-1], radii=0.02, bevel=0.015)
    slab(m, Frame((0, ROOF_Y - 0.03, (HOOD_BACK_Z - 0.1 + CAB_BACK_Z) / 2), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(-1.05, -(HOOD_BACK_Z - 0.1 - CAB_BACK_Z) / 2), (1.05, -(HOOD_BACK_Z - 0.1 - CAB_BACK_Z) / 2), (1.05, (HOOD_BACK_Z - 0.1 - CAB_BACK_Z) / 2), (-1.05, (HOOD_BACK_Z - 0.1 - CAB_BACK_Z) / 2)], 0.06, 0.012)
    # rear cargo shell, with the bumperettes and the pintle under it
    shell = [(CAB_BACK_Z, SILL_Y), (CAB_BACK_Z, 1.62), (REAR_Z + 0.12, 1.55), (REAR_Z + 0.12, SILL_Y)]
    loft(m, SIDE, [(-BODY_HALF_W + 0.02, shell), (BODY_HALF_W - 0.02, shell)], radii=[0.01, 0.03, 0.03, 0.01], bevel=0.015)
    zr = AXLES_Z[1]
    for sx in (1, -1):  # rear wheel arches' flares
        poly = [(CAB_BACK_Z + 0.02, 0.95), (CAB_BACK_Z + 0.02, 0.78)] + arch(zr, TYRE_R, 0.56, 0.78) + [(REAR_Z + 0.16, 0.78), (REAR_Z + 0.16, 0.95)]
        slab(m, Frame((sx * (BODY_HALF_W - 0.015), 0, 0), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), poly, 0.03, 0.006)
    for sx in (1, -1):
        box(m, (sx * 0.85, 0.66, REAR_Z + 0.08), (0.3, 0.14, 0.14), 0.015, 1, mat=1)
    lathe(m, Frame((0, 0.62, REAR_Z + 0.06), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.03, -0.03), (0.06, -0.03), (0.06, 0.03), (0.03, 0.03), (0.03, -0.03)], 14, mat=1)
    objs.append(m.to_object("Body_Shell", [M["paint"], M["chassis"]], node, sharp_angle=40))
    objs += windows(M, node)
    objs += doors(M, node)
    objs += front_end(M, node)
    objs += cargo_lid(M, node)
    objs += mirrors(M, node)
    objs += lights(M, node)
    return objs


def windows(M, parent):
    """The windshield's two armoured panes and the rear cab window, the dark cab behind them."""
    g, k, f = Mesh(), Mesh(), Mesh()
    z0, z1 = HOOD_BACK_Z - 0.02, HOOD_BACK_Z - 0.14
    for sx in (1, -1):
        a, b = sx * 0.06, sx * 0.94
        P = [np.array([a, 1.44, z0 - 0.006]), np.array([b, 1.44, z0 - 0.006]), np.array([b, ROOF_Y - 0.1, z1 - 0.006]), np.array([a, ROOF_Y - 0.1, z1 - 0.006])]
        n = norm(np.cross(P[1] - P[0], P[3] - P[0])) * (1 if sx > 0 else -1)
        if n[2] < 0:
            n = -n
        g.face(g.verts([p + n * 0.012 for p in P]))
        k.face(k.verts([p - n * 0.01 for p in P]))
        for p0, p1 in zip(P, P[1:] + P[:1]):
            tube(f, p0 + n * 0.01, p1 + n * 0.01, 0.03, 6)
    inside = lambda p: (0.0, 1.6, -0.1)
    return [g.to_object("Windshield_Glass", [M["glass"]], parent, smooth=False, per_face=inside),
            k.to_object("Windshield_Backing", [M["interior"]], parent, smooth=False, per_face=inside),
            f.to_object("Windshield_Frame", [M["paint"]], parent, sharp_angle=40)]


def doors(M, parent):
    """Four armoured doors hung on their front edges, each with a thick window and its combat lock."""
    objs = []
    for row, (z0, z1) in (("Front", (HOOD_BACK_Z - 0.04, -0.02)), ("Rear", (-0.06, CAB_BACK_Z + 0.02))):
        for side, sx in (("Left", 1), ("Right", -1)):
            x = sx * (BODY_HALF_W + 0.012)
            hinge = (x, 1.3, z0)
            d = empty(f"Door_{row}_{side}", hinge, parent)
            drive(d, "an armoured door: swings about local Y on its front hinges; + opens it outward (to 70 degrees)", control="hinge",
                  axis=[0, -1 if sx > 0 else 1, 0], limits=[0, 1.2], group="Doors")
            m = Mesh()
            L = z0 - z1
            Fd = Frame((x + sx * 0.03, 1.32, (z0 + z1) / 2), (0, 0, 1), (0, 1, 0), (sx, 0, 0))
            slab(m, Fd, [(-L / 2, -0.58), (L / 2, -0.58), (L / 2, 0.6), (L / 2 - 0.05, 0.66), (-L / 2 + 0.02, 0.66), (-L / 2, 0.6)], 0.07, 0.012)
            # the window's thick frame
            wy0, wy1 = 1.48, 1.86
            wz0, wz1 = (z0 + z1) / 2 + L * 0.36, (z0 + z1) / 2 - L * 0.36
            for p0, p1 in (((wz0, wy0), (wz1, wy0)), ((wz1, wy0), (wz1, wy1)), ((wz1, wy1), (wz0, wy1)), ((wz0, wy1), (wz0, wy0))):
                tube(m, (x + sx * 0.068, p0[1], p0[0]), (x + sx * 0.068, p1[1], p1[0]), 0.022, 6)
            # combat lock handle and the hinges
            box(m, (x + sx * 0.075, 1.3, z1 + 0.12), (0.03, 0.06, 0.16), 0.008, 1, mat=1)
            for y in (1.0, 1.6):
                lathe(m, Yframe((x + sx * 0.02, y - 0.07, z0 + 0.01)), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.14), (0.0, 0.14)], 10, mat=1)
            o = m.to_object(f"Door_{row}_{side}_Panel", [M["paint"], M["chassis"]], None, sharp_angle=40)
            set_parent(o, d)
            gl, bk = Mesh(), Mesh()
            P = [(x + sx * 0.07, wy0, wz0), (x + sx * 0.07, wy0, wz1), (x + sx * 0.07, wy1, wz1), (x + sx * 0.07, wy1, wz0)]
            gl.face(gl.verts(P))
            bk.face(bk.verts([(p[0] - sx * 0.004, p[1], p[2]) for p in P]))
            inside = lambda p: (0.0, 1.5, p[2])
            go = gl.to_object(f"Door_{row}_{side}_Glass", [M["glass"]], None, smooth=False, per_face=inside)
            bo = bk.to_object(f"Door_{row}_{side}_Window_Backing", [M["interior"]], None, smooth=False, per_face=inside)
            for ob in (go, bo):
                set_parent(ob, d)
            objs += [o, go, bo]
    return objs


def front_end(M, parent):
    """The bumper with its shackles and the brush guard, and the air intake beside the windshield."""
    m = Mesh()
    zf = FRONT_Z
    rbox(m, Zframe((0, 0.62, zf - 0.09)), (2.0, 0.18, 0.18), 0.02, 2)
    for sx in (1, -1):
        lathe(m, Frame((sx * 0.62, 0.5, zf - 0.05), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.022, -0.022), (0.045, -0.022), (0.045, 0.022), (0.022, 0.022), (0.022, -0.022)], 12, mat=1)
    # the brush guard round the grille
    path_tube(m, [np.array([0.72, 0.7, zf - 0.08]), np.array([0.72, 1.12, zf - 0.08]), np.array([0.6, 1.16, zf - 0.08]), np.array([-0.6, 1.16, zf - 0.08]), np.array([-0.72, 1.12, zf - 0.08]), np.array([-0.72, 0.7, zf - 0.08])], 0.025, 10)
    # the engine air intake on the right of the windshield
    path_tube(m, [np.array([-1.0, HOOD_Y_BACK, HOOD_BACK_Z + 0.06]), np.array([-1.0, 1.85, HOOD_BACK_Z]), np.array([-1.0, 1.92, HOOD_BACK_Z - 0.04])], 0.07, 14)
    rbox(m, Zframe((-1.0, 1.95, HOOD_BACK_Z - 0.02)), (0.2, 0.08, 0.2), 0.02, 2)
    return [m.to_object("Front_Bumper_And_Intake", [M["paint"], M["chassis"]], parent, sharp_angle=40)]


def cargo_lid(M, parent):
    hinge = (0, 1.64, CAB_BACK_Z - 0.04)
    n = empty("Cargo_Lid", hinge, parent)
    drive(n, "the cargo shell's deck lid: hinged at its front, turns about local X; + lifts it (to 80 degrees)", control="hinge", axis=[1, 0, 0], limits=[0, 1.4], group="Cargo lid")
    m = Mesh()
    L = CAB_BACK_Z - 0.04 - (REAR_Z + 0.16)
    slab(m, Frame((0, 1.6, (CAB_BACK_Z - 0.04 + REAR_Z + 0.16) / 2), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(-1.0, -L / 2), (1.0, -L / 2), (1.0, L / 2), (-1.0, L / 2)], 0.04, 0.01)
    for x in (-0.6, 0.0, 0.6):
        box(m, (x, 1.625, (CAB_BACK_Z + REAR_Z) / 2), (0.05, 0.012, L - 0.1), 0.004, 1)
    o = m.to_object("Cargo_Lid_Panel", [M["paint"]], None, sharp_angle=40)
    set_parent(o, n)
    return [o]


def mirrors(M, parent):
    """Big rectangular mirrors on arms from the windshield's posts: the vehicle's widest points."""
    m, g = Mesh(), Mesh()
    hw = SPEC["width"] / 2
    for sx in (1, -1):
        base = np.array([sx * 1.04, 1.55, HOOD_BACK_Z - 0.04])
        head = np.array([sx * (hw - 0.045), 1.62, HOOD_BACK_Z + 0.02])
        path_tube(m, [base, base + np.array([sx * 0.08, 0.05, 0.02]), head - np.array([sx * 0.04, 0.0, 0.0])], 0.015, 8)
        rbox(m, Zframe(head), (0.09, 0.32, 0.05), 0.015, 2)
        g.face(g.verts([head + np.array([sx * dx, dy, -0.0255]) for dx, dy in ((-0.035, -0.14), (0.035, -0.14), (0.035, 0.14), (-0.035, 0.14))]))
    return [m.to_object("Mirrors", [M["paint"]], parent, sharp_angle=40),
            g.to_object("Mirror_Glass", [M["mirror"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] + 1.0))]


def lights(M, parent):
    node = empty("Lights", (0, 1.0, 0), parent)
    objs = []
    zf = HOOD_FRONT_Z - 0.0
    for side, sx in (("Left", 1), ("Right", -1)):
        for name, mat, c, r in ((f"Light_Head_{side}", M["light_white"], (sx * 0.86, 1.0, zf), 0.09), (f"Light_Turn_Front_{side}", M["light_amber"], (sx * 0.86, 0.84, zf), 0.04)):
            c = np.array(c)
            n = empty(name, tuple(c), node)
            m = Mesh()
            lathe(m, Zframe(c - np.array([0, 0, 0.04])), [(0.0, 0.0), (r + 0.02, 0.0), (r + 0.02, 0.05), (r, 0.05), (0.0, 0.05)], 20, mat=1)
            lathe(m, Zframe(c + np.array([0, 0, 0.008])), [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.15), (0.0, r * 0.2)], 20, mat=0)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
        for name, mat, dy in ((f"Light_Tail_{side}", M["light_red"], 0.0), (f"Light_Turn_Rear_{side}", M["light_amber"], -0.1)):
            c = np.array([sx * 0.95, 1.2 + dy, REAR_Z + 0.117])
            n = empty(name, tuple(c), node)
            m = Mesh()
            box(m, tuple(c + np.array([0, 0, 0.0])), (0.1, 0.08, 0.006), 0.003, 1, mat=1)
            lathe(m, Zframe(c - np.array([0, 0, 0.003]), -1), [(0.0, 0.0), (0.03, 0.0), (0.024, 0.008), (0.0, 0.01)], 14, mat=0)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    return objs


# ---- gunner's turret ----------------------------------------------------------------------------------------------------------
def turret(M, parent):
    """O-GPK: a ring on the roof carrying the front shield with its armoured window, the angled side shields, and the
    M2 on its pintle."""
    c = np.array([0.0, ROOF_Y, TURRET_Z])
    ring = Mesh()
    lathe(ring, Yframe(c), [(0.5, 0.0), (0.62, 0.0), (0.62, 0.06), (0.58, 0.08), (0.5, 0.08)], 40)
    objs = [ring.to_object("Turret_Ring", [M["paint"]], parent, sharp_angle=40)]
    n = empty("Turret", tuple(c), parent)
    drive(n, "the gunner's turret: traverses about local Y; + turns it left (all the way round)", control="traverse", axis=[0, 1, 0])
    m, g = Mesh(), Mesh()
    lathe(m, Yframe(c + np.array([0, 0.08, 0])), [(0.52, 0.0), (0.6, 0.0), (0.6, 0.05), (0.52, 0.05)], 40)
    # the front shield: a wide plate, its window in the middle, a cut-out for the gun below
    y0 = ROOF_Y + 0.1
    Ff = Frame(c + np.array([0, 0.5, 0.6]), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    # the plate, with the gun's slot up through its lower middle
    slab(m, Ff, [(-0.6, -0.38), (-0.14, -0.38), (-0.14, -0.05), (0.14, -0.05), (0.14, -0.38), (0.6, -0.38), (0.6, 0.3), (0.45, 0.42), (-0.45, 0.42), (-0.6, 0.3)], 0.03, 0.006)
    for p0, p1 in (((-0.28, 0.04), (0.28, 0.04)), ((0.28, 0.04), (0.28, 0.34)), ((0.28, 0.34), (-0.28, 0.34)), ((-0.28, 0.34), (-0.28, 0.04))):
        tube(m, Ff.p((p0[0], p0[1], 0.02)), Ff.p((p1[0], p1[1], 0.02)), 0.018, 6)
    g.face(g.verts([Ff.p((-0.27, 0.05, 0.025)), Ff.p((0.27, 0.05, 0.025)), Ff.p((0.27, 0.33, 0.025)), Ff.p((-0.27, 0.33, 0.025))]))
    # side shields swept back at 35 degrees, each with a small window
    for sx in (1, -1):
        a = sx * 35 * deg
        o = c + np.array([sx * 0.78, 0.42, 0.3])
        Fs = Frame(o, (math.cos(a) * sx, 0, -math.sin(a) * sx), (0, 1, 0), (math.sin(a) * sx, 0, math.cos(a) * sx))
        slab(m, Fs, [(-0.3, -0.3), (0.3, -0.3), (0.3, 0.36), (-0.3, 0.3)], 0.03, 0.006)
        g.face(g.verts([Fs.p((-0.12, 0.02, 0.016)), Fs.p((0.12, 0.02, 0.016)), Fs.p((0.12, 0.2, 0.016)), Fs.p((-0.12, 0.2, 0.016))]))
        tube(m, c + np.array([sx * 0.5, 0.13, 0.35]), o - Fs.x * 0.25 * sx + np.array([0, -0.25, 0]), 0.02, 8, mat=1)
    objs.append(m.to_object("Turret_Shields", [M["paint"], M["chassis"]], n, sharp_angle=40))
    objs.append(g.to_object("Turret_Windows", [M["glass"]], n, smooth=False, per_face=lambda p: (0.0, p[1], TURRET_Z)))
    # the M2 on its pintle
    piv = c + np.array([0.0, 0.24, 0.32])
    tube(m, c + np.array([0, 0.1, 0.32]), piv, 0.035, 10, mat=1)
    gun = empty("Gun", tuple(piv), n)
    drive(gun, "the M2 .50 cal on its pintle: elevates about local X; + raises it (-15 to +50 degrees)", control="elevate", axis=[-1, 0, 0], limits=[-15 * deg, 50 * deg])
    k = Mesh()
    F2 = Frame(piv + np.array([0, 0.06, 0.05]), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    rbox(k, Frame(F2.p((0, 0, -0.1)), F2.x, F2.y, F2.z), (0.12, 0.16, 0.6), 0.01, 1)
    lathe(k, Frame(F2.p((0, 0.02, 0.2)), F2.x, F2.y, F2.z), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.3), (0.024, 0.32), (0.024, 1.1), (0.03, 1.12), (0.03, 1.2), (0.0, 1.2)], 14)
    for sx in (1, -1):
        tube(k, F2.p((sx * 0.06, 0.0, -0.4)), F2.p((sx * 0.06, -0.12, -0.46)), 0.016, 8)
    box(k, tuple(F2.p((0.12, -0.04, -0.05))), (0.12, 0.2, 0.3), 0.008, 1)
    objs.append(k.to_object("M2", [M["gun"]], gun, sharp_angle=40))
    return objs


# ---- chassis and wheels ------------------------------------------------------------------------------------------------------
def chassis(M, parent):
    node = empty("Chassis", (0, 0.6, 0), parent)
    m = Mesh()
    for sx in (1, -1):
        box(m, (sx * 0.42, 0.62, (FRONT_Z + REAR_Z) / 2), (0.08, 0.16, FRONT_Z - REAR_Z - 0.3), 0.01, 1)
    for k, za in enumerate(AXLES_Z):
        # differential and half shafts up to the portal hubs, the A-arms
        lathe(m, Zframe((0, TYRE_R + 0.03, za - 0.15)), [(0.0, 0.0), (0.12, 0.02), (0.15, 0.08), (0.15, 0.22), (0.12, 0.28), (0.0, 0.3)], 18)
        for sx in (1, -1):
            tube(m, (sx * 0.15, TYRE_R + 0.03, za), (sx * (WHEEL_X - 0.2), TYRE_R + 0.03, za), 0.035, 10)
            for dz, dy in ((0.18, 0.12), (-0.18, 0.12), (0.18, -0.08), (-0.18, -0.08)):
                tube(m, (sx * 0.4, TYRE_R + 0.03 + dy, za + dz), (sx * (WHEEL_X - 0.2), TYRE_R + 0.03 + dy * 0.6, za), 0.025, 8)
            tube(m, (sx * (WHEEL_X - 0.3), TYRE_R + 0.05, za - 0.05), (sx * 0.7, 1.05, za - 0.1), 0.04, 10)  # coil-over
            lathe(m, Xframe((sx * (WHEEL_X - 0.2), TYRE_R - 0.04, za), sx), [(0.0, 0.0), (0.12, 0.0), (0.13, 0.04), (0.13, 0.12), (0.0, 0.12)], 18)  # portal hub
    # skid plate, exhaust and fuel tank
    box(m, (0, 0.46, 1.9), (0.8, 0.02, 0.9), 0.006, 1)
    path_tube(m, [np.array([0.3, 0.55, 1.2]), np.array([0.5, 0.52, 0.0]), np.array([0.6, 0.52, -1.5]), np.array([0.7, 0.55, REAR_Z + 0.25])], 0.04, 10)
    rbox(m, Zframe((-0.6, 0.6, -1.95)), (0.5, 0.3, 0.55), 0.04, 2)
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
            drive(w, "spin about local X; + rolls the vehicle forward", control="wheel", axis=[1, 0, 0], radius=round(TYRE_R, 4))
            m = Mesh()
            tyre(m, c, sx, TYRE_R, TYRE_W, RIM_R, blocks=26, block=(0.36, 0.03, 0.09), chevron=30, rows=3, studs=8, disc="flat", beadlock=12)
            objs.append(m.to_object(f"Wheel_{i + 1}_{side}_Mesh", [M["rubber"], M["chassis"]], w, sharp_angle=60))
    return objs
