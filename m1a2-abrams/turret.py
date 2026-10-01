"""The Abrams' turret: the faceted armour shell with its bustle, the gun
shield and the 120 mm M256 in its thermal sleeve, the gunner's primary sight,
the commander's independent thermal viewer, both hatches, CROWS-LP with its
M2 on the commander's side, the loader's M240, smoke grenade launchers,
side stowage boxes, the bustle rack with its load, antennas, the crosswind
sensor and combat ID panels.

Moving parts:
  Turret                 traverses about local Y (+ turns it left)
  Gun                    elevates about local X: axis (-1, 0, 0), + raises it (-9 to +20 degrees)
  Commander_Hatch, Loader_Hatch   hinge up at the back about local X
  CROWS                  the remote weapon station slews about local Y
  CITV                   the viewer's head slews about local Y"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm
from running_gear import loft, slab, bolt, bolt_row
from vehicle import drive
from abrams import *

deg = math.pi / 180


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def plan(side_x=1.68, bustle_x=1.58, cheek=0.0, rear=0.0):
    """The turret's outline from above, (x, z) about the ring centre: cheeks raked back from the gun's recess,
    flat sides, the bustle a little narrower."""
    L = [(0.4, 1.3), (0.46, 1.62 - cheek), (side_x - 0.07, 0.95 - cheek), (side_x, 0.66 - cheek * 0.5), (side_x, -1.1),
         (bustle_x, -1.4), (bustle_x - 0.07, -2.75 + rear), (bustle_x - 0.21, -2.88 + rear)]
    return L + [(-x, z) for x, z in reversed(L)]


def at(x, y, zr):
    """Turret-relative (x, z from the ring centre) to model."""
    return np.array([x, y, TURRET_Z + zr])


def turret(M, parent):
    node = empty("Turret", (0, TURRET_BASE_Y, TURRET_Z), parent)
    drive(node, "the turret: traverses about local Y; + turns it left (all the way round)", control="traverse", axis=[0, 1, 0])
    objs = []
    m = Mesh()
    F = Frame((0, 0, TURRET_Z), (1, 0, 0), (0, 0, -1), (0, 1, 0))  # plan (x, z) -> local (x, -z); local Z up
    flip = lambda poly: [(x, -z) for x, z in poly]
    sections = [
        (TURRET_BASE_Y, flip(plan(1.6, 1.5, 0.06, 0.06))),
        (1.8, flip(plan())),
        (2.3, flip(plan(1.62, 1.53, 0.02, 0.02))),
        (TURRET_ROOF_Y, flip(plan(1.57, 1.49, 0.04, 0.04))),
    ]
    loft(m, F, sections, radii=0.02, bevel=0.025)
    objs.append(m.to_object("Turret_Shell", [M["paint"]], node, sharp_angle=40))
    objs += gun(M, node)
    objs += roof(M, node)
    objs += sides(M, node)
    objs += bustle_rack(M, node)
    return objs


# ---- the gun --------------------------------------------------------------------------------------------------------------
def gun(M, parent):
    tx, ty, tz = TRUNNION
    g = empty("Gun", TRUNNION, parent)
    drive(g, "the main gun, 120 mm M256: elevates about local X; + raises it (-9 to +20 degrees)", control="elevate", axis=[-1, 0, 0], limits=[-9 * deg, 20 * deg])
    objs = []
    m = Mesh()
    # gun shield: the armoured block in the turret's front recess
    sz = TURRET_Z + 1.45
    slab(m, Frame((0, ty, sz), (1, 0, 0), (0, 1, 0), (0, 0, 1)), [(-0.36, -0.3), (0.36, -0.3), (0.36, 0.26), (0.3, 0.32), (-0.3, 0.32), (-0.36, 0.26)], 0.3, 0.02)
    # coaxial M240 port right of the barrel, the gun's boot
    lathe(m, Zframe((-0.24, ty + 0.02, sz + 0.15)), [(0.0, 0.0), (0.045, 0.0), (0.045, 0.03), (0.02, 0.035), (0.0, 0.035)], 14, mat=1)
    lathe(m, Zframe((0, ty, sz + 0.15)), [(0.0, 0.0), (0.2, 0.0), (0.2, 0.05), (0.17, 0.09), (0.0, 0.09)], 32)
    # barrel: thermal sleeve in sections with straps, the bore evacuator, the muzzle and its reference sensor
    z0 = sz + 0.22
    zm = MUZZLE_Z
    L = zm - z0
    prof = [(0.0, 0.0), (0.138, 0.0), (0.138, 0.02)]
    def r_at(t):  # the sleeve's outer radius, tapering to the muzzle
        return 0.134 - 0.03 * t
    ev0 = 0.52  # bore evacuator, as a fraction of the length
    for k in range(1, 30):
        t = k / 30
        if abs(t - ev0) < 0.07:
            continue
        prof.append((r_at(t), t * L))
    prof += [(r_at(ev0 - 0.07), (ev0 - 0.07) * L), (0.165, (ev0 - 0.05) * L), (0.17, (ev0 - 0.02) * L), (0.17, (ev0 + 0.04) * L), (0.165, (ev0 + 0.06) * L), (r_at(ev0 + 0.07), (ev0 + 0.07) * L)]
    prof = sorted(prof, key=lambda p: (p[1], -p[0] if p[1] == 0 else p[0]))
    prof += [(0.096, L - 0.06), (0.104, L - 0.04), (0.104, L), (0.064, L), (0.06, L - 0.3)]
    lathe(m, Zframe((0, ty, z0)), prof, 40, mat=2)
    for k in range(1, 10):  # sleeve straps
        t = k / 10
        if abs(t - ev0) < 0.1:
            continue
        r = r_at(t) + 0.004
        lathe(m, Zframe((0, ty, z0 + t * L - 0.012)), [(r - 0.006, 0.0), (r, 0.0), (r, 0.024), (r - 0.006, 0.024)], 40, mat=1)
    # muzzle reference sensor on top of the muzzle, its cable running back along the barrel
    box(m, (0, ty + 0.135, zm - 0.12), (0.08, 0.07, 0.16), 0.015, 2, mat=1)
    path_tube(m, [np.array([0.03, ty + r_at(1.0) + 0.01, zm - 0.2]), np.array([0.05, ty + r_at(0.6) + 0.01, z0 + 0.6 * L]), np.array([0.07, ty + 0.16, z0 + 0.1])], 0.008, 6, mat=1)
    objs.append(m.to_object("Gun_Mesh", [M["paint"], M["chassis"], M["gun"]], g, sharp_angle=40))
    return objs


# ---- roof ----------------------------------------------------------------------------------------------------------------------
def roof(M, parent):
    y = TURRET_ROOF_Y
    objs = []
    m = Mesh()
    gl = Mesh()  # sight glass
    # gunner's primary sight: the doghouse on the right front, its armoured doors open on the window
    gx, gz = -0.72, 0.95
    box(m, tuple(at(gx, y + 0.15, gz)), (0.5, 0.3, 0.62), 0.03, 2)
    box(m, tuple(at(gx, y + 0.16, gz + 0.32)), (0.42, 0.22, 0.04), 0.01, 1, mat=1)
    for sx in (1, -1):  # the doors, swung open either side of the window
        rbox(m, Frame(at(gx + sx * 0.27, y + 0.16, gz + 0.36), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), (0.18, 0.24, 0.03), 0.008, 1)
    c = at(gx, y + 0.16, gz + 0.345)
    gl.face(gl.verts([c + np.array([-0.16, -0.08, 0]), c + np.array([0.16, -0.08, 0]), c + np.array([0.16, 0.08, 0]), c + np.array([-0.16, 0.08, 0])]))
    # crosswind sensor mast at the back of the roof, antenna bases at the rear corners
    ws = at(0.15, y, -1.25)
    lathe(m, Yframe(ws), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.02, 0.07), (0.02, 0.55), (0.0, 0.56)], 12, mat=1)
    tube(m, ws + np.array([-0.12, 0.6, 0]), ws + np.array([0.12, 0.6, 0]), 0.025, 10, mat=1)
    tube(m, ws + np.array([0, 0.53, 0]), ws + np.array([0, 0.6, 0]), 0.012, 8, mat=1)
    for sx in (1, -1):
        b = at(sx * 1.22, y, -1.45)
        lathe(m, Yframe(b), [(0.0, 0.0), (0.07, 0.0), (0.07, 0.08), (0.04, 0.12), (0.03, 0.2), (0.0, 0.2)], 14, mat=1)
        tube(m, b + np.array([0, 0.2, 0]), b + np.array([sx * 0.15, 2.1, -0.6]), 0.006, 6, mat=1, r1=0.003)
    # lifting eyes, grab rails
    for x, zr in ((1.3, 0.6), (-1.3, 0.6), (1.25, -2.6), (-1.25, -2.6)):
        lathe(m, Frame(at(x, y + 0.045, zr), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.025, -0.015), (0.05, -0.015), (0.05, 0.015), (0.025, 0.015), (0.025, -0.015)], 12, mat=1)
    path_tube(m, [at(1.1, y, 0.2), at(1.1, y + 0.08, 0.15), at(1.1, y + 0.08, -0.25), at(1.1, y, -0.3)], 0.014, 8, mat=1)
    objs.append(m.to_object("Turret_Roof_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(gl.to_object("GPS_Window", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    objs += citv(M, parent)
    objs += hatches(M, parent)
    objs += crows(M, parent)
    objs += loader_gun(M, parent)
    return objs


def citv(M, parent):
    y = TURRET_ROOF_Y
    c = at(0.62, y, 0.72)
    n = empty("CITV", tuple(c), parent)
    drive(n, "the commander's independent thermal viewer: its head slews about local Y", control="aux", axis=[0, 1, 0])
    m = Mesh()
    lathe(m, Yframe(c), [(0.0, 0.0), (0.2, 0.0), (0.2, 0.06), (0.15, 0.08), (0.15, 0.2), (0.0, 0.2)], 28)
    rbox(m, Zframe(c + np.array([0, 0.36, 0.02])), (0.42, 0.32, 0.38), 0.04, 2)
    box(m, tuple(c + np.array([0, 0.36, 0.215])), (0.32, 0.2, 0.02), 0.006, 1, mat=1)
    for sx in (1, -1):  # ballistic shutters
        rbox(m, Frame(c + np.array([sx * 0.2, 0.36, 0.23]), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), (0.06, 0.24, 0.025), 0.006, 1)
    g = Mesh()
    w = c + np.array([0, 0.36, 0.227])
    g.face(g.verts([w + np.array([-0.13, -0.07, 0]), w + np.array([0.13, -0.07, 0]), w + np.array([0.13, 0.07, 0]), w + np.array([-0.13, 0.07, 0])]))
    return [m.to_object("CITV_Head", [M["paint"], M["chassis"]], n, sharp_angle=40),
            g.to_object("CITV_Window", [M["optic"]], n, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0))]


def hatch(M, parent, name, c, r, what):
    """A round hatch: the ring on the roof, the lid hinged at the back opening upward about local X."""
    objs = []
    ring = Mesh()
    lathe(ring, Yframe(c), [(r - 0.02, 0.0), (r + 0.09, 0.0), (r + 0.09, 0.05), (r + 0.06, 0.08), (r - 0.02, 0.08)], 40)
    for k in range(8):  # vision blocks round the commander's ring
        if name != "Commander_Hatch":
            break
        a = 2 * math.pi * (k + 0.5) / 8
        p = c + np.array([math.sin(a) * (r + 0.05), 0.11, math.cos(a) * (r + 0.05)])
        rbox(ring, Frame.along(p, (math.sin(a), 0, math.cos(a))), (0.14, 0.07, 0.06), 0.012, 1)
    objs.append(ring.to_object(name + "_Ring", [M["paint"]], parent, sharp_angle=40))
    hinge = c + np.array([0, 0.09, -r])
    n = empty(name, tuple(hinge), parent)
    drive(n, f"{what}: hinged at its back, turns about local X; + opens it upward (to 100 degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, 1.75], group="Hatches")
    lid = Mesh()
    lathe(lid, Yframe(c + np.array([0, 0.08, 0])), [(0.0, 0.0), (r, 0.0), (r + 0.01, 0.02), (r - 0.02, 0.05), (r * 0.5, 0.07), (0.0, 0.075)], 40)
    box(lid, tuple(hinge + np.array([0, 0.01, 0.02])), (0.3, 0.06, 0.08), 0.015, 1)
    path_tube(lid, [c + np.array([-0.1, 0.13, 0.15]), c + np.array([-0.1, 0.18, 0.15]), c + np.array([0.1, 0.18, 0.15]), c + np.array([0.1, 0.13, 0.15])], 0.012, 8)
    o = lid.to_object(name + "_Lid", [M["paint"]], None, sharp_angle=40)
    set_parent(o, n)
    objs.append(o)
    return objs


def hatches(M, parent):
    y = TURRET_ROOF_Y
    return hatch(M, parent, "Commander_Hatch", at(-0.6, y, -0.42), 0.38, "the commander's hatch") + \
        hatch(M, parent, "Loader_Hatch", at(0.62, y, -0.48), 0.36, "the loader's hatch")


def m2(m, F, mat_gun, mat_dark):
    """An M2 .50 cal: receiver, barrel with its carry handle and flash hider, spade grips (along the frame's +Z)."""
    rbox(m, Frame(F.p((0, 0, -0.1)), F.x, F.y, F.z), (0.12, 0.16, 0.6), 0.01, 1, mat=mat_gun)
    lathe(m, Frame(F.p((0, 0.02, 0.2)), F.x, F.y, F.z), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.3), (0.024, 0.32), (0.024, 1.1), (0.03, 1.12), (0.03, 1.2), (0.0, 1.2)], 14, mat=mat_dark)
    path_tube(m, [F.p((0, 0.05, 0.45)), F.p((0, 0.13, 0.48)), F.p((0, 0.13, 0.62)), F.p((0, 0.05, 0.65))], 0.01, 6, mat=mat_dark)
    for sx in (1, -1):
        tube(m, F.p((sx * 0.06, 0.0, -0.4)), F.p((sx * 0.06, -0.12, -0.46)), 0.016, 8, mat=mat_dark)


def crows(M, parent):
    """CROWS-LP on the commander's side: a low turntable, the cradle with the M2 and its ammunition box, and the
    sensor pod on the right."""
    y = TURRET_ROOF_Y
    c = at(-1.02, y, 0.15)
    n = empty("CROWS", tuple(c), parent)
    drive(n, "CROWS-LP, the remote weapon station: slews about local Y on its own", control="aux", axis=[0, 1, 0])
    m = Mesh()
    lathe(m, Yframe(c), [(0.0, 0.0), (0.3, 0.0), (0.3, 0.08), (0.26, 0.11), (0.0, 0.11)], 32)
    box(m, tuple(c + np.array([0, 0.24, -0.05])), (0.4, 0.26, 0.5), 0.03, 2)
    for sx in (1, -1):
        prism(m, Frame(c + np.array([sx * 0.18, 0.4, 0.0]), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), [(-0.2, -0.1), (0.2, -0.1), (0.12, 0.12), (-0.15, 0.12)], 0.04)
    m2(m, Frame(c + np.array([0.02, 0.48, 0.1]), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 1, 2)
    box(m, tuple(c + np.array([0.24, 0.42, -0.02])), (0.14, 0.24, 0.36), 0.015, 1)  # ammunition box
    box(m, tuple(c + np.array([-0.24, 0.46, 0.04])), (0.2, 0.22, 0.3), 0.025, 2)  # sensor pod
    g = Mesh()
    w = c + np.array([-0.24, 0.46, 0.191])
    g.face(g.verts([w + np.array([-0.07, -0.06, 0]), w + np.array([0.07, -0.06, 0]), w + np.array([0.07, 0.06, 0]), w + np.array([-0.07, 0.06, 0])]))
    return [m.to_object("CROWS_Mount", [M["paint"], M["chassis"], M["gun"]], n, sharp_angle=40),
            g.to_object("CROWS_Window", [M["optic"]], n, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0))]


def loader_gun(M, parent):
    """The loader's M240 on its skate-ring mount ahead of the hatch, with an ammunition can."""
    y = TURRET_ROOF_Y
    c = at(0.62, y + 0.09, -0.02)
    m = Mesh()
    tube(m, c, c + np.array([0, 0.32, 0]), 0.025, 10, mat=1)
    box(m, tuple(c + np.array([0, 0.36, -0.05])), (0.08, 0.12, 0.5), 0.01, 1, mat=2)
    lathe(m, Zframe(c + np.array([0, 0.38, 0.2])), [(0.0, 0.0), (0.016, 0.0), (0.016, 0.62), (0.022, 0.64), (0.022, 0.7), (0.0, 0.7)], 10, mat=2)
    tube(m, c + np.array([0, 0.3, -0.3]), c + np.array([0, 0.36, -0.12]), 0.03, 8, mat=2)
    box(m, tuple(c + np.array([0.09, 0.32, -0.02])), (0.1, 0.18, 0.28), 0.008, 1, mat=1)
    return [m.to_object("Loader_M240", [M["paint"], M["chassis"], M["gun"]], parent, sharp_angle=40)]


# ---- sides ------------------------------------------------------------------------------------------------------------------
def sides(M, parent):
    objs = []
    m = Mesh()
    cip = Mesh()
    for side, sx in (("Left", 1), ("Right", -1)):
        # six-tube smoke grenade launchers on the front corners, angled forward and out
        base = at(sx * 1.56, 2.12, 0.74)
        d = norm(np.array([sx * 0.55, 0.45, 0.7]))
        box(m, tuple(base), (0.22, 0.12, 0.26), 0.015, 1, mat=1)
        for row in range(2):
            for k in range(3):
                p = base + np.array([sx * 0.0 + (k - 1) * 0.07 * (1 if sx > 0 else -1), 0.06 + row * 0.08, 0.02])
                lathe(m, Frame.along(p, d), [(0.0, 0.0), (0.04, 0.0), (0.04, 0.2), (0.032, 0.2), (0.032, 0.05), (0.0, 0.05)], 12, mat=1)
        # stowage boxes on the bustle's sides, with their lids' hinges and latches
        bc = at(sx * (1.58 + 0.12), 2.06, -2.1)
        rbox(m, Zframe(bc), (0.24, 0.4, 0.95), 0.025, 2)
        for dz in (-0.3, 0.3):
            box(m, tuple(bc + np.array([sx * 0.123, 0.08, dz])), (0.012, 0.07, 0.06), 0.004, 1, mat=1)
        tube(m, bc + np.array([-sx * 0.05, 0.205, -0.45]), bc + np.array([-sx * 0.05, 0.205, 0.45]), 0.012, 8, mat=1)
        # combat ID panel on the turret's side
        cc = at(sx * 1.69, 2.0, -0.35)
        rbox(cip, Frame(cc, (0, 0, 1), (0, 1, 0), (sx, 0, 0)), (0.55, 0.42, 0.02), 0.006, 1)
        for dz in (-0.24, 0.24):
            box(m, tuple(cc + np.array([-sx * 0.0, 0.0, dz])), (0.035, 0.46, 0.03), 0.006, 1, mat=1)
    objs.append(m.to_object("Turret_Side_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(cip.to_object("Combat_ID_Panels", [M["cip"]], parent, sharp_angle=40))
    return objs


def bustle_rack(M, parent):
    """The rack round the bustle's back, with what a crew carries in it: a rolled camouflage net, duffel bags,
    water cans and a box of track tools."""
    objs = []
    m = Mesh()
    z0, z1 = -2.88, -3.28
    y0, y1 = 1.86, 2.36
    for x in (1.45, -1.45):
        for zr in (z0 + 0.02, z1):
            tube(m, at(x, y0, zr), at(x, y1, zr), 0.018, 8)
    for y in (y0, (y0 + y1) / 2, y1):
        path_tube(m, [at(1.45, y, z0 + 0.02), at(1.45, y, z1), at(-1.45, y, z1), at(-1.45, y, z0 + 0.02)], 0.016, 8)
    for x in np.linspace(-1.35, 1.35, 10):
        tube(m, at(x, y0, z0), at(x, y0, z1), 0.01, 6)
        tube(m, at(x, y0, z1), at(x, y1, z1), 0.008, 6)
    objs.append(m.to_object("Bustle_Rack", [M["paint"]], parent, sharp_angle=40))
    s = Mesh()
    # camouflage net rolled and strapped along the rack
    F = Xframe(at(0.0, y0 + 0.2, -3.1))
    lathe(s, Frame(F.o - F.z * 0.9, F.x, F.y, F.z), [(0.0, 0.0), (0.15, 0.0), (0.19, 0.04), (0.2, 0.2), (0.19, 1.6), (0.18, 1.76), (0.14, 1.8), (0.0, 1.8)], 24, mat=0)
    for t in (-0.6, 0.0, 0.6):
        lathe(s, Frame(F.o + F.z * t, F.x, F.y, F.z), [(0.2, -0.025), (0.215, -0.025), (0.215, 0.025), (0.2, 0.025)], 24, mat=1)
    # duffel bags on top of the net, and water cans in the rack's corners
    for x in (0.75, -0.55):
        rbox(s, Xframe(at(x, y0 + 0.47, -3.08)), (0.32, 0.3, 0.75), 0.13, 3, mat=2)
    for x in (1.3, 1.12, -1.12, -1.3):
        c = at(x, y0 + 0.26, -3.0)
        rbox(s, Zframe(c), (0.15, 0.48, 0.32), 0.02, 2, mat=3)
        box(s, tuple(c + np.array([0, 0.26, 0.06])), (0.05, 0.05, 0.04), 0.01, 1, mat=3)
    objs.append(s.to_object("Bustle_Stowage", [M["canvas"], M["strap"], M["duffel"], M["jerrycan"]], parent, sharp_angle=50))
    cip = Mesh()
    rbox(cip, Zframe(at(0.0, 2.1, -3.295)), (0.55, 0.42, 0.02), 0.006, 1)
    objs.append(cip.to_object("Combat_ID_Panel_Rear", [M["cip"]], parent, sharp_angle=40))
    return objs
