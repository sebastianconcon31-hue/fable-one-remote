"""The helmet's geometry: shell, trim, ear domes and liner; the visor housing and the two visors; the display;
the boom microphone; the straps and cables. Each moving part is its own node pivoted where it turns."""
import math
import sys
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))
from geom import Mesh, Frame, empty, set_parent, lathe, tube, path_tube, rbox, norm, pchip, Xframe, Yframe, Zframe
from vehicle import drive
from helmet import *


def surf_normals(P):
    """Outward normals of a closed-in-phi grid of points P[k][i] (rings k, points i round)."""
    dphi = (np.roll(P, -1, axis=1) - np.roll(P, 1, axis=1))
    dk = np.gradient(P, axis=0)
    n = np.cross(dk, dphi)
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-12)
    c = P.reshape(-1, 3).mean(axis=0)
    flip = np.sign(np.einsum("kij,kij->ki", n, P - c))
    flip[flip == 0] = 1
    # one sign for the whole surface: whichever most of it has
    s = 1.0 if flip.sum() >= 0 else -1.0
    return n * s


def shell_rings(n_phi=96, n_rings=40):
    """The outer shell as rings from the lower edge up to the crown, each ring a loop round the head."""
    phis = [2 * math.pi * i / n_phi for i in range(n_phi)]
    rings = []
    for k in range(n_rings + 1):
        t = k / n_rings
        f = math.sin(t * math.pi / 2 * 0.996) if t > 0 else 0.0  # closely spaced where the walls round over into the crown
        ring = []
        for phi in phis:
            ye = rim_y(phi)
            ring.append(shell_point(phi, ye + (Y_TOP - ye) * f))
        rings.append(ring)
    return np.array(rings)


def shell(M, parent, rings=None):
    rings = shell_rings() if rings is None else rings
    n = surf_normals(rings)
    inner = rings - n * WALL
    m = Mesh()
    ido = m.grid([list(r) for r in rings], closed=True, mat=0, orient=False)
    idi = m.grid([list(r) for r in inner], closed=True, mat=1, orient=False)
    N = rings.shape[1]
    for j in range(N):
        k = (j + 1) % N
        m.face((ido[0][j], ido[0][k], idi[0][k], idi[0][j]), 2)
    m.cap(ido[-1], 0, center=(0, rings[-1][:, 1].mean(), 0))
    m.cap(idi[-1], 1, center=(0, inner[-1][:, 1].mean(), 0), flip=True)
    o = m.to_object("Shell", [M["shell"], M["shell_inner"], M["shell_inner"]], None, normals="recalc", sharp_angle=50)
    set_parent(o, parent)
    return o, rings, n


def rim_trim(M, parent, rings, normals):
    """The rolled black edge round the shell's lower rim."""
    N = rings.shape[1]
    loops = []
    for i in range(N):
        p = rings[0][i]
        nrm = normals[0][i]
        out = norm(np.array([nrm[0], 0, nrm[2]]))
        mid = p - out * (WALL / 2)
        w, up, dn = 0.0052, 0.011, 0.004
        prof = [(-w, up), (w, up), (w + 0.0006, 0.0), (w, -dn), (w * 0.4, -dn - 0.001), (-w * 0.4, -dn - 0.001), (-w, -dn), (-w - 0.0006, 0.0)]
        loops.append([mid + out * a + np.array([0, 1, 0]) * b for a, b in prof])
    m = Mesh()
    m.grid(loops + [loops[0]], closed=True, mat=0, orient=False)  # the last ring is the first again: round the whole head
    o = m.to_object("Shell_Trim", [M["rubber"]], None, normals="recalc")
    set_parent(o, parent)
    return o


def ear_domes(M, parent):
    """Each ear's dome, with the ring that stands round it, and the earcup under it."""
    out = []
    for side, sx in (("Left", 1), ("Right", -1)):
        F = Xframe((0.0, -0.004, -0.004), sx)
        prof = [(0.0015, 0.1205), (0.016, 0.1203), (0.028, 0.1190), (0.036, 0.1168), (0.0395, 0.1148), (0.0440, 0.1148), (0.0462, 0.1125), (0.0472, 0.1080), (0.0472, 0.0900), (0.0, 0.0900)]
        m = Mesh()
        f0 = len(m.f)
        lathe(m, F, [(r, x) for r, x in prof], 40, mat=0, caps=False)
        o = m.to_object(f"Ear_Dome_{side}", [M["shell"]], None, normals="recalc", sharp_angle=50)
        set_parent(o, parent)
        out.append(o)
    return out


# ---- helpers -------------------------------------------------------------------------------------------------------
def spline(pts, n=40):
    """A smooth (Catmull-Rom) curve through the points: n samples per span."""
    P = [np.asarray(p, float) for p in pts]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return out


def resample(pts, step):
    """Points along a polyline `step` apart."""
    pts = [np.asarray(p, float) for p in pts]
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        d = np.linalg.norm(b - a)
        while acc + step <= d + 1e-12:
            acc += step
            out.append(a + (b - a) * (acc / d))
        acc -= d
    if np.linalg.norm(out[-1] - pts[-1]) > step * 0.3:
        out.append(pts[-1])
    return out


def corrugated_tube(m, pts, r, pitch=0.0035, depth=0.14, n=10, mat=0, caps=True):
    """A flexible boom's ribbed tube along a path."""
    P = resample(pts, pitch / 4)
    rings = []
    prev_x = None
    for i, p in enumerate(P):
        t = norm(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        up = prev_x if prev_x is not None else ((0, 1, 0) if abs(t[1]) < 0.9 else (1, 0, 0))
        x = norm(np.cross(up, t)) if prev_x is None else norm(prev_x - t * np.dot(prev_x, t))
        y = np.cross(t, x)
        prev_x = x
        rr = r * (1 + depth * math.cos(2 * math.pi * i / 4))  # four rings to the pitch
        rings.append([p + (x * math.cos(2 * math.pi * j / n) + y * math.sin(2 * math.pi * j / n)) * rr for j in range(n)])
    ids = m.grid(rings, closed=True, mat=mat, orient=False)
    if caps:
        m.cap(ids[0], mat, flip=True)
        m.cap(ids[-1], mat)
    return ids


def strap(m, pts, width, thick, out_fn, mat=0, step=0.004, caps=True):
    """Webbing along a path: a flat strip lying against the head (out_fn(point) -> the way it faces)."""
    P = resample(spline(pts, 8), step)
    rings = []
    for i, p in enumerate(P):
        t = norm(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        o = norm(np.asarray(out_fn(p), float))
        o = norm(o - t * np.dot(o, t))
        s = np.cross(t, o)
        w, h = width / 2, thick / 2
        rings.append([p + s * w + o * h, p - s * w + o * h, p - s * w - o * h, p + s * w - o * h])
    ids = m.grid(rings, closed=True, mat=mat, orient=False)
    if caps:
        m.cap(ids[0], mat, flip=True)
        m.cap(ids[-1], mat)
    return ids


def solid_sheet(m, outer, inner, mats=(0, 0, 0)):
    """A closed sheet of thickness from two matching grids of points (rings i, points j)."""
    ido = m.grid([list(r) for r in outer], closed=False, mat=mats[0], orient=False)
    idi = m.grid([list(r) for r in inner], closed=False, mat=mats[1], orient=False)
    R, Pn = len(outer), len(outer[0])
    for j in range(Pn - 1):  # the two ends of the sweep
        m.face((ido[0][j], ido[0][j + 1], idi[0][j + 1], idi[0][j]), mats[2])
        m.face((ido[-1][j], ido[-1][j + 1], idi[-1][j + 1], idi[-1][j]), mats[2])
    for i in range(R - 1):  # the two edges along it
        m.face((ido[i][0], ido[i + 1][0], idi[i + 1][0], idi[i][0]), mats[2])
        m.face((ido[i][Pn - 1], ido[i + 1][Pn - 1], idi[i + 1][Pn - 1], idi[i][Pn - 1]), mats[2])


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sphere_pt(R, beta, alpha):
    """A point on the sphere of radius R about the pivot: beta across (+ toward the left), alpha up from straight ahead."""
    return PIV + R * np.array([math.sin(beta), math.cos(beta) * math.sin(alpha), math.cos(beta) * math.cos(alpha)])


# ---- the visor housing, the visors ---------------------------------------------------------------------------------
HOOD_HALF_X = 0.1000
STOW = math.radians(30)  # how far the visors turn up to stow


def hood_lip(beta):
    """The housing's lower edge (alpha, radians) across the front."""
    b = abs(math.degrees(beta))
    return math.radians(float(pchip([0, 20, 35, 43.8], [12, 10, 2, -12])(min(b, 43.8))))


def visor_housing(M, parent):
    m = Mesh()
    bm = math.asin(HOOD_HALF_X / R_HOOD)
    rings_o, rings_i = [], []
    nb, na = 26, 20
    for i in range(nb + 1):
        beta = -bm + 2 * bm * i / nb
        a0 = hood_lip(beta)
        ahi = math.radians(51 - 15 * (beta / bm) ** 2)  # the top edge rounds over toward the sides, like the dome
        ro, ri = [], []
        for j in range(na + 1):
            a = a0 + (ahi - a0) * j / na
            ro.append(sphere_pt(R_HOOD, beta, a))
            ri.append(sphere_pt(R_HOOD - 0.0035, beta, a))
        rings_o.append(ro)
        rings_i.append(ri)
    solid_sheet(m, rings_o, rings_i, (0, 1, 0))
    o = m.to_object("Visor_Housing", [M["plastic"], M["shell_inner"]], None, normals="recalc", sharp_angle=60)
    set_parent(o, parent)
    return o


def visor_low(beta, right_cut):
    """A visor's lower edge (alpha, radians): the nose-high sweep across the front and the bit cut away from the
    bottom of the right side for the display."""
    b = abs(math.degrees(beta))
    a = float(pchip([0, 12, 30, 40, 50], [-24, -23, -12, -1, 8])(min(b, 50)))
    if right_cut and beta < 0:
        w = smoothstep(-47.0, -41.0, math.degrees(beta)) * (1 - smoothstep(-20.0, -13.0, math.degrees(beta)))
        a = a + (12.0 - a) * w if a < 12.0 else a
    return math.radians(a)


def visor(M, parent, name, R, mat, right_cut=True):
    node = empty(name, tuple(PIV), parent)
    drive(node, f"a visor: swings up into the housing about local X; + raises it (to {math.degrees(STOW):.0f} degrees)", control="hinge", axis=[-1, 0, 0], limits=[0, STOW], group="Visors")
    m = Mesh()
    bm = math.asin(VISOR_HALF_X / R)
    rings_o, rings_i = [], []
    nb, na = 28, 18
    for i in range(nb + 1):
        beta = -bm + 2 * bm * i / nb
        a0 = visor_low(beta, right_cut)
        ahi = math.radians(18 - 10 * (beta / bm) ** 2)  # and the visors' tops follow, so they stow under it
        ro, ri = [], []
        for j in range(na + 1):
            a = a0 + (ahi - a0) * j / na
            ro.append(sphere_pt(R, beta, a))
            ri.append(sphere_pt(R - VISOR_T, beta, a))
        rings_o.append(ro)
        rings_i.append(ri)
    solid_sheet(m, rings_o, rings_i, (0, 0, 0))
    o = m.to_object(name + "_Sheet", [M[mat]], None, normals="recalc")
    set_parent(o, node)
    return node


# ---- the helmet display unit ---------------------------------------------------------------------------------------
GLASS_N = norm(np.array([-1.0, 0.0, -1.0]))  # the combiner's normal on the eye's side: it turns the beam arriving along +X back along -Z
GLASS_A, GLASS_H = 0.0165, 0.0135  # the combiner glass' half axes in its own plane (x', y)
STOW_HDU = math.radians(38)


def glass_frame():
    """A frame on the combiner: Z toward the eye along its normal, X across it (horizontal), Y up."""
    z = GLASS_N
    x = norm(np.cross((0, 1, 0), z))
    y = np.cross(z, x)
    return Frame(COMBINER, x, y, z)


def hdu(M, parent):
    node = empty("HDU", tuple(HDU_PIVOT), parent)
    node["role"] = "helmet display unit: the CRT, relay optics and combiner, clipped to the adapter block on the right ear dome"
    body = Mesh()
    # the CRT module above the ear, along Z, with its yoke at the back
    prof = [(0.0, 0.0), (0.0235, 0.0), (0.0245, 0.002), (0.0245, 0.0275), (0.0225, 0.0285), (0.0215, 0.030), (0.0205, 0.042), (0.0205, 0.070), (0.0228, 0.072), (0.0228, 0.084), (0.0, 0.084)]
    lathe(body, Zframe((-0.1195, 0.066, -0.050)), prof, 40, mat=0, caps=False)
    for k in range(7):  # cooling fins round the yoke
        z0 = -0.048 + 0.0036 * k
        lathe(body, Zframe((-0.1195, 0.066, z0)), [(0.0235, 0.0), (0.0262, 0.0004), (0.0262, 0.0016), (0.0235, 0.002)], 40, mat=0, caps=False)
    lathe(body, Zframe((-0.1195, 0.066, -0.0515)), [(0.0, 0.0), (0.0105, 0.0), (0.0105, 0.004), (0.0, 0.004)], 24, mat=1, caps=False)  # the cable socket
    # the relay: an elbow down and forward along the cheek, a collar, then the short stub in front of the eye
    relay = [(-0.1195, 0.066, 0.032), (-0.113, 0.055, 0.046), (-0.098, 0.040, 0.060), (-0.089, 0.031, 0.078), (-0.088, 0.030, 0.108)]
    path_tube(body, spline(relay, 8), 0.0098, 14, mat=0, caps=True)
    for z in (0.064, 0.100):
        lathe(body, Zframe((-0.0885, 0.030, z)), [(0.0098, 0.0), (0.0120, 0.0), (0.0120, 0.006), (0.0098, 0.006)], 24, mat=0, caps=False)
    path_tube(body, [(-0.088, 0.030, 0.1085), (-0.062, 0.0285, 0.1135), (-0.048, 0.027, 0.1175)], 0.0078, 12, mat=0, caps=True)
    # the combiner's housing: a bezel round the glass and a body behind it
    G = glass_frame()
    lathe(body, G, [(0.0140, -0.004), (0.0192, -0.004), (0.0192, 0.0035), (0.0152, 0.0035), (0.0152, 0.0), (0.0140, 0.0)], 40, mat=0, caps=False)
    Fb = Frame(COMBINER - GLASS_N * 0.010, G.x, G.y, G.z)
    rbox(body, Fb, (0.037, 0.030, 0.012), 0.005, 3, mat=0)
    # the adapter block on the dome and the mount's clamp are part of the helmet; the HDU carries the clamp's hinge pin
    lathe(body, Xframe(HDU_PIVOT + np.array([-0.0005, 0, 0]), -1), [(0.0, 0.0), (0.0075, 0.0), (0.0075, 0.0045), (0.0, 0.0045)], 20, mat=1, caps=False)
    o = body.to_object("HDU_Body", [M["hdu"], M["metal"]], None, normals="recalc", sharp_angle=55)
    set_parent(o, node)
    # the glass and the display
    gm = Mesh()
    ring = [G.p((GLASS_A * math.cos(a), GLASS_H * math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    ids = gm.verts(ring)
    gm.face(ids)
    go = gm.to_object("HDU_Combiner", [M["combiner"]], None, smooth=False, per_face=lambda p: COMBINER + GLASS_N * 1.0)
    set_parent(go, node)
    # the display: it lies on the glass and subtends exactly the published field of view from the eye. Its width and
    # height are found by bisection, since the glass is tilted and the eye is off its centre
    def corners(w, h):
        return [G.p((-w / 2, h / 2, 0.0004)), G.p((w / 2, h / 2, 0.0004)), G.p((w / 2, -h / 2, 0.0004)), G.p((-w / 2, -h / 2, 0.0004))]

    def subtended(a, b):
        va, vb = np.asarray(a) - EYE_R, np.asarray(b) - EYE_R
        return math.degrees(math.acos(float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))))

    def solve(want, which):
        lo, hi = 0.002, 0.060
        for _ in range(40):
            mid = (lo + hi) / 2
            w, h = (mid, 0.01) if which == "w" else (0.01, mid)
            q = corners(w, h)
            ang = subtended((np.asarray(q[0]) + np.asarray(q[3])) / 2, (np.asarray(q[1]) + np.asarray(q[2])) / 2) if which == "w" else subtended((np.asarray(q[0]) + np.asarray(q[1])) / 2, (np.asarray(q[3]) + np.asarray(q[2])) / 2)
            lo, hi = (mid, hi) if ang < want else (lo, mid)
        return (lo + hi) / 2

    w, h = solve(SPEC["fovH"], "w"), solve(SPEC["fovV"], "h")
    sm = Mesh()
    sm.face(sm.verts(corners(w, h)))
    so = sm.to_object("HDU_Screen", [M["display"]], None, smooth=False, per_face=lambda p: COMBINER + GLASS_N * 1.0)
    # UVs: the image's 4:3 frame over the quad, top left to bottom right
    me = so.data
    uv = me.uv_layers.new(name="UVMap")
    corners = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (0, 0)}
    for li, loop in enumerate(me.loops):
        uv.data[li].uv = corners[loop.vertex_index % 4]
    so["role"] = "display"
    so["fov"] = [SPEC["fovH"], SPEC["fovV"]]
    so["aspect"] = 4 / 3
    so["eyeRelief"] = EYE_RELIEF
    so["note"] = "an image plane: from Eye_Right it subtends 40 x 30 degrees. For a first-person view, render the display into this material and look through it from Eye_Right."
    set_parent(so, node)
    return node, o, go, so


# ---- the microphone ----------------------------------------------------------------------------------------------------
MIC_DIR = norm(np.array([-0.010, 0.001, -0.008]))  # from the capsule's face toward the lips
MIC_TRAVEL = math.radians(15)  # the clear travel the fit check finds before the boom meets the visor


def mic_mount(M, parent):
    m = Mesh()
    rbox(m, Xframe(MIC_PIVOT + np.array([-0.0035, 0, 0]), 1), (0.030, 0.026, 0.008), 0.004, 3, mat=0)
    for dz in (-0.009, 0.009):
        lathe(m, Xframe(MIC_PIVOT + np.array([-0.0005, 0, dz]), 1), [(0.0, 0.0), (0.0032, 0.0), (0.0032, 0.0016), (0.0, 0.0016)], 12, mat=1, caps=False)
    o = m.to_object("Mic_Mount", [M["plastic"], M["metal"]], None, normals="recalc", sharp_angle=55)
    set_parent(o, parent)
    return o


def mic(M, parent):
    node = empty("Mic_Boom", tuple(MIC_PIVOT), parent)
    drive(node, f"the boom microphone: swings on its mount about local X; + raises it away from the mouth (to {math.degrees(MIC_TRAVEL):.0f} degrees, where it meets the visor)", control="hinge", axis=[-1, 0, 0], limits=[0, MIC_TRAVEL], group="Microphone")
    end = MIC_AT - MIC_DIR * 0.016  # the capsule's back
    pts = [MIC_PIVOT + np.array([0.0, 0, 0]), (0.1275, -0.004, 0.044), (0.1225, -0.020, 0.072), (0.106, -0.037, 0.100), (0.080, -0.048, 0.119), (0.055, -0.0505, 0.1285), tuple(end)]
    m = Mesh()
    corrugated_tube(m, spline(pts, 10), 0.0036, mat=0)
    # the pivot's knuckle where the boom leaves its mount
    lathe(m, Xframe(MIC_PIVOT + np.array([0.0, 0, 0]), 1), [(0.0, 0.0), (0.0085, 0.0), (0.0085, 0.0075), (0.0, 0.0075)], 20, mat=1, caps=False)
    # the capsule: a dynamic noise-cancelling element in its case, a foam cover on its face
    F = Frame.along(MIC_AT - MIC_DIR * 0.0, MIC_DIR)
    lathe(m, Frame(MIC_AT, F.x, F.y, -MIC_DIR), [(0.0, 0.0), (0.0090, 0.0), (0.0112, 0.0030), (0.0112, 0.0140), (0.0098, 0.0165), (0.0, 0.0165)], 28, mat=1, caps=False)
    lathe(m, Frame(MIC_AT + MIC_DIR * 0.0012, F.x, F.y, -MIC_DIR), [(0.0, 0.0), (0.0088, 0.0), (0.0090, 0.0012), (0.0, 0.0018)], 28, mat=2, caps=False)  # the grille on the face
    o = m.to_object("Mic_Boom_Body", [M["rubber"], M["plastic"], M["foam"]], None, normals="recalc", sharp_angle=60)
    set_parent(o, node)
    return node


# ---- what's on the shell: the head tracker's emitters, the visor pivots ------------------------------------------------
def shell_frame(phi, y):
    """A frame on the shell's outer surface: Z out along the normal, Y up along the shell."""
    p = shell_point(phi, y)
    d = 1e-4
    dphi = shell_point(phi + d, y) - shell_point(phi - d, y)
    dy = shell_point(phi, y + d) - shell_point(phi, y - d)
    n = norm(np.cross(dy, dphi))
    if np.dot(n, p - np.array([0, 0.03, 0])) < 0:
        n = -n
    yv = norm(dy - n * np.dot(dy, n))
    return Frame(p, np.cross(yv, n), yv, n)


def emitters(M, parent):
    """The head tracker's infrared emitters: two on each side of the shell, in identical positions."""
    out = []
    for side, sx in (("Left", 1), ("Right", -1)):
        for tag, deg_, y in (("Front", 78, 0.100), ("Rear", 112, 0.094)):
            F = shell_frame(sx * math.radians(deg_), y)
            m = Mesh()
            rbox(m, Frame(F.p((0, 0, 0.0035)), F.x, F.y, F.z), (0.030, 0.020, 0.012), 0.0035, 3, mat=0)
            lens = Mesh()
            for dx in (-0.0075, 0.0075):
                lathe(lens, Frame(F.p((dx, 0, 0.0093)), F.x, F.y, F.z), [(0.0, 0.0), (0.0044, 0.0), (0.0052, 0.0015), (0.0, 0.0030)], 20, mat=0, caps=False)
            node = empty(f"IR_Emitter_{side}_{tag}", tuple(F.p((0, 0, 0.0))), parent)
            node["role"] = "head tracker emitter"
            o = m.to_object(f"IR_Emitter_{side}_{tag}_Housing", [M["plastic"]], None, normals="recalc", sharp_angle=55)
            lo = lens.to_object(f"IR_Emitter_{side}_{tag}_Lens", [M["led"]], None, normals="recalc")
            set_parent(o, node)
            set_parent(lo, node)
            out.append(node)
    return out


def pivots(M, parent):
    """The visor pivots on the shell's sides and the adapter block for the display on the right ear dome."""
    m = Mesh()
    for sx in (1, -1):
        lathe(m, Xframe(PIV + np.array([sx * 0.0985, 0, 0]), sx), [(0.0, 0.0), (0.0155, 0.0), (0.0155, 0.0075), (0.0125, 0.0105), (0.0, 0.0105)], 28, mat=0, caps=False)
        lathe(m, Xframe(PIV + np.array([sx * 0.1085, 0, 0]), sx), [(0.0, 0.0), (0.0052, 0.0), (0.0052, 0.0014), (0.0, 0.0014)], 12, mat=1, caps=False)
    o = m.to_object("Visor_Pivots", [M["plastic"], M["metal"]], None, normals="recalc", sharp_angle=55)
    set_parent(o, parent)
    b = Mesh()
    rbox(b, Xframe(HDU_PIVOT + np.array([0.0035, 0, 0]), -1), (0.050, 0.036, 0.011), 0.005, 3, mat=0)
    for dz in (-0.014, 0.014):
        lathe(b, Xframe(HDU_PIVOT + np.array([-0.0015, 0, dz]), -1), [(0.0, 0.0), (0.0034, 0.0), (0.0034, 0.0015), (0.0, 0.0015)], 12, mat=1, caps=False)
    ob = b.to_object("HDU_Adapter_Block", [M["plastic"], M["metal"]], None, normals="recalc", sharp_angle=55)
    set_parent(ob, parent)
    return o, ob


# ---- inside: liner, comfort pads, earcups --------------------------------------------------------------------------------
def liner(M, parent, rings, normals):
    """The energy-absorbing liner in the shell, and the comfort liner against the head."""
    out = []
    for name, off, off2, mat in (("Liner", WALL + 0.0005, WALL + 0.0155, "liner"), ("Comfort_Pad", WALL + 0.0155, WALL + 0.0195, "fabric")):
        keep = rings[1:-1]  # the liner stops a little short of the lower edge and the crown
        nk = normals[1:-1]
        a = keep - nk * off
        b = keep - nk * off2
        m = Mesh()
        ia = m.grid([list(r) for r in a], closed=True, mat=0, orient=False)
        ib = m.grid([list(r) for r in b], closed=True, mat=0, orient=False)
        N = rings.shape[1]
        for j in range(N):
            k = (j + 1) % N
            m.face((ia[0][j], ia[0][k], ib[0][k], ib[0][j]), 0)
        m.cap(ia[-1], 0, center=a[-1].mean(axis=0))
        m.cap(ib[-1], 0, center=b[-1].mean(axis=0), flip=True)
        o = m.to_object(name, [M[mat]], None, normals="recalc")
        set_parent(o, parent)
        out.append(o)
    return out


def earcups(M, parent):
    out = []
    for side, sx in (("Left", 1), ("Right", -1)):
        m = Mesh()
        c = np.array([sx * 0.0, -0.004, -0.004])
        F = Xframe(c, sx)
        # the cup (headphone housing) and its foam seal against the head
        lathe(m, F, [(0.0, 0.0950), (0.0285, 0.0950), (0.0300, 0.0928), (0.0300, 0.0860), (0.0275, 0.0840), (0.0, 0.0840)], 28, mat=0, caps=False)
        lathe(m, F, [(0.0205, 0.0845), (0.0290, 0.0845), (0.0335, 0.0805), (0.0352, 0.0775), (0.0345, 0.0765), (0.0300, 0.0763), (0.0205, 0.0763), (0.0207, 0.0800), (0.0205, 0.0845)], 28, mat=1, caps=False)
        o = m.to_object(f"Earcup_{side}", [M["plastic"], M["foam"]], None, normals="recalc", sharp_angle=55)
        set_parent(o, parent)
        out.append(o)
    return out


# ---- the straps and the cords -----------------------------------------------------------------------------------------------
HEAD_C = np.array([0.0, 0.0, 0.0])


def toward_out(p):
    return np.asarray(p, float) - np.array([0.0, 0.02, -0.01])


def chin_strap(M, parent):
    m = Mesh()
    for sx in (1, -1):
        pts = [(sx * 0.0985, -0.0545, 0.0), (sx * 0.0925, -0.080, 0.018), (sx * 0.074, -0.107, 0.047), (sx * 0.045, -0.126, 0.078), (sx * 0.020, -0.131, 0.091)]
        strap(m, pts, 0.0165, 0.0030, toward_out, mat=0)
    cup = Mesh()
    strap(cup, [(0.030, -0.1305, 0.087), (0.0, -0.1345, 0.0965), (-0.030, -0.1305, 0.087)], 0.034, 0.0075, lambda p: np.array([p[0] * 0.2, -1.0, 0.45]), mat=0)
    o = m.to_object("Chin_Strap", [M["fabric"]], None, normals="recalc")
    oc = cup.to_object("Chin_Cup", [M["foam"]], None, normals="recalc")
    # the quick-release buckle on the left strap, and the rings where each strap meets the shell
    b = Mesh()
    for sx in (1, -1):
        lathe(b, Xframe((sx * 0.1005, -0.0545, 0.0), sx), [(0.0, 0.0), (0.0075, 0.0), (0.0075, 0.0030), (0.0, 0.0030)], 16, mat=0, caps=False)
    rbox(b, Frame.along((0.0745, -0.1055, 0.046), (-0.55, -0.45, 0.7)), (0.026, 0.014, 0.0055), 0.002, 2, mat=0)
    ob = b.to_object("Chin_Strap_Hardware", [M["metal"]], None, normals="recalc", sharp_angle=55)
    for x in (o, oc, ob):
        set_parent(x, parent)
    return o, oc, ob


def nape(M, parent):
    m = Mesh()
    pts = [(0.0975, -0.050, -0.028), (0.090, -0.056, -0.075), (0.055, -0.060, -0.104), (0.0, -0.062, -0.112), (-0.055, -0.060, -0.104), (-0.090, -0.056, -0.075), (-0.0975, -0.050, -0.028)]
    strap(m, pts, 0.026, 0.004, lambda p: np.array([p[0], 0.0, p[2] + 0.02]), mat=0)
    o = m.to_object("Nape_Strap", [M["fabric"]], None, normals="recalc")
    set_parent(o, parent)
    return o


def cords(M, parent):
    """The comms cord and the display's cable, each ending in its plug, hanging behind the neck."""
    out = []
    for name, pts, r in (
        ("Cord_Comms", [(0.0985, -0.052, -0.020), (0.1005, -0.075, -0.050), (0.088, -0.108, -0.092), (0.070, -0.150, -0.118), (0.058, -0.205, -0.124), (0.052, -0.250, -0.120)], 0.0046),
        ("Cable_Display", [(-0.1195, 0.066, -0.0555), (-0.109, 0.050, -0.082), (-0.096, 0.010, -0.106), (-0.074, -0.052, -0.124), (-0.056, -0.110, -0.130), (-0.050, -0.170, -0.128), (-0.046, -0.222, -0.122)], 0.0036),
    ):
        m = Mesh()
        P = spline(pts, 10)
        path_tube(m, P, r, 10, mat=0, caps=True)
        end, prev = np.asarray(P[-1]), np.asarray(P[-5])
        F = Frame.along(end, end - prev)
        # the plug: a coupling ring, a barrel and a strain relief
        lathe(m, F, [(r, -0.012), (0.0072, -0.012), (0.0072, 0.006), (0.0100, 0.007), (0.0100, 0.026), (0.0092, 0.028), (0.0092, 0.034), (0.0, 0.034)], 24, mat=1, caps=False)
        o = m.to_object(name, [M["rubber"], M["metal"]], None, normals="recalc", sharp_angle=55)
        set_parent(o, parent)
        out.append(o)
    return out


def eyes(parent):
    """Where the eyes and the mouth are, for a game to put its camera and its voice."""
    for name, p, role in (("Eye_Right", EYE_R, "the right eye: the display's"), ("Eye_Left", EYE_L, "the left eye"), ("Mouth", HEAD["stomion"], "the lips: the microphone's target")):
        e = empty(name, tuple(p), parent, size=0.01)
        e["role"] = role
