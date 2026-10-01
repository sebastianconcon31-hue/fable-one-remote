"""The M2A3 Bradley's outside: the hull with its sloped front, the engine
grilles and exhaust, add-on side armour and skirts, the rear ramp with its
door, the troop hatch; the two-man turret with the 25 mm M242 Bushmaster
and coaxial M240C, the twin TOW launcher, IBAS and the commander's
independent viewer, smoke launchers and the bustle rack; the running gear
(modelkit's running_gear.tracked with the T157 track, sprocket at the front).

Moving parts:
  Turret (traverse, local Y), Gun (elevate, axis -X: + raises it), TOW_Launcher (raises about local X)
  Ramp (lowers about local X at its foot), Ramp_Door, Troop_Hatch, Driver_Hatch, Commander_Hatch, Gunner_Hatch
  Road_Wheel_*, Sprocket_*, Idler_*, Return_Roller_* (spin), Track_{Left,Right} (links round the loop)"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm
from running_gear import loft, slab, bolt, tracked, link_double_pin
from vehicle import drive
from bradley import *

deg = math.pi / 180
SIDE = Frame((0, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0))  # side profiles (z, y), lofted across x
F, R = FRONT_Z, REAR_PLATE_Z


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def glacis_y(z):
    return NOSE_Y + (F - z) / (F - GLACIS_TOP_Z) * (ROOF_Y - NOSE_Y)


def hatch_lid(M, parent, name, hinge, c, r, axis, limits, what, group="Hatches", shape=None):
    n = empty(name, tuple(hinge), parent)
    drive(n, what, control="hinge", axis=axis, limits=limits, group=group)
    m = Mesh()
    if shape is None:
        lathe(m, Yframe(c), [(0.0, 0.0), (r, 0.0), (r + 0.008, 0.02), (r - 0.02, 0.05), (0.0, 0.055)], 32)
    else:
        w, l = shape
        rbox(m, Zframe(np.asarray(c) + np.array([0, 0.025, 0])), (w, 0.05, l), 0.02, 2)
    box(m, tuple(np.asarray(hinge) + np.array([0, 0.0, 0.0])), (0.22, 0.05, 0.07), 0.012, 1)
    path_tube(m, [np.asarray(c) + np.array([-0.08, 0.05, 0.1]), np.asarray(c) + np.array([-0.08, 0.1, 0.1]), np.asarray(c) + np.array([0.08, 0.1, 0.1]), np.asarray(c) + np.array([0.08, 0.05, 0.1])], 0.01, 8)
    o = m.to_object(name + "_Lid", [M["paint"]], None, sharp_angle=40)
    set_parent(o, n)
    return [o]


# ---- hull ----------------------------------------------------------------------------------------------------------------------
def hull(M, parent):
    node = empty("Hull", (0, 1.2, 0), parent)
    objs = []
    m = Mesh()
    # the lower hull between the tracks; its top stays inside the upper hull (no coplanar faces)
    lower = [(F, 0.95), (F - 0.12, SPONSON_Y + 0.08), (R + 0.1, SPONSON_Y + 0.08), (R, SPONSON_Y), (R, 0.62), (R + 0.32, BELLY_Y), (F - 0.5, BELLY_Y)]
    loft(m, SIDE, [(-LOWER_HALF_W, lower), (LOWER_HALF_W, lower)], radii=[0.03, 0.02, 0.02, 0.02, 0.04, 0.05, 0.05], bevel=0.02)
    upper = [(F - 0.02, SPONSON_Y), (F, NOSE_Y), (GLACIS_TOP_Z, ROOF_Y), (R + 0.06, ROOF_Y), (R, ROOF_Y - 0.06), (R, SPONSON_Y)]
    loft(m, SIDE, [(-HULL_HALF_W, upper), (HULL_HALF_W, upper)], radii=[0.01, 0.03, 0.04, 0.03, 0.03, 0.01], bevel=0.02)
    objs.append(m.to_object("Hull_Armour", [M["paint"]], node, sharp_angle=40))
    objs += front(M, node)
    objs += roof(M, node)
    objs += side_armour(M, node)
    objs += rear(M, node)
    objs += lights(M, node)
    _, gear = tracked(M, parent, dict(
        x=TRACK_X, wheels_z=WHEELS_Z, wheel_y=WHEEL_Y, wheel_r=WHEEL_R, wheel_w=0.17, wheel_gap=0.12,
        idler=IDLER, sprocket=(SPROCKET[0], SPROCKET[1], PITCH / (2 * math.sin(math.pi / SPROCKET_TEETH)), SPROCKET_TEETH),
        rollers=ROLLERS, W=TRACK_W, pitch=PITCH, t_in=T_IN, t_out=T_OUT,
        link=lambda m, p: link_double_pin(m, TRACK_W, p, T_IN, T_OUT, 0.085, guide_w=0.06),
        sag=0.0, hull_x=LOWER_HALF_W, arm=(-0.34, 0.1), shocks=(0, 1, 5), holes=6, tyre_t=0.04, roller_w=0.42,
        sprocket_w=0.045, sprocket_gap=0.14,
        mats=dict(wheel=M["chassis"], rubber=M["rubber"], track=[M["track"], M["rubber"]])))
    objs += gear
    return objs


def front(M, parent):
    objs = []
    m = Mesh()
    slope = math.atan2(ROOF_Y - NOSE_Y, F - GLACIS_TOP_Z)
    G = lambda x, z, h=0.0: Frame((x, glacis_y(z) + h, z), (1, 0, 0), (0, math.sin(slope), -math.cos(slope)), (0, math.cos(slope), math.sin(slope)))
    # engine air intake and access grilles on the right of the glacis
    Gc = G(-0.55, 2.55, 0.012)
    slab(m, Gc, [(-0.42, -0.42), (0.42, -0.42), (0.42, 0.42), (-0.42, 0.42)], 0.024, 0.006)
    for k in range(14):
        v = -0.38 + k * 0.058
        rbox(m, Frame(Gc.p((0, v, 0.018)), Gc.x, Gc.y, Gc.z), (0.78, 0.012, 0.016), 0.003, 1, mat=1)
    # power-pack access plate (left), its hinges and lifting eyes
    Ga = G(0.45, 2.75, 0.008)
    slab(m, Ga, [(-0.38, -0.3), (0.38, -0.3), (0.38, 0.3), (-0.38, 0.3)], 0.016, 0.005)
    for u in (-0.25, 0.25):
        lathe(m, Frame(Ga.p((u, -0.3, 0.02)), Ga.y, Ga.z, Ga.x), [(0.0, -0.05), (0.022, -0.05), (0.022, 0.05), (0.0, 0.05)], 10, mat=1)
    for sx in (1, -1):
        lathe(m, Frame((sx * 1.3, glacis_y(2.9) + 0.05, 2.9), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.025, -0.015), (0.05, -0.015), (0.05, 0.015), (0.025, 0.015), (0.025, -0.015)], 12, mat=1)
    # tow hooks under the nose, the towing shackles
    for sx in (1, -1):
        slab(m, Frame((sx * 0.6, 0.9, F - 0.06), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.05, -0.08), (0.05, -0.08), (0.06, 0.06), (-0.06, 0.06)], 0.12, 0.01, mat=1)
        lathe(m, Frame((sx * 0.6, 0.86, F - 0.06), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.028, -0.028), (0.055, -0.028), (0.055, 0.028), (0.028, 0.028), (0.028, -0.028)], 12, mat=1)
    # the exhaust outlet on the right side, near the front, with its grille
    ex = np.array([-HULL_HALF_W - 0.001, 1.45, 2.1])
    rbox(m, Frame(ex, (0, 0, 1), (0, 1, 0), (-1, 0, 0)), (0.5, 0.3, 0.03), 0.01, 1)
    for k in range(6):
        rbox(m, Frame(ex + np.array([-0.02, -0.12 + k * 0.048, 0]), (0, 0, 1), (0, 1, 0), (-1, 0, 0)), (0.46, 0.012, 0.02), 0.003, 1, mat=1)
    # driver's periscopes round the hatch
    g = Mesh()
    for k, (dx, a) in enumerate(((-0.22, 0.5), (-0.08, 0.15), (0.08, -0.15), (0.22, -0.5))):
        z = 1.98 + abs(dx) * 0.1 + 0.35
        base = glacis_y(z) if z > GLACIS_TOP_Z else ROOF_Y  # they stand on the glacis, ahead of the hatch
        c = np.array([0.6 + dx, base + 0.05, z])
        d = norm(np.array([math.sin(a) * 0.6, 0.0, 1.0]))
        rbox(m, Frame.along(c, d), (0.13, 0.1, 0.1), 0.015, 1)
        Fg = Frame.along(c + d * 0.051, d)
        g.face(g.verts([Fg.p((-0.05, -0.03, 0)), Fg.p((0.05, -0.03, 0)), Fg.p((0.05, 0.03, 0)), Fg.p((-0.05, 0.03, 0))]))
    objs.append(m.to_object("Hull_Front_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(g.to_object("Driver_Periscope_Glass", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    # driver's hatch: on the roof's front left, hinged at its back, lifting up
    c = np.array([0.6, ROOF_Y + 0.03, 1.98])
    ring = Mesh()
    lathe(ring, Yframe((0.6, ROOF_Y, 1.98)), [(0.3, 0.0), (0.37, 0.0), (0.37, 0.035), (0.3, 0.04)], 32)
    objs.append(ring.to_object("Driver_Hatch_Ring", [M["paint"]], parent, sharp_angle=40))
    objs += hatch_lid(M, parent, "Driver_Hatch", (0.6, ROOF_Y + 0.05, 1.68), c, 0.3, [-1, 0, 0], [0, 1.6], "the driver's hatch: hinged at its back, turns about local X; + opens it upward")
    return objs


def roof(M, parent):
    objs = []
    m = Mesh()
    ant = Mesh()  # whip antennas: left out of the published height
    # troop hatch over the squad compartment: a big plate hinged at its back
    tz = R + 0.95
    lathe(m, Yframe((0, ROOF_Y, tz)), [(0.5, 0.0), (0.58, 0.0), (0.58, 0.03), (0.5, 0.035)], 40)
    # roof-edge stowage rails, lifting eyes and the antenna bases at the back corners
    for sx in (1, -1):
        path_tube(m, [np.array([sx * 1.5, ROOF_Y, -0.5]), np.array([sx * 1.5, ROOF_Y + 0.12, -0.55]), np.array([sx * 1.5, ROOF_Y + 0.12, R + 0.25]), np.array([sx * 1.5, ROOF_Y, R + 0.2])], 0.016, 8, mat=1)
        for z in (-0.9, -1.7, R + 0.55):
            tube(m, (sx * 1.5, ROOF_Y, z), (sx * 1.5, ROOF_Y + 0.12, z), 0.012, 6, mat=1)
        b = np.array([sx * 1.42, ROOF_Y, R + 0.12])
        lathe(m, Yframe(b), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.07), (0.035, 0.1), (0.025, 0.18), (0.0, 0.18)], 12, mat=1)
        tube(ant, b + np.array([0, 0.18, 0]), b + np.array([sx * 0.1, 1.9, 0.35]), 0.005, 6, r1=0.0025)
        for z in (GLACIS_TOP_Z - 0.2, R + 0.3):
            lathe(m, Frame((sx * 1.55, ROOF_Y + 0.045, z), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.025, -0.015), (0.05, -0.015), (0.05, 0.015), (0.025, 0.015), (0.025, -0.015)], 12, mat=1)
    objs.append(m.to_object("Hull_Roof_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(ant.to_object("Antennas", [M["chassis"]], parent, sharp_angle=40))
    objs += hatch_lid(M, parent, "Troop_Hatch", (0, ROOF_Y + 0.05, tz - 0.55), (0, ROOF_Y + 0.03, tz), 0.52, [1, 0, 0], [0, 1.7], "the squad's roof hatch: hinged at its back, turns about local X; + opens it upward and back", group="Hatches")
    return objs


def side_armour(M, parent):
    """Add-on armour panels bolted along both sides above the tracks, with the skirts below them."""
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        m = Mesh()
        z0, z1 = F - 0.55, R + 0.12
        edges = np.linspace(z0, z1, 6)
        for k in range(5):
            a, b = edges[k] - 0.006, edges[k + 1] + 0.006
            top = lambda z: min(ROOF_Y - 0.08, glacis_y(z) - 0.03)
            poly = [(a, top(a)), (b, top(b)), (b, SPONSON_Y + 0.02), (a + (0.15 if k == 0 else 0.0), SPONSON_Y + 0.02)]  # the first raked forward
            slab(m, Frame((sx * (ARMOUR_X - 0.0125 - 0.05), 0, 0), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), poly, 0.1, 0.012)
            for zz in np.linspace(min(a, b) + 0.12, max(a, b) - 0.12, 4):
                for yy in (SPONSON_Y + 0.12, ROOF_Y - 0.2):
                    bolt(m, Frame((sx * (ARMOUR_X - 0.0125), yy, zz), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), 0.02, 0.012, mat=1)
        # skirts below the armour, down over the road wheels' tops
        edges = np.linspace(F - 0.5, R + 0.12, 5)
        for k in range(4):
            a, b = edges[k] - 0.004, edges[k + 1] + 0.004
            poly = [(a, SPONSON_Y + 0.04), (b, SPONSON_Y + 0.04), (b, 0.66), (a - (0.2 if k == 0 else 0.0), 0.66)]  # the first raked forward
            slab(m, Frame((sx * (ARMOUR_X - 0.0125 - 0.015), 0, 0), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), poly, 0.03, 0.006)
            for zz in np.linspace(min(a, b) + 0.1, max(a, b) - 0.1, 3):
                bolt(m, Frame((sx * (ARMOUR_X - 0.0125), SPONSON_Y - 0.02, zz), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), 0.016, 0.012, mat=1)
        objs.append(m.to_object(f"Side_Armour_{side}", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    return objs


def rear(M, parent):
    objs = []
    m = Mesh()
    # stowage boxes either side of the ramp, the tow pintle, the rear lifting eyes
    for sx in (1, -1):
        rbox(m, Zframe((sx * 1.25, 1.45, R - 0.035)), (0.62, 0.7, 0.07), 0.015, 1)
        box(m, (sx * 1.25, 1.62, R - 0.073), (0.5, 0.03, 0.012), 0.004, 1, mat=1)
        for y in (1.25, 1.65):
            box(m, (sx * (1.25 - 0.3), y, R - 0.06), (0.03, 0.06, 0.04), 0.006, 1, mat=1)
    lathe(m, Frame((0, 0.6, R - 0.005), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.035, -0.035), (0.075, -0.035), (0.075, 0.035), (0.035, 0.035), (0.035, -0.035)], 18, mat=1)
    objs.append(m.to_object("Hull_Rear_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    # the ramp, hinged at its foot, with the door in it
    hinge = (0, 0.6, R - 0.03)
    n = empty("Ramp", hinge, parent)
    drive(n, "the rear ramp: hinged at its foot, turns about local X; + lowers it to the ground (about 113 degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, 1.98], group="Ramp")
    r = Mesh()
    rc = (0, 1.25, R - 0.03)
    slab(r, Frame(rc, (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.86, -0.64), (0.86, -0.64), (0.86, 0.6), (0.8, 0.66), (-0.8, 0.66), (-0.86, 0.6)], 0.06, 0.01)
    for x in (-0.55, 0.0, 0.55):
        box(r, (x, 1.25, R - 0.064), (0.05, 1.1, 0.012), 0.004, 1, mat=0)
    for sx in (1, -1):
        lathe(r, Xframe((sx * 0.7, 0.6, R - 0.03), sx), [(0.0, -0.08), (0.045, -0.08), (0.045, 0.08), (0.0, 0.08)], 12, mat=1)
    o = r.to_object("Ramp_Panel", [M["paint"], M["chassis"]], None, sharp_angle=40)
    set_parent(o, n)
    objs.append(o)
    # the door in the ramp's left half, hinged on its left edge
    dh = (0.62, 1.3, R - 0.065)
    d = empty("Ramp_Door", dh, n)
    drive(d, "the door in the ramp: hinged on its left edge, turns about local Y; + opens it outward", control="hinge", axis=[0, -1, 0], limits=[0, 1.6], group="Ramp door")
    dm = Mesh()
    slab(dm, Frame((0.3, 1.3, R - 0.065), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.3, -0.5), (0.3, -0.5), (0.3, 0.5), (-0.3, 0.5)], 0.016, 0.005)
    box(dm, (0.06, 1.3, R - 0.0765), (0.04, 0.2, 0.007), 0.003, 1, mat=1)
    for y in (0.95, 1.65):
        lathe(dm, Yframe((0.62, y - 0.05, R - 0.062)), [(0.0, 0.0), (0.017, 0.0), (0.017, 0.1), (0.0, 0.1)], 10, mat=1)
    o = dm.to_object("Ramp_Door_Panel", [M["paint"], M["chassis"]], None, sharp_angle=40)
    set_parent(o, d)
    objs.append(o)
    return objs


def lights(M, parent):
    node = empty("Lights", (0, 1.3, 0), parent)
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        z = F - 0.12
        for name, mat, dx, r in ((f"Light_Head_{side}", M["light_white"], 0.0, 0.07), (f"Light_Blackout_{side}", M["light_amber"], -sx * 0.17, 0.04)):
            c = np.array([sx * 1.3 + dx, glacis_y(z) + 0.09, z])
            n = empty(name, tuple(c), node)
            m = Mesh()
            lathe(m, Zframe(c - np.array([0, 0, 0.08])), [(0.0, 0.0), (r + 0.02, 0.0), (r + 0.02, 0.09), (r, 0.09), (0.0, 0.09)], 20, mat=1)
            lathe(m, Zframe(c + np.array([0, 0, 0.008])), [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.15), (0.0, r * 0.2)], 20, mat=0)
            path_tube(m, [c + np.array([-0.1, -0.1, 0.0]), c + np.array([-0.1, 0.1, 0.06]), c + np.array([0.1, 0.1, 0.06]), c + np.array([0.1, -0.1, 0.0])], 0.01, 6, mat=1)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
        for name, mat, dy in ((f"Light_Tail_{side}", M["light_red"], 0.0), (f"Light_Tail_Blackout_{side}", M["light_amber"], -0.12)):
            c = np.array([sx * 1.45, 1.9 + dy, R - 0.003])
            n = empty(name, tuple(c), node)
            m = Mesh()
            box(m, tuple(c + np.array([0, 0, 0.0])), (0.12, 0.1, 0.006), 0.004, 1, mat=1)
            lathe(m, Zframe(c - np.array([0, 0, 0.003]), -1), [(0.0, 0.0), (0.035, 0.0), (0.028, 0.008), (0.0, 0.01)], 16, mat=0)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    return objs


# ---- turret --------------------------------------------------------------------------------------------------------------------
def plan(side=1.08, front=1.0, rear=-1.05, nose=0.58):
    """The turret from above, (x, z) about the ring centre: a sloped front, flat sides, the bustle."""
    L = [(0.0, front + 0.02), (nose, front), (side, front - 0.3), (side, -0.7), (side - 0.08, rear + 0.1), (side - 0.2, rear)]
    return L + [(-x, z) for x, z in reversed(L[1:])]


def at(x, y, zr):
    return np.array([x, y, TURRET_Z + zr])


def turret(M, parent):
    node = empty("Turret", (0, TURRET_BASE_Y, TURRET_Z), parent)
    drive(node, "the turret: traverses about local Y; + turns it left (all the way round)", control="traverse", axis=[0, 1, 0])
    objs = []
    m = Mesh()
    Fp = Frame((0, 0, TURRET_Z), (1, 0, 0), (0, 0, -1), (0, 1, 0))
    flip = lambda poly: [(x, -z) for x, z in poly]
    loft(m, Fp, [(TURRET_BASE_Y, flip(plan(1.02, 0.98, -1.0))), (2.12, flip(plan())), (TURRET_ROOF_Y, flip(plan(0.98, 0.55, -1.0, 0.45)))], radii=0.02, bevel=0.02)
    objs.append(m.to_object("Turret_Shell", [M["paint"]], node, sharp_angle=40))
    objs += gun(M, node)
    objs += tow(M, node)
    objs += turret_top(M, node)
    return objs


def gun(M, parent):
    tx, ty, tz = TRUNNION
    g = empty("Gun", TRUNNION, parent)
    drive(g, "the 25 mm M242 Bushmaster and the coaxial M240C: elevate about local X; + raises them (-10 to +60 degrees)", control="elevate", axis=[-1, 0, 0], limits=[-10 * deg, 60 * deg])
    m = Mesh()
    # mantlet with the gun's recoil housing, the barrel, its muzzle device; the coax beside it
    rbox(m, Zframe((0.0, ty, tz + 0.02)), (0.52, 0.3, 0.36), 0.03, 2)
    lathe(m, Zframe((0.0, ty, tz + 0.2)), [(0.0, 0.0), (0.085, 0.0), (0.085, 0.42), (0.06, 0.46), (0.045, 0.48), (0.04, 0.5), (0.04, 1.74), (0.05, 1.76), (0.05, 1.88), (0.032, 1.9), (0.0, 1.9)], 20, mat=1)
    lathe(m, Zframe((-0.17, ty - 0.02, tz + 0.2)), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.08), (0.02, 0.1), (0.016, 0.42), (0.0, 0.42)], 12, mat=1)
    return [m.to_object("Gun_Mesh", [M["paint"], M["gun"]], g, sharp_angle=40)]


def tow(M, parent):
    """The twin TOW launcher on the turret's left side: it raises on its arm at the back to fire."""
    piv = at(1.22, 2.22, -0.55)
    n = empty("TOW_Launcher", tuple(piv), parent)
    drive(n, "the twin TOW launcher: raises about local X at its back; + lifts it to the firing position (about 45 degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, 0.78], group="TOW launcher")
    m = Mesh()
    c = at(1.27, 2.32, 0.02)
    rbox(m, Zframe(c), (0.36, 0.42, 1.18), 0.03, 2)
    for k, dy in enumerate((-0.1, 0.1)):
        lathe(m, Zframe(c + np.array([0.0, dy, 0.59])), [(0.0, 0.0), (0.085, 0.0), (0.085, 0.004), (0.0, 0.004)], 20, mat=1)
    box(m, tuple(c + np.array([0, 0.0, 0.6])), (0.3, 0.38, 0.012), 0.006, 1)
    box(m, tuple(piv + np.array([-0.08, -0.04, 0.0])), (0.18, 0.12, 0.14), 0.02, 1)
    o = m.to_object("TOW_Launcher_Box", [M["paint"], M["gun"]], n, sharp_angle=40)
    return [o]


def turret_top(M, parent):
    y = TURRET_ROOF_Y
    objs = []
    m = Mesh()
    g = Mesh()
    # IBAS, the gunner's sight, on the turret's front right with its armoured doors
    sc = at(-0.62, y + 0.15, 0.35)
    rbox(m, Zframe(sc), (0.4, 0.3, 0.5), 0.03, 2)
    for sx in (1, -1):
        rbox(m, Frame(sc + np.array([sx * 0.22, 0.0, 0.28]), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), (0.12, 0.24, 0.02), 0.006, 1)
    w = sc + np.array([0, 0.0, 0.252])
    g.face(g.verts([w + np.array([-0.14, -0.08, 0]), w + np.array([0.14, -0.08, 0]), w + np.array([0.14, 0.08, 0]), w + np.array([-0.14, 0.08, 0])]))
    # smoke grenade launchers, four tubes a side on the turret's front corners
    for sx in (1, -1):
        base = at(sx * 0.95, 2.36, 0.62)
        d = norm(np.array([sx * 0.5, 0.5, 0.7]))
        box(m, tuple(base), (0.16, 0.1, 0.2), 0.012, 1, mat=1)
        for k in range(4):
            p = base + np.array([(k % 2 - 0.5) * 0.07, 0.05 + (k // 2) * 0.07, 0.0])
            lathe(m, Frame.along(p, d), [(0.0, 0.0), (0.036, 0.0), (0.036, 0.18), (0.028, 0.18), (0.028, 0.04), (0.0, 0.04)], 12, mat=1)
    # bustle rack and its load
    z0, z1 = -1.02, -1.38
    for x in (0.9, -0.9):
        tube(m, at(x, 2.15, z0), at(x, 2.15, z1), 0.014, 8, mat=1)
    path_tube(m, [at(0.9, 2.15, z0), at(0.9, 2.5, z1), at(-0.9, 2.5, z1), at(-0.9, 2.15, z0)], 0.014, 8, mat=1)
    path_tube(m, [at(0.9, 2.15, z1), at(-0.9, 2.15, z1)], 0.014, 8, mat=1)
    for x in np.linspace(-0.8, 0.8, 7):
        tube(m, at(x, 2.15, z1), at(x, 2.5, z1), 0.008, 6, mat=1)
    objs.append(m.to_object("Turret_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(g.to_object("IBAS_Window", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    s = Mesh()
    F_ = Xframe(at(0.0, 2.3, -1.2))
    lathe(s, Frame(F_.o - F_.z * 0.7, F_.x, F_.y, F_.z), [(0.0, 0.0), (0.12, 0.0), (0.15, 0.03), (0.16, 0.15), (0.16, 1.25), (0.15, 1.37), (0.12, 1.4), (0.0, 1.4)], 20, mat=0)
    for t in (-0.45, 0.0, 0.45):
        lathe(s, Frame(F_.o + F_.z * t, F_.x, F_.y, F_.z), [(0.16, -0.02), (0.175, -0.02), (0.175, 0.02), (0.16, 0.02)], 20, mat=1)
    rbox(s, Xframe(at(0.4, 2.52, -1.2)), (0.26, 0.24, 0.6), 0.1, 3, mat=2)
    objs.append(s.to_object("Turret_Stowage", [M["canvas"], M["strap"], M["duffel"]], parent, sharp_angle=50))
    # the commander's independent viewer on its mast at the right rear: the vehicle's highest point
    cv = at(-0.62, y, -0.62)
    n = empty("CIV", tuple(cv), parent)
    drive(n, "the commander's independent viewer: its head slews about local Y", control="aux", axis=[0, 1, 0])
    c = Mesh()
    lathe(c, Yframe(cv), [(0.0, 0.0), (0.17, 0.0), (0.17, 0.05), (0.09, 0.08), (0.09, 0.16), (0.0, 0.16)], 24)
    top = SPEC["height"]
    rbox(c, Zframe(cv + np.array([0, (top - y) - 0.11 - 0.0, 0.02])), (0.36, 0.22, 0.38), 0.04, 2)
    gc = Mesh()
    wv = cv + np.array([0, top - y - 0.11, 0.211])
    gc.face(gc.verts([wv + np.array([-0.12, -0.06, 0]), wv + np.array([0.12, -0.06, 0]), wv + np.array([0.12, 0.06, 0]), wv + np.array([-0.12, 0.06, 0])]))
    objs.append(c.to_object("CIV_Head", [M["paint"]], n, sharp_angle=40))
    objs.append(gc.to_object("CIV_Window", [M["optic"]], n, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    # the commander's and gunner's hatches
    for name, x, zr, what in (("Commander_Hatch", -0.48, -0.1, "the commander's hatch"), ("Gunner_Hatch", 0.45, -0.18, "the gunner's hatch")):
        hc = at(x, y, zr)
        ring = Mesh()
        lathe(ring, Yframe(hc), [(0.3, 0.0), (0.37, 0.0), (0.37, 0.04), (0.3, 0.05)], 32)
        objs.append(ring.to_object(name + "_Ring", [M["paint"]], parent, sharp_angle=40))
        objs += hatch_lid(M, parent, name, hc + np.array([0, 0.06, -0.31]), hc + np.array([0, 0.035, 0]), 0.3, [-1, 0, 0], [0, 1.7], f"{what}: hinged at its back, turns about local X; + opens it upward")
    return objs
