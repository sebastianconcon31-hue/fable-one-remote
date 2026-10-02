"""Running gear the ground vehicles share: tyres on wheels, and track systems
(road wheels, sprockets, idlers, return rollers and the track itself).

A track is a node (Track_Left / Track_Right) holding one link mesh used by
every link node (Track_Left_Link_000 ...). The node's extras carry the
loop the links ride round (`path`, flattened z, y pairs in the node's own
frame), the link `pitch` and how many `links` there are, so a game or the
viewer can move the links round the loop as the vehicle drives: link i sits
on the chord between pins at i*pitch + travel and (i+1)*pitch + travel.

Model axes as everywhere here: metres, +Y up, +Z forward, +X left."""
import math
import numpy as np

from geom import Mesh, Frame, lathe, tube, rbox, prism, path_tube, fillet_path, norm, empty, set_parent, Xframe, Zframe, Yframe
from vehicle import drive, place

deg = math.pi / 180


# ---- 2D outlines -------------------------------------------------------------------------------------------------------------
def inset(poly, d, miter=3.0):
    """Offset a closed 2D polygon inward by d (either winding); corners mitred, limited to `miter` times d."""
    P = [np.asarray(p, float) for p in poly]
    n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    s = 1.0 if area > 0 else -1.0  # CCW: inward is to the left of each edge
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1, e2 = norm(b - a), norm(c - b)
        n1 = s * np.array([-e1[1], e1[0]])
        n2 = s * np.array([-e2[1], e2[0]])
        if np.linalg.norm(b - a) < 1e-9:
            n1 = n2
        if np.linalg.norm(c - b) < 1e-9:
            n2 = n1
        m = norm(n1 + n2)
        cosh = max(np.dot(m, n1), 1.0 / miter)
        out.append(tuple(b + m * d / cosh))
    return out


def loft(m, F, sections, radii=0.0, bevel=0.0, arc_n=2, mat=0, caps=True):
    """A solid lofted through 2D outlines along the frame's Z: sections = [(z, outline in frame XY)], all with the
    same number of corners. Corners rounded to `radii`; both ends bevelled by `bevel` (inset end rings)."""
    rings2d = []
    for z, poly in sections:
        rr = radii if isinstance(radii, (list, tuple)) else [radii] * len(poly)
        loop = fillet_path(poly, rr, arc_n=arc_n, seg_n=0, closed=True) if max(rr) > 0 else [tuple(p) for p in poly]
        rings2d.append((z, loop))
    if bevel > 0:
        z0, l0 = rings2d[0]
        z1, l1 = rings2d[-1]
        dz = 1 if z1 > z0 else -1
        rings2d = [(z0, inset(l0, bevel))] + [(z0 + dz * bevel, l0)] + rings2d[1:-1] + [(z1 - dz * bevel, l1), (z1, inset(l1, bevel))]
    rings = [[F.p((x, y, z)) for x, y in loop] for z, loop in rings2d]
    f0 = len(m.f)
    ids = m.grid(rings, closed=True, mat=mat)
    if caps:
        # cap winding: face away from the solid, i.e. along -Z at the start and +Z at the end
        m.cap(ids[0], mat)
        m.cap(ids[-1], mat)
        for k, (ring, sign) in enumerate(((ids[0], -1), (ids[-1], 1))):
            fi = len(m.f) - 2 + k
            vs = [np.asarray(m.v[j]) for j in m.f[fi]]
            nrm = np.zeros(3)
            for a, b in zip(vs, vs[1:] + vs[:1]):
                nrm += np.cross(a, b)
            zdir = F.z * (1 if rings2d[-1][0] > rings2d[0][0] else -1) * sign
            if np.dot(nrm, zdir) < 0:
                m.f[fi] = m.f[fi][::-1]
    return ids


def slab(m, F, poly, depth, bevel=0.008, radii=0.0, mat=0):
    """A plate: a 2D outline (frame XY) extruded along Z by depth (centred), its edges bevelled."""
    return loft(m, F, [(-depth / 2, poly), (depth / 2, poly)], radii, min(bevel, depth * 0.45), mat=mat)


def bolt(m, F, r=0.012, h=0.008, n=6, mat=0):
    """A hex bolt head standing on the frame's XY plane, along +Z."""
    lathe(m, F, [(0.0, 0.0), (r, 0.0), (r, h * 0.8), (r * 0.8, h), (0.0, h)], n, mat=mat)


def bolt_row(m, F, a, b, pitch, r=0.012, h=0.008, mat=0):
    """Bolts in a line from a to b (frame-local XY points) on the frame's plane."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = np.linalg.norm(b - a)
    k = max(1, int(round(L / pitch)))
    for i in range(k + 1):
        p = a + (b - a) * i / k
        bolt(m, Frame(F.p((p[0], p[1], 0)), F.x, F.y, F.z), r, h, mat=mat)


# ---- tyres --------------------------------------------------------------------------------------------------------------------
def tyre(m, c, sx, R, W, rim_r, blocks=34, block=(0.42, 0.04, 0.17), chevron=25, rows=2, shoulder=0.2, mat_tyre=0, mat_rim=1,
         studs=10, stud_r=None, disc="dished", beadlock=0, ctis=True):
    """A radial off-road tyre on a steel wheel, its axis along X (sx: +1 outboard to +X).

    R outer radius at the tread blocks' tops, W section width, rim_r the rim's radius (20 in = 0.254).
    blocks: lugs round the tyre per row; block = (length across as a fraction of W, height, width as a fraction of
    R... in metres for the last two); chevron: the lugs' angle; rows: 2 staggered (chevron) or 3 (centre row too)."""
    F = Xframe(c, sx)
    h = block[1]
    Rc = R - h  # the crown under the lugs
    w = W / 2
    sw = Rc - rim_r  # sidewall height
    prof = [(rim_r + 0.015, -w * 0.8), (rim_r + 0.035, -w * 0.88), (rim_r + sw * 0.45, -w * 0.99), (rim_r + sw * 0.75, -w),
            (Rc - sw * 0.1, -w * 0.96), (Rc - 0.008, -w * 0.86), (Rc, -w * 0.7),
            (Rc, w * 0.7), (Rc - 0.008, w * 0.86), (Rc - sw * 0.1, w * 0.96), (rim_r + sw * 0.75, w), (rim_r + sw * 0.45, w * 0.99),
            (rim_r + 0.035, w * 0.88), (rim_r + 0.015, w * 0.8)]
    lathe(m, F, prof, 64, mat=mat_tyre)
    bl = block[0] * W
    bw = block[2]
    for k in range(blocks):
        for half in ((-1, 1) if rows == 2 else (-1, 0, 1)):
            a = 2 * math.pi * (k + (0.5 if half > 0 else 0)) / blocks
            radial = np.array([math.cos(a), math.sin(a), 0.0])
            tang = np.array([-math.sin(a), math.cos(a), 0.0])
            if half == 0:
                o = radial * (Rc + h / 2 - 0.006)
                G = Frame(F.p(o), F.d(tang), F.d(radial), F.d(np.array([0.0, 0.0, 1.0])))
                rbox(m, G, (bw * 0.9, h, bl * 0.5), 0.006, 1, mat=mat_tyre)
                continue
            axial = np.array([0.0, 0.0, half * 1.0])
            ax_dir = norm(axial * math.cos(chevron * deg) + tang * math.sin(chevron * deg))
            o = radial * (Rc + h / 2 - 0.006) + axial * (w - bl / 2 * math.cos(chevron * deg) - bw / 2 * math.sin(chevron * deg) - 0.004)
            G = Frame(F.p(o), F.d(ax_dir), F.d(radial), F.d(np.cross(ax_dir, radial)))
            rbox(m, G, (bl, h + 0.008, bw), 0.007, 1, mat=mat_tyre)
    # wheel: rim flanges and barrel, the disc, hub and studs
    rw = w * 0.72
    lathe(m, F, [(rim_r - 0.015, -rw), (rim_r + 0.015, -rw - 0.01), (rim_r + 0.02, -rw), (rim_r + 0.003, -rw + 0.02), (rim_r - 0.003, rw - 0.02),
                 (rim_r + 0.02, rw), (rim_r + 0.015, rw + 0.01), (rim_r - 0.015, rw)], 48, mat=mat_rim)
    if disc == "dished":
        lathe(m, F, [(rim_r - 0.003, 0.0), (rim_r * 0.8, rw * 0.35), (rim_r * 0.48, rw * 0.42), (rim_r * 0.4, rw * 0.48), (0.0, rw * 0.48)], 40, mat=mat_rim)
    else:  # flat disc set outboard (military split rims)
        lathe(m, F, [(rim_r - 0.003, rw * 0.5), (rim_r * 0.75, rw * 0.62), (rim_r * 0.45, rw * 0.62), (rim_r * 0.4, rw * 0.66), (0.0, rw * 0.66)], 40, mat=mat_rim)
    z_face = rw * (0.48 if disc == "dished" else 0.66)
    hub_r = rim_r * 0.28
    lathe(m, F, [(0.0, z_face), (hub_r, z_face), (hub_r * 1.05, z_face + 0.06), (hub_r * 0.85, z_face + 0.08), (0.0, z_face + 0.085)], 24, mat=mat_rim)
    sr = stud_r or rim_r * 0.58
    for j in range(studs):
        a = 2 * math.pi * j / studs
        p = np.array([math.cos(a) * sr, math.sin(a) * sr, z_face])
        lathe(m, Frame(F.p(p), F.x, F.y, F.z), [(0.0, 0.0), (0.02, 0.0), (0.02, 0.022), (0.011, 0.032), (0.0, 0.032)], 6, mat=mat_rim)
    for j in range(6):
        a = 2 * math.pi * (j + 0.5) / 6
        p = np.array([math.cos(a) * rim_r * 0.78, math.sin(a) * rim_r * 0.78, z_face - 0.012])
        lathe(m, Frame(F.p(p), F.x, F.y, F.z), [(0.0, -0.01), (rim_r * 0.14, -0.01), (rim_r * 0.14, 0.0), (0.0, 0.0)], 14, mat=mat_rim)
    for j in range(beadlock):  # the bolt ring of a two-piece beadlock rim
        a = 2 * math.pi * j / beadlock
        p = np.array([math.cos(a) * (rim_r - 0.012), math.sin(a) * (rim_r - 0.012), rw + 0.004])
        lathe(m, Frame(F.p(p), F.x, F.y, F.z), [(0.0, 0.0), (0.013, 0.0), (0.013, 0.012), (0.0, 0.016)], 6, mat=mat_rim)
    if ctis:
        tube(m, F.p((0.0, 0.0, z_face + 0.085)), F.p((rim_r * 0.3, rim_r * 0.45, z_face + 0.1)), 0.008, 6, mat=mat_rim)


# ---- tracks ----------------------------------------------------------------------------------------------------------------
def circle_hull(circles, n=160):
    """The loop a belt makes round circles [(z, y, r)]: their convex hull, clockwise seen from the left
    (forward along the top run, rearward along the bottom), as (z, y) points."""
    pts = []
    for z, y, r in circles:
        for k in range(n):
            a = 2 * math.pi * k / n
            pts.append((z + r * math.cos(a), y + r * math.sin(a)))
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    ccw = lower[:-1] + upper[:-1]
    return [np.array(p) for p in ccw[::-1]]


def resample(path, step):
    """A closed polyline resampled to about `step` spacing (keeps corners round)."""
    P = path + [path[0]]
    seg = [np.linalg.norm(b - a) for a, b in zip(P, P[1:])]
    L = sum(seg)
    n = max(8, int(round(L / step)))
    return [point_at(P, seg, L, L * i / n) for i in range(n)], L


def point_at(P, seg, L, s):
    s = s % L
    for a, b, l in zip(P, P[1:], seg):
        if s <= l:
            return a + (b - a) * (s / l if l > 0 else 0)
        s -= l
    return P[-1]


def sag(path, supports, depth):
    """Let the top run hang between supports: supports are the z values it rests on (rollers, sprocket, idler)."""
    zs = sorted(supports)
    top = max(p[1] for p in path)
    out = []
    for p in path:
        q = p.copy()
        if p[1] > top - 0.06 and zs[0] < p[0] < zs[-1]:
            for a, b in zip(zs, zs[1:]):
                if a <= p[0] <= b:
                    u = (p[0] - a) / (b - a)
                    q[1] -= depth * 4 * u * (1 - u) * min(1.0, (b - a) / 1.2)
        out.append(q)
    return out


def track(M, parent, side, x, loop, pitch, link, mats, travel=0.0):
    """Lay a track round `loop` ((z, y) points, clockwise from the left): one shared link mesh made by link(m, pitch)
    in link space (X across, Y out of the loop, Z along it, pins at Z = +-pitch/2), one node per link."""
    import bpy
    P = loop + [loop[0]]
    seg = [float(np.linalg.norm(b - a)) for a, b in zip(P, P[1:])]
    L = sum(seg)
    n = int(round(L / pitch))
    p = L / n
    node = empty(f"Track_{side}", (x, 0, 0), parent)
    flat = []
    for q in loop:
        flat += [round(float(q[0]), 4), round(float(q[1]), 4)]
    drive(node, "the track: its links ride round `path` (z, y pairs in this node's frame, clockwise seen from the left: "
          "forward along the top run). Link i sits on the chord between the pins at i*pitch + travel and (i+1)*pitch + travel, "
          "where travel is how far the vehicle has driven forward.", control="track", path=flat, pitch=round(p, 5), links=n, length=round(L, 4))
    m = Mesh()
    link(m, p)
    proto = m.to_object(f"Track_{side}_Link_000", mats, None, sharp_angle=40)
    me = proto.data
    me.name = f"Track_Link_{side}"
    objs = [proto]
    for i in range(n):
        o = proto if i == 0 else bpy.data.objects.new(f"Track_{side}_Link_{i:03d}", me)
        if i:
            bpy.context.scene.collection.objects.link(o)
        a = point_at(P, seg, L, i * p + travel)
        b = point_at(P, seg, L, (i + 1) * p + travel)
        t = norm(b - a)
        c = (a + b) / 2
        nrm = np.array([-t[1], t[0]])  # out of the loop, for a clockwise loop in (z, y): left of the direction of travel
        o.parent = node
        o.matrix_parent_inverse = node.matrix_world.inverted()
        place(o, (x, c[1], c[0]), (1.0, 0.0, 0.0), (0.0, nrm[1], nrm[0]), (0.0, t[1], t[0]))
        objs.append(o) if i else None
    return node, objs, n, p, L


def link_double_pin(m, W, p, t_in, t_out, guide_h, guide_w=0.07, pad=True, mat_steel=0, mat_rubber=1):
    """A double-pin track shoe (Abrams T158, Bradley T157): binocular body round its two pins, rubber pads outside,
    rubber road-wheel paths inside, end connectors at both ends and a centre guide at the joint."""
    w = W / 2
    e = 0.03  # pin offset in from the shoe's ends
    body = p - 2 * 0.012
    # the shoe body, binocular in section: two pin bosses joined by the web
    for zc in (-(p / 2 - e), p / 2 - e):
        tube(m, (-w + 0.07, 0.0, zc), (w - 0.07, 0.0, zc), 0.028, 8, mat=mat_steel)
    rbox(m, Zframe((0.0, 0.0, 0.0)), (W - 0.14, 0.036, body - 2 * e), 0.008, 1, mat=mat_steel)
    # rubber road-wheel paths on the inside, either side of the centre
    for sx in (1, -1):
        rbox(m, Zframe((sx * w * 0.42, -t_in + 0.012, 0.0)), (w * 0.5, 0.024, body - 0.01), 0.006, 1, mat=mat_rubber)
    if pad:  # replaceable rubber pads on the outside, a split down the middle
        for sx in (1, -1):
            rbox(m, Zframe((sx * w * 0.47, t_out - 0.025, 0.0)), (w * 0.82, 0.05, body - 0.02), 0.012, 1, mat=mat_rubber)
    # end connectors across the joint (half of each sits on this shoe), with their wedge bolts
    for sx in (1, -1):
        rbox(m, Zframe((sx * (w - 0.035), 0.0, p / 2)), (0.07, 0.07, 2 * e + 0.05), 0.012, 1, mat=mat_steel)
        tube(m, (sx * (w - 0.07), -0.03, p / 2), (sx * (w - 0.07), -0.05, p / 2), 0.012, 6, mat=mat_steel)
    # the centre guide, standing in towards the wheels at the joint
    prism(m, Frame((0.0, -t_in - guide_h / 2 + 0.02, p / 2), (0, 0, 1), (0, -1, 0), (1, 0, 0)),
          [(-0.05, -guide_h / 2), (0.05, -guide_h / 2), (0.025, guide_h / 2), (-0.025, guide_h / 2)], guide_w, mat=mat_steel)
    rbox(m, Zframe((0.0, -0.01, p / 2)), (guide_w + 0.02, 0.06, 2 * e + 0.04), 0.01, 1, mat=mat_steel)


def link_single_pin(m, W, p, t_in, t_out, guide_h, mat_steel=0):
    """A single-pin cast steel link (T-72 RMSh): a cast plate with grousers, the pin knuckles interleaving along both
    ends, and a guide horn on every link."""
    w = W / 2
    # cast plate
    rbox(m, Zframe((0.0, 0.002, 0.0)), (W - 0.02, 0.03, p - 0.035), 0.008, 1, mat=mat_steel)
    # knuckles: 5 at the front end, 4 at the back, interleaving with the next link's
    for k in range(5):
        x = -w + 0.04 + k * (W - 0.08) / 4
        tube(m, (x - 0.035, 0.0, p / 2 - 0.004), (x + 0.035, 0.0, p / 2 - 0.004), 0.021, 10, mat=mat_steel)
    for k in range(4):
        x = -w + 0.04 + (k + 0.5) * (W - 0.08) / 4
        tube(m, (x - 0.035, 0.0, -p / 2 + 0.004), (x + 0.035, 0.0, -p / 2 + 0.004), 0.021, 10, mat=mat_steel)
    # the pin through it, its head showing on the inner side
    tube(m, (-w, 0.0, p / 2 - 0.004), (w, 0.0, p / 2 - 0.004), 0.011, 8, mat=mat_steel)
    # grousers outside
    for zc in (-p * 0.22, p * 0.22):
        rbox(m, Zframe((0.0, t_out - 0.016, zc)), (W - 0.06, 0.032, 0.024), 0.006, 1, mat=mat_steel)
    rbox(m, Zframe((0.0, t_out - 0.024, 0.0)), (0.12, 0.03, p * 0.4), 0.008, 1, mat=mat_steel)
    # lightening pockets in the inner face, the wheel path, and the guide horn
    for sx in (1, -1):
        rbox(m, Zframe((sx * w * 0.5, -t_in + 0.006, 0.0)), (w * 0.62, 0.012, p - 0.05), 0.004, 1, mat=mat_steel)
    prism(m, Frame((0.0, -t_in - guide_h / 2 + 0.01, -0.005), (0, 0, 1), (0, -1, 0), (1, 0, 0)),
          [(-0.045, -guide_h / 2), (0.045, -guide_h / 2), (0.02, guide_h / 2), (-0.02, guide_h / 2)], 0.045, mat=mat_steel)


# ---- wheels a track runs on ------------------------------------------------------------------------------------------------
def road_wheel(m, c, r, w, gap, sx=1, spokes=0, holes=6, mat_wheel=0, mat_rubber=1, tyre_t=0.05, hub_bolts=8):
    """A dual road wheel: two discs with rubber tyres either side of the guide horns, on one hub (axis along X).
    gap is the space between the two halves; w each half's width."""
    F = Xframe(c, sx)
    for half in (-1, 1):
        z0 = half * gap / 2
        z1 = half * (gap / 2 + w)
        a, b = (z0, z1) if half > 0 else (z1, z0)
        # rubber tyre
        lathe(m, F, [(r - tyre_t, a + 0.004), (r - 0.012, a), (r, a + 0.012), (r, b - 0.012), (r - 0.012, b), (r - tyre_t, b - 0.004)], 48, mat=mat_rubber)
        # dished disc
        mid = (a + b) / 2
        dish = half * w * 0.25
        lathe(m, F, [(r - tyre_t, b - 0.004 if half > 0 else a + 0.004), (r - tyre_t - 0.02, mid + dish), (r * 0.42, mid + dish * 1.3), (r * 0.3, mid + dish * 0.6), (0.0, mid + dish * 0.6)][:: 1 if half > 0 else 1], 36, mat=mat_wheel)
        lathe(m, F, [(0.0, mid - dish * 0.3), (r * 0.3, mid - dish * 0.3), (r * 0.42, mid), (r - tyre_t - 0.02, mid - dish * 0.2), (r - tyre_t, a + 0.004 if half > 0 else b - 0.004)], 36, mat=mat_wheel)
        for k in range(holes):  # lightening holes as dark recessed discs
            ang = 2 * math.pi * (k + 0.5) / holes
            pc = np.array([math.cos(ang) * r * 0.62, math.sin(ang) * r * 0.62, mid + dish * 1.2 + half * 0.002])
            lathe(m, Frame(F.p(pc), F.x, F.y, F.z * half), [(0.0, 0.0), (r * 0.12, 0.0), (r * 0.12, 0.004), (0.0, 0.004)], 14, mat=mat_wheel)
        for k in range(spokes):
            ang = 2 * math.pi * k / spokes
            d = np.array([math.cos(ang), math.sin(ang), 0.0])
            G = Frame(F.p(d * r * 0.6 + np.array([0, 0, mid + dish * 1.1])), F.d(d), F.d(np.array([-d[1], d[0], 0])), F.z)
            rbox(m, G, (r * 0.62, 0.025, 0.02), 0.006, 1, mat=mat_wheel)
    # hub with its cap and bolts on the outboard face
    zo = gap / 2 + w
    lathe(m, F, [(0.0, -zo * 0.6), (r * 0.22, -zo * 0.6), (r * 0.22, zo + 0.02), (r * 0.17, zo + 0.05), (0.0, zo + 0.055)], 24, mat=mat_wheel)
    for k in range(hub_bolts):
        ang = 2 * math.pi * k / hub_bolts
        bolt(m, Frame(F.p((math.cos(ang) * r * 0.17, math.sin(ang) * r * 0.17, zo + 0.02)), F.x, F.y, F.z), 0.011, 0.012, mat=mat_wheel)


def sprocket(m, c, r_pitch, teeth, w, gap, sx=1, mat=0, double=True, holes=8):
    """A drive sprocket: toothed rings (two, either side of the guides, or one) on a hub, axis along X."""
    F = Xframe(c, sx)
    halves = (-1, 1) if double else (0,)
    for half in halves:
        zc = half * (gap / 2 + w / 2)
        prof = []
        n = teeth * 6
        tooth = []
        for k in range(n + 1):
            a = 2 * math.pi * k / n
            ph = (k % 6) / 6
            rr = r_pitch + 0.035 * max(0.0, math.cos(ph * 2 * math.pi)) ** 0.6 - 0.012
            tooth.append((rr * math.cos(a), rr * math.sin(a)))
        ring = [F.p((x, y, zc - w / 2)) for x, y in tooth[:-1]]
        ring2 = [F.p((x, y, zc + w / 2)) for x, y in tooth[:-1]]
        ids = m.grid([ring, ring2], closed=True, mat=mat)
        inner = [F.p(((r_pitch - 0.07) * math.cos(2 * math.pi * k / n), (r_pitch - 0.07) * math.sin(2 * math.pi * k / n), zc - w / 2)) for k in range(n)]
        inner2 = [F.p(((r_pitch - 0.07) * math.cos(2 * math.pi * k / n), (r_pitch - 0.07) * math.sin(2 * math.pi * k / n), zc + w / 2)) for k in range(n)]
        a_ids = m.verts(inner)
        b_ids = m.verts(inner2)
        for k in range(n):
            j = (k + 1) % n
            m.face((ids[0][k], ids[0][j], a_ids[j], a_ids[k]), mat)
            m.face((ids[1][j], ids[1][k], b_ids[k], b_ids[j]), mat)
        # web with holes
        lathe(m, F, [(r_pitch - 0.07, zc - w * 0.3), (r_pitch * 0.35, zc - w * 0.3), (r_pitch * 0.35, zc + w * 0.3), (r_pitch - 0.07, zc + w * 0.3)], 36, mat=mat)
        for k in range(holes):
            ang = 2 * math.pi * (k + 0.5) / holes
            pc = np.array([math.cos(ang) * r_pitch * 0.62, math.sin(ang) * r_pitch * 0.62, zc + w * 0.3 + 0.001])
            lathe(m, Frame(F.p(pc), F.x, F.y, F.z), [(0.0, 0.0), (r_pitch * 0.11, 0.0), (r_pitch * 0.11, 0.004), (0.0, 0.004)], 12, mat=mat)
    zo = (gap / 2 + w) if double else w / 2
    lathe(m, F, [(0.0, -zo - 0.1), (r_pitch * 0.33, -zo - 0.1), (r_pitch * 0.36, zo + 0.02), (r_pitch * 0.25, zo + 0.07), (0.0, zo + 0.075)], 28, mat=mat)
    for k in range(10):
        ang = 2 * math.pi * k / 10
        bolt(m, Frame(F.p((math.cos(ang) * r_pitch * 0.29, math.sin(ang) * r_pitch * 0.29, zo + 0.02)), F.x, F.y, F.z), 0.012, 0.014, mat=mat)


def return_roller(m, c, r, w, sx=1, mat_wheel=0, mat_rubber=1):
    F = Xframe(c, sx)
    lathe(m, F, [(r * 0.7, -w / 2), (r - 0.01, -w / 2), (r, -w / 2 + 0.01), (r, w / 2 - 0.01), (r - 0.01, w / 2), (r * 0.7, w / 2)], 28, mat=mat_rubber)
    lathe(m, F, [(0.0, -w / 2 - 0.12), (r * 0.3, -w / 2 - 0.12), (r * 0.3, -w / 2), (r * 0.7, -w / 2 + 0.005), (r * 0.7, w / 2 - 0.005), (r * 0.35, w / 2 + 0.01), (0.0, w / 2 + 0.03)], 24, mat=mat_wheel)


def spin_node(name, c, parent, radius, what):
    n = empty(name, c, parent)
    drive(n, f"{what}: spins about local X; + turns as the vehicle drives forward, one radian for every {radius:.3f} m driven",
          control="wheel", axis=[1, 0, 0], radius=round(float(radius), 4))
    return n


def tracked(M, parent, S):
    """Both sides' running gear: road wheels on trailing arms, the idler, the drive sprocket, return rollers and
    the track round them all. S holds the layout: x (track centres), wheels_z, wheel_y, wheel_r, wheel_w, wheel_gap,
    idler (z, y, r), sprocket (z, y, pitch radius, teeth), rollers [(z, y, r)], W, pitch, t_in, t_out, link(m, pitch),
    sag (top-run droop), hull_x (where the arms pivot), arm (pivot offset ahead of each wheel, and its height),
    shocks (wheel indices with shock absorbers), mats: wheel, rubber, track (list for the link)."""
    import bpy
    node = empty("Running_Gear", (0, S["wheel_y"], 0), parent)
    mw, mr = S["mats"]["wheel"], S["mats"]["rubber"]
    objs = []
    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * S["x"]
        y = S["wheel_y"]
        r, w, gap = S["wheel_r"], S["wheel_w"], S["wheel_gap"]
        arms = Mesh()
        for k, z in enumerate(S["wheels_z"]):
            c = (x, y, z)
            n = spin_node(f"Road_Wheel_{side}_{k + 1}", c, node, r, "a road wheel")
            m = Mesh()
            road_wheel(m, c, r, w, gap, sx=sx, holes=S.get("holes", 6), spokes=S.get("spokes", 0), tyre_t=S.get("tyre_t", 0.05))
            objs.append(m.to_object(f"Road_Wheel_{side}_{k + 1}_Mesh", [mw, mr], n, sharp_angle=50))
            # trailing arm from its pivot on the hull to the hub, with the torsion bar's anchor
            dz, dy = S["arm"]
            xi = x - sx * (gap / 2 + w + 0.03)
            piv = np.array([sx * S["hull_x"], y + dy, z + dz])
            hub = np.array([xi, y, z])
            lathe(arms, Xframe(piv, sx), [(0.0, -0.02), (0.11, -0.02), (0.11, 0.1), (0.08, 0.13), (0.0, 0.13)], 20)
            mid = np.array([xi, y + dy * 0.4, z + dz * 0.55])
            path_tube(arms, [piv + np.array([sx * 0.08, 0, 0]), mid, hub], 0.065, 12)
            lathe(arms, Xframe(hub - np.array([sx * 0.02, 0, 0]), sx), [(0.0, -0.06), (0.1, -0.06), (0.1, 0.03), (0.0, 0.03)], 18)
            if k in S.get("shocks", ()):
                top = np.array([sx * (S["hull_x"] + 0.05), y + 0.42, z - dz * 0.3])
                tube(arms, top, mid + np.array([sx * 0.02, 0.06, 0]), 0.05, 14)
                tube(arms, top + (mid - top) * 0.15, top + (mid - top) * 0.55, 0.068, 14)
        # idler on its arm, sprocket on its final drive
        iz, iy, ir = S["idler"]
        n = spin_node(f"Idler_{side}", (x, iy, iz), node, ir + S["t_in"], "the idler")
        m = Mesh()
        road_wheel(m, (x, iy, iz), ir, w, gap, sx=sx, holes=8, tyre_t=0.03)
        objs.append(m.to_object(f"Idler_{side}_Mesh", [mw, mr], n, sharp_angle=50))
        piv = np.array([sx * S["hull_x"], iy + 0.08, iz - math.copysign(0.42, iz)])  # the idler's arm reaches in from the hull
        path_tube(arms, [piv, np.array([x - sx * (gap / 2 + w + 0.03), iy, iz])], 0.07, 12)
        lathe(arms, Xframe(piv, sx), [(0.0, -0.02), (0.12, -0.02), (0.12, 0.12), (0.0, 0.12)], 20)
        sz, sy, spr, teeth = S["sprocket"]
        n = spin_node(f"Sprocket_{side}", (x, sy, sz), node, spr, "the drive sprocket")
        m = Mesh()
        sprocket(m, (x, sy, sz), spr, teeth, S.get("sprocket_w", 0.06), S.get("sprocket_gap", gap + 0.02), sx=sx, double=S.get("sprocket_double", True))
        objs.append(m.to_object(f"Sprocket_{side}_Mesh", [mw], n, sharp_angle=40))
        lathe(arms, Xframe((sx * S["hull_x"], sy, sz), sx), [(0.0, -0.05), (spr * 0.6, -0.05), (spr * 0.6, 0.12), (spr * 0.45, S["x"] - S["hull_x"] - 0.2), (0.0, S["x"] - S["hull_x"] - 0.2)], 28)
        for j, (rz, ry, rr) in enumerate(S["rollers"]):
            n = spin_node(f"Return_Roller_{side}_{j + 1}", (x, ry, rz), node, rr + S["t_in"], "a return roller")
            m = Mesh()
            return_roller(m, (x, ry, rz), rr, S.get("roller_w", w * 2 + gap), sx=sx)
            objs.append(m.to_object(f"Return_Roller_{side}_{j + 1}_Mesh", [mw, mr], n, sharp_angle=50))
            tube(arms, (sx * S["hull_x"], ry, rz), (x - sx * (S.get("roller_w", w * 2 + gap) / 2 + 0.1), ry, rz), 0.04, 12)
        objs.append(arms.to_object(f"Suspension_{side}", [mw], node, sharp_angle=50))
        # the track
        circles = [(z, y, r + S["t_in"]) for z in S["wheels_z"]] + [(iz, iy, ir + S["t_in"]), (sz, sy, spr)] + [(rz, ry, rr + S["t_in"]) for rz, ry, rr in S["rollers"]]
        loop = circle_hull(circles)
        if S.get("sag"):
            loop = sag(loop, [sz, iz] + [rz for rz, _, _ in S["rollers"]], S["sag"])
        loop, _ = resample(loop, 0.02)
        tnode, links, count, p, L = track(M, node, side, x, loop, S["pitch"], S["link"], S["mats"]["track"])
        objs += links
    return node, objs
