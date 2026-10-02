"""The M1126 Stryker's outside: the faceted hull (lofted nose to tail through
its cross-sections), the bolted ceramic armour tiles, the engine grilles and
exhaust, the driver's and commander's stations, the M151 Protector remote
weapon station with its M2, the troop hatches, the rear ramp with its door,
lights, eight wheels on Michelin 12.00R20 XML tyres, the front four steering.

Moving parts:
  RWS (traverse, local Y), RWS_Cradle (elevate, axis -X: + raises it)
  Wheel_{1-4}_{Left,Right} spin about local X; Steer_{1,2}_{Left,Right} steer about local Y
  Ramp, Ramp_Door, Driver_Hatch, Commander_Hatch, Troop_Hatch_{Left,Right}"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm
from running_gear import loft, slab, bolt, tyre
from vehicle import drive
from stryker import *

deg = math.pi / 180
ZF = Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))  # cross-sections (x, y) lofted along z


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def top_y(z):
    if z <= GLACIS_TOP_Z:
        return ROOF_Y
    return ROOF_Y + (z - GLACIS_TOP_Z) / (FRONT_Z - GLACIS_TOP_Z) * (NOSE_TOP_Y - ROOF_Y)


def bot_y(z):
    if z <= BELLY_FRONT_Z:
        return BELLY_Y
    return BELLY_Y + (z - BELLY_FRONT_Z) / (FRONT_Z - BELLY_FRONT_Z) * (NOSE_BOT_Y - BELLY_Y)


# the lower hull narrows to its belly, inboard of the front tyres' sweep at full lock
HALF = [(0.56, BELLY_Y), (0.78, 1.18), (HALF_W, SHELF_Y), (HALF_W, 1.66), (1.06, ROOF_Y)]


def section(z):
    """The hull's cross-section at z: lower hull, the shelf over the wheels, upright sides, the sloped upper sides.
    Toward the nose the lot is squeezed between the glacis and the rising belly."""
    yt, yb = top_y(z), bot_y(z)
    mid = min(SHELF_Y, yt - 0.06)
    def remap(y):
        if y <= SHELF_Y:
            return yb + (y - BELLY_Y) / (SHELF_Y - BELLY_Y) * (mid - yb)
        return mid + (y - SHELF_Y) / (ROOF_Y - SHELF_Y) * (yt - mid)
    half = [(x, remap(y)) for x, y in HALF]
    return [(x, y) for x, y in half] + [(-x, y) for x, y in reversed(half)]


def hull(M, parent):
    node = empty("Hull", (0, 1.3, 0), parent)
    objs = []
    m = Mesh()
    zs = [RAMP_Z, GLACIS_TOP_Z, BELLY_FRONT_Z, FRONT_Z]
    loft(m, ZF, [(z, section(z)) for z in zs], radii=[0.04, 0.03, 0.02, 0.03, 0.03, 0.03, 0.03, 0.02, 0.03, 0.04], bevel=0.02)
    objs.append(m.to_object("Hull_Armour", [M["paint"]], node, sharp_angle=35))
    objs += tiles(M, node)
    objs += front(M, node)
    objs += roof(M, node)
    objs += rear(M, node)
    objs += lights(M, node)
    objs += wheels(M, parent)
    return objs


def tiles(M, parent):
    """Bolted ceramic armour tiles over the upright sides and the sloped upper sides."""
    m = Mesh()
    t = 0.04
    for sx in (1, -1):
        # upright sides: two rows
        for z in np.arange(RAMP_Z + 0.32, GLACIS_TOP_Z - 0.05, 0.44):
            for y0, y1 in ((SHELF_Y + 0.02, 1.43), (1.45, 1.65)):
                c = (sx * (HALF_W + t / 2), (y0 + y1) / 2, z)
                slab(m, Frame(c, (0, 0, 1), (0, 1, 0), (sx, 0, 0)), [(-0.21, -(y1 - y0) / 2), (0.21, -(y1 - y0) / 2), (0.21, (y1 - y0) / 2), (-0.21, (y1 - y0) / 2)], t, 0.008)
        # the sloped band above
        a = math.atan2(ROOF_Y - 1.66, HALF_W - 1.06)
        for z in np.arange(RAMP_Z + 0.32, GLACIS_TOP_Z - 0.05, 0.44):
            mid = np.array([sx * (HALF_W + 1.06) / 2, (1.66 + ROOF_Y) / 2, z])
            nrm = np.array([sx * math.sin(a), math.cos(a), 0.0])
            up = np.array([-sx * math.cos(a), math.sin(a), 0.0])
            c = mid + nrm * (t / 2)
            slab(m, Frame(c, (0, 0, 1), up, nrm) if sx < 0 else Frame(c, (0, 0, -1), up, nrm), [(-0.21, -0.2), (0.21, -0.2), (0.21, 0.2), (-0.21, 0.2)], t, 0.008)
    # the glacis: tiles in rows down the slope
    s = math.atan2(ROOF_Y - NOSE_TOP_Y, FRONT_Z - GLACIS_TOP_Z)
    up = np.array([0.0, math.sin(s), -math.cos(s)])
    nrm = np.array([0.0, math.cos(s), math.sin(s)])
    for k in range(3):
        z = GLACIS_TOP_Z + 0.3 + k * 0.42
        for x in (-0.66, -0.22, 0.22, 0.66):
            c = np.array([x, top_y(z), z]) + nrm * (t / 2)
            slab(m, Frame(c, (1, 0, 0), up, nrm), [(-0.21, -0.2), (0.21, -0.2), (0.21, 0.2), (-0.21, 0.2)], t, 0.008)
    return [m.to_object("Armour_Tiles", [M["paint"]], parent, sharp_angle=40)]


def front(M, parent):
    objs = []
    m = Mesh()
    s = math.atan2(ROOF_Y - NOSE_TOP_Y, FRONT_Z - GLACIS_TOP_Z)
    # tow eyes either side of the nose, the winch fairlead between them
    for sx in (1, -1):
        lathe(m, Frame((sx * 0.55, (NOSE_TOP_Y + NOSE_BOT_Y) / 2 - 0.02, FRONT_Z - 0.06), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.025, -0.025), (0.05, -0.025), (0.05, 0.025), (0.025, 0.025), (0.025, -0.025)], 12, mat=1)
    box(m, (0, (NOSE_TOP_Y + NOSE_BOT_Y) / 2, FRONT_Z - 0.03), (0.34, 0.08, 0.04), 0.01, 1, mat=1)
    # engine air intake grille on the glacis' right half, ahead of the tiles; the exhaust grille on the right side
    for k in range(10):
        z = GLACIS_TOP_Z + 0.06 + k * 0.022
        box(m, (-0.85, top_y(z) + 0.012, z), (0.36, 0.012, 0.012), 0.003, 1, mat=1)
    ex = np.array([-HALF_W - 0.001, 1.52, 2.1])
    rbox(m, Frame(ex, (0, 0, 1), (0, 1, 0), (-1, 0, 0)), (0.45, 0.22, 0.03), 0.01, 1)
    for k in range(5):
        rbox(m, Frame(ex + np.array([-0.02, -0.08 + k * 0.04, 0]), (0, 0, 1), (0, 1, 0), (-1, 0, 0)), (0.4, 0.012, 0.02), 0.003, 1, mat=1)
    # driver's periscopes round the hatch
    g = Mesh()
    for k, a in enumerate((-0.6, -0.2, 0.2, 0.6)):
        c = np.array([0.6 + math.sin(a) * 0.32, ROOF_Y + 0.05, 1.62 + math.cos(a) * 0.32])
        d = np.array([math.sin(a) * 0.6, 0.0, 1.0])
        rbox(m, Frame.along(c, d), (0.12, 0.09, 0.09), 0.012, 1)
        Fg = Frame.along(c + norm(d) * 0.046, d)
        g.face(g.verts([Fg.p((-0.045, -0.025, 0)), Fg.p((0.045, -0.025, 0)), Fg.p((0.045, 0.025, 0)), Fg.p((-0.045, 0.025, 0))]))
    objs.append(m.to_object("Hull_Front_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(g.to_object("Vision_Blocks_Driver", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    ring = Mesh()
    lathe(ring, Yframe((0.6, ROOF_Y, 1.62)), [(0.27, 0.0), (0.33, 0.0), (0.33, 0.035), (0.27, 0.04)], 32)
    objs.append(ring.to_object("Driver_Hatch_Ring", [M["paint"]], parent, sharp_angle=40))
    objs += lid(M, parent, "Driver_Hatch", (0.6, ROOF_Y + 0.05, 1.33), (0.6, ROOF_Y + 0.03, 1.62), 0.27, [-1, 0, 0], [0, 1.6], "the driver's hatch: hinged at its back, turns about local X; + opens it upward")
    return objs


def lid(M, parent, name, hinge, c, r, axis, limits, what, rect=None, group="Hatches"):
    n = empty(name, tuple(hinge), parent)
    drive(n, what, control="hinge", axis=axis, limits=limits, group=group)
    m = Mesh()
    if rect:
        slab(m, Frame(np.asarray(c) + np.array([0, 0.02, 0]), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(-rect[0] / 2, -rect[1] / 2), (rect[0] / 2, -rect[1] / 2), (rect[0] / 2, rect[1] / 2), (-rect[0] / 2, rect[1] / 2)], 0.04, 0.01)
    else:
        lathe(m, Yframe(c), [(0.0, 0.0), (r, 0.0), (r + 0.008, 0.02), (r - 0.02, 0.05), (0.0, 0.055)], 32)
    box(m, tuple(hinge), (0.07, 0.05, 0.2) if abs(axis[2]) > 0.5 else (0.2, 0.05, 0.07), 0.012, 1)  # the hinge, along its axis
    path_tube(m, [np.asarray(c) + np.array([-0.08, 0.04, 0.0]), np.asarray(c) + np.array([-0.08, 0.09, 0.0]), np.asarray(c) + np.array([0.08, 0.09, 0.0]), np.asarray(c) + np.array([0.08, 0.04, 0.0])], 0.01, 8)
    o = m.to_object(name + "_Lid", [M["paint"]], None, sharp_angle=40)
    set_parent(o, n)
    return [o]


def roof(M, parent):
    objs = []
    m = Mesh()
    ant = Mesh()
    g = Mesh()
    # commander's cupola: a ring of vision blocks round the hatch, behind the weapon station
    cc = np.array([-0.3, ROOF_Y, 0.3])
    lathe(m, Yframe(cc), [(0.3, 0.0), (0.42, 0.0), (0.42, 0.06), (0.38, 0.12), (0.3, 0.12)], 36)
    for k in range(6):
        a = (k * 60 + 30) * deg
        p = cc + np.array([math.sin(a) * 0.4, 0.09, math.cos(a) * 0.4])
        d = np.array([math.sin(a), 0.0, math.cos(a)])
        rbox(m, Frame.along(p, d), (0.13, 0.08, 0.06), 0.012, 1)
        Fg = Frame.along(p + d * 0.031, d)
        g.face(g.verts([Fg.p((-0.05, -0.025, 0)), Fg.p((0.05, -0.025, 0)), Fg.p((0.05, 0.025, 0)), Fg.p((-0.05, 0.025, 0))]))
    # rails along the roof's edges, lifting eyes, the antenna bases at the back corners
    for sx in (1, -1):
        path_tube(m, [np.array([sx * 0.98, ROOF_Y, 0.4]), np.array([sx * 0.98, ROOF_Y + 0.1, 0.35]), np.array([sx * 0.98, ROOF_Y + 0.1, RAMP_Z + 0.35]), np.array([sx * 0.98, ROOF_Y, RAMP_Z + 0.3])], 0.015, 8, mat=1)
        for z in (1.6, RAMP_Z + 0.2):
            lathe(m, Frame((sx * 1.0, ROOF_Y + 0.045, z), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.025, -0.015), (0.05, -0.015), (0.05, 0.015), (0.025, 0.015), (0.025, -0.015)], 12, mat=1)
        b = np.array([sx * 0.85, ROOF_Y, RAMP_Z + 0.12])
        lathe(m, Yframe(b), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.07), (0.035, 0.1), (0.025, 0.18), (0.0, 0.18)], 12, mat=1)
        tube(ant, b + np.array([0, 0.18, 0]), b + np.array([sx * 0.1, 2.0, 0.4]), 0.005, 6, r1=0.0025)
    objs.append(m.to_object("Roof_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(ant.to_object("Antennas", [M["chassis"]], parent))
    objs.append(g.to_object("Vision_Blocks_Commander", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0] + 0.3, p[1] - 0.2, p[2] - 0.3)))
    objs += lid(M, parent, "Commander_Hatch", cc + np.array([0, 0.14, -0.3]), cc + np.array([0, 0.12, 0]), 0.3, [-1, 0, 0], [0, 1.7], "the commander's hatch: hinged at its back, turns about local X; + opens it upward")
    # two troop hatches over the squad compartment, hinged at their outer edges
    for side, sx in (("Left", 1), ("Right", -1)):
        c = np.array([sx * 0.45, ROOF_Y, -1.75])
        r = Mesh()
        slab(r, Frame(c + np.array([0, 0.012, 0]), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(-0.36, -0.52), (0.36, -0.52), (0.36, 0.52), (-0.36, 0.52)], 0.024, 0.006)
        objs.append(r.to_object(f"Troop_Hatch_{side}_Frame", [M["paint"]], parent, sharp_angle=40))
        objs += lid(M, parent, f"Troop_Hatch_{side}", c + np.array([sx * 0.37, 0.07, 0]), c + np.array([0, 0.024, 0]), 0, [0, 0, -sx], [0, 1.8],
                    "a troop hatch: hinged along its outer edge, turns about local Z; + opens it upward and out", rect=(0.6, 0.96))
    objs += rws(M, parent)
    return objs


def m2(m, F, mat_gun, mat_dark):
    rbox(m, Frame(F.p((0, 0, -0.1)), F.x, F.y, F.z), (0.12, 0.16, 0.6), 0.01, 1, mat=mat_gun)
    lathe(m, Frame(F.p((0, 0.02, 0.2)), F.x, F.y, F.z), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.3), (0.024, 0.32), (0.024, 1.1), (0.03, 1.12), (0.03, 1.2), (0.0, 1.2)], 14, mat=mat_dark)
    path_tube(m, [F.p((0, 0.05, 0.45)), F.p((0, 0.13, 0.48)), F.p((0, 0.13, 0.62)), F.p((0, 0.05, 0.65))], 0.01, 6, mat=mat_dark)


def rws(M, parent):
    """The M151 Protector: turntable and yoke that slew, the cradle that elevates with the M2, its sensor box and
    ammunition can."""
    x, y, z = RWS
    n = empty("RWS", (x, y, z), parent)
    drive(n, "the remote weapon station, M151 Protector: slews about local Y; + turns it left (all the way round)", control="traverse", axis=[0, 1, 0])
    m = Mesh()
    lathe(m, Yframe((x, y, z)), [(0.0, 0.0), (0.24, 0.0), (0.24, 0.08), (0.2, 0.1), (0.16, 0.1), (0.14, 0.2), (0.0, 0.2)], 28)
    for sx in (1, -1):
        prism(m, Frame((x + sx * 0.3, y + 0.32, z), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), [(-0.16, -0.14), (0.16, -0.14), (0.1, 0.14), (-0.1, 0.14)], 0.04)
    box(m, (x, y + 0.12, z), (0.64, 0.04, 0.3), 0.01, 1)  # the yoke's bridge, low enough for the cradle to swing over it
    objs = [m.to_object("RWS_Mount", [M["paint"]], n, sharp_angle=40)]
    piv = (x, y + 0.4, z)
    c = empty("RWS_Cradle", piv, n)
    drive(c, "the cradle with the M2 and its sights: elevates about local X; + raises it (-20 to +60 degrees)", control="elevate", axis=[-1, 0, 0], limits=[-20 * deg, 60 * deg])
    k = Mesh()
    m2(k, Frame((x + 0.02, y + 0.42, z + 0.2), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 1, 1)  # forward in the cradle, so its receiver clears the turntable at +60
    box(k, (x + 0.2, y + 0.4, z - 0.02), (0.14, 0.24, 0.36), 0.015, 1, mat=0)  # ammunition can
    rbox(k, Zframe((x - 0.2, y + 0.43, z + 0.02)), (0.2, 0.22, 0.3), 0.025, 2, mat=0)  # sensor box
    tube(k, (x - 0.28, y + 0.4, z), (x + 0.28, y + 0.4, z), 0.03, 10, mat=1)
    g = Mesh()
    w = np.array([x - 0.2, y + 0.43, z + 0.171])
    g.face(g.verts([w + np.array([-0.07, -0.06, 0]), w + np.array([0.07, -0.06, 0]), w + np.array([0.07, 0.06, 0]), w + np.array([-0.07, 0.06, 0])]))
    objs.append(k.to_object("RWS_Cradle_Mesh", [M["paint"], M["gun"]], c, sharp_angle=40))
    objs.append(g.to_object("RWS_Window", [M["optic"]], c, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    return objs


def rear(M, parent):
    objs = []
    m = Mesh()
    R = RAMP_Z
    for sx in (1, -1):
        # tow pintle brackets, the rear stowage racks either side of the ramp
        lathe(m, Frame((sx * 0.55, 0.75, R - 0.02), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.022, -0.02), (0.045, -0.02), (0.045, 0.02), (0.022, 0.02), (0.022, -0.02)], 12, mat=1)
        for y in (1.4, 1.85):
            tube(m, (sx * 0.95, y, R - 0.03), (sx * 1.25, y, R - 0.03), 0.014, 8, mat=1)
        for xx in (0.95, 1.25):
            tube(m, (sx * xx, 1.35, R - 0.03), (sx * xx, 1.9, R - 0.03), 0.014, 8, mat=1)
    objs.append(m.to_object("Rear_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    hinge = (0, 0.66, R - 0.03)
    n = empty("Ramp", hinge, parent)
    drive(n, "the rear ramp: hinged at its foot, turns about local X; + lowers it to the ground (about 115 degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, 2.0], group="Ramp")
    r = Mesh()
    slab(r, Frame((0, 1.33, R - 0.03), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.8, -0.67), (0.8, -0.67), (0.8, 0.62), (0.74, 0.68), (-0.74, 0.68), (-0.8, 0.62)], 0.055, 0.01)
    for sx in (1, -1):
        lathe(r, Xframe((sx * 0.62, 0.66, R - 0.03), sx), [(0.0, -0.08), (0.04, -0.08), (0.04, 0.08), (0.0, 0.08)], 12, mat=1)
    o = r.to_object("Ramp_Panel", [M["paint"], M["chassis"]], None, sharp_angle=40)
    set_parent(o, n)
    objs.append(o)
    dh = (-0.6, 1.33, R - 0.06)
    d = empty("Ramp_Door", dh, n)
    drive(d, "the door in the ramp: hinged on its right edge, turns about local Y; + opens it outward", control="hinge", axis=[0, 1, 0], limits=[0, 1.6], group="Ramp door")
    dm = Mesh()
    slab(dm, Frame((-0.3, 1.33, R - 0.06), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.29, -0.52), (0.29, -0.52), (0.29, 0.52), (-0.29, 0.52)], 0.012, 0.004)
    box(dm, (-0.06, 1.33, R - 0.069), (0.035, 0.18, 0.006), 0.002, 1, mat=1)
    o = dm.to_object("Ramp_Door_Panel", [M["paint"], M["chassis"]], None, sharp_angle=40)
    set_parent(o, d)
    objs.append(o)
    return objs


def lights(M, parent):
    node = empty("Lights", (0, 1.3, 0), parent)
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        z = FRONT_Z - 0.25
        for name, mat, dx, r in ((f"Light_Head_{side}", M["light_white"], 0.0, 0.065), (f"Light_Blackout_{side}", M["light_amber"], -sx * 0.16, 0.035)):
            c = np.array([sx * 1.0 + dx, top_y(z) + 0.08, z])
            n = empty(name, tuple(c), node)
            m = Mesh()
            lathe(m, Zframe(c - np.array([0, 0, 0.08])), [(0.0, 0.0), (r + 0.02, 0.0), (r + 0.02, 0.09), (r, 0.09), (0.0, 0.09)], 20, mat=1)
            lathe(m, Zframe(c + np.array([0, 0, 0.008])), [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.15), (0.0, r * 0.2)], 20, mat=0)
            path_tube(m, [c + np.array([-0.09, -0.09, 0.0]), c + np.array([-0.09, 0.09, 0.05]), c + np.array([0.09, 0.09, 0.05]), c + np.array([0.09, -0.09, 0.0])], 0.009, 6, mat=1)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
        for name, mat, dy in ((f"Light_Tail_{side}", M["light_red"], 0.0), (f"Light_Tail_Blackout_{side}", M["light_amber"], -0.1)):
            c = np.array([sx * 1.1, 1.75 + dy, RAMP_Z - 0.003])
            n = empty(name, tuple(c), node)
            m = Mesh()
            box(m, tuple(c), (0.1, 0.08, 0.006), 0.003, 1, mat=1)
            lathe(m, Zframe(c - np.array([0, 0, 0.003]), -1), [(0.0, 0.0), (0.03, 0.0), (0.024, 0.008), (0.0, 0.01)], 14, mat=0)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    return objs


def wheels(M, parent):
    node = empty("Wheels", (0, TYRE_R, 0), parent)
    objs = []
    for i, za in enumerate(AXLES_Z):
        for side, sx in (("Left", 1), ("Right", -1)):
            c = (sx * WHEEL_X, TYRE_R, za)
            holder = node
            if i < 2:
                holder = empty(f"Steer_{i + 1}_{side}", c, node)
                lock = STEER_LOCK[i]
                drive(holder, f"steer about local Y; + turns left. Full lock ({math.degrees(STEER_LOCK[0]):.0f} degrees on the first axle, "
                              f"{math.degrees(STEER_LOCK[1]):.0f} on the second) is the inner wheels' for the published 52 ft turning circle.",
                      control="steer", axis=[0, 1, 0], limits=[-round(lock, 4), round(lock, 4)])
            w = empty(f"Wheel_{i + 1}_{side}", c, holder)
            drive(w, "spin about local X; + rolls the vehicle forward", control="wheel", axis=[1, 0, 0], radius=round(TYRE_R, 4))
            m = Mesh()
            tyre(m, c, sx, TYRE_R, TYRE_W, 0.254, blocks=30, block=(0.4, 0.032, 0.1), chevron=18, studs=10)
            objs.append(m.to_object(f"Wheel_{i + 1}_{side}_Mesh", [M["rubber"], M["chassis"]], w, sharp_angle=60))
    # axles and suspension arms under the hull
    a = Mesh()
    for za in AXLES_Z:
        for sx in (1, -1):
            tube(a, (sx * 0.16, AXLE_Y, za), (sx * (WHEEL_X - 0.12), TYRE_R, za), 0.05, 12)  # half shaft, down to the hub
            tube(a, (sx * 0.5, TYRE_R + 0.18, za + 0.2), (sx * (WHEEL_X - 0.3), TYRE_R + 0.1, za + 0.05), 0.03, 8)  # upper arm
            tube(a, (sx * 0.64, TYRE_R + 0.1, za - 0.1), (sx * 0.7, 1.15, za - 0.18), 0.04, 10)  # strut, up into the hull
        lathe(a, Zframe((0, AXLE_Y, za - 0.15)), [(0.0, 0.0), (0.12, 0.02), (0.16, 0.08), (0.16, 0.22), (0.12, 0.28), (0.0, 0.3)], 18)
    objs.append(a.to_object("Axles_And_Suspension", [M["chassis"]], node, sharp_angle=50))
    return objs
