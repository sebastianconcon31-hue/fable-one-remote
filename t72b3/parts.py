"""The T-72B3's outside: the hull with Kontakt-5 on its glacis, the
splashboard and dozer blade, fenders with their fuel tanks and boxes,
rubber skirts with ERA, the engine deck, the exhaust on the left, two fuel
drums and the unditching log at the back; the cast dome turret with its
Kontakt-5 wedges and roof bricks, the 125 mm 2A46M-5 in its thermal sleeve,
the Sosna-U and 1A40 sights, the commander's cupola with the 12.7 mm Kord,
902B smoke dischargers, the snorkel and stowage; the running gear
(modelkit's running_gear.tracked with the single-pin RMSh track, the top run
sagging between its rollers).

Moving parts:
  Turret (traverse, local Y), Gun (elevate, axis -X: + raises it), Commander_Cupola (slews about local Y)
  Driver_Hatch, Commander_Hatch, Gunner_Hatch
  Road_Wheel_*, Sprocket_*, Idler_*, Return_Roller_* (spin), Track_{Left,Right} (links round the loop)"""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, path_tube, rbox, prism, empty, set_parent, Yframe, Xframe, Zframe, norm
from running_gear import loft, slab, bolt, tracked, link_single_pin
from vehicle import drive
from t72 import *

deg = math.pi / 180
SIDE = Frame((0, 0, 0), (0, 0, 1), (0, 1, 0), (-1, 0, 0))
F, R = FRONT_Z, REAR_PLATE_Z


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


def glacis_y(z):
    return NOSE_Y + (F - z) / (F - GLACIS_TOP_Z) * (DECK_Y - NOSE_Y)


SLOPE = math.atan2(DECK_Y - NOSE_Y, F - GLACIS_TOP_Z)


def on_glacis(x, z, h=0.0):
    """A frame on the glacis: X across, Y up the slope, Z out of it."""
    return Frame((x, glacis_y(z) + h / math.cos(SLOPE), z), (1, 0, 0), (0, math.sin(SLOPE), -math.cos(SLOPE)), (0, math.cos(SLOPE), math.sin(SLOPE)))


def hinged_lid(M, parent, name, hinge, c, r, what, axis=(-1, 0, 0), limits=(0, 1.7)):
    n = empty(name, tuple(hinge), parent)
    drive(n, what, control="hinge", axis=list(axis), limits=list(limits), group="Hatches")
    m = Mesh()
    lathe(m, Yframe(c), [(0.0, 0.0), (r, 0.0), (r + 0.008, 0.02), (r - 0.02, 0.045), (r * 0.5, 0.06), (0.0, 0.062)], 32)
    box(m, tuple(hinge), (0.2, 0.05, 0.07), 0.012, 1)
    path_tube(m, [np.asarray(c) + np.array([-0.07, 0.05, 0.08]), np.asarray(c) + np.array([-0.07, 0.1, 0.08]), np.asarray(c) + np.array([0.07, 0.1, 0.08]), np.asarray(c) + np.array([0.07, 0.05, 0.08])], 0.01, 8)
    o = m.to_object(name + "_Lid", [M["paint"]], None, sharp_angle=40)
    set_parent(o, n)
    return [o]


# ---- hull ----------------------------------------------------------------------------------------------------------------------
def hull(M, parent):
    node = empty("Hull", (0, 1.0, 0), parent)
    objs = []
    m = Mesh()
    lower = [(F, NOSE_Y - 0.04), (F - 0.1, FENDER_Y + 0.05), (R + 0.1, FENDER_Y + 0.05), (R, FENDER_Y), (R, 0.7), (R + 0.3, BELLY_Y), (F - 0.5, BELLY_Y)]
    loft(m, SIDE, [(-LOWER_HALF_W, lower), (LOWER_HALF_W, lower)], radii=[0.03, 0.02, 0.02, 0.02, 0.04, 0.05, 0.06], bevel=0.02)
    upper = [(F - 0.02, FENDER_Y + 0.02), (F, NOSE_Y), (GLACIS_TOP_Z, DECK_Y), (R + 0.06, DECK_Y), (R, DECK_Y - 0.06), (R, FENDER_Y + 0.02)]
    loft(m, SIDE, [(-1.42, upper), (1.42, upper)], radii=[0.01, 0.04, 0.04, 0.03, 0.03, 0.01], bevel=0.02)
    objs.append(m.to_object("Hull_Armour", [M["paint"]], node, sharp_angle=40))
    objs += glacis(M, node)
    objs += fenders(M, node)
    objs += deck(M, node)
    objs += rear(M, node)
    objs += lights(M, node)
    _, gear = tracked(M, parent, dict(
        x=TRACK_X, wheels_z=WHEELS_Z, wheel_y=WHEEL_Y, wheel_r=WHEEL_R, wheel_w=0.2, wheel_gap=0.1,
        idler=IDLER, sprocket=(SPROCKET[0], SPROCKET[1], PITCH / (2 * math.sin(math.pi / SPROCKET_TEETH)), SPROCKET_TEETH),
        rollers=ROLLERS, W=TRACK_W, pitch=PITCH, t_in=T_IN, t_out=T_OUT,
        link=lambda m, p: link_single_pin(m, TRACK_W, p, T_IN, T_OUT, 0.1),
        sag=0.05, hull_x=LOWER_HALF_W, arm=(0.36, 0.1), shocks=(0, 1, 5), holes=0, spokes=8, tyre_t=0.06, roller_w=0.3,
        sprocket_w=0.05, sprocket_gap=0.12, sprocket_double=True,
        mats=dict(wheel=M["chassis"], rubber=M["rubber"], track=[M["track"]])))
    objs += gear
    return objs


def era_brick(m, F_, w, h, d, mat=0):
    """A Kontakt-5 container: a flat steel box with a bolted lid."""
    rbox(m, F_, (w, h, d), 0.006, 1, mat=mat)
    for u in (-w / 2 + 0.03, w / 2 - 0.03):
        for v in (-d / 2 + 0.03, d / 2 - 0.03):
            bolt(m, Frame(F_.p((u, h / 2, v)), F_.x, -F_.z, F_.y), 0.008, 0.006, mat=1)


def glacis(M, parent):
    objs = []
    m = Mesh()
    # Kontakt-5 over the upper front plate: two rows of containers either side, a gap down the middle
    for sx in (1, -1):
        for row in range(4):
            z = F - 0.22 - row * 0.26
            G = on_glacis(sx * 0.58, z, 0.06)
            era_brick(m, Frame(G.o, G.x, G.z, -G.y), 1.0, 0.12, 0.25)
    # the splashboard across the nose, angled forward
    for sx in (1, -1):
        G = on_glacis(sx * 0.62, F - 0.06, 0.2)
        slab(m, Frame(G.o, (1, 0, 0), norm(G.z + G.y * 0.6), norm(np.cross((1, 0, 0), norm(G.z + G.y * 0.6)))), [(-0.55, -0.12), (0.55, -0.12), (0.55, 0.12), (-0.55, 0.12)], 0.02, 0.005)
    # the dozer blade folded up under the nose, its rams
    bl = np.array([0.0, 0.72, F - 0.17])
    slab(m, Frame(bl, (1, 0, 0), (0, math.cos(35 * deg), math.sin(35 * deg)), (0, -math.sin(35 * deg), math.cos(35 * deg))), [(-1.0, -0.16), (1.0, -0.16), (1.0, 0.16), (-1.0, 0.16)], 0.03, 0.006)
    for sx in (1, -1):
        tube(m, (sx * 0.75, 0.62, F - 0.32), (sx * 0.75, 0.86, F - 0.08), 0.03, 10, mat=1)
    # tow hooks
    for sx in (1, -1):
        lathe(m, Frame((sx * 0.8, 0.86, F - 0.05), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.025, -0.025), (0.05, -0.025), (0.05, 0.025), (0.025, 0.025), (0.025, -0.025)], 12, mat=1)
    objs.append(m.to_object("Glacis_ERA", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    # driver's hatch at the top of the glacis, centred; it lifts and swings
    hz = GLACIS_TOP_Z - 0.22
    ring = Mesh()
    lathe(ring, Yframe((0, DECK_Y, hz)), [(0.27, 0.0), (0.33, 0.0), (0.33, 0.03), (0.27, 0.035)], 32)
    g = Mesh()
    c = np.array([0.0, DECK_Y + 0.04, hz + 0.33])
    rbox(ring, Frame.along(c, (0, 0.35, 1)), (0.22, 0.08, 0.12), 0.012, 1)
    Fg = Frame.along(c + norm(np.array([0, 0.35, 1])) * 0.061, (0, 0.35, 1))
    g.face(g.verts([Fg.p((-0.09, -0.025, 0)), Fg.p((0.09, -0.025, 0)), Fg.p((0.09, 0.025, 0)), Fg.p((-0.09, 0.025, 0))]))
    objs.append(ring.to_object("Driver_Hatch_Ring", [M["paint"]], parent, sharp_angle=40))
    objs.append(g.to_object("Driver_Periscope_Glass", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    objs += hinged_lid(M, parent, "Driver_Hatch", (-0.28, DECK_Y + 0.04, hz), (0, DECK_Y + 0.025, hz), 0.27,
                       "the driver's hatch: lifts and swings back about the post on its right, local Y; + opens it", axis=(0, 1, 0), limits=(0, 1.5))
    return objs


def fenders(M, parent):
    """Fenders over the tracks with the fuel tanks and boxes on them, the rubber skirts and their ERA."""
    objs = []
    m = Mesh()
    k = Mesh()  # skirts
    for side, sx in (("Left", 1), ("Right", -1)):
        # the fender plate and its front and rear mud guards
        x0, x1 = sx * 1.4, sx * FENDER_HALF_W
        box(m, ((x0 + x1) / 2, FENDER_Y, (F - 0.15 + R) / 2), (abs(x1 - x0), 0.012, F - 0.15 - R), 0.004, 1)
        slab(m, Frame(((x0 + x1) / 2, FENDER_Y - 0.12, F - 0.12), (1, 0, 0), (0, math.cos(40 * deg), math.sin(40 * deg)), (0, -math.sin(40 * deg), math.cos(40 * deg))), [(-abs(x1 - x0) / 2, -0.15), (abs(x1 - x0) / 2, -0.15), (abs(x1 - x0) / 2, 0.15), (-abs(x1 - x0) / 2, 0.15)], 0.012, 0.004)
        # fuel tanks and stowage boxes along the fender
        for k_, (z0, z1, kind) in enumerate(((1.95, 0.95, "tank"), (0.9, -0.1, "tank" if sx < 0 else "box"), (-0.15, -1.15, "box"), (-1.2, -2.2, "tank" if sx < 0 else "box"))):
            c = ((x0 + x1) / 2, FENDER_Y + 0.2, (z0 + z1) / 2)
            rbox(m, Zframe(c), (abs(x1 - x0) - 0.04, 0.38, abs(z1 - z0) - 0.04), 0.03 if kind == "tank" else 0.015, 2)
            if kind == "tank":
                lathe(m, Yframe((c[0], FENDER_Y + 0.39, c[2] + 0.2)), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.03), (0.0, 0.035)], 14, mat=1)
            else:
                for dz in (-0.3, 0.3):
                    box(m, (c[0] + sx * 0.15, FENDER_Y + 0.3, c[2] + dz), (0.012, 0.05, 0.05), 0.004, 1, mat=1)
        # rubber skirts hung from the fender, ERA on the front panels
        kz0, kz1 = F - 0.35, R + 0.15
        n = 6
        for j in range(n):
            a = kz0 - j * (kz0 - kz1) / n - 0.004
            b = kz0 - (j + 1) * (kz0 - kz1) / n + 0.004
            poly = [(a, FENDER_Y - 0.02), (b, FENDER_Y - 0.02), (b, 0.62), (a, 0.62)]
            slab(k, Frame((sx * (SKIRT_X - 0.076 - 0.012), 0, 0), (0, 0, 1), (0, 1, 0), (-sx, 0, 0)), poly, 0.024, 0.005)
            if j < 2:
                for row in range(2):
                    c = np.array([sx * (SKIRT_X - 0.041), 0.8 + row * 0.2, (a + b) / 2])
                    era_brick(m, Frame(c, (0, 0, 1), (sx, 0, 0), (0, sx, 0)), abs(a - b) - 0.06, 0.07, 0.18)
    objs.append(m.to_object("Fenders_And_Stowage", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(k.to_object("Rubber_Skirts", [M["rubber"]], parent, sharp_angle=40))
    return objs


def deck(M, parent):
    objs = []
    m = Mesh()
    y = DECK_Y
    # engine deck: the cooling-air grilles over the radiators, access plates, the deck's lifting eyes
    for sx in (1, -1):
        x0, x1 = sx * 0.1, sx * 1.3
        z0, z1 = -1.5, R + 0.25
        box(m, ((x0 + x1) / 2, y + 0.01, (z0 + z1) / 2), (abs(x1 - x0), 0.02, z0 - z1), 0.006, 1)
        for z in np.arange(z0 - 0.08, z1, -0.07):
            box(m, ((x0 + x1) / 2, y + 0.026, z), (abs(x1 - x0) - 0.08, 0.012, 0.03), 0.003, 1, mat=1)
        for z in (-1.0, R + 0.15):
            lathe(m, Frame((sx * 1.3, y + 0.045, z), (0, 0, 1), (0, 1, 0), (1, 0, 0)), [(0.025, -0.015), (0.05, -0.015), (0.05, 0.015), (0.025, 0.015), (0.025, -0.015)], 12, mat=1)
    objs.append(m.to_object("Engine_Deck", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    return objs


def rear(M, parent):
    """Two 200 l drums and the unditching log across the back, the exhaust on the left fender."""
    objs = []
    m = Mesh()
    for k, x in enumerate((0.48, -0.48)):
        F_ = Xframe((x, 1.0, R - 0.295))
        lathe(m, Frame(F_.o - F_.z * 0.44, F_.x, F_.y, F_.z), [(0.0, 0.0), (0.27, 0.0), (0.29, 0.015), (0.29, 0.29), (0.3, 0.3), (0.29, 0.31), (0.29, 0.57), (0.3, 0.58), (0.29, 0.59), (0.29, 0.865), (0.27, 0.88), (0.0, 0.88)], 28, mat=2)
        for dz in (-0.2, 0.2):  # their brackets and straps
            lathe(m, Frame(F_.o + F_.z * dz, F_.x, F_.y, F_.z), [(0.295, -0.02), (0.305, -0.02), (0.305, 0.02), (0.295, 0.02)], 28, mat=1)
            box(m, (x + dz, 0.7, R - 0.15), (0.05, 0.12, 0.3), 0.01, 1, mat=1)
    F_ = Xframe((0, 1.48, R - 0.25))
    lathe(m, Frame(F_.o - F_.z * 1.35, F_.x, F_.y, F_.z), [(0.0, 0.0), (0.1, 0.0), (0.12, 0.02), (0.12, 2.68), (0.1, 2.7), (0.0, 2.7)], 16, mat=3)
    for t in (-0.9, 0.9):
        lathe(m, Frame(F_.o + F_.z * t, F_.x, F_.y, F_.z), [(0.12, -0.02), (0.13, -0.02), (0.13, 0.02), (0.12, 0.02)], 16, mat=1)
    # the exhaust louvre on the left fender, at the back
    ex = np.array([1.42 + 0.001, 1.25, -1.3])
    rbox(m, Frame(ex, (0, 0, 1), (0, 1, 0), (1, 0, 0)), (0.6, 0.22, 0.03), 0.01, 1)
    for j in range(5):
        rbox(m, Frame(ex + np.array([0.02, -0.08 + j * 0.04, 0]), (0, 0, 1), (0, 1, 0), (1, 0, 0)), (0.56, 0.012, 0.02), 0.003, 1, mat=1)
    objs.append(m.to_object("Rear_Drums_And_Log", [M["paint"], M["chassis"], M["drum"], M["wood"]], parent, sharp_angle=40))
    return objs


def lights(M, parent):
    node = empty("Lights", (0, 1.4, 0), parent)
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        z = F - 0.35
        for name, mat, dx, r in ((f"Light_Head_{side}", M["light_white"], 0.0, 0.07), (f"Light_Blackout_{side}", M["light_amber"], -sx * 0.16, 0.035)):
            c = np.array([sx * 1.55 + dx, FENDER_Y + 0.12, z])
            n = empty(name, tuple(c), node)
            m = Mesh()
            lathe(m, Zframe(c - np.array([0, 0, 0.09])), [(0.0, 0.0), (r + 0.02, 0.0), (r + 0.02, 0.1), (r, 0.1), (0.0, 0.1)], 20, mat=1)
            lathe(m, Zframe(c + np.array([0, 0, 0.008])), [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.15), (0.0, r * 0.2)], 20, mat=0)
            box(m, tuple(c - np.array([0, 0.1, 0.03])), (r * 2 + 0.06, 0.06, 0.08), 0.008, 1, mat=1)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
        c = np.array([sx * 1.55, FENDER_Y + 0.1, R + 0.05])
        n = empty(f"Light_Tail_{side}", tuple(c), node)
        m = Mesh()
        box(m, tuple(c + np.array([0, 0, 0.03])), (0.1, 0.08, 0.06), 0.008, 1, mat=1)
        lathe(m, Zframe(c, -1), [(0.0, 0.0), (0.03, 0.0), (0.024, 0.008), (0.0, 0.01)], 14, mat=0)
        objs.append(m.to_object(f"Light_Tail_{side}_Lens", [M["light_red"], M["chassis"]], n))
    return objs


# ---- turret --------------------------------------------------------------------------------------------------------------------
def dome(hw, front, rear, k=40, point=1.4):
    """A slice of the cast turret: rounded, the front drawn to a blunt point."""
    pts = []
    for i in range(k):
        t = 2 * math.pi * (i + 0.5) / k
        c, s = math.cos(t), math.sin(t)
        x = hw * math.copysign(abs(c) ** 0.85, c)
        if s > 0:
            z = front * math.copysign(abs(s) ** point, s)
        else:
            z = rear * -math.copysign(abs(s) ** 0.8, s)
        pts.append((x, z))
    return pts


def at(x, y, zr):
    return np.array([x, y, TURRET_Z + zr])


def turret(M, parent):
    node = empty("Turret", (0, TURRET_BASE_Y, TURRET_Z), parent)
    drive(node, "the turret: traverses about local Y; + turns it left (all the way round)", control="traverse", axis=[0, 1, 0])
    objs = []
    m = Mesh()
    Fp = Frame((0, 0, TURRET_Z), (1, 0, 0), (0, 0, -1), (0, 1, 0))
    flip = lambda poly: [(x, -z) for x, z in poly]
    sections = [(TURRET_BASE_Y, dome(1.2, 1.25, -1.3)), (1.62, dome(1.28, 1.32, -1.38)), (1.85, dome(1.24, 1.22, -1.36)),
                (2.03, dome(1.1, 1.02, -1.26)), (2.17, dome(0.88, 0.75, -1.08)), (TURRET_ROOF_Y, dome(0.6, 0.45, -0.85))]
    loft(m, Fp, [(y, flip(p)) for y, p in sections], radii=0.0, bevel=0.03, arc_n=1)
    objs.append(m.to_object("Turret_Shell", [M["paint"]], node, sharp_angle=60))
    objs += turret_era(M, node)
    objs += gun(M, node)
    objs += turret_roof(M, node)
    objs += turret_stowage(M, node)
    return objs


def turret_era(M, parent):
    """Kontakt-5 on the turret: the two wedges over the front quarters, bricks along the roof's front edge."""
    m = Mesh()
    for sx in (1, -1):
        # the wedge: a flat box on its side, its face swept back at 30 degrees either side of the gun
        c = at(sx * 0.66, 1.9, 1.06)
        yaw = sx * 34 * deg
        Fw = Frame(c, (math.cos(yaw), 0, -math.sin(yaw)), (0, 1, 0), (math.sin(yaw), 0, math.cos(yaw)))
        rbox(m, Fw, (1.05, 0.5, 0.55), 0.02, 2)
        rbox(m, Frame(Fw.p((0, 0.25, -0.05)), Fw.x, Fw.y, Fw.z), (0.92, 0.04, 0.5), 0.01, 1)
        for u in np.linspace(-0.38, 0.38, 4):
            bolt(m, Frame(Fw.p((u, 0.272, 0.12)), Fw.x, -Fw.z, Fw.y), 0.01, 0.008, mat=1)
            bolt(m, Frame(Fw.p((u, 0.272, -0.22)), Fw.x, -Fw.z, Fw.y), 0.01, 0.008, mat=1)
        # roof bricks behind the wedge
        for k in range(3):
            bc = at(sx * (0.35 + k * 0.24), 2.2 - k * 0.04, 0.5 - k * 0.05)
            era_brick(m, Zframe(bc), 0.22, 0.06, 0.34)
    return [m.to_object("Turret_ERA", [M["paint"], M["chassis"]], parent, sharp_angle=40)]


def gun(M, parent):
    tx, ty, tz = TRUNNION
    g = empty("Gun", TRUNNION, parent)
    drive(g, "the main gun, 125 mm 2A46M-5, with the coaxial PKT: elevates about local X; + raises it (-6 to +14 degrees)", control="elevate", axis=[-1, 0, 0], limits=[-6 * deg, 14 * deg])
    m = Mesh()
    z0 = tz + 0.42
    # the mantlet's canvas boot, then the barrel: thermal sleeve, fume extractor about two-fifths along, the muzzle
    lathe(m, Zframe((0, ty, tz + 0.12)), [(0.0, 0.0), (0.26, 0.0), (0.27, 0.05), (0.24, 0.18), (0.19, 0.27), (0.16, 0.3), (0.0, 0.3)], 28, mat=1)
    L = MUZZLE_Z - z0
    r_at = lambda t: 0.118 - 0.022 * t
    ev = 0.45
    prof = [(0.0, 0.0), (0.12, 0.0)]
    for k in range(1, 30):
        t = k / 30
        if abs(t - ev) < 0.07:
            continue
        prof.append((r_at(t), t * L))
    prof += [(r_at(ev - 0.07), (ev - 0.07) * L), (0.15, (ev - 0.05) * L), (0.155, (ev - 0.02) * L), (0.155, (ev + 0.04) * L), (0.15, (ev + 0.06) * L), (r_at(ev + 0.07), (ev + 0.07) * L)]
    prof = sorted(prof, key=lambda p: (p[1], -p[0] if p[1] == 0 else p[0]))
    prof += [(0.094, L - 0.03), (0.094, L), (0.064, L), (0.062, L - 0.3)]
    lathe(m, Zframe((0, ty, z0)), prof, 36, mat=0)
    for k in range(1, 9):
        t = k / 9
        if abs(t - ev) < 0.1:
            continue
        r = r_at(t) + 0.004
        lathe(m, Zframe((0, ty, z0 + t * L - 0.01)), [(r - 0.006, 0.0), (r, 0.0), (r, 0.02), (r - 0.006, 0.02)], 36, mat=2)
    box(m, (0, ty + 0.125, MUZZLE_Z - 0.1), (0.06, 0.05, 0.12), 0.01, 2, mat=2)
    lathe(m, Zframe((0.22, ty - 0.02, tz + 0.3)), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.06), (0.02, 0.08), (0.0, 0.08)], 10, mat=2)
    return [m.to_object("Gun_Mesh", [M["paint"], M["canvas"], M["chassis"]], g, sharp_angle=40)]


def turret_roof(M, parent):
    y = TURRET_ROOF_Y
    objs = []
    m = Mesh()
    g = Mesh()
    # Sosna-U, the gunner's multichannel sight, in its armoured box on the right front of the roof
    sc = at(-0.5, y + 0.17, 0.3)
    rbox(m, Zframe(sc), (0.42, 0.34, 0.5), 0.03, 2)
    for k, (dx, dy) in enumerate(((-0.08, 0.04), (0.1, 0.04), (0.0, -0.08))):
        w = sc + np.array([dx, dy, 0.252])
        r = 0.06 if k < 2 else 0.04
        g.face(g.verts([w + np.array([-r, -r * 0.7, 0]), w + np.array([r, -r * 0.7, 0]), w + np.array([r, r * 0.7, 0]), w + np.array([-r, r * 0.7, 0])]))
    box(m, tuple(sc + np.array([0, 0.19, 0.08])), (0.46, 0.03, 0.38), 0.008, 1)
    # the 1A40 day sight on the left, in front of the gunner's hatch
    s2 = at(0.48, y + 0.1, 0.25)
    rbox(m, Zframe(s2), (0.22, 0.2, 0.28), 0.02, 2)
    w = s2 + np.array([0, 0.03, 0.142])
    g.face(g.verts([w + np.array([-0.07, -0.04, 0]), w + np.array([0.07, -0.04, 0]), w + np.array([0.07, 0.04, 0]), w + np.array([-0.07, 0.04, 0])]))
    # 902B smoke dischargers, six a side on the front quarters
    for sx in (1, -1):
        for k in range(6):
            a = (24 + k * 9) * deg
            p = at(sx * (0.95 + k * 0.035), 1.98, 0.62 - k * 0.12)
            d = norm(np.array([sx * math.sin(a), 0.55, math.cos(a)]))
            lathe(m, Frame.along(p, d), [(0.0, 0.0), (0.045, 0.0), (0.045, 0.24), (0.037, 0.24), (0.037, 0.05), (0.0, 0.05)], 12, mat=1)
    # the meteorological sensor mast at the back of the roof, an antenna base
    ws = at(-0.15, y, -0.72)
    lathe(m, Yframe(ws), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.04), (0.018, 0.06), (0.018, 0.45), (0.0, 0.46)], 10, mat=1)
    rbox(m, Zframe(ws + np.array([0, 0.5, 0])), (0.12, 0.08, 0.08), 0.015, 1, mat=1)
    ab = at(0.55, y - 0.05, -0.85)
    lathe(m, Yframe(ab), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.08), (0.03, 0.12), (0.0, 0.12)], 12, mat=1)
    objs.append(m.to_object("Turret_Roof_Fittings", [M["paint"], M["chassis"]], parent, sharp_angle=40))
    objs.append(g.to_object("Sight_Windows", [M["optic"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] - 1.0)))
    a = Mesh()
    tube(a, ab + np.array([0, 0.12, 0]), ab + np.array([0.05, 2.0, -0.4]), 0.005, 6, r1=0.0025)
    objs.append(a.to_object("Antenna", [M["chassis"]], parent))
    # gunner's hatch (left), the commander's cupola (right) with its Kord on the cupola's edge
    gh = at(0.48, y, -0.18)
    ring = Mesh()
    lathe(ring, Yframe(gh), [(0.28, 0.0), (0.34, 0.0), (0.34, 0.04), (0.28, 0.05)], 32)
    objs.append(ring.to_object("Gunner_Hatch_Ring", [M["paint"]], parent, sharp_angle=40))
    objs += hinged_lid(M, parent, "Gunner_Hatch", gh + np.array([0, 0.06, -0.3]), gh + np.array([0, 0.035, 0]), 0.28,
                       "the gunner's hatch: hinged at its back, turns about local X; + opens it upward")
    cc = at(-0.52, y - 0.02, -0.25)
    cu = empty("Commander_Cupola", tuple(cc), parent)
    drive(cu, "the commander's cupola with its periscopes and the 12.7 mm Kord: slews about local Y", control="aux", axis=[0, 1, 0])
    c = Mesh()
    lathe(c, Yframe(cc), [(0.0, 0.0), (0.42, 0.0), (0.42, 0.06), (0.4, 0.14), (0.33, 0.16), (0.33, 0.12), (0.0, 0.12)], 36)
    for k in range(4):
        a_ = (-60 + k * 40) * deg
        p = cc + np.array([math.sin(a_) * 0.36, 0.13, math.cos(a_) * 0.36])
        rbox(c, Frame.along(p, (math.sin(a_), 0, math.cos(a_))), (0.1, 0.07, 0.06), 0.01, 1)
    # the Kord on its mount at the cupola's right edge, pointing forward, clear of the hatch as it opens
    mc = cc + np.array([-0.38, 0.3, -0.15])
    tube(c, cc + np.array([-0.38, 0.12, -0.17]), mc, 0.03, 10, mat=1)
    rbox(c, Zframe(mc + np.array([0, 0.05, 0.05])), (0.1, 0.12, 0.62), 0.01, 1, mat=1)
    lathe(c, Zframe(mc + np.array([0, 0.06, 0.36])), [(0.0, 0.0), (0.024, 0.0), (0.024, 0.9), (0.032, 0.92), (0.032, 1.0), (0.0, 1.0)], 12, mat=1)
    box(c, tuple(mc + np.array([-0.1, -0.02, 0.0])), (0.1, 0.16, 0.28), 0.008, 1)  # its ammunition box, outboard
    objs.append(c.to_object("Commander_Cupola_Mesh", [M["paint"], M["chassis"]], cu, sharp_angle=40))
    objs += hinged_lid(M, cu, "Commander_Hatch", cc + np.array([0, 0.16, -0.31]), cc + np.array([0, 0.13, 0]), 0.31,
                       "the commander's hatch: hinged at its back, turns about local X; + opens it upward")
    return objs


def turret_stowage(M, parent):
    """Boxes round the turret's back, the snorkel tube across them and a rolled tarpaulin."""
    m = Mesh()
    for k, a in enumerate(np.linspace(110, 250, 6)):
        t = a * deg
        p = at(math.sin(t) * 1.3, 1.72, -abs(math.cos(t)) * 1.25 - 0.1)
        d = np.array([math.sin(t), 0.0, math.cos(t)])
        rbox(m, Frame(p, np.cross((0, 1, 0), d), (0, 1, 0), d), (0.42, 0.34, 0.24), 0.02, 2)
    for sx in (1, -1):
        p = at(sx * 1.32, 1.85, -0.6)
        rbox(m, Frame(p, (0, 0, 1), (0, 1, 0), (sx, 0, 0)), (0.7, 0.3, 0.2), 0.02, 2)
    F_ = Xframe(at(0.0, 1.98, -1.42))
    lathe(m, Frame(F_.o - F_.z * 1.1, F_.x, F_.y, F_.z), [(0.0, 0.0), (0.09, 0.0), (0.09, 2.2), (0.0, 2.2)], 18, mat=0)
    for t in (-0.8, 0.0, 0.8):
        lathe(m, Frame(F_.o + F_.z * t, F_.x, F_.y, F_.z), [(0.09, -0.02), (0.1, -0.02), (0.1, 0.02), (0.09, 0.02)], 18, mat=1)
    s = Mesh()
    F2 = Xframe(at(0.0, 2.0, -1.12))
    lathe(s, Frame(F2.o - F2.z * 0.8, F2.x, F2.y, F2.z), [(0.0, 0.0), (0.1, 0.0), (0.13, 0.03), (0.13, 1.57), (0.1, 1.6), (0.0, 1.6)], 18)
    return [m.to_object("Turret_Boxes_And_Snorkel", [M["paint"], M["chassis"]], parent, sharp_angle=40),
            s.to_object("Turret_Tarpaulin", [M["canvas"]], parent, sharp_angle=50)]
