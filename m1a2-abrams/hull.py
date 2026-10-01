"""The Abrams' hull: the lower hull between the tracks and the sponsons over
them, the long shallow glacis with the driver's hatch and periscopes, the
engine deck's grilles and access plates, the rear exhaust grille, side
skirts, fenders, lights, tow fittings and the running gear (modelkit's
running_gear.tracked with the T158 track).

Moving parts:
  Driver_Hatch            lifts and swings right about local Y
  Road_Wheel_*, Idler_*, Sprocket_*, Return_Roller_*   spin about local X
  Track_{Left,Right}      the links ride round the loop in the node's extras"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe
from running_gear import loft, slab, bolt, bolt_row, tracked, link_double_pin
from vehicle import drive
from abrams import *

deg = math.pi / 180
SIDE = Frame((0, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0))  # side profiles: (z, y), lofted across x (local Z is -x)


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def glacis_y(z):
    """Height of the upper glacis at z (it runs from the nose up to the turret's front)."""
    z0, y0, z1, y1 = HULL_FRONT_Z, 1.15, 2.0, 1.585
    return y0 + (z0 - z) / (z0 - z1) * (y1 - y0)


def hull(M, parent):
    node = empty("Hull", (0, 1.1, 0.3), parent)
    objs = []
    F, R = HULL_FRONT_Z, REAR_PLATE_Z
    # the lower hull between the tracks; its top stays inside the sponsons' hull (no coplanar faces)
    lower = [(F, 1.06), (F - 0.12, SPONSON_Y + 0.08), (R + 0.1, SPONSON_Y + 0.08), (R, SPONSON_Y), (R, 0.95), (R + 0.22, BELLY_Y), (F - 0.71, BELLY_Y)]
    m = Mesh()
    loft(m, SIDE, [(-HULL_HALF_W, lower), (HULL_HALF_W, lower)], radii=[0.02, 0.02, 0.02, 0.02, 0.03, 0.05, 0.05], bevel=0.02)
    upper = [(F - 0.02, SPONSON_Y), (F, 1.15), (2.0, 1.585), (1.75, DECK_Y), (R + 0.12, DECK_Y), (R, DECK_Y - 0.06), (R, SPONSON_Y)]
    loft(m, SIDE, [(-SPONSON_HALF_W, upper), (SPONSON_HALF_W, upper)], radii=[0.01, 0.03, 0.05, 0.05, 0.03, 0.03, 0.01], bevel=0.02)
    objs.append(m.to_object("Hull_Armour", [M["paint"]], node, sharp_angle=40))
    objs += front(M, node)
    objs += deck(M, node)
    objs += rear(M, node)
    objs += skirts(M, node)
    objs += lights(M, node)
    gear, gear_objs = tracked(M, parent, running_gear_spec(M))
    objs += gear_objs
    return objs


def running_gear_spec(M):
    return dict(
        x=TRACK_X, wheels_z=WHEELS_Z, wheel_y=WHEEL_Y, wheel_r=WHEEL_R, wheel_w=0.2, wheel_gap=0.13,
        idler=IDLER, sprocket=(SPROCKET[0], SPROCKET[1], PITCH / (2 * math.sin(math.pi / SPROCKET_TEETH)), SPROCKET_TEETH),
        rollers=ROLLERS, W=TRACK_W, pitch=PITCH, t_in=T_IN, t_out=T_OUT,
        link=lambda m, p: link_double_pin(m, TRACK_W, p, T_IN, T_OUT, 0.1),
        sag=0.0, hull_x=HULL_HALF_W, arm=(0.36, 0.1), shocks=(0, 1, 6), holes=6, tyre_t=0.045, roller_w=0.5,
        sprocket_w=0.05, sprocket_gap=0.16,
        mats=dict(wheel=M["chassis"], rubber=M["rubber"], track=[M["track"], M["rubber"]]),
    )


def front(M, parent):
    objs = []
    m = Mesh()
    F = HULL_FRONT_Z
    # tow eyes either side of the nose and the shackles in them
    for sx in (1, -1):
        c = np.array([sx * 0.62, 0.98, F - 0.06])
        slab(m, Frame(c, (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.05, -0.08), (0.05, -0.08), (0.06, 0.06), (-0.06, 0.06)], 0.12, 0.01, mat=1)
        lathe(m, Frame(c + np.array([0, -0.04, 0.0]), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.03, -0.03), (0.06, -0.03), (0.06, 0.03), (0.03, 0.03), (0.03, -0.03)], 14, mat=1)
    # front fenders over the idlers: thin plates hinged down from the sponsons' noses
    for sx in (1, -1):
        x0 = sx * (HULL_HALF_W + 0.02)
        x1 = sx * (SPONSON_HALF_W - 0.01)
        slab(m, Frame(((x0 + x1) / 2, 1.0, F - 0.03), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-abs(x1 - x0) / 2, -0.1), (abs(x1 - x0) / 2, -0.1), (abs(x1 - x0) / 2, 0.1), (-abs(x1 - x0) / 2, 0.1)], 0.02, 0.004)
    # driver's periscopes: three heads in a row ahead of the hatch, their glass facing forward
    g = Mesh()
    for k, a in enumerate((-0.32, 0.0, 0.32)):
        z = 2.8 - abs(a) * 0.15
        y = glacis_y(z)
        c = np.array([a * 0.95, y + 0.06, z])
        rbox(m, Frame.along(c, (a * 0.4, 0, 1)), (0.2, 0.12, 0.14), 0.02, 2)
        gc = c + Frame.along(c, (a * 0.4, 0, 1)).z * 0.071
        G = Frame.along(gc, (a * 0.4, 0, 1))
        g.face(g.verts([G.p((-0.08, -0.04, 0)), G.p((0.08, -0.04, 0)), G.p((0.08, 0.04, 0)), G.p((-0.08, 0.04, 0))]))
        rbox(m, Frame.along(c + np.array([0, 0.065, -0.01]), (a * 0.4, 0, 1)), (0.24, 0.02, 0.17), 0.006, 1)  # brow
    objs.append(m.to_object("Hull_Front_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(g.to_object("Driver_Periscope_Glass", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    # driver's hatch: a disc set into the glacis, its hinge on the right; it lifts and swings right
    hz = 2.44
    hy = glacis_y(hz)
    hinge = (-0.36, hy + 0.04, hz)
    d = empty("Driver_Hatch", hinge, parent)
    drive(d, "the driver's hatch: lifts and swings right about its hinge, local Y; + opens it (to 90 degrees)", control="hinge", axis=[0, 1, 0], limits=[0, -1.57], group="Hatches")
    h = Mesh()
    slope = math.atan2(1.585 - 1.15, HULL_FRONT_Z - 2.0)
    Fh = Frame((0.0, hy + 0.03, hz), (1, 0, 0), (0, math.sin(slope), -math.cos(slope)), (0, math.cos(slope), math.sin(slope)))
    lathe(h, Fh, [(0.0, 0.0), (0.33, 0.0), (0.34, 0.02), (0.32, 0.05), (0.0, 0.055)], 36)
    rbox(h, Frame(Fh.p((-0.33, 0.0, 0.04)), Fh.x, Fh.y, Fh.z), (0.12, 0.14, 0.05), 0.012, 1)
    path_tube(h, [Fh.p((0.12, -0.08, 0.05)), Fh.p((0.12, -0.08, 0.1)), Fh.p((0.12, 0.08, 0.1)), Fh.p((0.12, 0.08, 0.05))], 0.012, 8)
    o = h.to_object("Driver_Hatch_Lid", [M["paint"]], None, sharp_angle=40)
    set_parent(o, d)
    objs.append(o)
    r = Mesh()
    lathe(r, Fh, [(0.36, -0.03), (0.42, -0.03), (0.42, 0.015), (0.36, 0.015)], 36)
    objs.append(r.to_object("Driver_Hatch_Ring", [M["paint"]], parent, sharp_angle=40))
    return objs


def deck(M, parent):
    objs = []
    m = Mesh()
    y = DECK_Y
    # two engine grille doors at the back of the deck: frames with louvres, hinges and lift handles
    for sx in (1, -1):
        x0, x1 = sx * 0.12, sx * 1.22
        xc, w = (x0 + x1) / 2, abs(x1 - x0)
        z0, z1 = -1.62, REAR_PLATE_Z + 0.1
        zc, L = (z0 + z1) / 2, z0 - z1
        box(m, (xc, y + 0.012, zc), (w, 0.024, L), 0.006, 1)
        for z in np.arange(z0 - 0.06, z1 + 0.05, -0.055):
            rbox(m, Frame((xc, y + 0.03, z), (1, 0, 0), (0, math.cos(35 * deg), math.sin(35 * deg)), (0, -math.sin(35 * deg), math.cos(35 * deg))), (w - 0.08, 0.008, 0.05), 0.002, 1, mat=1)
        for z in (z0 - 0.4, z1 + 0.4):
            lathe(m, Xframe((x0 + sx * 0.02, y + 0.03, z), sx), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.12), (0.0, 0.12)], 10, mat=1)
        path_tube(m, [np.array([xc + sx * 0.3, y + 0.02, zc - 0.1]), np.array([xc + sx * 0.3, y + 0.08, zc - 0.1]), np.array([xc + sx * 0.3, y + 0.08, zc + 0.1]), np.array([xc + sx * 0.3, y + 0.02, zc + 0.1])], 0.012, 8, mat=1)
    # air intake grilles along the deck's sides behind the turret
    for sx in (1, -1):
        for z in np.arange(-0.9, -1.55, -0.05):
            box(m, (sx * 1.45, y + 0.015, z), (0.4, 0.012, 0.02), 0.003, 1, mat=1)
        box(m, (sx * 1.45, y + 0.004, -1.22), (0.46, 0.008, 0.72), 0.003, 1)
    # fuel fillers at the deck's corners, lifting eyes, access-plate handles
    for sx in (1, -1):
        for z in (1.45, REAR_PLATE_Z + 0.25):
            lathe(m, Yframe((sx * 1.5, y, z)), [(0.0, 0.0), (0.1, 0.0), (0.1, 0.018), (0.085, 0.03), (0.0, 0.032)], 20)
            box(m, (sx * 1.5, y + 0.04, z), (0.12, 0.02, 0.03), 0.006, 1, mat=1)
        for z in (1.2, REAR_PLATE_Z + 0.5):
            lathe(m, Frame((sx * 1.62, y + 0.05, z), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.03, -0.015), (0.055, -0.015), (0.055, 0.015), (0.03, 0.015), (0.03, -0.015)], 14, mat=1)
            box(m, (sx * 1.62, y + 0.015, z), (0.03, 0.03, 0.12), 0.006, 1, mat=1)
    # turret ring guard round the turret's base
    lathe(m, Yframe((0, y, TURRET_Z)), [(RING_R + 0.05, 0.0), (RING_R + 0.12, 0.0), (RING_R + 0.12, 0.03), (RING_R + 0.05, 0.05)], 72)
    objs.append(m.to_object("Engine_Deck", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    return objs


def rear(M, parent):
    objs = []
    m = Mesh()
    R = REAR_PLATE_Z
    # the exhaust grille across the rear plate: a frame of louvres
    box(m, (0, 1.24, R - 0.02), (2.0, 0.6, 0.04), 0.01, 1)
    for k in range(10):
        yy = 0.99 + k * 0.052
        rbox(m, Frame((0, yy, R - 0.045), (1, 0, 0), (0, math.cos(30 * deg), math.sin(30 * deg)), (0, -math.sin(30 * deg), math.cos(30 * deg))), (1.9, 0.008, 0.06), 0.002, 1, mat=1)
    for x in (-0.65, 0.0, 0.65):
        box(m, (x, 1.24, R - 0.05), (0.04, 0.58, 0.04), 0.006, 1)
    # tow pintle and tow hooks, the rear lifting eyes
    lathe(m, Frame((0, 0.82, R - 0.005), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.04, -0.04), (0.09, -0.04), (0.09, 0.04), (0.04, 0.04), (0.04, -0.04)], 20, mat=1)
    rbox(m, Zframe((0, 0.82, R - 0.02)), (0.2, 0.18, 0.06), 0.02, 1, mat=1)
    for sx in (1, -1):
        slab(m, Frame((sx * 0.75, 0.78, R - 0.05), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.05, -0.09), (0.05, -0.09), (0.06, 0.07), (-0.06, 0.07)], 0.1, 0.01, mat=1)
        lathe(m, Frame((sx * 0.75, 0.74, R - 0.04), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.03, -0.03), (0.06, -0.03), (0.06, 0.03), (0.03, 0.03), (0.03, -0.03)], 14, mat=1)
    # the infantry phone box on the right rear and the rear fenders' mud flaps
    rbox(m, Zframe((-1.4, 1.38, R - 0.045)), (0.26, 0.3, 0.09), 0.02, 2)
    box(m, (-1.4, 1.38, R - 0.093), (0.2, 0.22, 0.008), 0.004, 1, mat=1)
    objs.append(m.to_object("Hull_Rear", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    f = Mesh()
    for sx in (1, -1):
        box(f, (sx * TRACK_X, 0.85, R + 0.03), (0.66, 0.42, 0.012), 0.004, 1)
    objs.append(f.to_object("Mud_Flaps_Rear", [M["rubber"]], parent))
    return objs


def skirts(M, parent):
    """Seven skirt panels a side: the front three thick armour with a raked leading edge, the rest thinner."""
    objs = []
    zf = HULL_FRONT_Z - 0.38
    zr = REAR_PLATE_Z + 0.05
    edges = np.linspace(zf, zr, 8)
    for side, sx in (("Left", 1), ("Right", -1)):
        m = Mesh()
        for k in range(7):
            z0, z1 = edges[k] - 0.004, edges[k + 1] + 0.004
            thick = 0.1 if k < 3 else 0.04
            x = sx * (SKIRT_FACE - thick / 2)
            top = lambda z: min(DECK_Y - 0.02, glacis_y(z) - 0.012)
            bot = 0.58
            if k == 0:
                poly = [(z0 + 0.3, top(z0 + 0.3)), (z1, top(z1)), (z1, bot), (z0 - 0.3, bot), (z0, bot + 0.3)]
            else:
                poly = [(z0, top(z0)), (z1, top(z1)), (z1, bot), (z0, bot)]
            if k < 3:  # the armoured panels' tops follow the glacis: add a corner where it meets the deck
                pass
            slab(m, Frame((x, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0) if sx > 0 else (1, 0, 0)), poly, thick, 0.012, mat=0)
            # bolts along the panel's top and a lift handle
            Fb = Frame((sx * (SKIRT_FACE + 0.0005), 0, 0), (0, 0, 1), (0, 1, 0), (sx, 0, 0))
            for zz in np.linspace(min(z0, z1) + 0.12, max(z0, z1) - 0.12, 4):
                bolt(m, Frame(Fb.p((zz, top(zz) - 0.07, 0)), Fb.x, Fb.y, Fb.z), 0.016, 0.012, mat=1)
            if k >= 3:
                path_tube(m, [np.array([sx * (SKIRT_FACE + 0.003), bot + 0.08, (z0 + z1) / 2 - 0.12]), np.array([sx * (SKIRT_FACE + 0.003), bot + 0.08, (z0 + z1) / 2 + 0.12])], 0.009, 6, mat=1)
        objs.append(m.to_object(f"Skirt_{side}", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    return objs


def lights(M, parent):
    """Headlight clusters on the front fenders behind brush guards, tail lights in the rear corners."""
    node = empty("Lights", (0, 1.4, 0), parent)
    objs = []
    F, R = HULL_FRONT_Z, REAR_PLATE_Z
    for side, sx in (("Left", 1), ("Right", -1)):
        z = F - 0.3
        y = glacis_y(z)
        for name, mat, dx, r in ((f"Light_Head_{side}", M["light_white"], 0.0, 0.085), (f"Light_Blackout_{side}", M["light_amber"], -sx * 0.2, 0.045)):
            c = np.array([sx * 1.42 + dx, y + 0.1, z])
            n = empty(name, tuple(c), node)
            m = Mesh()
            lathe(m, Zframe(c - np.array([0, 0, 0.08])), [(0.0, 0.0), (r + 0.02, 0.0), (r + 0.02, 0.09), (r, 0.09), (0.0, 0.09)], 20, mat=1)
            lathe(m, Zframe(c + np.array([0, 0, 0.008])), [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.15), (0.0, r * 0.2)], 20, mat=0)
            box(m, tuple(c - np.array([0, 0.11, 0.0])), (r * 2 + 0.08, 0.04, 0.16), 0.008, 1, mat=1)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
        # brush guard over the cluster
        g = Mesh()
        c = np.array([sx * 1.32, y + 0.1, z])
        path_tube(g, [c + np.array([sx * 0.25, -0.1, -0.05]), c + np.array([sx * 0.25, 0.16, 0.0]), c + np.array([-sx * 0.25, 0.16, 0.0]), c + np.array([-sx * 0.25, -0.1, -0.05])], 0.016, 8)
        for dx in (-0.12, 0.0, 0.12):
            tube(g, c + np.array([dx, 0.16, 0.0]), c + np.array([dx, -0.1, 0.12]), 0.01, 6)
        objs.append(g.to_object(f"Light_Guard_{side}", [M["paint"]], node, sharp_angle=50))
        for name, mat, dx in ((f"Light_Tail_{side}", M["light_red"], 0.0), (f"Light_Tail_Blackout_{side}", M["light_amber"], -sx * 0.14)):
            c = np.array([sx * 1.45 + dx, DECK_Y - 0.12, R - 0.003])
            n = empty(name, tuple(c), node)
            m = Mesh()
            box(m, tuple(c + np.array([0, 0, 0.03])), (0.12, 0.16, 0.06), 0.01, 1, mat=1)
            lathe(m, Zframe(c, -1), [(0.0, 0.0), (0.04, 0.0), (0.03, 0.01), (0.0, 0.012)], 16, mat=0)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    return objs
