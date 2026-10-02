"""Geometry helpers for the exterior: everything is authored in the model's
own axes - metres, +Y up, +Z toward the nose, +X to the crew's left (glTF's
axes, the same as the cockpit) - and converted to Blender's Z-up axes only
when a mesh object is made. glTF export converts them back.
"""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix


def B(p):
    """Model (x left, y up, z forward) to Blender (x, -z, y)."""
    return (float(p[0]), -float(p[2]), float(p[1]))


def norm(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


# ---- smooth interpolation along a piece -----------------------------------------------------------------------------------
def pchip(xs, ys):
    """Monotone cubic through (xs, ys): smooth without overshoot. Returns f(x); ys may be vectors."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    if ys.ndim == 1:
        ys = ys[:, None]
    n = len(xs)
    h = np.diff(xs)
    d = np.diff(ys, axis=0) / h[:, None]
    m = np.zeros_like(ys)
    if n == 2:
        m[:] = d[0]
    else:
        for i in range(1, n - 1):
            for k in range(ys.shape[1]):
                if d[i - 1, k] * d[i, k] <= 0:
                    m[i, k] = 0
                else:
                    w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                    m[i, k] = (w1 + w2) / (w1 / d[i - 1, k] + w2 / d[i, k])
        m[0] = d[0]
        m[-1] = d[-1]

    def f(x):
        x = float(np.clip(x, xs[0], xs[-1]))
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, n - 2))
        t = (x - xs[i]) / h[i]
        h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
        v = h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
        return v if v.shape[0] > 1 else float(v[0])

    return f


def table(stations, keys):
    """stations: list of (z, {key: value or tuple}) -> f(z) giving a dict with every key interpolated smoothly."""
    zs = [s[0] for s in stations]
    fns = {}
    for k in keys:
        vals = [np.atleast_1d(np.asarray(s[1][k], dtype=float)) for s in stations]
        fns[k] = pchip(zs, np.stack(vals))
    def at(z):
        out = {}
        for k, f in fns.items():
            v = f(z)
            out[k] = np.atleast_1d(v) if np.ndim(v) else float(v)
        return out
    return at


def spacing(z0, z1, step, dense=()):
    """Stations from z0 to z1 (either direction) about `step` apart, with extra stations near the given z values."""
    n = max(2, int(math.ceil(abs(z1 - z0) / step)) + 1)
    zs = list(np.linspace(z0, z1, n))
    for zd, halfwidth, st in dense:
        lo, hi = sorted((zd - halfwidth, zd + halfwidth))
        lo, hi = max(lo, min(z0, z1)), min(hi, max(z0, z1))
        if hi > lo:
            zs += list(np.linspace(lo, hi, max(2, int((hi - lo) / st) + 1)))
    zs = sorted(set(round(z, 5) for z in zs), reverse=z0 > z1)
    return zs


# ---- rounded polylines ---------------------------------------------------------------------------------------------------
def fillet_path(pts, radii, arc_n=4, seg_n=2, closed=False):
    """A polyline through 2D corner points, each interior corner rounded to its radius.

    Every corner gives `arc_n` points and every straight run `seg_n` extra points, whatever the
    geometry, so paths built from the same corner list always have the same point count and can be lofted.
    arc_n / seg_n may be lists (per corner / per segment)."""
    P = [np.asarray(p, dtype=float) for p in pts]
    n = len(P)
    corners = range(n) if closed else range(1, n - 1)
    an = arc_n if isinstance(arc_n, (list, tuple)) else [arc_n] * n
    sn = seg_n if isinstance(seg_n, (list, tuple)) else [seg_n] * n
    arcs = {}
    for i in corners:
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        u, w = norm(b - a), norm(c - b)
        la, lc = np.linalg.norm(b - a), np.linalg.norm(c - b)
        cosang = float(np.clip(np.dot(-u, w), -1, 1))
        theta = math.acos(cosang)  # interior angle
        r = max(float(radii[i]), 1e-4)
        if theta > math.pi - 1e-3:  # straight through
            arcs[i] = [b.copy() for _ in range(an[i])]
            continue
        d = r / math.tan(theta / 2)
        dmax = 0.49 * min(la, lc)
        if d > dmax:
            d = dmax
            r = d * math.tan(theta / 2)
        t1, t2 = b - u * d, b + w * d
        # centre: from t1 perpendicular toward the inside of the turn
        cross = u[0] * w[1] - u[1] * w[0]
        perp = np.array([-u[1], u[0]]) if cross > 0 else np.array([u[1], -u[0]])
        cen = t1 + perp * r
        a0 = math.atan2(t1[1] - cen[1], t1[0] - cen[0])
        a1 = math.atan2(t2[1] - cen[1], t2[0] - cen[0])
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        k = an[i]
        arcs[i] = [cen + r * np.array([math.cos(a0 + da * j / (k - 1)), math.sin(a0 + da * j / (k - 1))]) for j in range(k)] if k > 1 else [b.copy()]
    out = []
    order = list(range(n))
    for i in order:
        if i in arcs:
            pts_i = arcs[i]
        else:
            pts_i = [P[i]]
        out += pts_i
        if not closed and i == n - 1:
            break
        j = (i + 1) % n
        start = pts_i[-1]
        end = arcs[j][0] if j in arcs else P[j]
        for s in range(1, sn[i] + 1):
            out.append(start + (end - start) * s / (sn[i] + 1))
    return [tuple(p) for p in out]


def airfoil(t, n=18, camber=0.0):
    """Symmetric (or lightly cambered) NACA-style section, chord 0..1 from the leading edge.
    Returns a closed loop: trailing edge -> upper surface -> leading edge -> lower surface, (x, y) pairs, 2n points."""
    xs = [(1 - math.cos(math.pi * i / n)) / 2 for i in range(n + 1)]  # cosine spacing, 0 at LE
    def yt(x):
        return 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    def yc(x):
        return camber * 4 * x * (1 - x)
    upper = [(x, yc(x) + yt(x)) for x in reversed(xs)]  # TE -> LE
    lower = [(x, yc(x) - yt(x)) for x in xs[1:-1]]  # LE -> TE (excluding both ends)
    return upper + lower


# ---- mesh building ---------------------------------------------------------------------------------------------------------
class Mesh:
    """Collects vertices (model axes) and faces, then becomes a Blender object."""

    def __init__(self):
        self.v = []
        self.f = []
        self.fm = []  # material slot per face
        self.sharp = []  # vertex index pairs to mark sharp

    def verts(self, pts):
        i = len(self.v)
        self.v += [tuple(map(float, p)) for p in pts]
        return list(range(i, i + len(pts)))

    def face(self, idx, mat=0):
        self.f.append(tuple(idx))
        self.fm.append(mat)

    def grid(self, rings, closed=False, mat=0, flip=False, mats=None, orient=True):
        """Quads between consecutive rings of equal length. closed: each ring is a loop, and unless orient=False the
        faces are turned to face away from the loop's centre. mats: optional function (ring index, point index) -> slot."""
        if closed and orient and len(rings) > 1:
            score = 0.0
            for ra, rb in zip(rings, rings[1:]):
                A, Bn = np.asarray(ra, float), np.asarray(rb, float)
                c = (A.mean(axis=0) + Bn.mean(axis=0)) / 2
                for j in range(len(ra)):
                    k = (j + 1) % len(ra)
                    n = np.cross(A[k] - A[j], Bn[j] - A[j])
                    score += np.dot(n, (A[j] + A[k] + Bn[j] + Bn[k]) / 4 - c)
            if (score < 0) != flip:
                rings = [list(r)[::-1] for r in rings]
                if mats:
                    m0 = len(rings[0])
                    orig = mats
                    mats = lambda ri, j, orig=orig, m0=m0: orig(ri, (m0 - 2 - j) % m0)
            flip = False
        ids = [self.verts(r) for r in rings]
        m = len(rings[0])
        for a, b in zip(ids, ids[1:]):
            rng = range(m) if closed else range(m - 1)
            for j in rng:
                k = (j + 1) % m
                q = (a[j], a[k], b[k], b[j])
                if flip:
                    q = q[::-1]
                self.face(q, mats(ids.index(a), j) if mats else mat)
        return ids

    def cap(self, ring_ids, mat=0, flip=False, center=None):
        """Close a loop: an n-gon, or a fan to `center` if given."""
        if center is None:
            self.face(ring_ids[::-1] if flip else ring_ids, mat)
        else:
            c = self.verts([center])[0]
            m = len(ring_ids)
            for j in range(m):
                t = (ring_ids[j], ring_ids[(j + 1) % m], c)
                self.face(t[::-1] if flip else t, mat)

    def orient_from(self, center, start=0):
        """Point faces from `start` on away from `center` (for convex parts)."""
        c = np.asarray(center, float)
        for i in range(start, len(self.f)):
            vs = [np.asarray(self.v[j]) for j in self.f[i]]
            n = np.zeros(3)
            for a, b in zip(vs, vs[1:] + vs[:1]):
                n += np.cross(a, b)
            if np.dot(n, np.mean(vs, axis=0) - c) < 0:
                self.f[i] = self.f[i][::-1]

    def extend(self, other):
        off = len(self.v)
        self.v += other.v
        self.f += [tuple(i + off for i in f) for f in other.f]
        self.fm += other.fm
        self.sharp += [(a + off, b + off) for a, b in other.sharp]

    def transformed(self, fn):
        m = Mesh()
        m.v = [tuple(fn(np.asarray(p))) for p in self.v]
        m.f, m.fm, m.sharp = list(self.f), list(self.fm), list(self.sharp)
        return m

    def mirrored(self):
        """Mirror across the centreline (x -> -x), keeping faces facing outward."""
        m = self.transformed(lambda p: np.array([-p[0], p[1], p[2]]))
        m.f = [f[::-1] for f in m.f]
        return m

    def to_object(self, name, materials, parent=None, smooth=True, sharp_angle=None, outward=None, collection=None, probe=None, normals=None, per_face=None):
        """outward: f(model point) -> a point inside, to vote the faces outward; probe: (model point, direction) the
        nearest face must face; otherwise normals="recalc" makes closed shells face out, and None keeps the winding."""
        me = bpy.data.meshes.new(name)
        me.from_pydata([B(p) for p in self.v], [], self.f)
        me.validate(clean_customdata=False)
        me.update()
        for mat in materials:
            me.materials.append(mat)
        if self.fm:
            fm = self.fm[: len(me.polygons)]
            me.polygons.foreach_set("material_index", fm + [0] * (len(me.polygons) - len(fm)))
        obj = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(obj)
        if outward is not None:
            orient_outward(obj, outward)
        elif probe is not None:
            orient_probe(obj, *probe)
        elif per_face is not None:
            orient_faces(obj, per_face)
        elif normals == "recalc":
            recalc_normals(obj)
        if smooth:
            me.shade_smooth()
            if sharp_angle is not None:
                me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        if parent is not None:
            set_parent(obj, parent)
        return obj


def orient_outward(obj, center_fn):
    """Flip every face if most of them point toward the inside. center_fn(model point) -> a model point inside."""
    me = obj.data
    score = 0.0
    for p in me.polygons:
        c = p.center
        cm = (c.x, c.z, -c.y)  # back to model axes
        ic = np.asarray(center_fn(np.asarray(cm)))
        d = Vector(B(np.asarray(cm) - ic))
        score += p.normal.dot(d) * p.area
    if score < 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        for f in bm.faces:
            f.normal_flip()
        bm.to_mesh(me)
        bm.free()
        me.update()


def orient_faces(obj, center_fn):
    """Turn each face on its own to face away from center_fn(face centre) - for loose flat panes."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        c = f.calc_center_median()
        cm = np.array((c.x, c.z, -c.y))
        d = Vector(B(cm - np.asarray(center_fn(cm))))
        if f.normal.dot(d) < 0:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    me.update()


def orient_probe(obj, point, direction):
    """Flip every face if the face nearest `point` doesn't face `direction` (model axes)."""
    me = obj.data
    bp, bd = Vector(B(point)), Vector(B(direction))
    best = min(me.polygons, key=lambda p: (p.center - bp).length)
    if best.normal.dot(bd) < 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        for f in bm.faces:
            f.normal_flip()
        bm.to_mesh(me)
        bm.free()
        me.update()


def recalc_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def set_parent(obj, parent):
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()


def empty(name, at=(0, 0, 0), parent=None, collection=None, size=0.1):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    e.location = B(at)
    (collection or bpy.context.scene.collection).objects.link(e)
    if parent is not None:
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return e


# ---- frames: an origin and three axes in model space -----------------------------------------------------------------
class Frame:
    def __init__(self, o, x=(1, 0, 0), y=(0, 1, 0), z=(0, 0, 1)):
        self.o = np.asarray(o, float)
        self.x, self.y, self.z = norm(x), norm(y), norm(z)

    @staticmethod
    def along(o, fwd, up=(0, 1, 0)):
        """Local Z along fwd, Y as close to up as it can be."""
        z = norm(fwd)
        x = norm(np.cross(up, z))
        if np.linalg.norm(x) < 1e-6:
            x = norm(np.cross((1, 0, 0), z))
        y = np.cross(z, x)
        return Frame(o, x, y, z)

    def p(self, local):
        l = np.asarray(local, float)
        return self.o + self.x * l[0] + self.y * l[1] + self.z * l[2]

    def d(self, local):
        l = np.asarray(local, float)
        return self.x * l[0] + self.y * l[1] + self.z * l[2]


# ---- primitives --------------------------------------------------------------------------------------------------------------
def lathe(m, F, profile, n=24, mat=0, a0=0.0, a1=2 * math.pi, caps=False):
    """Revolve (radius, along) pairs about the frame's Z axis."""
    full = abs(a1 - a0 - 2 * math.pi) < 1e-6
    k = n if full else n + 1
    rings = []
    for r, t in profile:
        ring = []
        for i in range(k):
            a = a0 + (a1 - a0) * i / n
            ring.append(F.p((r * math.cos(a), r * math.sin(a), t)))
        rings.append(ring)
    # grid wants rings along the profile; here "rings" are profile stations, points go round
    ids = m.grid(rings, closed=full, mat=mat, orient=False)
    if caps and full:
        if profile[0][0] > 1e-6:
            m.cap(ids[0], mat, flip=True)
        if profile[-1][0] > 1e-6:
            m.cap(ids[-1], mat)
    return ids


def tube(m, a, b, r, n=12, mat=0, caps=True, r1=None):
    a, b = np.asarray(a, float), np.asarray(b, float)
    F = Frame.along(a, b - a, up=(0, 1, 0) if abs(norm(b - a)[1]) < 0.9 else (1, 0, 0))
    L = np.linalg.norm(b - a)
    r1 = r if r1 is None else r1
    return lathe(m, F, [(r, 0), (r1, L)], n, mat, caps=caps)


def path_tube(m, pts, r, n=10, mat=0, caps=True):
    """A tube along a polyline, with mitred joints."""
    pts = [np.asarray(p, float) for p in pts]
    rings = []
    prev_x = None
    for i, p in enumerate(pts):
        if i == 0:
            t = norm(pts[1] - pts[0])
        elif i == len(pts) - 1:
            t = norm(pts[-1] - pts[-2])
        else:
            t = norm(norm(pts[i] - pts[i - 1]) + norm(pts[i + 1] - pts[i]))
        up = prev_x if prev_x is not None else ((0, 1, 0) if abs(t[1]) < 0.9 else (1, 0, 0))
        x = norm(np.cross(up, t)) if prev_x is None else norm(prev_x - t * np.dot(prev_x, t))
        y = np.cross(t, x)
        prev_x = x
        rings.append([p + (x * math.cos(2 * math.pi * j / n) + y * math.sin(2 * math.pi * j / n)) * r for j in range(n)])
    ids = m.grid(rings, closed=True, mat=mat, orient=False)
    if caps:
        m.cap(ids[0], mat, flip=True)
        m.cap(ids[-1], mat)
    return ids


def rbox(m, F, size, r=0.01, seg=2, mat=0):
    """A box of `size` (x, y, z) centred on the frame, its edges rounded to radius r."""
    sx, sy, sz = [s / 2 for s in size]
    r = min(r, sx * 0.999, sy * 0.999, sz * 0.999)
    # a rounded box as a lofted rounded rectangle along Z with rounded ends
    prof = fillet_path([(sx, sy), (-sx, sy), (-sx, -sy), (sx, -sy)], [r] * 4, arc_n=seg + 1, seg_n=0, closed=True)
    rings = []
    # (z, inset) down the box: the ends curl in by r over a quarter circle
    for z, inset in [(-sz + r - r * math.cos((math.pi / 2) * j / seg), r - r * math.sin((math.pi / 2) * j / seg)) for j in range(seg + 1)] + [
        (sz - r + r * math.sin((math.pi / 2) * j / seg), r - r * math.cos((math.pi / 2) * j / seg)) for j in range(seg + 1)
    ]:
        shrink = [(x - math.copysign(inset, x) if abs(x) > 1e-9 else x, y - math.copysign(inset, y) if abs(y) > 1e-9 else y) for x, y in prof]
        rings.append([F.p((x, y, z)) for x, y in shrink])
    f0 = len(m.f)
    ids = m.grid(rings, closed=True, mat=mat, orient=False)
    m.cap(ids[0], mat, flip=True)
    m.cap(ids[-1], mat)
    m.orient_from(F.o, f0)
    return ids


def prism(m, F, poly, depth, mat=0, r=0.0, seg=1):
    """Extrude a 2D polygon (frame XY) along the frame's Z by depth (centred), corners rounded to r in-plane."""
    loop = fillet_path(poly, [r] * len(poly), arc_n=seg + 1, seg_n=0, closed=True) if r > 0 else [tuple(p) for p in poly]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]))
    handed = np.dot(np.cross(F.x, F.y), F.z)  # a left-handed frame mirrors the winding
    if area * handed < 0:
        loop = loop[::-1]
    a = [F.p((x, y, -depth / 2)) for x, y in loop]
    b = [F.p((x, y, depth / 2)) for x, y in loop]
    if handed < 0:
        a, b = b[::-1], a[::-1]
    ids = m.grid([a, b], closed=True, mat=mat, orient=False)
    m.cap(ids[0], mat, flip=True)
    m.cap(ids[1], mat)
    return ids


def disc(m, F, r, n=16, mat=0):
    ids = m.verts([F.p((r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 0)) for i in range(n)])
    m.face(ids, mat)
    return ids


# ---- frames for parts that turn about a model axis -----------------------------------------------------------------------------
def Yframe(o):
    """Frame at o with local Z pointing up (lathes about a vertical axis)."""
    return Frame(o, (1, 0, 0), (0, 0, -1), (0, 1, 0))


def Xframe(o, sx=1):
    """Frame at o with local Z along +X (sx=1) or -X (wheels, axles)."""
    return Frame(o, (0, 0, -sx), (0, 1, 0), (sx, 0, 0))


def Zframe(o, sz=1):
    """Frame at o with local Z along +Z (sz=1) or -Z."""
    return Frame(o, (sz, 0, 0), (0, 1, 0), (0, 0, sz))
