"""The M978A4's fuel body: the 2,500 gallon tank on its cradles, catwalk,
manholes and fold-down handrails, the ladder, hose tubes and extinguishers,
the rear pump module with its doors, hose reels, pump, filter-separator and
meters, and the rear end.

Moving parts are their own nodes:
  Pump_Door_{Left,Right}       the rear doors, on hinges at their outer edges (local Y)
  Pump_Side_Door_{Left,Right}  the side doors, hinged along their tops (local Z)
  Hose_Reel_{1,2}              the reels turn about local X to pay hose out"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, fillet_path, Yframe, Xframe, Zframe
from running_gear import slab, loft, bolt
from vehicle import drive
from m978 import *

deg = math.pi / 180


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def superellipse(a, b, n=TANK_N, k=56):
    pts = []
    for i in range(k):
        t = 2 * math.pi * (i + 0.5) / k
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def tank_rings(a=TANK_A, b=TANK_B, y=TANK_Y, z0=TANK_FRONT_Z, length=TANK_LEN, head=TANK_HEAD, steps=7):
    """Rings from the front head's tip to the rear head's: the dished heads ease the oval down to a small flat."""
    rings = []
    for j in range(steps, 0, -1):  # front head
        u = j / steps
        s = math.sqrt(max(0.0, 1 - u * u)) * 0.96 + 0.04
        rings.append([(x * s, y + yy * s, z0 - head * (1 - u)) for x, yy in superellipse(a, b)])
    for z in np.linspace(z0 - head, z0 - length + head, 12):
        rings.append([(x, y + yy, z) for x, yy in superellipse(a, b)])
    for j in range(1, steps + 1):  # rear head
        u = j / steps
        s = math.sqrt(max(0.0, 1 - u * u)) * 0.96 + 0.04
        rings.append([(x * s, y + yy * s, z0 - length + head * (1 - u)) for x, yy in superellipse(a, b)])
    return rings


def tank(M, parent):
    node = empty("Tank", (0, TANK_Y, (TANK_FRONT_Z + TANK_REAR_Z) / 2), parent)
    objs = []
    m = Mesh()
    ids = m.grid(tank_rings(), closed=True)
    m.cap(ids[0], center=np.mean([m.v[i] for i in ids[0]], axis=0))
    m.cap(ids[-1], center=np.mean([m.v[i] for i in ids[-1]], axis=0))
    # girth seams where the shell's sheets are welded, standing proud
    for z in (TANK_FRONT_Z - TANK_HEAD - 0.01, TANK_FRONT_Z - TANK_LEN / 2, TANK_REAR_Z + TANK_HEAD + 0.01):
        ring = superellipse(TANK_A + 0.006, TANK_B + 0.006)
        m.grid([[(x, TANK_Y + y, z + 0.012) for x, y in ring], [(x, TANK_Y + y, z - 0.012) for x, y in ring]], closed=True)
    objs.append(m.to_object("Tank_Shell", [M["paint"]], node, sharp_angle=50))
    # hold-down bands over the shell into the cradles, and the cradles on the frame
    c = Mesh()
    zc = (TANK_FRONT_Z + TANK_REAR_Z) / 2
    for z in (TANK_FRONT_Z - 0.55, zc, TANK_REAR_Z + 0.55):
        ring = superellipse(TANK_A + 0.014, TANK_B + 0.014)
        c.grid([[(x, TANK_Y + y, z + 0.04) for x, y in ring], [(x, TANK_Y + y, z - 0.04) for x, y in ring]], closed=True, mat=1)
        for sx in (1, -1):
            box(c, (sx * (TANK_A - 0.05), TANK_BOTTOM_Y + 0.05, z), (0.06, 0.1, 0.1), 0.01, 1, mat=1)
            bolt(c, Frame((sx * (TANK_A - 0.05), TANK_BOTTOM_Y + 0.1, z), (1, 0, 0), (0, 0, 1), (0, 1, 0)), 0.014, 0.02, mat=1)
        # cradle: a saddle shaped to the shell's underside, standing on the frame rails
        cr = [(x, y) for x, y in superellipse(TANK_A, TANK_B) if y < -0.3 * TANK_B]
        cr = sorted(cr, key=lambda p: p[0])
        poly = [(cr[0][0], RAIL_Y1 - TANK_Y)] + [(x, y - 0.004) for x, y in cr] + [(cr[-1][0], RAIL_Y1 - TANK_Y)]
        prism(c, Frame((0, TANK_Y, z), (1, 0, 0), (0, 1, 0), (0, 0, 1)), poly[::-1], 0.12, mat=1)
    # subframe side rails along the tank's base, carrying the side reflectors and the hose tubes
    for sx in (1, -1):
        box(c, (sx * 1.17, 1.44, (TANK_FRONT_Z + PUMP_FRONT_Z) / 2), (0.06, 0.14, TANK_FRONT_Z - PUMP_FRONT_Z), 0.01, 1, mat=0)
        for z in np.arange(TANK_FRONT_Z - 0.3, PUMP_FRONT_Z, -0.7):
            box(c, (sx * 0.8, 1.38, z), (0.72, 0.08, 0.08), 0.01, 1, mat=1)
    objs.append(c.to_object("Tank_Cradles", [M["paint"], M["chassis"]], node, sharp_angle=45))
    objs += tank_top(M, node)
    objs += tank_sides(M, node)
    return objs


def tank_top(M, parent):
    objs = []
    top = TANK_Y + TANK_B
    t = Mesh()
    # catwalk: a grating down the middle, on stand-offs
    z0, z1 = TANK_FRONT_Z - 0.3, TANK_REAR_Z + 0.25
    zc, L = (z0 + z1) / 2, z0 - z1
    for sx in (1, -1):
        box(t, (sx * 0.31, top + 0.06, zc), (0.04, 0.05, L), 0.006, 1, mat=0)
    for z in np.arange(z0 - 0.02, z1, -0.055):
        box(t, (0, top + 0.07, z), (0.6, 0.03, 0.012), 0.003, 1, mat=0)
    for z in np.arange(z0 - 0.2, z1, -0.6):
        box(t, (0, top + 0.03, z), (0.5, 0.05, 0.05), 0.006, 1, mat=0)
    # fold-down handrails, lying flat along both sides of the catwalk
    for sx in (1, -1):
        x = sx * 0.5
        path_tube(t, [np.array([x, top + 0.035, z0]), np.array([x, top + 0.035, z1])], 0.017, 10, mat=1)
        for z in np.linspace(z0 - 0.1, z1 + 0.1, 4):
            box(t, (sx * 0.43, top + 0.035, z), (0.16, 0.035, 0.05), 0.008, 1, mat=1)
            lathe(t, Xframe((sx * 0.36, top + 0.03, z), sx), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.05), (0.0, 0.05)], 10, mat=1)
    objs.append(t.to_object("Catwalk_And_Handrails", [M["chassis"], M["paint"]], parent, sharp_angle=45))
    # two manholes with their lids, dog clamps, hinges and vent valves
    h = Mesh()
    for z in (TANK_FRONT_Z - 0.95, TANK_REAR_Z + 1.05):
        c = (0.0, top - 0.02, z)
        lathe(h, Yframe(c), [(0.0, 0.0), (0.33, 0.0), (0.33, 0.1), (0.31, 0.12), (0.26, 0.12)], 40, mat=0)
        lathe(h, Yframe((0, top + 0.1, z)), [(0.27, 0.0), (0.3, 0.005), (0.3, 0.03), (0.26, 0.05), (0.15, 0.07), (0.0, 0.075)], 40, mat=0)
        for k in range(6):
            a = 2 * math.pi * (k + 0.5) / 6
            p = np.array([math.cos(a) * 0.31, top + 0.12, z + math.sin(a) * 0.31])
            box(h, tuple(p), (0.05, 0.04, 0.05), 0.008, 1, mat=1)
            tube(h, p, p + np.array([0, 0.07, 0]), 0.008, 6, mat=1)
        box(h, (0.0, top + 0.12, z - 0.33), (0.18, 0.05, 0.06), 0.01, 1, mat=1)
        # pressure-vacuum vent and the fill cap beside the lid
        lathe(h, Yframe((0.2, top + 0.17, z + 0.05)), [(0.0, 0.0), (0.045, 0.0), (0.045, 0.06), (0.07, 0.07), (0.07, 0.1), (0.0, 0.11)], 18, mat=1)
        lathe(h, Yframe((-0.18, top + 0.17, z - 0.02)), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.05), (0.0, 0.055)], 18, mat=1)
    objs.append(h.to_object("Manholes", [M["paint"], M["chassis"]], parent, sharp_angle=45))
    return objs


def tank_sides(M, parent):
    objs = []
    s = Mesh()
    # ladder up the front left of the tank to the catwalk
    lx, lz = 1.0, TANK_FRONT_Z - 0.08
    for dx in (-0.2, 0.2):
        path_tube(s, [np.array([lx + dx * 0.0, 0.58, lz + dx]), np.array([lx, TANK_Y + TANK_B + 0.4, lz + dx])], 0.018, 10, mat=1)
    for y in np.arange(0.66, TANK_Y + TANK_B + 0.2, 0.3):
        tube(s, (lx, y, lz - 0.2), (lx, y, lz + 0.2), 0.014, 8, mat=1)
    # hose tubes under the tank on the right: the suction hoses ride in them, capped at the back
    for k, y in enumerate((1.22, 1.06)):
        tube(s, (-1.0, y, TANK_FRONT_Z - 0.6), (-1.0, y, PUMP_FRONT_Z + 0.05), 0.075, 20, mat=0)
        lathe(s, Zframe((-1.0, y, PUMP_FRONT_Z + 0.04), -1), [(0.0, 0.0), (0.085, 0.0), (0.085, 0.05), (0.0, 0.055)], 20, mat=1)
        for z in (TANK_FRONT_Z - 1.0, TANK_REAR_Z + 1.2):
            box(s, (-0.95, y + 0.05, z), (0.22, 0.03, 0.05), 0.006, 1, mat=1)
    # fire extinguishers in quick-release brackets, front of the tank, both sides
    for sx in (1, -1):
        c = (sx * 1.02, 1.08, TANK_FRONT_Z - 0.2 if sx > 0 else TANK_FRONT_Z - 0.15)
        lathe(s, Yframe(c), [(0.0, 0.0), (0.085, 0.0), (0.09, 0.02), (0.09, 0.52), (0.07, 0.58), (0.03, 0.6), (0.0, 0.6)], 20, mat=2)
        lathe(s, Yframe((c[0], c[1] + 0.6, c[2])), [(0.0, 0.0), (0.025, 0.0), (0.025, 0.06), (0.0, 0.065)], 10, mat=1)
        tube(s, (c[0], c[1] + 0.64, c[2]), (c[0] + sx * 0.0, c[1] + 0.66, c[2] + 0.12), 0.008, 6, mat=1)
        for y in (0.12, 0.45):
            box(s, (c[0], c[1] + y, c[2]), (0.2, 0.03, 0.2), 0.004, 1, mat=1)
    # tool box under the left of the tank, behind the vehicle's own fuel tank
    rbox(s, Zframe((1.0, 1.05, -0.95)), (0.38, 0.5, 0.9), 0.03, 2, mat=0)
    for dz in (-0.25, 0.25):
        box(s, (1.193, 1.2, -0.95 + dz), (0.012, 0.06, 0.05), 0.004, 1, mat=1)
    objs.append(s.to_object("Tank_Side_Equipment", [M["paint"], M["chassis"], M["extinguisher"]], parent, sharp_angle=45))
    return objs


# ---- rear pump module ----------------------------------------------------------------------------------------------------
def pump_module(M, parent):
    z0, z1 = PUMP_FRONT_Z, PUMP_REAR_Z
    zc, L = (z0 + z1) / 2, z0 - z1
    yc, H = (PUMP_BOTTOM_Y + PUMP_TOP_Y) / 2, PUMP_TOP_Y - PUMP_BOTTOM_Y
    node = empty("Pump_Module", (0, yc, zc), parent)
    objs = []
    m = Mesh()
    W = 2 * PUMP_HALF_W
    t = 0.03
    # the enclosure: roof, floor, front wall, the side frames round the side doors, the rear frame round the rear doors
    box(m, (0, PUMP_TOP_Y - t / 2, zc), (W, t, L), 0.012, 1, mat=0)
    box(m, (0, PUMP_BOTTOM_Y + t / 2, zc), (W, t, L), 0.008, 1, mat=0)
    box(m, (0, yc, z0 - t / 2), (W, H, t), 0.01, 1, mat=0)
    for sx in (1, -1):
        x = sx * (PUMP_HALF_W - t / 2)
        box(m, (x, yc, z0 - 0.06), (t, H, 0.12), 0.008, 1, mat=0)
        box(m, (x, yc, z1 + 0.06), (t, H, 0.12), 0.008, 1, mat=0)
        box(m, (x, PUMP_BOTTOM_Y + 0.12, zc), (t, 0.24, L), 0.008, 1, mat=0)
        box(m, (x, PUMP_TOP_Y - 0.06, zc), (t, 0.12, L), 0.008, 1, mat=0)
    box(m, (0, PUMP_TOP_Y - 0.06, z1 + t / 2), (W, 0.12, t), 0.008, 1, mat=0)
    box(m, (0, PUMP_BOTTOM_Y + 0.06, z1 + t / 2), (W, 0.12, t), 0.008, 1, mat=0)
    box(m, (0, yc, z1 + t / 2), (0.08, H, t), 0.008, 1, mat=0)
    # rain gutter round the roof, and lifting eyes
    for sx in (1, -1):
        box(m, (sx * (PUMP_HALF_W + 0.012), PUMP_TOP_Y - 0.01, zc), (0.025, 0.03, L + 0.04), 0.006, 1, mat=0)
        for z in (z0 - 0.15, z1 + 0.15):
            lathe(m, Frame((sx * (PUMP_HALF_W - 0.1), PUMP_TOP_Y + 0.035, z), (0, 1, 0), (1, 0, 0), (0, 0, 1)), [(0.02, -0.012), (0.04, -0.012), (0.04, 0.012), (0.02, 0.012), (0.02, -0.012)], 12, mat=1)
    objs.append(m.to_object("Pump_Enclosure", [M["paint"], M["chassis"]], node, sharp_angle=45))
    # inside: dark walls, the pump and its engine, filter-separator, meters, valves and two hose reels
    i = Mesh()
    dials = Mesh()
    box(i, (0, yc, z0 - t - 0.002), (W - 0.08, H - 0.08, 0.004), 0.002, 1, mat=0)
    for sx in (1, -1):
        box(i, (sx * (PUMP_HALF_W - t - 0.003), yc, zc), (0.004, H - 0.08, L - 0.1), 0.002, 1, mat=0)
    rbox(i, Zframe((0.55, PUMP_BOTTOM_Y + 0.3, z0 - 0.45)), (0.6, 0.5, 0.6), 0.04, 2, mat=1)  # pump unit
    lathe(i, Yframe((-0.6, PUMP_BOTTOM_Y + 0.04, z0 - 0.42)), [(0.0, 0.0), (0.2, 0.0), (0.22, 0.04), (0.22, 0.85), (0.18, 0.95), (0.0, 0.98)], 28, mat=1)  # filter-separator
    for k in range(2):  # flow meters with their dials
        mc = (0.05 + k * 0.42, PUMP_BOTTOM_Y + 0.72, z0 - 0.3)
        rbox(i, Zframe(mc), (0.32, 0.26, 0.22), 0.03, 2, mat=1)
        lathe(dials, Zframe((mc[0], mc[1] + 0.02, mc[2] - 0.111), -1), [(0.0, 0.0), (0.09, 0.0), (0.09, 0.012), (0.0, 0.012)], 24)
    path_tube(i, [np.array([0.55, PUMP_BOTTOM_Y + 0.3, z0 - 0.15]), np.array([0.55, PUMP_BOTTOM_Y + 0.3, z0 - 0.05]), np.array([-0.6, PUMP_BOTTOM_Y + 0.3, z0 - 0.05]), np.array([-0.6, PUMP_BOTTOM_Y + 0.3, z0 - 0.2])], 0.05, 14, mat=1)
    for x in (-0.25, 0.3):
        lathe(i, Zframe((x, PUMP_BOTTOM_Y + 1.0, z0 - 0.06)), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.08), (0.0, 0.08)], 14, mat=3)
    objs.append(i.to_object("Pump_Equipment", [M["interior"], M["chassis"], M["glass"], M["hazard"]], node, sharp_angle=45))
    objs.append(dials.to_object("Meter_Dials", [M["glass"]], node, sharp_angle=45))
    for k, x in enumerate((0.55, -0.55)):
        c = (x, PUMP_BOTTOM_Y + 0.62, z1 + 0.62)
        reel = empty(f"Hose_Reel_{k + 1}", c, node)
        drive(reel, "a hose reel: turns about local X; + pays the hose out", control="wheel", axis=[1, 0, 0], radius=0.3)
        r = Mesh()
        F = Xframe(c)
        lathe(r, F, [(0.0, -0.3), (0.42, -0.3), (0.42, -0.28), (0.12, -0.27), (0.12, 0.27), (0.42, 0.28), (0.42, 0.3), (0.0, 0.3)], 36, mat=0)
        for j in range(6):  # wound hose, a few turns deep
            for layer in range(3):
                rr = 0.16 + layer * 0.055
                ring = [F.p((rr * math.cos(a) + 0.0, rr * math.sin(a), -0.24 + j * 0.095)) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
                path_tube(r, ring + [ring[0]], 0.026, 8, mat=1, caps=False)
        objs.append(r.to_object(f"Hose_Reel_{k + 1}_Mesh", [M["chassis"], M["hose"]], reel, sharp_angle=50))
        # the nozzle on its bracket
        n = Mesh()
        nc = np.array([x, PUMP_BOTTOM_Y + 1.02, z1 + 0.25])
        rbox(n, Zframe(nc), (0.12, 0.2, 0.3), 0.03, 2, mat=1)
        tube(n, nc + np.array([0, 0.02, -0.15]), nc + np.array([0, -0.05, -0.32]), 0.03, 12, mat=1)
        objs.append(n.to_object(f"Nozzle_{k + 1}", [M["chassis"], M["steel"]], node, sharp_angle=45))
    objs += pump_doors(M, node)
    return objs


def pump_doors(M, parent):
    """Rear doors hinge at their outer edges and swing out; side doors hinge along their tops and lift."""
    objs = []
    z1 = PUMP_REAR_Z
    y0, y1 = PUMP_BOTTOM_Y + 0.12, PUMP_TOP_Y - 0.12
    for side, sx in (("Left", 1), ("Right", -1)):
        hx = sx * (PUMP_HALF_W - 0.03)
        d = empty(f"Pump_Door_{side}", (hx, (y0 + y1) / 2, z1 - 0.005), parent)
        drive(d, "a rear pump-module door: swings about local Y on its outer hinges; + opens it outward (to 100 degrees)",
              control="hinge", axis=[0, -1 if sx > 0 else 1, 0], limits=[0, 1.75], group="Pump doors")
        m = Mesh()
        w = PUMP_HALF_W - 0.07
        cx = hx - sx * w / 2
        box(m, (cx, (y0 + y1) / 2, z1 - 0.012), (w - 0.01, y1 - y0 - 0.01, 0.025), 0.008, 1, mat=0)
        for yy in (y0 + 0.2, (y0 + y1) / 2, y1 - 0.2):  # stiffeners pressed into the door
            box(m, (cx, yy, z1 - 0.027), (w - 0.12, 0.05, 0.006), 0.004, 1, mat=0)
        for yy in (y0 + 0.12, y1 - 0.12):
            lathe(m, Yframe((hx + sx * 0.005, yy - 0.06, z1 - 0.02)), [(0.0, 0.0), (0.018, 0.0), (0.018, 0.12), (0.0, 0.12)], 10, mat=1)
        # lever latch near the meeting edge
        lx = hx - sx * (w - 0.08)
        box(m, (lx, (y0 + y1) / 2, z1 - 0.035), (0.04, 0.32, 0.025), 0.008, 1, mat=1)
        box(m, (lx, (y0 + y1) / 2 + 0.1, z1 - 0.05), (0.03, 0.06, 0.03), 0.006, 1, mat=1)
        o = m.to_object(f"Pump_Door_{side}_Panel", [M["paint"], M["chassis"]], None, sharp_angle=45)
        set_parent(o, d)
        objs.append(o)
        # side door
        hy = PUMP_TOP_Y - 0.12
        zc = (PUMP_FRONT_Z + PUMP_REAR_Z) / 2
        L = PUMP_FRONT_Z - PUMP_REAR_Z - 0.26
        sd = empty(f"Pump_Side_Door_{side}", (sx * (PUMP_HALF_W + 0.002), hy, zc), parent)
        drive(sd, "a side door of the pump module: hinged along its top, turns about local Z; + lifts it (to 80 degrees)",
              control="hinge", axis=[0, 0, 1 if sx > 0 else -1], limits=[0, 1.4], group="Pump doors")
        s = Mesh()
        sh = hy - (PUMP_BOTTOM_Y + 0.24)
        box(s, (sx * (PUMP_HALF_W + 0.012), hy - sh / 2, zc), (0.022, sh - 0.01, L), 0.008, 1, mat=0)
        for zz in np.linspace(zc - L / 2 + 0.25, zc + L / 2 - 0.25, 3):
            box(s, (sx * (PUMP_HALF_W + 0.026), hy - sh / 2, zz), (0.006, sh - 0.12, 0.05), 0.003, 1, mat=0)
        tube(s, (sx * (PUMP_HALF_W + 0.012), hy + 0.005, zc - L / 2 + 0.05), (sx * (PUMP_HALF_W + 0.012), hy + 0.005, zc + L / 2 - 0.05), 0.012, 8, mat=1)
        for zz in (zc - L / 2 + 0.2, zc + L / 2 - 0.2):
            box(s, (sx * (PUMP_HALF_W + 0.03), hy - sh + 0.06, zz), (0.025, 0.06, 0.12), 0.006, 1, mat=1)
        o = s.to_object(f"Pump_Side_Door_{side}_Panel", [M["paint"], M["chassis"]], None, sharp_angle=45)
        set_parent(o, sd)
        objs.append(o)
    return objs


# ---- rear end ----------------------------------------------------------------------------------------------------------------
def rear_end(M, parent):
    node = empty("Rear_End", (0, 0.9, REAR_Z + 0.5), parent)
    objs = []
    r = Mesh()
    # deck between the frame and the pump module
    box(r, (0, RAIL_Y1 + 0.02, (PUMP_FRONT_Z + PUMP_REAR_Z) / 2), (2.2, 0.06, PUMP_FRONT_Z - PUMP_REAR_Z), 0.01, 1, mat=0)
    zr = BUMPER_REAR_Z
    rbox(r, Zframe((0, 0.92, zr + 0.07)), (2.2, 0.3, 0.14), 0.025, 2, mat=0)
    for sx in (1, -1):
        box(r, (sx * 0.5, 1.1, (zr + PUMP_REAR_Z) / 2 + 0.05), (0.1, 0.36, PUMP_REAR_Z - zr + 0.1), 0.01, 1, mat=0)
    lathe(r, Frame((0, 0.88, zr - 0.06), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.05, -0.04), (0.11, -0.04), (0.11, 0.04), (0.05, 0.04), (0.05, -0.04)], 20, mat=1)
    rbox(r, Zframe((0, 0.88, zr + 0.0)), (0.16, 0.14, 0.12), 0.02, 1, mat=1)
    for sx in (1, -1):
        lathe(r, Frame((sx * 0.62, 0.8, zr - 0.02), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.035, -0.035), (0.07, -0.035), (0.07, 0.035), (0.035, 0.035), (0.035, -0.035)], 16, mat=1)
    # static grounding reel on the bumper's right end, with its clamp
    gc = (-0.85, 1.12, zr + 0.14)
    lathe(r, Xframe(gc), [(0.0, -0.08), (0.14, -0.08), (0.14, -0.07), (0.05, -0.065), (0.05, 0.065), (0.14, 0.07), (0.14, 0.08), (0.0, 0.08)], 24, mat=1)
    for k in range(5):
        lathe(r, Xframe((gc[0], gc[1], gc[2])), [(0.06 + k * 0.012, -0.06), (0.065 + k * 0.012, -0.06), (0.065 + k * 0.012, 0.06), (0.06 + k * 0.012, 0.06)], 20, mat=2)
    objs.append(r.to_object("Rear_Bumper", [M["paint"], M["chassis"], M["hose"]], node, sharp_angle=45))
    mf = Mesh()
    for sx in (1, -1):
        box(mf, (sx * 0.98, 0.78, AXLES_Z[3] - 0.78), (0.42, 0.7, 0.012), 0.004, 1)
    objs.append(mf.to_object("Mud_Flaps_Rear", [M["rubber"]], node))
    return objs
