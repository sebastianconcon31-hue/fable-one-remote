"""Everything that moves or bolts on: main and tail rotors, the Longbow radar,
TADS and PNVS sensor turrets, the M230 gun, landing gear, rocket pods and
Hellfire launchers, lights, antennas and sensors.

Driven parts are their own nodes, pivoted where the real part turns, with the
names the viewer drives (Main_Rotor spins about local Y, Tail_Rotor about
local X, TADS_Turret / PNVS_Turret / M230_Turret slew about Y, TADS_Sensors and
M230_Gun elevate about X)."""
import math
import numpy as np
from geom import Mesh, fillet_path, airfoil, Frame, lathe, tube, path_tube, rbox, prism, disc, empty, norm
from ah64 import (HUB, HUB_H, R_MAIN, R_TAIL, TAIL_HUB, FCR_TOP_Y, HUB_TOP_Y, GROUND_Y, MAIN_WHEEL, MAIN_WHEEL_R, TAIL_WHEEL_Z,
                  TAIL_WHEEL_R, NOSE_Z, TADS_AZ, TADS_EL, PNVS, GUN_TURRET, GUN_PIVOT, GUN_MUZZLE, WING_TIP_X, TAIL_Z,
                  PYLON_INBOARD_X, PYLON_OUTBOARD_X, SPEC)

UP = np.array([0.0, 1.0, 0.0])
deg = math.pi / 180


def Yframe(o):
    """Frame at o with local Z pointing up (for lathes about a vertical axis)."""
    return Frame(o, (1, 0, 0), (0, 0, -1), (0, 1, 0))


def Xframe(o, sx=1):
    """Frame at o with local Z along +X (sx=1) or -X."""
    return Frame(o, (0, 0, -sx), (0, 1, 0), (sx, 0, 0))


def Zframe(o, sz=1):
    return Frame(o, (sz, 0, 0), (0, 1, 0), (0, 0, sz))


# ---- main rotor ----------------------------------------------------------------------------------------------------------------
def blade_section(r, dir_, side, n=18):
    """Points of the blade section at radius r: HH-02-like cambered section, swept tip, twisted, with a little static droop."""
    root = 0.8
    if r < 1.3:
        k = (r - root) / (1.3 - root)
        c = 0.24 + (0.533 - 0.24) * (k * k * (3 - 2 * k))
        t = 0.5 - 0.405 * (k * k * (3 - 2 * k))  # thick oval cuff blending into the airfoil
    else:
        c = 0.533
        t = 0.095 - 0.03 * (r - 1.3) / (R_MAIN - 1.3)
    sweep = 0.0
    if r > 6.78:
        e = (r - 6.78) / (R_MAIN - 6.78)
        sweep = (r - 6.78) * math.tan(20 * deg)
        c = 0.533 - 0.17 * e
    pitch = (6.0 - 9.0 * max(0.0, r - 1.3) / (R_MAIN - 1.3)) * deg
    droop = -0.16 * ((r - root) / (R_MAIN - root)) ** 2
    pts = []
    for u, v in airfoil(t, n, camber=0.018 if r >= 1.3 else 0.0):
        s = (0.25 - u) * c - sweep  # + toward the leading edge
        h = v * c
        s2 = s * math.cos(pitch) - h * math.sin(pitch)
        h2 = s * math.sin(pitch) + h * math.cos(pitch)
        pts.append(np.asarray(HUB) + dir_ * r + side * s2 + UP * (h2 + droop))
    return pts


def main_rotor(M, parent):
    node = empty("Main_Rotor", HUB, parent)
    hub = Mesh()
    hx, hy, hz = HUB
    # hub body and the mast below it
    F = Yframe((hx, hy - HUB_H / 2, hz))
    lathe(hub, F, [(0.0, 0.0), (0.2, 0.0), (0.27, 0.02), (0.29, 0.06), (0.29, 0.16), (0.25, HUB_H), (0.0, HUB_H)], 32, mat=0)
    lathe(hub, Yframe((hx, 2.3, hz)), [(0.11, 0.0), (0.11, 0.42), (0.13, 0.44), (0.13, 0.5)], 24, mat=1, caps=True)
    # rotating swashplate ring
    lathe(hub, Yframe((hx, 2.53, hz)), [(0.14, 0.0), (0.33, 0.0), (0.34, 0.015), (0.34, 0.04), (0.33, 0.055), (0.14, 0.055), (0.14, 0.0)], 36, mat=0)
    blades = Mesh()
    for i in range(4):
        a = i * math.pi / 2 + 20 * deg
        d = np.array([math.cos(a), 0.0, math.sin(a)])
        side = np.cross(UP, d)  # leading edge: the rotor turns counter-clockwise seen from above
        H = np.asarray(HUB)
        # strap-pack housing and pitch housing out to the blade grip
        rbox(hub, Frame.along(H + d * 0.46 + UP * 0.02, d), (0.19, 0.12, 0.42), 0.03, 2, mat=0)
        lathe(hub, Frame.along(H + d * 0.3, d), [(0.0, 0.0), (0.085, 0.0), (0.095, 0.02), (0.095, 0.4), (0.105, 0.42), (0.105, 0.47), (0.0, 0.47)], 20, mat=0)
        # blade grip clevis and its two retention bolts
        G = Frame.along(H + d * 0.86, d)
        rbox(hub, G, (0.2, 0.2, 0.2), 0.03, 2, mat=0)
        for k in (-0.05, 0.05):
            tube(hub, G.p((0, -0.13, k)), G.p((0, 0.13, k)), 0.022, 12, mat=1)
            for yy in (-0.13, 0.13):
                lathe(hub, Frame.along(G.p((0, yy, k)), G.d((0, np.sign(yy), 0))), [(0, 0), (0.035, 0), (0.035, 0.015), (0.0, 0.02)], 6, mat=1)
        # lead-lag damper from the hub to the pitch housing, trailing side
        p0 = H + d * 0.18 - side * 0.2 + UP * 0.03
        p1 = H + d * 0.64 - side * 0.1 + UP * 0.03
        tube(hub, p0, p0 + (p1 - p0) * 0.62, 0.05, 14, mat=0)
        tube(hub, p0 + (p1 - p0) * 0.58, p1, 0.028, 12, mat=1)
        # pitch horn on the leading side, and the pitch link down to the swashplate
        horn = H + d * 0.42 + side * 0.2 - UP * 0.06
        rbox(hub, Frame.along((H + d * 0.42 + horn) / 2, horn - (H + d * 0.42)), (0.06, 0.05, 0.22), 0.015, 1, mat=0)
        low = np.array([hx, 2.585, hz]) + (d * 0.42 + side * 0.2) * (0.33 / np.linalg.norm(d * 0.42 + side * 0.2))
        tube(hub, low, horn, 0.018, 10, mat=1)
        for p in (low, horn):
            lathe(hub, Frame.along(p - UP * 0.02, UP), [(0, 0), (0.028, 0), (0.03, 0.02), (0.028, 0.04), (0, 0.04)], 10, mat=0)
        # the blade: cuff, airfoil, swept tip; nickel leading-edge strip and tip cap are their own materials
        rs = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.6, 2.2, 3.0, 4.0, 5.0, 5.8, 6.4, 6.78, 6.9, 7.0, 7.1, 7.2, 7.26, R_MAIN]
        secs = [blade_section(r, d, side) for r in rs]
        n = len(secs[0])
        us = [u for u, _ in airfoil(0.1, 18)]

        def mats(ri, j, rs=rs, us=us, n=n):
            if rs[ri] >= 7.2:
                return 2
            k = (j + 1) % n
            if rs[ri] >= 1.3 and max(us[j], us[k]) < 0.1:
                return 1
            return 0

        H2 = np.asarray(HUB)
        far = max(math.hypot(p[0] - H2[0], p[2] - H2[2]) for sec in secs for p in sec)
        k = R_MAIN / far
        secs = [[np.array([H2[0] + (p[0] - H2[0]) * k, p[1], H2[2] + (p[2] - H2[2]) * k]) for p in sec] for sec in secs]
        ids = blades.grid(secs, closed=True, mats=mats)
        blades.cap(ids[0], mat=0, flip=True)
        blades.cap(ids[-1], mat=2)
        # trim tab at the trailing edge, outboard
        te = lambda r: blade_section(r, d, side)[0]
        t0, t1 = te(5.2), te(5.9)
        rbox(blades, Frame.along((t0 + t1) / 2 - side * 0.035, t1 - t0), (0.07, 0.004, np.linalg.norm(t1 - t0)), 0.001, 1, mat=0)
    objs = [hub.to_object("Main_Rotor_Hub", [M["mech"], M["steel"]], node, sharp_angle=50),
            blades.to_object("Main_Rotor_Blades", [M["blade"], M["blade_le"], M["blade_tip"]], node, sharp_angle=60)]
    return node, objs


def rotor_fixed(M, parent):
    """Parts that don't turn with the rotor: the stationary swashplate and its servos, the FCR mast and radome."""
    m = Mesh()
    hx, _, hz = HUB
    lathe(m, Yframe((hx, 2.47, hz)), [(0.13, 0.0), (0.34, 0.0), (0.35, 0.02), (0.35, 0.045), (0.34, 0.06), (0.13, 0.06), (0.13, 0.0)], 36, mat=0)
    for a in (30, 150, 270):
        d = np.array([math.cos(a * deg), 0, math.sin(a * deg)])
        base = np.array([hx, 2.3, hz]) + d * 0.3
        tube(m, base, base + UP * 0.12, 0.05, 14, mat=0)
        tube(m, base + UP * 0.1, base + UP * 0.2, 0.025, 10, mat=1)
    # scissors link between the stationary and rotating swashplates
    tube(m, (hx + 0.2, 2.5, hz + 0.2), (hx + 0.16, 2.58, hz + 0.16), 0.018, 8, mat=0)
    objs = [m.to_object("Swashplate", [M["mech"], M["steel"]], parent)]
    fcr = empty("FCR_Radome", (0, FCR_TOP_Y - 0.3, hz), parent)
    r = Mesh()
    base = FCR_TOP_Y - 0.6
    tube(r, (hx, HUB_TOP_Y - 0.02, hz), (hx, base + 0.02, hz), 0.075, 20, mat=1)
    lathe(r, Yframe((hx, base, hz)), [(0.0, 0.0), (0.14, 0.0), (0.19, 0.07), (0.44, 0.12), (0.52, 0.2), (0.53, 0.28), (0.5, 0.4), (0.4, 0.51), (0.22, 0.58), (0.0, 0.6)], 48, mat=0)
    # radar frequency interferometer, on the radome's underside
    rbox(r, Frame((hx, base + 0.06, hz + 0.32)), (0.26, 0.09, 0.16), 0.03, 2, mat=0)
    objs.append(r.to_object("FCR_Radome_Mesh", [M["paint"], M["mech"]], fcr, sharp_angle=60))
    return objs


# ---- tail rotor ----------------------------------------------------------------------------------------------------------------
def tail_rotor(M, parent):
    node = empty("Tail_Rotor", TAIL_HUB, parent)
    hub = Mesh()
    H = np.asarray(TAIL_HUB)
    lathe(hub, Xframe((0.02, H[1], H[2])), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.2), (0.09, 0.22), (0.09, 0.34), (0.06, 0.38), (0.0, 0.38)], 20, mat=0)
    blades = Mesh()
    X = np.array([1.0, 0, 0])
    for pair, (a0, xo) in enumerate(((0.0, 0.335), (55 * deg, 0.265))):
        for flip in (0, math.pi):
            a = a0 + flip
            d = np.array([0.0, math.sin(a), math.cos(a)])
            side = np.cross(X, d)
            c0 = np.array([xo, H[1], H[2]])
            rbox(hub, Frame.along(c0 + d * 0.1, d), (0.1, 0.07, 0.2), 0.02, 1, mat=0)
            secs = []
            for r in (0.19, 0.24, 0.3, 0.6, 0.9, 1.2, 1.33, R_TAIL):
                c = SPEC["tailRotorChord"] * (0.7 if r < 0.24 else 1.0)
                t = 0.14 if r < 0.24 else 0.1
                pitch = (12 - 6 * (r - 0.3)) * deg
                pts = []
                for u, v in airfoil(t, 12):
                    s = (0.25 - u) * c
                    h = v * c
                    s2 = s * math.cos(pitch) - h * math.sin(pitch)
                    h2 = s * math.sin(pitch) + h * math.cos(pitch)
                    pts.append(c0 + d * r + side * s2 + X * h2)
                secs.append(pts)
            far = max(math.hypot(p[1] - H[1], p[2] - H[2]) for sec in secs for p in sec)
            k = R_TAIL / far
            secs = [[np.array([p[0], H[1] + (p[1] - H[1]) * k, H[2] + (p[2] - H[2]) * k]) for p in sec] for sec in secs]
            ids = blades.grid(secs, closed=True, mats=lambda ri, j: 2 if ri == len(secs) - 2 else 0)
            blades.cap(ids[0], flip=True)
            blades.cap(ids[-1], mat=2)
            # pitch-change link
            tube(hub, c0 + d * 0.16 + side * 0.08, c0 + side * 0.06 + X * 0.07, 0.008, 6, mat=1)
    objs = [hub.to_object("Tail_Rotor_Hub", [M["mech"], M["steel"]], node, sharp_angle=50),
            blades.to_object("Tail_Rotor_Blades", [M["blade"], M["blade_le"], M["blade_tip"]], node, sharp_angle=60)]
    return node, objs


# ---- sensors: TADS and PNVS -------------------------------------------------------------------------------------------------
def window(m, G, hw, hh, frame_mat=1, glass_mat=2, r=None):
    """A framed window on a front face: frame G at the face, local Z out of it."""
    rbox(m, G, (hw * 2 + 0.034, hh * 2 + 0.034, 0.022), 0.012, 2, mat=frame_mat)
    rr = min(hw, hh) * 0.55 if r is None else r
    loop = fillet_path([(hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)], [rr] * 4, arc_n=5, seg_n=2, closed=True)[::-1]
    ids = m.verts([G.p((x, y, 0.0112)) for x, y in loop])
    m.face(ids, mat=glass_mat)


def sensors(M, parent):
    objs = []
    az = empty("TADS_Turret", TADS_AZ, parent)
    t = Mesh()
    # azimuth gimbal: the drum under the nose that the whole sight turns on
    lathe(t, Yframe((0, -0.02, 2.2)), [(0.0, 0.0), (0.2, 0.0), (0.225, 0.025), (0.235, 0.08), (0.235, 0.3), (0.2, 0.36), (0.0, 0.37)], 40, mat=0)
    objs.append(t.to_object("TADS_Gimbal", [M["paint"]], az))
    el = empty("TADS_Sensors", TADS_EL, az)
    s = Mesh()
    front = NOSE_Z - 0.0222
    for sx in (1, -1):
        x0 = sx * 0.34
        F = Zframe((x0, -0.04, NOSE_Z - 0.3))
        # sensor shroud: a tall rounded box, its front edges rolled
        rings = []
        for z, sc in ((-0.29, 0.9), (-0.275, 0.975), (-0.25, 1.0), (0.25, 1.0), (0.272, 0.985), (0.285, 0.955), (0.29, 0.935)):
            loop = fillet_path([(0.14, 0.3), (0.14, -0.3), (-0.14, -0.3), (-0.14, 0.3)], [0.035, 0.05, 0.05, 0.035], arc_n=5, seg_n=5, closed=True)
            rings.append([F.p((x * sc, y * sc, z)) for x, y in loop])
        ids = s.grid(rings, closed=True, mat=0)
        s.cap(ids[0], flip=True)
        s.cap(ids[-1])
        if sx > 0:  # night sensor (FLIR): one big window
            window(s, Zframe((x0, 0.0, front)), 0.085, 0.095)
        else:  # day sensor: TV / direct-view optics window, and the laser rangefinder-designator ports
            window(s, Zframe((x0, 0.075, front)), 0.085, 0.06)
            window(s, Zframe((x0 - 0.045 * sx, -0.09, front)), 0.04, 0.04, r=0.035)
            window(s, Zframe((x0 + 0.06 * sx, -0.09, front)), 0.026, 0.026, r=0.022)
    # the gimbal's centre section between the shrouds
    rbox(s, Zframe((0, -0.03, 2.3)), (0.44, 0.46, 0.4), 0.05, 3, mat=0)
    rbox(s, Zframe((0, -0.03, 2.2)), (0.6, 0.12, 0.3), 0.04, 2, mat=1)
    objs.append(s.to_object("TADS_Sensor_Shrouds", [M["paint"], M["mech"], M["sensor_glass"]], el, sharp_angle=50))
    # PNVS: the small turret on top of the nose
    pn = empty("PNVS_Turret", PNVS, parent)
    p = Mesh()
    lathe(p, Yframe(PNVS), [(0.0, -0.02), (0.12, -0.02), (0.14, 0.0), (0.145, 0.06), (0.145, 0.19), (0.13, 0.22), (0.0, 0.225)], 32, mat=0)
    window(p, Zframe((0, PNVS[1] + 0.1, PNVS[2] + 0.141)), 0.05, 0.045, r=0.02)
    objs.append(p.to_object("PNVS_Mesh", [M["paint"], M["mech"], M["sensor_glass"]], pn))
    return objs


# ---- M230 30 mm chain gun ------------------------------------------------------------------------------------------------
def gun(M, parent):
    tr = empty("M230_Turret", GUN_TURRET, parent)
    t = Mesh()
    # the turret drive: a ring, so the gun's breech can swing up inside it at full depression
    lathe(t, Yframe((0, -0.5, 0.35)), [(0.15, 0.0), (0.2, 0.0), (0.24, 0.02), (0.25, 0.06), (0.24, 0.08), (0.15, 0.08), (0.15, 0.0)], 32, mat=0)
    # yoke arms down to the elevation trunnions
    py = GUN_PIVOT[1]
    yc, h = (-0.5 + py - 0.05) / 2, (-0.5 - (py - 0.05)) / 2  # from the turret's underside to just below the trunnions
    for sx in (1, -1):
        prism(t, Frame((sx * 0.155, yc, 0.4), (0, 0, 1), (0, 1, 0), (sx, 0, 0)), [(-0.12, h), (0.1, h), (0.06, -h), (-0.06, -h)], 0.04, mat=0)
    objs = [t.to_object("M230_Turret_Mesh", [M["mech"]], tr)]
    gn = empty("M230_Gun", GUN_PIVOT, tr)
    g = Mesh()
    # receiver, feeder and recoil housings
    rbox(g, Zframe((0, py, 0.45)), (0.24, 0.2, 0.62), 0.03, 2, mat=0)
    rbox(g, Zframe((0.14, py + 0.02, 0.42)), (0.08, 0.16, 0.34), 0.02, 2, mat=0)
    tube(g, (0, py, 0.4), (0.14, py, 0.4), 0.05, 16, mat=0)
    tube(g, (0, py, 0.4), (-0.14, py, 0.4), 0.05, 16, mat=0)
    # barrel with its cooling jacket and the muzzle brake
    mx, my, mz = GUN_MUZZLE
    tube(g, (0, my, 0.75), (0, my, 1.0), 0.055, 20, mat=0)
    tube(g, (0, my, 1.0), (0, my, mz - 0.14), 0.036, 20, mat=1)
    lathe(g, Zframe((0, my, mz - 0.15)), [(0.0, 0.0), (0.05, 0.0), (0.052, 0.01), (0.052, 0.14), (0.045, 0.15), (0.03, 0.15), (0.03, 0.12), (0.0, 0.12)], 20, mat=1)
    for k in range(6):
        a = k * math.pi / 3
        c = np.array([0, my, mz - 0.07]) + np.array([math.cos(a), math.sin(a), 0]) * 0.052
        rbox(g, Frame(c, (math.cos(a), math.sin(a), 0), (-math.sin(a), math.cos(a), 0), (0, 0, 1)), (0.004, 0.018, 0.08), 0.001, 1, mat=2)
    objs.append(g.to_object("M230_Gun_Mesh", [M["mech"], M["gun"], M["exhaust"]], gn, sharp_angle=45))
    # ammunition: a chute along the belly from the magazine to the turret's centre, where it turns on a rotary joint,
    # and the feed chute that turns with the turret from there down to the gun's feeder
    c = Mesh()
    pts = [np.array([0.3, -0.41, 0.0]), np.array([0.2, -0.405, 0.15]), np.array([0.05, -0.4, 0.3]), np.array([0.0, -0.4, 0.35])]
    path_tube(c, pts, 0.045, 10, mat=0)
    objs.append(c.to_object("Ammo_Chute", [M["mech"]], parent))
    f = Mesh()
    pts = [np.array([0.0, -0.4, 0.35]), np.array([0.12, -0.4, 0.36]), np.array([0.2, -0.5, 0.39]), np.array([0.19, py + 0.06, 0.41]), np.array([0.17, py + 0.02, 0.42])]
    path_tube(f, pts, 0.04, 10, mat=0)
    objs.append(f.to_object("Ammo_Feed", [M["mech"]], tr))
    return objs


# ---- landing gear ---------------------------------------------------------------------------------------------------------
def wheel(m, c, r, w, sx, tire=0, hub=1):
    F = Xframe(c, sx)
    tread = [(r * 0.62, -w / 2), (r * 0.86, -w / 2), (r * 0.95, -w * 0.46), (r, -w * 0.32), (r, w * 0.32), (r * 0.95, w * 0.46), (r * 0.86, w / 2), (r * 0.62, w / 2)]
    lathe(m, F, [(a, b) for a, b in tread], 48, mat=tire)
    lathe(m, F, [(r * 0.62, w * 0.5), (r * 0.6, w * 0.44), (r * 0.25, w * 0.42), (r * 0.2, w * 0.5), (0.0, w * 0.52)], 32, mat=hub)
    lathe(m, F, [(0.0, -w * 0.52), (r * 0.2, -w * 0.5), (r * 0.25, -w * 0.42), (r * 0.6, -w * 0.44), (r * 0.62, -w * 0.5)], 32, mat=hub)
    for k in range(6):
        a = k * math.pi / 3
        tube(m, F.p((math.cos(a) * r * 0.16, math.sin(a) * r * 0.16, w * 0.5)), F.p((math.cos(a) * r * 0.16, math.sin(a) * r * 0.16, w * 0.56)), 0.009, 6, mat=hub)


def gear(M, parent):
    node = empty("Landing_Gear", (0, -0.3, -1.6), parent)
    objs = []
    wx, wy, wz = MAIN_WHEEL
    for side, sx in (("Left", 1), ("Right", -1)):
        m = Mesh()
        axle = np.array([sx * 0.9, wy, wz])
        pivot = np.array([sx * 0.47, -0.3, -0.98])
        # trailing arm from the fuselage pivot back to the axle
        tube(m, pivot, axle, 0.062, 16, mat=0)
        tube(m, pivot + np.array([0, 0, 0.0]), pivot + np.array([sx * -0.06, 0, 0]), 0.075, 16, mat=0)
        tube(m, axle, np.array([sx * (wx - 0.07), wy, wz]), 0.045, 14, mat=0)
        # oleo shock strut: cylinder from the wing root, chrome piston down to the arm
        top = np.array([sx * 0.62, 0.42, -2.05])
        mid = axle + (pivot - axle) * 0.18 + np.array([0, 0.08, 0])
        tube(m, top, top + (mid - top) * 0.62, 0.068, 18, mat=0)
        tube(m, top + (mid - top) * 0.58, mid, 0.042, 16, mat=1)
        lathe(m, Frame.along(mid, top - mid), [(0.0, -0.04), (0.06, -0.04), (0.06, 0.05), (0.0, 0.05)], 12, mat=0)
        lathe(m, Frame.along(top, top - mid), [(0.0, -0.05), (0.08, -0.05), (0.08, 0.06), (0.0, 0.06)], 12, mat=0)
        # drag brace
        tube(m, np.array([sx * 0.5, 0.05, -1.35]), axle + (pivot - axle) * 0.45, 0.03, 10, mat=0)
        # brake housing and the wheel
        tb = Mesh()
        wheel(tb, (sx * wx, wy, wz), MAIN_WHEEL_R, 0.2, sx)
        lathe(m, Xframe((sx * (wx - 0.1), wy, wz), sx), [(0.0, 0.0), (0.13, 0.0), (0.13, 0.05), (0.0, 0.05)], 20, mat=0)
        objs.append(m.to_object(f"Main_Gear_{side}", [M["mech"], M["steel"]], node, sharp_angle=50))
        objs.append(tb.to_object(f"Main_Wheel_{side}", [M["rubber"], M["mech"]], node, sharp_angle=60))
    # tail wheel: castering fork on a long shock strut under the fin
    m = Mesh()
    tw = np.array([0.0, GROUND_Y + TAIL_WHEEL_R, TAIL_WHEEL_Z])
    top = np.array([0.0, 0.5, -11.98])
    kn = np.array([0.0, -0.3, -12.0])
    tube(m, top, top + (kn - top) * 0.55, 0.06, 16, mat=0)
    tube(m, top + (kn - top) * 0.5, kn, 0.04, 14, mat=1)
    for sx in (1, -1):
        tube(m, kn + np.array([sx * 0.08, 0, 0]), tw + np.array([sx * 0.08, 0, 0]), 0.022, 10, mat=0)
    tube(m, kn + np.array([0.1, 0, 0]), kn + np.array([-0.1, 0, 0]), 0.035, 12, mat=0)
    tw_m = Mesh()
    wheel(tw_m, tw, TAIL_WHEEL_R, 0.12, 1)
    objs.append(m.to_object("Tail_Gear", [M["mech"], M["steel"]], node, sharp_angle=50))
    objs.append(tw_m.to_object("Tail_Wheel", [M["rubber"], M["mech"]], node, sharp_angle=60))
    return objs


# ---- stores -----------------------------------------------------------------------------------------------------------------
def hellfire(M, node, c):
    """AGM-114: 1.63 m, 178 mm; seeker dome, canards, tail fins. Olive with the yellow (warhead) and brown (motor) bands."""
    m = Mesh()
    F = Zframe(c)
    L, r = 1.63, 0.089
    prof = [(0.0, L / 2 + 0.005), (0.035, L / 2 - 0.005), (0.058, L / 2 - 0.03), (0.07, L / 2 - 0.05)][::-1]
    # seeker dome (glass) and its metal ring
    lathe(m, F, prof, 32, mat=3)
    body = [(0.07, L / 2 - 0.05), (0.08, L / 2 - 0.09), (0.086, L / 2 - 0.14), (r, L / 2 - 0.2)][::-1]
    lathe(m, F, body, 32, mat=0)
    # bands: warhead yellow, then olive, motor brown, olive, nozzle
    segs = [(L / 2 - 0.2, L / 2 - 0.26, 1), (L / 2 - 0.26, L / 2 - 0.3, 0), (L / 2 - 0.3, L / 2 - 0.34, 1), (L / 2 - 0.34, -0.1, 0), (-0.1, -0.16, 2), (-0.16, -L / 2 + 0.02, 0)]
    for a, b, mat in segs:
        lathe(m, F, [(r, b), (r, a)], 32, mat=mat)
    lathe(m, F, [(0.0, -L / 2 + 0.03), (0.045, -L / 2 + 0.02), (0.05, -L / 2), (0.085, -L / 2), (r, -L / 2 + 0.02)], 32, mat=4)
    for k in range(4):
        a = (k + 0.5) * math.pi / 2
        d = np.array([math.cos(a), math.sin(a), 0.0])
        G = Frame(F.p(d * (r + 0.04) + np.array([0, 0, L / 2 - 0.36])), d, np.cross((0, 0, 1), d), (0, 0, 1))
        prism(m, G, [(-0.045, -0.05), (0.045, -0.03), (0.045, 0.02), (-0.045, 0.05)], 0.004, mat=0)
        G = Frame(F.p(d * (r + 0.07) + np.array([0, 0, -L / 2 + 0.14])), d, np.cross((0, 0, 1), d), (0, 0, 1))
        prism(m, G, [(-0.075, -0.1), (0.075, -0.1), (0.075, 0.04), (-0.075, 0.1)], 0.005, mat=0)
    return m.to_object(node.name + "_Mesh", [M["stores"], M["band_yellow"], M["band_brown"], M["sensor_glass"], M["exhaust"]], node, sharp_angle=40)


def stores(M, wing_nodes):
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        wn = wing_nodes[side]
        # inboard: M261 19-shot 2.75 in rocket pod
        x = sx * PYLON_INBOARD_X
        pc = np.array([x, 0.1, -2.55])
        pod = empty(f"Store_{side}_Inboard", pc, wn)
        m = Mesh()
        L, R = 1.68, 0.2
        F = Zframe(pc)
        lathe(m, F, [(0.0, -L / 2 + 0.01), (R - 0.03, -L / 2), (R - 0.01, -L / 2 + 0.01), (R, -L / 2 + 0.04), (R, L / 2 - 0.04), (R - 0.01, L / 2 - 0.01), (R - 0.03, L / 2), (0.0, L / 2 - 0.01)], 48, mat=0)
        # the 19 tubes at each end: a rim and a dark bore, with rocket noses showing at the front
        hexes = [(0, 0)] + [(0.078 * math.cos(k * math.pi / 3), 0.078 * math.sin(k * math.pi / 3)) for k in range(6)] + [
            (0.155 * math.cos(k * math.pi / 6), 0.155 * math.sin(k * math.pi / 6)) for k in range(12)]
        for end in (1, -1):
            for hx, hy in hexes:
                G = Frame(F.p((hx, hy, end * (L / 2 - 0.009))), (end, 0, 0), (0, 1, 0), (0, 0, end))
                lathe(m, G, [(0.036, 0.0), (0.036, 0.004), (0.031, 0.004), (0.031, -0.03), (0.0, -0.03)], 16, mat=1)
                if end > 0:
                    lathe(m, Frame(G.p((0, 0, -0.03)), G.x, G.y, G.z), [(0.029, -0.01), (0.029, 0.0), (0.02, 0.012), (0.0, 0.02)], 12, mat=2)
        # suspension lugs and fairing strap
        for dz in (-0.25, 0.25):
            rbox(m, Frame((x, 0.1 + R + 0.01, -2.55 + dz)), (0.05, 0.03, 0.06), 0.008, 1, mat=0)
        for dz in (-0.5, 0.5):
            lathe(m, Frame.along((x, 0.1, -2.55 + dz - 0.015), (0, 0, 1)), [(R + 0.004, 0.0), (R + 0.004, 0.03)], 48, mat=0)
        objs.append(m.to_object(f"Store_{side}_Inboard_Mesh", [M["stores"], M["exhaust"], M["stores_dark"]], pod, sharp_angle=50))
        # outboard: M299 launcher with four Hellfires
        x = sx * PYLON_OUTBOARD_X
        lc = np.array([x, 0.19, -2.5])
        ln = empty(f"Store_{side}_Outboard", lc, wn)
        m = Mesh()
        rbox(m, Zframe((x, 0.3, -2.5)), (0.3, 0.035, 1.32), 0.012, 2, mat=0)  # upper rail beam
        rbox(m, Zframe((x, 0.055, -2.5)), (0.3, 0.03, 1.28), 0.01, 2, mat=0)  # lower rail beam
        rbox(m, Zframe((x, 0.18, -2.5)), (0.06, 0.26, 1.2), 0.015, 2, mat=0)  # spine
        rbox(m, Zframe((x, 0.2, -1.83)), (0.14, 0.18, 0.12), 0.03, 2, mat=0)  # electronics at the front
        for dx in (-0.13, 0.13):
            for y in (0.3 - 0.028, 0.055 - 0.025):
                rbox(m, Zframe((x + dx, y, -2.55)), (0.03, 0.02, 1.1), 0.004, 1, mat=0)
        objs.append(m.to_object(f"Store_{side}_Outboard_Mesh", [M["stores"]], ln, sharp_angle=45))
        for i, (dx, y) in enumerate(((-0.13, 0.19), (0.13, 0.19), (-0.13, -0.055), (0.13, -0.055))):
            mc = np.array([x + dx * sx, y, -2.42])
            mn = empty(f"Hellfire_{side}_{i + 1}", mc, ln)
            objs.append(hellfire(M, mn, mc))
    return objs


# ---- lights, antennas, sensors, steps -------------------------------------------------------------------------------------------
def dome(m, c, d, r, mat, n=16):
    F = Frame.along(c, d)
    lathe(m, F, [(0.0, -0.008), (r * 1.08, -0.008), (r * 1.08, 0.0), (r, 0.0), (r * 0.87, r * 0.5), (r * 0.5, r * 0.87), (0.0, r)], n, mat=mat)


def lights(M, parent):
    node = empty("Lights", (0, 1, -3), parent)
    objs = []
    specs = [
        ("Light_Nav_Left", M["nav_red"], (WING_TIP_X - 0.01, 0.62, -2.2), (0.6, 0, 0.8), 0.028),
        ("Light_Nav_Right", M["nav_green"], (-WING_TIP_X + 0.01, 0.62, -2.2), (-0.6, 0, 0.8), 0.028),
        ("Light_Nav_Tail", M["nav_white"], (0.0, 2.02, TAIL_Z - 0.005), (0, 0, -1), 0.025),
        ("Light_Anticollision_Top", M["beacon"], (0.0, 2.77, -11.95), (0, 1, 0), 0.045),
        ("Light_Anticollision_Bottom", M["beacon"], (0.0, -0.43, -1.3), (0, -1, 0), 0.045),
    ]
    for name, mat, c, d, r in specs:
        n = empty(name, c, node)
        m = Mesh()
        dome(m, np.asarray(c), norm(d), r, 0)
        objs.append(m.to_object(name + "_Lens", [mat], n))
    # formation light strips: boom sides, fin and wingtips
    m2 = Mesh()
    for sx in (1, -1):
        for z0, z1, y, x in ((-6.2, -6.9, 1.52, 0.225), (-9.2, -9.9, 1.47, 0.185)):
            rbox(m2, Frame((sx * x, y, (z0 + z1) / 2), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.012, 0.025, abs(z1 - z0)), 0.005, 1)
        rbox(m2, Frame((sx * (WING_TIP_X - 0.005), 0.66, -2.75), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.012, 0.02, 0.4), 0.005, 1)
    for y0, y1 in ((1.9, 2.4),):
        rbox(m2, Frame((0.0, (y0 + y1) / 2, TAIL_Z + 0.02), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.03, y1 - y0, 0.012), 0.004, 1)
    objs.append(m2.to_object("Light_Formation_Strips", [M["formation"]], node))
    # searchlight lens under the nose
    s = Mesh()
    lathe(s, Frame((0, -0.335, 1.55), (1, 0, 0), (0, 0, 1), (0, -1, 0)), [(0.0, -0.01), (0.11, -0.01), (0.11, 0.0), (0.1, 0.0), (0.09, 0.006), (0.0, 0.012)], 24)
    objs.append(s.to_object("Light_Search_Lens", [M["searchlight"]], node))
    return objs


def details(M, parent):
    node = empty("Details", (0, 1, -3), parent)
    m = Mesh()  # painted bits
    k = Mesh()  # dark / metal bits
    # CMWS missile-warning sensors: two looking forward from the nose, two aft from the tail boom
    for sx in (1, -1):
        for c, d in (((sx * 0.3, 0.38, 1.72), (sx * 0.7, 0.1, 0.7)), ((sx * 0.235, 1.42, -6.05), (sx * 0.7, 0.05, -0.7))):
            c, d = np.asarray(c), norm(d)
            lathe(m, Frame.along(c - d * 0.02, d), [(0.0, 0.0), (0.06, 0.0), (0.062, 0.03), (0.05, 0.05), (0.0, 0.055)], 20)
            dome(k, c + d * 0.045, d, 0.028, 1)
        # radar warning spiral antennas on the nose and at the tail
        for c, d in (((sx * 0.26, 0.58, 1.82), (sx * 0.75, 0.2, 0.62)), ((sx * 0.07, 2.45, -12.1), (sx * 0.6, 0.2, -0.8))):
            c, d = np.asarray(c), norm(d)
            lathe(k, Frame.along(c, d), [(0.0, 0.0), (0.05, 0.0), (0.04, 0.018), (0.0, 0.02)], 20, mat=2)
        # chaff and flare dispensers on the boom
        z = -5.3
        rbox(k, Frame((sx * 0.3, 1.08, z), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.05, 0.16, 0.36), 0.01, 1, mat=0)
    # blade antennas: two on top, two underneath
    for c, h, ch, up in (((0.0, 1.73, -6.3), 0.2, 0.22, 1), ((0.0, 1.66, -8.0), 0.16, 0.18, 1), ((0.0, 0.62, -5.8), 0.2, 0.2, -1), ((0.0, -0.42, -2.2), 0.14, 0.2, -1)):
        G = Frame(c, (0, 0, 1), (0, up, 0), (1, 0, 0))
        prism(k, G, [(ch / 2, 0), (-ch / 2, 0), (-ch / 2 + 0.06, h), (ch / 2 - 0.02, h)], 0.012, mat=0)
    # air data sensor on its mast, over the right engine
    tube(k, (-0.28, 2.3, -2.3), (-0.34, 2.62, -2.2), 0.018, 10, mat=0)
    lathe(k, Frame.along((-0.34, 2.64, -2.35), (0, 0, 1)), [(0.0, 0.0), (0.03, 0.02), (0.035, 0.1), (0.03, 0.24), (0.0, 0.26)], 14, mat=0)
    # ALQ-144 infrared jammer behind the mast
    lathe(k, Yframe((0.0, 2.33, -3.72)), [(0.0, 0.0), (0.11, 0.0), (0.12, 0.05), (0.12, 0.2), (0.1, 0.24), (0.0, 0.26)], 24, mat=1)
    # steps and handholds up the right side, under the crew doors
    for c in ((-0.64, 0.2, 0.3), (-0.64, 0.2, -1.2)):
        rbox(k, Frame(c), (0.04, 0.03, 0.22), 0.01, 1, mat=0)
    for a, b in (((-0.5, 0.95, 0.6), (-0.5, 0.95, 0.3)), ((-0.53, 1.34, -0.9), (-0.53, 1.34, -1.2))):
        a, b = np.asarray(a), np.asarray(b)
        path_tube(k, [a, a + np.array([-0.035, 0, 0]), b + np.array([-0.035, 0, 0]), b], 0.012, 8, mat=0)
    # tie-down rings and jacking points
    for c in ((0.3, -0.42, -0.6), (-0.3, -0.42, -0.6), (0.28, -0.3, -3.2), (-0.28, -0.3, -3.2)):
        lathe(k, Yframe((c[0], c[1] - 0.02, c[2])), [(0.0, 0.0), (0.04, 0.0), (0.04, 0.02), (0.0, 0.02)], 12, mat=0)
    objs = [m.to_object("Sensor_Housings", [M["paint"]], node), k.to_object("Antennas_And_Fittings", [M["mech"], M["sensor_glass"], M["stores_dark"]], node, sharp_angle=50)]
    return objs
