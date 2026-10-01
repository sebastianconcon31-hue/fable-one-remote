"""The HEMTT M977A4's outside: cab, bumper and winch, fenders, frame and
running gear, engine bay with its intake and exhaust stacks, spare tyre,
fuel tank and boxes, the 18 ft cargo body, the rear material-handling crane,
lights, mirrors and the eight pallet loads it carries.

Moving parts are their own nodes, pivoted where they turn:
  Wheel_{1-4}_{Left,Right}   spin about local X (1, 2 sit inside Steer_* nodes, which steer about local Y)
  Door_{Left,Right}          swing about local Y on the front hinge
  Crane / Crane_Boom / Crane_Boom_Extension / Crane_Hook   slew, luff, telescope, hoist
  Cargo_Pallet_{1-8}         each load can be lifted out on its own"""
import math
import bpy
import numpy as np
from geom import Mesh, fillet_path, Frame, lathe, tube, path_tube, rbox, prism, empty, norm, set_parent, Yframe, Xframe, Zframe
from m977 import *

deg = math.pi / 180


def box(m, c, size, r=0.01, seg=1, mat=0):
    rbox(m, Zframe(c), size, r, seg, mat)


# ---- cab ------------------------------------------------------------------------------------------------------------------------------
def cab_profile(front_shift=0.0, inset=0.0):
    """The cab's side outline (z, y) with its corner radii; front_shift pulls the front back (the chamfered corners)."""
    F, R = CAB_FRONT_Z - front_shift, CAB_REAR_Z + inset
    B, T = CAB_BOTTOM_Y + inset, CAB_ROOF_Y - inset
    pts = [(F, B), (F - 0.012, 1.955), (F - 0.035, 1.985), (F - 0.165 - inset * 0.5, 2.70 - inset), (F - 0.26, T - 0.015), (R + 0.06, T), (R, T - 0.05), (R, B)]
    radii = [0.02, 0.015, 0.01, 0.03, 0.07, 0.05, 0.03, 0.02]
    return pts, radii


def cab(M, parent):
    node = empty("Cab", (0, 2.1, 3.4), parent)
    m = Mesh()
    xs = [1.2, 1.198, 1.192, 1.18, 1.16, 1.12, 1.06, 1.02]
    stations = [-x for x in xs] + list(reversed(xs))
    rings = []
    for x in stations:
        ax = abs(x)
        shift = max(0.0, ax - 1.02) * 0.9  # chamfered front corners
        inset = 0.0 if ax < 1.16 else 0.03 * (1 - math.cos(min(1.0, (ax - 1.16) / 0.04) * math.pi / 2))
        pts, radii = cab_profile(shift, inset)
        loop = fillet_path(pts, radii, arc_n=4, seg_n=[3, 1, 6, 2, 8, 1, 6, 6], closed=True)
        rings.append([(x, y, z) for z, y in loop])
    ids = m.grid(rings, closed=True)
    m.cap(ids[0], flip=True)
    m.cap(ids[-1])
    shell = m.to_object("Cab_Shell", [M["paint"]], node, outward=lambda p: (p[0] * 0.0, 2.1, 3.4), sharp_angle=50)
    objs = [shell]
    # windscreen: two panes either side of a centre post, dark behind the glass
    w = Mesh()  # seals and the centre post
    g = Mesh()  # glass
    k = Mesh()  # the dark cab interior seen through the glass
    F = CAB_FRONT_Z
    a = np.array([0.0, 1.995, F - 0.04])
    b = np.array([0.0, 2.69, F - 0.165])
    up = norm(b - a)
    n = norm(np.cross((1, 0, 0), up))  # facing forward
    for sx in (1, -1):
        x0, x1 = 0.055 * sx, 0.97 * sx
        corners = [a + np.array([x0, 0, 0]) + up * 0.02, a + np.array([x1, 0, 0]) + up * 0.02, b + np.array([x1, 0, 0]) - up * 0.02, b + np.array([x0, 0, 0]) - up * 0.02]
        corners = [c + n * 0.004 for c in corners]
        g.face(g.verts(corners))
        k.face(k.verts([c - n * 0.002 for c in corners]))
        # rubber surround
        for p0, p1 in zip(corners, corners[1:] + corners[:1]):
            tube(w, p0, p1, 0.012, 6, mat=2)
    mid = (a + b) / 2
    rbox(w, Frame.along(mid + n * 0.01, up, n), (0.09, 0.03, np.linalg.norm(b - a) + 0.02), 0.01, 1, mat=0)
    # door windows' dark backing and the rear windows are on the doors / rear wall below
    for sx in (1, -1):
        G = Frame((sx * 0.55, 2.42, CAB_REAR_Z - 0.004), (1, 0, 0), (0, 1, 0), (0, 0, -1))
        loop = fillet_path([(0.28, 0.17), (0.28, -0.17), (-0.28, -0.17), (-0.28, 0.17)], [0.04] * 4, arc_n=3, seg_n=1, closed=True)
        k.face(k.verts([G.p((x, y, -0.002)) for x, y in loop]))
        g.face(g.verts([G.p((x, y, -0.006)) for x, y in loop]))
    inside = lambda p: (0.0, 2.1, 3.4)
    objs.append(w.to_object("Cab_Window_Seals", [M["paint"], M["interior"], M["rubber"]], node, sharp_angle=40))
    objs.append(k.to_object("Cab_Window_Backing", [M["interior"]], node, smooth=False, per_face=inside))
    objs.append(g.to_object("Cab_Glass", [M["glass"]], node, smooth=False, per_face=inside))
    # grille: a recessed frame with horizontal bars, the radiator dark behind
    gr = Mesh()
    gz = CAB_FRONT_Z + 0.003
    rbox(gr, Zframe((0, 1.69, gz)), (1.56, 0.5, 0.03), 0.02, 2, mat=0)
    box(gr, (0, 1.69, gz + 0.006), (1.44, 0.4, 0.024), 0.004, 1, mat=1)
    for k in range(8):
        box(gr, (0, 1.515 + k * 0.05, gz + 0.022), (1.42, 0.022, 0.02), 0.006, 1, mat=0)
    for sx in (1, -1):
        box(gr, (sx * 0.36, 1.69, gz + 0.024), (0.03, 0.4, 0.024), 0.006, 1, mat=0)
    objs.append(gr.to_object("Grille", [M["paint"], M["interior"]], node, sharp_angle=40))
    # roof: hatch ring and lid on the right, clearance lights along the front edge, an amber beacon
    r = Mesh()
    hc = (-0.45, CAB_ROOF_Y, 3.05)
    lathe(r, Yframe(hc), [(0.33, 0.0), (0.42, 0.0), (0.42, 0.06), (0.4, 0.075), (0.33, 0.075), (0.33, 0.0)], 40)
    lathe(r, Yframe((hc[0], CAB_ROOF_Y + 0.06, hc[2])), [(0.0, 0.0), (0.35, 0.0), (0.35, 0.03), (0.3, 0.06), (0.0, 0.065)], 40)
    rbox(r, Zframe((hc[0] + 0.3, CAB_ROOF_Y + 0.115, hc[2])), (0.05, 0.04, 0.22), 0.01, 1)
    objs.append(r.to_object("Roof_Hatch", [M["paint"]], node, sharp_angle=45))
    objs += doors(M, node)
    objs += mirrors_and_trim(M, node)
    return objs


def doors(M, parent):
    """Doors hang on hinges at their front edge; local Y is the hinge axis, and +angle opens either door outward."""
    objs = []
    z0, z1 = 4.06, 2.74  # front and rear edges
    y0, y1 = 1.47, 2.76
    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * (CAB_HALF_W + 0.012)
        hinge = (x + sx * 0.03, (y0 + y1) / 2, z0)  # on the outer skin, so the door's front edge swings out, not forward
        d = empty(f"Door_{side}", hinge, parent)
        d["drive"] = "swing about the hinge; +angle about `axis` opens the door outward (up to 80 degrees)"
        d["axis"] = [0.0, -1.0 if sx > 0 else 1.0, 0.0]
        d["limits"] = [0.0, 1.4]
        m = Mesh()
        F = Frame((x, (y0 + y1) / 2, (z0 + z1) / 2), (0, 0, 1), (0, 1, 0), (sx, 0, 0))
        rbox(m, F, (z0 - z1, y1 - y0, 0.05), 0.02, 2, mat=0)
        # window: dark backing and glass, with a rubber seal
        wz0, wz1, wy0, wy1 = z0 - 0.08, z1 + 0.08, 2.08, y1 - 0.08
        corners = [(x + sx * 0.026, wy0, wz0), (x + sx * 0.026, wy0, wz1), (x + sx * 0.026, wy1, wz1), (x + sx * 0.026, wy1, wz0)]
        P = [np.asarray(c, float) for c in corners]
        for p0, p1 in zip(P, P[1:] + P[:1]):
            tube(m, p0 + np.array([sx * 0.004, 0, 0]), p1 + np.array([sx * 0.004, 0, 0]), 0.011, 6, mat=2)
        # handle and lock, hinges
        tube(m, (x + sx * 0.035, 1.98, z1 + 0.12), (x + sx * 0.035, 1.98, z1 + 0.3), 0.01, 8, mat=3)
        for hy in (1.75, 2.45):
            lathe(m, Yframe((x + sx * 0.03, hy - 0.06, z0 + 0.01)), [(0.0, 0.0), (0.025, 0.0), (0.025, 0.12), (0.0, 0.12)], 10, mat=3)
        door = m.to_object(f"Door_{side}_Panel", [M["paint"], M["interior"], M["rubber"], M["chassis"]], None, sharp_angle=40)
        set_parent(door, d)
        gm, km = Mesh(), Mesh()
        gm.face(gm.verts([p + np.array([sx * 0.007, 0, 0]) for p in P]))
        km.face(km.verts(P))
        inside = lambda p: (0.0, 2.1, 3.4)
        glass = gm.to_object(f"Door_{side}_Glass", [M["glass"]], None, smooth=False, per_face=inside)
        back = km.to_object(f"Door_{side}_Window_Backing", [M["interior"]], None, smooth=False, per_face=inside)
        for o in (glass, back):
            set_parent(o, d)
        objs += [door, glass, back]
    return objs


def mirrors_and_trim(M, parent):
    m = Mesh()
    mg = Mesh()  # mirror glass
    for sx in (1, -1):
        # west-coast mirrors on tubular arms from the front corner pillar
        base = np.array([sx * (CAB_HALF_W - 0.02), 2.32, 4.28])
        out = np.array([sx * 1.47, 2.36, 4.32])
        path_tube(m, [base, base + np.array([sx * 0.12, 0.06, 0.02]), out], 0.018, 10, mat=1)
        path_tube(m, [base - np.array([0, 0.5, 0]), base - np.array([0, 0.5, 0]) + np.array([sx * 0.15, 0.1, 0.02]), out - np.array([0, 0.32, 0])], 0.016, 10, mat=1)
        head = np.array([sx * 1.5, 2.2, 4.33])
        rbox(m, Zframe(head), (0.1, 0.48, 0.07), 0.025, 2, mat=1)
        mg.face(mg.verts([head + np.array([sx * dx, dy, -0.0352]) for dx, dy in ((-0.04, -0.21), (0.04, -0.21), (0.04, 0.21), (-0.04, 0.21))]))
        cv = head + np.array([0, -0.38, 0.01])
        lathe(m, Frame.along(cv, (0, 0, 1)), [(0.0, -0.03), (0.075, -0.03), (0.08, 0.0), (0.07, 0.03), (0.0, 0.04)], 20, mat=1)
        # grab handle beside the door, and the two-step ladder below it
        hx0, hx1 = sx * (CAB_HALF_W - 0.01), sx * (CAB_HALF_W + 0.045)
        path_tube(m, [np.array([hx0, 1.7, 4.12]), np.array([hx1, 1.72, 4.12]), np.array([hx1, 2.42, 4.12]), np.array([hx0, 2.44, 4.12])], 0.014, 8, mat=1)
        # the ladder between the first and second axles, narrow enough to clear both pairs of tyres as they steer
        for k, y in enumerate((0.86, 1.18)):
            box(m, (sx * (0.98 + 0.05 * k), y, 2.67), (0.24, 0.035, 0.24), 0.008, 1, mat=1)
        for dz in (-0.11, 0.11):
            tube(m, (sx * 0.98, 0.84, 2.67 + dz), (sx * 1.05, 1.42, 2.67 + dz), 0.014, 8, mat=1)
    # windscreen wipers
    for x0 in (0.5, -0.4):
        base = np.array([x0, 2.0, CAB_FRONT_Z - 0.02])
        tip = base + np.array([0.08, 0.55, -0.11])
        tube(m, base, tip, 0.008, 6, mat=1)
        tube(m, base + np.array([0.02, 0.05, 0.012]), tip + np.array([0.02, 0.0, 0.012]), 0.006, 6, mat=3)
    # whip antenna on the right rear corner of the cab
    lathe(m, Yframe((-1.05, CAB_ROOF_Y - 0.02, CAB_REAR_Z + 0.1)), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.08), (0.02, 0.14), (0.0, 0.14)], 12, mat=1)
    tube(m, (-1.05, CAB_ROOF_Y + 0.12, CAB_REAR_Z + 0.1), (-1.05, CAB_ROOF_Y + 1.6, CAB_REAR_Z - 0.25), 0.006, 6, mat=1, r1=0.003)
    return [m.to_object("Mirrors_And_Trim", [M["paint"], M["chassis"], M["mirror"], M["rubber"]], parent, sharp_angle=45),
            mg.to_object("Mirror_Glass", [M["mirror"]], parent, smooth=False, per_face=lambda p: (p[0], p[1], p[2] + 1.0))]


def steer_limits():
    """Each steered axle's full lock (its inner wheel's) for the published turning circle, the wheels turning about one
    centre on the line through the rear pair (Ackermann): the first axle's, the second's."""
    R = SPEC["turningCircle"] / 2
    rear = (AXLES_Z[2] + AXLES_Z[3]) / 2
    L1, L2 = AXLES_Z[0] - rear, AXLES_Z[1] - rear
    across = R * math.cos(math.asin(L1 / R)) - SPEC["track"]  # from the turning centre to the inner wheels
    return math.atan(L1 / across), math.atan(L2 / across)


# ---- front end ------------------------------------------------------------------------------------------------------------------
def front(M, parent):
    node = empty("Front_End", (0, 0.85, FRONT_Z - 0.15), parent)
    m = Mesh()
    zf = BUMPER_FRONT_Z
    # bumper: a heavy steel box across the frame's ends, high enough (its underside 0.855 m up, the tow eyes' 0.885 m)
    # for the published 41 degree approach angle
    yb = BUMPER_Y
    rbox(m, Zframe((0, yb, zf - 0.09)), (2.34, 0.36, 0.18), 0.03, 2, mat=0)
    # winch: recessed drum behind a roller fairlead
    box(m, (0, yb, zf - 0.005), (0.62, 0.22, 0.02), 0.01, 1, mat=1)
    lathe(m, Xframe((-0.24, yb, zf - 0.09)), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.48), (0.0, 0.48)], 20, mat=1)
    for dy in (-0.07, 0.07):
        tube(m, (-0.18, yb + dy, zf + 0.03), (0.18, yb + dy, zf + 0.03), 0.025, 12, mat=1)
    for dx in (-0.2, 0.2):
        tube(m, (dx, yb - 0.09, zf + 0.03), (dx, yb + 0.09, zf + 0.03), 0.025, 12, mat=1)
    # tow eyes and lifting shackles
    for sx in (1, -1):
        lathe(m, Frame((sx * 0.62, yb - 0.07, zf + 0.04), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.04, -0.04), (0.08, -0.04), (0.08, 0.04), (0.04, 0.04), (0.04, -0.04)], 20, mat=1)
        rbox(m, Zframe((sx * 0.62, yb + 0.01, zf - 0.02)), (0.08, 0.1, 0.12), 0.01, 1, mat=1)
    # radiator guard between the bumper and the cab, with the steps on the bumper's ends either side
    rbox(m, Zframe((0, 1.22, zf - 0.24)), (1.7, 0.4, 0.06), 0.02, 2, mat=0)
    for k in range(6):
        box(m, (0, 1.07 + k * 0.06, zf - 0.205), (1.6, 0.03, 0.02), 0.006, 1, mat=1)
    for sx in (1, -1):
        box(m, (sx * 1.0, yb + 0.198, zf - 0.09), (0.3, 0.035, 0.16), 0.008, 1, mat=1)
    objs = [m.to_object("Bumper", [M["paint"], M["chassis"]], node, sharp_angle=45)]
    # fenders over both front wheels, with mud flaps behind the second axle
    for side, sx in (("Left", 1), ("Right", -1)):
        f = Mesh()
        rings = []
        z_front, z_back = 4.32, 1.12
        for z in np.linspace(z_front, z_back, 26):
            drop = 0.0
            if z > 4.0:
                drop = (z - 4.0) / 0.32 * 0.22
            if z < 1.35:
                drop = (1.35 - z) / 0.23 * 0.05
            y = FENDER_Y - drop
            loop = fillet_path([(0.80, y), (1.205, y), (1.215, y - 0.17), (1.185, y - 0.17), (1.175, y - 0.03), (0.80, y - 0.03)], [0.0, 0.03, 0.01, 0.005, 0.02, 0.0], arc_n=3, seg_n=1, closed=True)
            rings.append([(sx * x, yy, z) for x, yy in loop])
        ids = f.grid(rings, closed=True)
        f.cap(ids[0], flip=True)
        f.cap(ids[-1])
        objs.append(f.to_object(f"Fender_{side}", [M["paint"]], node, outward=lambda p, sx=sx: (sx * 1.0, 1.3, p[2]), sharp_angle=50))
        mf = Mesh()
        box(mf, (sx * 0.98, 0.82, 1.1), (0.42, 0.62, 0.012), 0.004, 1, mat=0)
        objs.append(mf.to_object(f"Mud_Flap_Front_{side}", [M["rubber"]], node))
    return objs


# ---- frame, axles, suspension, drivetrain ----------------------------------------------------------------------------------------
def chassis(M, parent):
    node = empty("Chassis", (0, 0.9, -0.5), parent)
    m = Mesh()
    z_hi, z_lo = 4.4, REAR_Z + 0.15
    for sx in (1, -1):
        # C-channel rails, open inboard
        F = Frame((sx * RAIL_X, (RAIL_Y0 + RAIL_Y1) / 2, (z_hi + z_lo) / 2), (sx, 0, 0), (0, 1, 0), (0, 0, 1) if sx > 0 else (0, 0, -1))
        h, t, fl = RAIL_Y1 - RAIL_Y0, 0.012, 0.09
        c = [(0, -h / 2), (0, h / 2), (-fl, h / 2), (-fl, h / 2 - t), (-t, h / 2 - t), (-t, -h / 2 + t), (-fl, -h / 2 + t), (-fl, -h / 2)]
        prism(m, Frame(F.o, F.x, F.y, F.z), c, z_hi - z_lo, mat=0)
    for z in np.arange(4.2, z_lo, -1.15):
        box(m, (0, 1.15, z), (2 * RAIL_X - 0.02, 0.2, 0.08), 0.01, 1, mat=0)
    for k, za in enumerate(AXLES_Z):
        # axle housing, differential, hubs
        tube(m, (WHEEL_X - 0.2, TYRE_R, za), (-WHEEL_X + 0.2, TYRE_R, za), 0.075, 16, mat=0)
        lathe(m, Zframe((0.05, TYRE_R, za - 0.18)), [(0.0, 0.0), (0.12, 0.02), (0.2, 0.1), (0.22, 0.2), (0.2, 0.3), (0.12, 0.36), (0.0, 0.37)], 24, mat=0)
        if k < 2:
            # taper-leaf springs above the front axles
            for sx in (1, -1):
                for j in range(6):
                    sag = 0.012 * j
                    box(m, (sx * SPRING_X, 0.76 + j * 0.016 + sag * 0.3, za), (0.09, 0.014, 1.15 - j * 0.15), 0.004, 1, mat=0)
                tube(m, (sx * SPRING_X, 0.76, za + 0.55), (sx * SPRING_X, RAIL_Y0, za + 0.6), 0.03, 8, mat=0)
                tube(m, (sx * SPRING_X, 0.76, za - 0.55), (sx * SPRING_X, RAIL_Y0, za - 0.5), 0.03, 8, mat=0)
                # shock absorber
                tube(m, (sx * 0.56, TYRE_R + 0.05, za + 0.15), (sx * 0.46, 1.1, za + 0.2), 0.035, 10, mat=0)
            # the tie rod between the steering arms, inboard of the tyres as they steer
            tube(m, (WHEEL_X - 0.38, TYRE_R + 0.12, za - 0.15), (-WHEEL_X + 0.38, TYRE_R + 0.12, za - 0.15), 0.025, 10, mat=0)
        else:
            for sx in (1, -1):
                tube(m, (sx * 0.7, TYRE_R + 0.18, za), (sx * 0.4, 1.0, za + (0.3 if k == 2 else -0.3)), 0.03, 8, mat=0)
    # rear walking beams, pivoted at a trunnion between the rear axles
    zc = (AXLES_Z[2] + AXLES_Z[3]) / 2
    for sx in (1, -1):
        rbox(m, Zframe((sx * 0.7, 0.72, zc)), (0.14, 0.22, AXLE_PAIR_SPACING + 0.35), 0.03, 2, mat=0)
        lathe(m, Xframe((sx * 0.64, 0.82, zc), sx), [(0.0, 0.0), (0.14, 0.0), (0.14, 0.16), (0.0, 0.16)], 20, mat=0)
        rbox(m, Zframe((sx * 0.55, 1.0, zc)), (0.16, 0.36, 0.42), 0.02, 1, mat=0)
    # transfer case and driveshafts
    rbox(m, Zframe((0, 0.86, 0.55)), (0.5, 0.42, 0.5), 0.05, 2, mat=0)
    for za in AXLES_Z:
        a = np.array([0.0, 0.84, 0.55])
        b = np.array([0.05, TYRE_R + 0.05, za + (0.2 if za < 0.55 else -0.2)])
        tube(m, a, b, 0.045, 12, mat=0)
    # air tanks between the rails, and the exhaust under-run
    for z in (-0.6, -1.3):
        lathe(m, Xframe((-0.3, 1.0, z), 1), [(0.0, 0.0), (0.12, 0.02), (0.13, 0.08), (0.13, 0.52), (0.12, 0.58), (0.0, 0.6)], 20, mat=0)
    objs = [m.to_object("Frame_And_Running_Gear", [M["chassis"]], node, sharp_angle=50)]
    return objs


# ---- wheels and tyres ------------------------------------------------------------------------------------------------------------
def tyre(m, c, sx, mat_tyre=0, mat_rim=1):
    """16.00R20 XZL on a 20 in steel wheel: sidewalls, crown, the chunky staggered tread blocks, rim, hub and studs."""
    R, W = TYRE_R, TYRE_W
    F = Xframe(c, sx)
    prof = [(0.27, -0.17), (0.29, -0.19), (0.4, -0.212), (0.5, -0.214), (0.56, -0.205), (0.583, -0.185), (0.591, -0.15),
            (0.592, 0.15), (0.583, 0.185), (0.56, 0.205), (0.5, 0.214), (0.4, 0.212), (0.29, 0.19), (0.27, 0.17)]
    lathe(m, F, prof, 64, mat=mat_tyre)
    n = 34
    for k in range(n):
        for half in (-1, 1):
            a = 2 * math.pi * (k + (0.5 if half > 0 else 0)) / n
            radial = np.array([math.cos(a), math.sin(a), 0.0])
            tang = np.array([-math.sin(a), math.cos(a), 0.0])
            axial = np.array([0.0, 0.0, half * 1.0])
            ax_dir = norm(axial * math.cos(25 * deg) + tang * math.sin(25 * deg))
            o = radial * 0.6036 + axial * 0.1  # block tops at 0.6156 m, their corners at the 0.62 m radius
            G = Frame(F.p(o), F.d(ax_dir), F.d(radial), F.d(np.cross(ax_dir, radial)))
            rbox(m, G, (0.19, 0.024, 0.075), 0.008, 1, mat=mat_tyre)
    # wheel: rim flanges, dished centre, hub with ten studs and the tyre-inflation fitting
    lathe(m, F, [(0.255, -0.15), (0.27, -0.16), (0.275, -0.15), (0.258, -0.13), (0.252, 0.13), (0.275, 0.15), (0.27, 0.16), (0.255, 0.15)], 48, mat=mat_rim)
    lathe(m, F, [(0.252, 0.0), (0.2, 0.05), (0.12, 0.06), (0.1, 0.07), (0.0, 0.07)], 40, mat=mat_rim)
    lathe(m, F, [(0.0, 0.07), (0.07, 0.07), (0.075, 0.13), (0.06, 0.15), (0.0, 0.155)], 24, mat=mat_rim)
    for j in range(10):
        a = 2 * math.pi * j / 10
        p = np.array([math.cos(a) * 0.15, math.sin(a) * 0.15, 0.0])
        lathe(m, Frame(F.p(p + np.array([0, 0, 0.07])), F.x, F.y, F.z), [(0.0, 0.0), (0.022, 0.0), (0.022, 0.025), (0.012, 0.035), (0.0, 0.035)], 6, mat=mat_rim)
    for j in range(6):
        a = 2 * math.pi * (j + 0.5) / 6
        p = np.array([math.cos(a) * 0.2, math.sin(a) * 0.2, 0.0])
        lathe(m, Frame(F.p(p + np.array([0, 0, 0.058])), F.x, F.y, F.z), [(0.0, -0.01), (0.04, -0.01), (0.04, 0.0), (0.0, 0.0)], 14, mat=mat_rim)
    tube(m, F.p((0.0, 0.0, 0.155)), F.p((0.05, 0.08, 0.17)), 0.008, 6, mat=mat_rim)


def wheels(M, parent):
    node = empty("Wheels", (0, TYRE_R, 0), parent)
    objs = []
    for i, za in enumerate(AXLES_Z):
        for side, sx in (("Left", 1), ("Right", -1)):
            c = (sx * WHEEL_X, TYRE_R, za)
            holder = node
            if i < 2:
                holder = empty(f"Steer_{i + 1}_{side}", c, node)
            w = empty(f"Wheel_{i + 1}_{side}", c, holder)
            m = Mesh()
            tyre(m, c, sx)
            objs.append(m.to_object(f"Wheel_{i + 1}_{side}_Mesh", [M["rubber"], M["chassis"]], w, sharp_angle=60))
    return objs


# ---- behind the cab: engine bay, intake, exhaust, spare tyre, tank and boxes ---------------------------------------------------
def mid_body(M, parent):
    node = empty("Mid_Body", (0, 1.6, 1.0), parent)
    objs = []
    m = Mesh()
    # engine compartment cover with louvres along both sides
    rbox(m, Zframe((0, 1.82, 1.73)), (1.7, 1.0, 1.12), 0.06, 3, mat=0)
    for sx in (1, -1):
        for k in range(10):
            box(m, (sx * 0.86, 1.62 + k * 0.045, 1.73), (0.025, 0.012, 0.85), 0.004, 1, mat=0)
    # air cleaner and its intake hood (right), exhaust stack with heat shield (right rear of the cab)
    rbox(m, Zframe((-0.98, 1.95, 1.95)), (0.42, 0.85, 0.55), 0.06, 2, mat=0)
    path_tube(m, [np.array([-0.98, 2.35, 1.95]), np.array([-0.98, 2.62, 1.95]), np.array([-0.98, 2.72, 2.05])], 0.11, 18, mat=0)
    rbox(m, Frame.along(np.array([-0.98, 2.75, 2.12]), (0, 0, 1), (0, 1, 0)), (0.3, 0.12, 0.18), 0.03, 2, mat=0)
    ex = [np.array([-1.08, 1.35, 2.18]), np.array([-1.08, 2.78, 2.18]), np.array([-1.08, 2.86, 2.1]), np.array([-1.08, 2.88, 1.98])]
    path_tube(m, ex, 0.065, 16, mat=2, caps=False)
    tube(m, (-1.08, 1.7, 2.18), (-1.08, 2.7, 2.18), 0.095, 20, mat=0)
    objs.append(m.to_object("Engine_Bay", [M["paint"], M["chassis"], M["exhaust"]], node, sharp_angle=45))
    # spare tyre on its carrier: its top is the truck's highest point (118 in)
    sp = empty("Spare_Tire", SPARE, node)
    s = Mesh()
    tyre(s, SPARE, 1)
    objs.append(s.to_object("Spare_Tire_Mesh", [M["rubber"], M["chassis"]], sp, sharp_angle=60))
    c = Mesh()
    for dz in (-0.35, 0.35):
        box(c, (SPARE[0] - 0.1, 1.55, SPARE[2] + dz), (0.08, 0.5, 0.08), 0.01, 1, mat=0)
    box(c, (SPARE[0] - 0.1, 1.82, SPARE[2]), (0.08, 0.08, 0.8), 0.01, 1, mat=0)
    objs.append(c.to_object("Spare_Tire_Carrier", [M["chassis"]], node))
    # fuel tank (left), battery box and tool boxes (right)
    t = Mesh()
    rings = []
    for z in np.linspace(1.08, -0.34, 2):
        loop = fillet_path([(1.19, 1.28), (1.19, 0.72), (0.7, 0.72), (0.7, 1.28)], [0.22, 0.22, 0.04, 0.04], arc_n=6, seg_n=3, closed=True)
        rings.append([(x, y, z) for x, y in loop])
    ids = t.grid(rings, closed=True)
    t.cap(ids[0], flip=True)
    t.cap(ids[-1])
    for z in (0.85, -0.1):
        loop = fillet_path([(1.2, 1.29), (1.2, 0.71), (0.69, 0.71), (0.69, 1.29)], [0.23, 0.23, 0.04, 0.04], arc_n=6, seg_n=3, closed=True)
        t.grid([[(x, y, z + 0.03) for x, y in loop], [(x, y, z - 0.03) for x, y in loop]], closed=True, mat=1)
    lathe(t, Yframe((1.05, 1.28, 0.6)), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.07, 0.05), (0.07, 0.08), (0.0, 0.085)], 16, mat=1)
    objs.append(t.to_object("Fuel_Tank", [M["paint"], M["chassis"]], node, sharp_angle=50))
    b = Mesh()
    for c0, size in (((-0.94, 1.0, 0.72), (0.5, 0.52, 0.68)), ((-0.94, 0.98, -0.12), (0.5, 0.48, 0.82))):
        rbox(b, Zframe(c0), size, 0.03, 2, mat=0)
        for dz in (-size[2] / 4, size[2] / 4):
            box(b, (c0[0] - 0.255, c0[1] + 0.12, c0[2] + dz), (0.012, 0.06, 0.05), 0.004, 1, mat=1)
    objs.append(b.to_object("Battery_And_Tool_Boxes", [M["paint"], M["chassis"]], node, sharp_angle=45))
    return objs


# ---- cargo body -----------------------------------------------------------------------------------------------------------------
def cargo_body(M, parent):
    node = empty("Cargo_Body", (0, BED_FLOOR_Y, (BED_FRONT_Z + BED_REAR_Z) / 2), parent)
    m = Mesh()
    zc = (BED_FRONT_Z + BED_REAR_Z) / 2
    L = BED_FRONT_Z - BED_REAR_Z
    top = BED_FLOOR_Y + BED_SIDE_H
    # floor, its long sills on the frame and the cross-members
    rbox(m, Zframe((0, BED_FLOOR_Y - 0.03, zc)), (2 * BED_HALF_W, 0.06, L - 0.06), 0.01, 1, mat=0)
    for sx in (1, -1):
        box(m, (sx * RAIL_X, (RAIL_Y1 + BED_FLOOR_Y - 0.06) / 2, zc), (0.12, BED_FLOOR_Y - 0.06 - RAIL_Y1, L - 0.1), 0.005, 1, mat=0)
    for z in np.arange(BED_FRONT_Z - 0.15, BED_REAR_Z, -0.6):
        box(m, (0, BED_FLOOR_Y - 0.11, z), (2 * BED_HALF_W - 0.04, 0.1, 0.07), 0.005, 1, mat=0)
    # drop sides: panels with pressed ribs, a top rail, stake pockets, hinges and latches
    for sx in (1, -1):
        x = sx * (BED_HALF_W - 0.02)
        rbox(m, Zframe((x, BED_FLOOR_Y + BED_SIDE_H / 2, zc)), (0.035, BED_SIDE_H, L - 0.1), 0.008, 1, mat=0)
        rbox(m, Zframe((x + sx * 0.012, top - 0.025, zc)), (0.06, 0.05, L - 0.04), 0.012, 1, mat=0)
        for z in np.arange(BED_FRONT_Z - 0.3, BED_REAR_Z + 0.1, -0.6):
            box(m, (x + sx * 0.03, BED_FLOOR_Y + BED_SIDE_H / 2 - 0.02, z), (0.025, BED_SIDE_H - 0.1, 0.06), 0.006, 1, mat=0)
            box(m, (x + sx * 0.025, top - 0.07, z - 0.12), (0.04, 0.08, 0.06), 0.005, 1, mat=0)
            lathe(m, Zframe((x + sx * 0.02, BED_FLOOR_Y + 0.02, z - 0.25)), [(0.0, -0.06), (0.018, -0.06), (0.018, 0.06), (0.0, 0.06)], 8, mat=1)
        box(m, (x + sx * 0.025, BED_FLOOR_Y + 0.35, BED_REAR_Z + 0.08), (0.04, 0.12, 0.05), 0.006, 1, mat=1)
        # tie-down rings along the floor edge
        for z in np.arange(BED_FRONT_Z - 0.4, BED_REAR_Z, -0.9):  # folded flat into the floor
            lathe(m, Yframe((sx * (BED_HALF_W - 0.1), BED_FLOOR_Y - 0.01, z)), [(0.025, 0.0), (0.045, 0.0), (0.045, 0.009), (0.025, 0.009), (0.025, 0.0)], 12, mat=1)
    # front bulkhead (headboard) with ribs and a top rail; rear panel
    rbox(m, Zframe((0, BED_FLOOR_Y + 0.45, BED_FRONT_Z - 0.05)), (2 * BED_HALF_W, 0.9, 0.04), 0.01, 1, mat=0)
    for x in np.linspace(-1.0, 1.0, 6):
        box(m, (x, BED_FLOOR_Y + 0.45, BED_FRONT_Z - 0.015), (0.06, 0.86, 0.03), 0.006, 1, mat=0)
    box(m, (0, BED_FLOOR_Y + 0.9, BED_FRONT_Z - 0.05), (2 * BED_HALF_W, 0.05, 0.07), 0.012, 1, mat=0)
    # the rear panel, cut down where the crane's boom and lift cylinder reach over it
    n0, n1, nh = CRANE[0] - 0.2, CRANE[0] + 0.2, 0.36
    for x0, x1, h in ((-(BED_HALF_W - 0.03), n0, BED_SIDE_H), (n0, n1, nh), (n1, BED_HALF_W - 0.03, BED_SIDE_H)):
        rbox(m, Zframe(((x0 + x1) / 2, BED_FLOOR_Y + h / 2, BED_REAR_Z + 0.0425)), (x1 - x0, h, 0.035), 0.008, 1, mat=0)
    for x in np.linspace(-0.9, 0.9, 5):
        h = nh if n0 < x < n1 else BED_SIDE_H
        box(m, (x, BED_FLOOR_Y + h / 2, BED_REAR_Z + 0.0125), (0.06, h - 0.1, 0.025), 0.006, 1, mat=0)
    # the boom rest, where the stowed crane boom lies along the right side: an arm off the right side's top rail,
    # clear over the loads
    box(m, (-(BED_HALF_W - 0.02), top + 0.03, -1.15), (0.06, 0.06, 0.1), 0.01, 1, mat=0)
    box(m, ((-(BED_HALF_W + 0.01) + CRANE[0] + 0.12) / 2, top + 0.065, -1.15), (BED_HALF_W + 0.01 + CRANE[0] + 0.12, 0.04, 0.12), 0.01, 1, mat=0)
    objs = [m.to_object("Cargo_Body_Mesh", [M["paint"], M["chassis"]], node, sharp_angle=45)]
    # rear: crane deck, bumper with pintle hook, mud flaps
    r = Mesh()
    box(r, (0, RAIL_Y1 + 0.05, (BED_REAR_Z + REAR_Z) / 2 + 0.05), (2 * BED_HALF_W - 0.2, 0.18, BED_REAR_Z - REAR_Z - 0.12), 0.02, 1, mat=0)
    zr = BUMPER_REAR_Z
    rbox(r, Zframe((0, 0.92, zr + 0.07)), (2.2, 0.3, 0.14), 0.025, 2, mat=0)
    lathe(r, Frame((0, 0.88, zr - 0.06), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.05, -0.04), (0.11, -0.04), (0.11, 0.04), (0.05, 0.04), (0.05, -0.04)], 20, mat=1)
    rbox(r, Zframe((0, 0.88, zr + 0.0)), (0.16, 0.14, 0.12), 0.02, 1, mat=1)
    for sx in (1, -1):
        lathe(r, Frame((sx * 0.62, 0.8, zr - 0.02), (1, 0, 0), (0, 0, -1), (0, 1, 0)), [(0.035, -0.035), (0.07, -0.035), (0.07, 0.035), (0.035, 0.035), (0.035, -0.035)], 16, mat=1)
    objs.append(r.to_object("Rear_End", [M["paint"], M["chassis"]], node, sharp_angle=45))
    mf = Mesh()
    for sx in (1, -1):
        box(mf, (sx * 0.98, 0.78, AXLES_Z[3] - 0.78), (0.42, 0.7, 0.012), 0.004, 1)
    objs.append(mf.to_object("Mud_Flaps_Rear", [M["rubber"]], node))
    return objs


# ---- the crane ----------------------------------------------------------------------------------------------------------------
def crane(M, parent):
    cx, cy, cz = CRANE
    slew = empty("Crane", (cx, cy, cz), parent)
    objs = []
    m = Mesh()
    lathe(m, Yframe((cx, cy, cz)), [(0.0, 0.0), (0.3, 0.0), (0.3, 0.06), (0.26, 0.08), (0.26, 0.42), (0.28, 0.44), (0.28, 0.5), (0.0, 0.5)], 32, mat=0)
    rbox(m, Zframe((cx, cy + 0.66, cz - 0.02)), (0.42, 0.34, 0.5), 0.04, 2, mat=0)
    for sx in (1, -1):
        prism(m, Frame((cx + sx * 0.16, cy + 0.82, cz + 0.05), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), [(-0.2, -0.1), (0.22, -0.1), (0.18, 0.1), (-0.12, 0.12)], 0.04, mat=0)
    # control station on the turret's side
    rbox(m, Zframe((cx + 0.27, cy + 0.6, cz - 0.05)), (0.12, 0.3, 0.26), 0.02, 1, mat=1)
    for k in range(4):
        tube(m, (cx + 0.33, cy + 0.68, cz - 0.14 + k * 0.06), (cx + 0.43, cy + 0.78, cz - 0.14 + k * 0.06), 0.008, 6, mat=1)
    objs.append(m.to_object("Crane_Turret", [M["paint"], M["chassis"]], slew, sharp_angle=45))
    pivot = (cx, cy + 0.84, cz + 0.12)
    boom = empty("Crane_Boom", pivot, slew)
    b = Mesh()
    L = 3.55
    rbox(b, Zframe((cx, pivot[1], pivot[2] + L / 2 - 0.1)), (0.22, 0.3, L), 0.025, 2, mat=0)
    lathe(b, Xframe((cx - 0.13, pivot[1], pivot[2]), 1), [(0.0, 0.0), (0.09, 0.0), (0.09, 0.26), (0.0, 0.26)], 16, mat=1)
    # lift cylinder: barrel from the turret, chrome rod into the boom
    lo = np.array([cx, cy + 0.5, cz - 0.15])
    hi = np.array([cx, pivot[1] - 0.15, pivot[2] + 1.25])
    tube(b, lo, lo + (hi - lo) * 0.6, 0.075, 16, mat=1)
    tube(b, lo + (hi - lo) * 0.55, hi, 0.04, 12, mat=2)
    objs.append(b.to_object("Crane_Boom_Mesh", [M["paint"], M["chassis"], M["steel"]], boom, sharp_angle=45))
    ext = empty("Crane_Boom_Extension", (cx, pivot[1], pivot[2] + L - 0.1), boom)
    e = Mesh()
    tip = np.array([cx, pivot[1], pivot[2] + L + 0.18])
    rbox(e, Zframe((cx, pivot[1], pivot[2] + L - 0.6)), (0.17, 0.23, 1.6), 0.02, 2, mat=0)
    rbox(e, Zframe(tip - np.array([0, 0, 0.06])), (0.2, 0.26, 0.22), 0.03, 2, mat=0)
    lathe(e, Xframe(tip + np.array([-0.04, -0.02, 0.02]), 1), [(0.0, 0.0), (0.1, 0.0), (0.1, 0.08), (0.0, 0.08)], 20, mat=1)
    objs.append(e.to_object("Crane_Boom_Extension_Mesh", [M["paint"], M["chassis"]], ext, sharp_angle=45))
    # the hook block, stowed drawn up under the boom's tip
    hc = tip + np.array([0, -0.26, 0.06])
    hook = empty("Crane_Hook", tuple(hc), ext)
    h = Mesh()
    tube(h, tip + np.array([0, -0.12, 0.06]), hc + np.array([0, 0.1, 0]), 0.008, 6, mat=1)
    rbox(h, Zframe(hc), (0.1, 0.2, 0.12), 0.02, 2, mat=2)
    hk = [hc + np.array([0, -0.1, 0]), hc + np.array([0, -0.18, 0]), hc + np.array([0, -0.23, 0.05]), hc + np.array([0, -0.2, 0.1]), hc + np.array([0, -0.15, 0.09])]
    path_tube(h, hk, 0.022, 10, mat=1)
    objs.append(h.to_object("Crane_Hook_Mesh", [M["chassis"], M["steel"], M["hazard"]], hook, sharp_angle=50))
    return objs


# ---- lights ----------------------------------------------------------------------------------------------------------------
def lamp(m, c, d, r, lens=0, body=1, depth=0.05):
    F = Frame.along(c, d)
    lathe(m, Frame(F.o - F.z * depth, F.x, F.y, F.z), [(0.0, 0.0), (r + 0.015, 0.0), (r + 0.015, depth + 0.006), (r, depth + 0.006), (r, depth), (0.0, depth)], 20, mat=body)
    lathe(m, F, [(0.0, 0.0), (r, 0.0), (r * 0.7, r * 0.18), (0.0, r * 0.22)], 20, mat=lens)


def lights(M, parent):
    node = empty("Lights", (0, 1.2, 0), parent)
    objs = []
    specs = [
        ("Light_Head_Left", M["light_white"], (0.92, BUMPER_Y + 0.03, BUMPER_FRONT_Z + 0.002), (0, 0, 1), 0.09),
        ("Light_Head_Right", M["light_white"], (-0.92, BUMPER_Y + 0.03, BUMPER_FRONT_Z + 0.002), (0, 0, 1), 0.09),
        ("Light_Turn_Front_Left", M["light_amber"], (0.72, BUMPER_Y + 0.07, BUMPER_FRONT_Z + 0.002), (0, 0, 1), 0.045),
        ("Light_Turn_Front_Right", M["light_amber"], (-0.72, BUMPER_Y + 0.07, BUMPER_FRONT_Z + 0.002), (0, 0, 1), 0.045),
        ("Light_Tail_Left", M["light_red"], (0.9, 0.95, BUMPER_REAR_Z - 0.002), (0, 0, -1), 0.06),
        ("Light_Tail_Right", M["light_red"], (-0.9, 0.95, BUMPER_REAR_Z - 0.002), (0, 0, -1), 0.06),
        ("Light_Turn_Rear_Left", M["light_amber"], (0.74, 0.95, BUMPER_REAR_Z - 0.002), (0, 0, -1), 0.045),
        ("Light_Turn_Rear_Right", M["light_amber"], (-0.74, 0.95, BUMPER_REAR_Z - 0.002), (0, 0, -1), 0.045),
        ("Light_Reverse", M["light_white"], (0.4, 0.95, BUMPER_REAR_Z - 0.002), (0, 0, -1), 0.04),
        ("Light_Beacon", M["light_amber"], (0.85, CAB_ROOF_Y + 0.02, CAB_REAR_Z + 0.15), (0, 1, 0), 0.07),
    ]
    for x in (-0.3, 0.0, 0.3):
        specs.append((f"Light_Clearance_{'L' if x > 0 else 'R' if x < 0 else 'C'}", M["light_amber"], (x, CAB_ROOF_Y - 0.005, CAB_FRONT_Z - 0.235), (0, 0.6, 0.8), 0.025))
    for name, mat, c, d, r in specs:
        n = empty(name, c, node)
        m = Mesh()
        if name == "Light_Beacon":
            lathe(m, Yframe(c), [(0.0, 0.0), (0.09, 0.0), (0.09, 0.03), (0.075, 0.035), (0.07, 0.1), (0.05, 0.12), (0.0, 0.125)], 20, mat=0)
            lathe(m, Yframe(c), [(0.0, -0.02), (0.1, -0.02), (0.1, 0.0), (0.0, 0.0)], 20, mat=1)
            objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
            continue
        lamp(m, np.asarray(c, float), norm(d), r)
        if name.startswith("Light_Head"):
            # wire guard over the headlight
            for k in (-1, 0, 1):
                tube(m, np.asarray(c) + np.array([-0.1, k * 0.06, 0.04]), np.asarray(c) + np.array([0.1, k * 0.06, 0.04]), 0.006, 6, mat=1)
        objs.append(m.to_object(name + "_Lens", [mat, M["chassis"]], n))
    # reflectors: red at the back, amber on the sides
    rf = Mesh()
    for sx in (1, -1):
        box(rf, (sx * 0.6, 1.0, BUMPER_REAR_Z - 0.003), (0.08, 0.05, 0.006), 0.004, 1, mat=0)
        for z in (2.0, -1.0, -3.9):
            rbox(rf, Frame((sx * (BED_HALF_W + 0.012), BED_FLOOR_Y - 0.08, z), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), (0.07, 0.05, 0.006), 0.004, 1, mat=1)
    objs.append(rf.to_object("Reflectors", [M["light_red"], M["light_amber"]], node))
    return objs


# ---- cargo: eight pallet loads ----------------------------------------------------------------------------------------------
def pallet(m, c, mat=0):
    """A 40 x 48 in wooden pallet: three runners and the deck boards."""
    x, y, z = c
    for dx in (-0.46, 0.0, 0.46):
        box(m, (x + dx, y + 0.05, z), (0.09, 0.09, 1.2), 0.005, 1, mat=mat)
    for k in range(7):
        box(m, (x, y + 0.11, z - 0.56 + k * (1.12 / 6)), (1.0, 0.022, 0.13), 0.004, 1, mat=mat)
    for dz in (-0.55, 0.55):
        box(m, (x, y + 0.009, z + dz), (1.0, 0.018, 0.12), 0.004, 1, mat=mat)


def strap(m, c, w, h, d, mat):
    """A ratchet strap thrown over a load: across the top and down both sides."""
    x, y, z = c
    box(m, (x, y + h + 0.004, z), (w + 0.02, 0.006, 0.05), 0.002, 1, mat=mat)
    for sx in (1, -1):
        box(m, (x + sx * (w / 2 + 0.006), y + h / 2, z), (0.006, h, 0.05), 0.002, 1, mat=mat)


def cargo(M, parent):
    """Resources on the bed: ammunition, fuel drums, crates and rations, each pallet its own node."""
    node = empty("Cargo", (0, BED_FLOOR_Y, -1.5), parent)
    objs = []
    rows = [BED_FRONT_Z - 0.695 - k * 1.27 for k in range(4)]  # the front row just clear of the headboard
    kinds = ["drums", "ammo", "crates", "rations", "drums", "crates", "ammo", "rations"]
    slot = 0
    for r, z in enumerate(rows):
        for side, x in (("Left", 0.58), ("Right", -0.58)):
            kind = kinds[slot] if x > 0 else ["ammo", "ammo_low", "crates", "ammo"][r]  # the second sits under the stowed hook
            slot += 1
            c = (x, BED_FLOOR_Y + 0.003, z)
            n = empty(f"Cargo_Pallet_{slot}", c, node)
            m = Mesh()
            pallet(m, c, 0)
            y0 = c[1] + 0.12
            if kind == "drums":  # four 55-gallon drums, ribbed, with bungs on top
                for dx in (-0.25, 0.25):
                    for dz in (-0.3, 0.3):
                        p = (x + dx, y0, z + dz)
                        prof = [(0.0, 0.0), (0.27, 0.0), (0.29, 0.015), (0.29, 0.29), (0.3, 0.3), (0.29, 0.31), (0.29, 0.57), (0.3, 0.58), (0.29, 0.59), (0.29, 0.865), (0.27, 0.88), (0.0, 0.88)]
                        lathe(m, Yframe(p), prof, 28, mat=2)
                        lathe(m, Yframe((p[0] + 0.15, y0 + 0.88, p[2])), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.015), (0.0, 0.015)], 10, mat=1)
                strap(m, (x, y0, z), 1.0, 0.88, 1.2, 5)
            elif kind in ("ammo", "ammo_low"):  # olive ammunition cans, handles up: two layers, or one under the crane's hook
                layers = 1 if kind == "ammo_low" else 2
                for layer in range(layers):
                    for i in range(3):
                        for j in range(4):
                            p = (x - 0.32 + i * 0.32, y0 + 0.095 + layer * 0.19, z - 0.45 + j * 0.3)
                            box(m, p, (0.3, 0.18, 0.28), 0.01, 1, mat=3)
                            if layer == layers - 1:
                                box(m, (p[0], p[1] + 0.096, p[2]), (0.1, 0.012, 0.02), 0.004, 1, mat=1)
                strap(m, (x, y0, z - 0.3), 0.96, 0.19 * layers, 1.2, 5)
                strap(m, (x, y0, z + 0.3), 0.96, 0.19 * layers, 1.2, 5)
            elif kind == "crates":  # wooden crates, stencilled
                for i, dz in enumerate((-0.31, 0.31)):
                    p = (x, y0 + 0.22, z + dz)
                    rbox(m, Zframe(p), (0.98, 0.44, 0.58), 0.01, 1, mat=4)
                    for k in (-0.4, 0.0, 0.4):
                        box(m, (x + k, p[1], p[2] - 0.292), (0.06, 0.44, 0.01), 0.003, 1, mat=4)
                strap(m, (x, y0, z), 0.98, 0.44, 1.2, 5)
            else:  # rations: cardboard cases stretch-wrapped
                for layer in range(2):
                    for i in range(2):
                        for j in range(3):
                            box(m, (x - 0.25 + i * 0.5, y0 + 0.12 + layer * 0.24, z - 0.4 + j * 0.4), (0.48, 0.23, 0.38), 0.006, 1, mat=6)
                wrap = Mesh()
                rbox(wrap, Zframe((x, y0 + 0.24, z)), (1.0, 0.485, 1.22), 0.01, 1)
                objs.append(wrap.to_object(f"Cargo_Pallet_{slot}_Wrap", [M["wrap"]], n, sharp_angle=50))
            objs.append(m.to_object(f"Cargo_Pallet_{slot}_Mesh", [M["wood"], M["chassis"], M["drum"], M["ammo_can"], M["crate"], M["strap"], M["cardboard"]], n, sharp_angle=50))
    return objs
