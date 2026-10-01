"""Where each gun can point without going through its own vehicle.

For every step of the turret's traverse, the lowest and highest elevation at
which the gun (and everything that elevates with it) stays clear of the hull
and of the rest of the turret. It is the dead-zone table a game needs: clamp
the gun's elevation to the entry for the turret's current traverse, and the
gun lifts over the engine deck, the fuel drums or the open hatches instead
of sinking through them.

The build writes it into the elevating node's glTF extras before export:

    limits_by_traverse   [[lowest, highest], ...] in radians, one pair every
                         traverse_step degrees of traverse, from traverse 0
                         round the way + traverses
    traverse_step        degrees between the pairs

Interpolate between neighbouring pairs; the table already takes the tighter
of the samples either side of each entry, so the gun stays clear between
them. Whatever the gun already touches at rest (the gun port in the
turret's face, the armour round its mantlet, a crane boom's rest) is its
mounting, and only counts once the contact grows well past what it is at
rest.

    gun_limits()                      in the open Blender scene: {node: table}
    python modelkit/clearance.py MODEL.glb   prints the table for a delivered model"""
import sys
import os
import math
from collections import Counter

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import B

STEP = 5.0  # degrees of traverse between the table's entries
TOL = 6  # the gun's triangles newly touching a mesh before a pose counts as touching it
NEAR = 0.15  # m: how far from where it touches at rest a gun's sliding contact may spread


def _descendants(o):
    out = []
    for c in o.children:
        out += [c] + _descendants(c)
    return out


def _tris(objs):
    """World-space vertices, triangles and each triangle's mesh, for the objects as they stand."""
    V, T, own = [], [], []
    for o in objs:
        me = o.data
        mw = np.asarray(o.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        w = (mw[:3, :3] @ co.reshape(-1, 3).T).T + mw[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", tri)
        T.append(tri.reshape(-1, 3) + sum(len(v) for v in V))
        V.append(w)
        own += [o.name] * len(me.loop_triangles)
    if not V:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), []
    return np.vstack(V), np.vstack(T), own


def _rot(axis, angle):
    k = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * K @ K


class _Target:
    def __init__(self, objs):
        self.objs = objs
        v, t, self.own = _tris(objs)
        self.tree = BVHTree.FromPolygons([Vector(p) for p in v], t.tolist()) if len(t) else None

    def without(self, names):
        return _Target([o for o in self.objs if o.name not in names])

    def hits(self, gun_tree):
        """Which of the gun's triangles touch which of these meshes: a set of (gun triangle, mesh)."""
        if self.tree is None:
            return set()
        return {(i, self.own[j]) for i, j in gun_tree.overlap(self.tree)}


def _world_axis(o):
    a = np.asarray(o.matrix_world.to_3x3().normalized()) @ np.asarray(B(list(o["axis"])), float)
    return a / np.linalg.norm(a)


def table_for(gun, step=STEP, log=None):
    """The table for one elevating node, with the scene at rest (every hinge closed, turret and gun at 0)."""
    trav = gun.parent
    while trav is not None and trav.get("control") != "traverse":
        trav = trav.parent
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    gun_parts = [o for o in [gun] + _descendants(gun) if o.type == "MESH"]
    turret_parts = [o for o in ([trav] + _descendants(trav) if trav else []) if o.type == "MESH" and o not in gun_parts]
    hull_parts = [o for o in meshes if o not in gun_parts and o not in turret_parts]
    bpy.context.view_layer.update()
    gv, gt, _ = _tris(gun_parts)
    gt = gt.tolist()
    hull, turret = _Target(hull_parts), _Target(turret_parts)
    pg, ag = np.asarray(gun.matrix_world.translation), _world_axis(gun)
    pt, at = (np.asarray(trav.matrix_world.translation), _world_axis(trav)) if trav else (np.zeros(3), np.array([0, 0, 1.0]))

    def tree(a, e):
        v = (gv - pg) @ _rot(ag, e).T + pg
        v = (v - pt) @ _rot(at, a).T + pt
        return BVHTree.FromPolygons([Vector(p) for p in v], gt)

    # whatever part of the gun already touches something at rest is how it's mounted - the barrel through the gun
    # port, the trunnions in their yoke, a crane boom on its rest - and it slides against it by design. So a pose
    # touches when (a) more than TOL of the gun's triangles touch something that aren't within NEAR of where it
    # touched that at rest (the breech swinging up into the turret drive, the boom's far end), or (b) the contact with
    # what it's mounted in grows well past what it is at rest (the boom sliding off its rest through the side rail)
    t0 = tree(0.0, 0.0)
    base_h, base_t = hull.hits(t0), turret.hits(t0)
    cent = np.array([gv[t].mean(axis=0) for t in gt])
    near = {}
    for i, k in base_h | base_t:
        near.setdefault(k, set()).add(i)
    for k, idx in near.items():
        d = np.min(np.linalg.norm(cent[:, None, :] - cent[None, sorted(idx), :], axis=2), axis=1)
        near[k] = set(np.nonzero(d < NEAR)[0].tolist())
    rest_count = Counter(k for _, k in base_h | base_t)
    cache_t = {}

    def touching(c, base):
        far = Counter(k for i, k in c if i not in near.get(k, ()))
        if any(n > TOL for n in far.values()):
            return True
        now = Counter(k for _, k in c)
        return any(now[k] > n + max(TOL, 2 * n) for k, n in rest_count.items() if k in now)

    def clear(a, e):
        if e not in cache_t:  # against the turret it depends on the elevation only
            cache_t[e] = not touching(turret.hits(tree(0.0, e)), base_t)
        if not cache_t[e]:
            return False
        return not touching(hull.hits(tree(a, e)), base_h)

    lo_lim, hi_lim = (float(x) for x in gun["limits"])
    coarse = math.radians(1.0)

    def edge(a, start, end):
        """From a clear elevation `start` toward `end`: the last clear elevation before the gun touches. A touch that's
        clear again a degree further on is a graze in passing (a hook brushing a side board) and doesn't stop it."""
        sgn = 1 if end > start else -1
        e = start
        while sgn * (end - e) > 1e-9:
            nxt = e + sgn * min(coarse, abs(end - e))
            beyond = nxt + sgn * min(coarse, abs(end - nxt))
            if not clear(a, round(nxt, 6)) and (abs(beyond - nxt) < 1e-9 or not clear(a, round(beyond, 6))):
                ok_e, bad = e, nxt
                for _ in range(6):
                    mid = (ok_e + bad) / 2
                    if clear(a, round(mid, 6)):
                        ok_e = mid
                    else:
                        bad = mid
                return ok_e
            e = nxt
        return end

    def sample(a):
        e0 = 0.0
        if not clear(a, 0.0):
            e0 = None
            for k in range(1, int(math.degrees(hi_lim)) + 1):  # the lowest elevation clear for two degrees above it too
                if all(clear(a, round(math.radians(min(k + j, math.degrees(hi_lim))), 6)) for j in range(3)):
                    e0 = math.radians(k)
                    break
            if e0 is None:
                return (hi_lim, hi_lim)
        return (edge(a, e0, lo_lim), edge(a, e0, hi_lim))

    n = int(round(360 / step))
    half = {}
    for k in range(2 * n):  # every half step: each entry takes the tighter of itself and its neighbours
        half[k] = sample(math.radians(k * step / 2))
    out = []
    for k in range(n):
        s = [half[(2 * k + d) % (2 * n)] for d in (-1, 0, 1)]
        out.append([round(max(x[0] for x in s), 4), round(min(x[1] for x in s), 4)])
    if log:
        tight = [(k * step, v) for k, v in enumerate(out) if v[0] > lo_lim + 1e-3 or v[1] < hi_lim - 1e-3]
        log(f"  {gun.name}: limits {math.degrees(lo_lim):.0f} to {math.degrees(hi_lim):.0f} deg; tighter at {len(tight)} of {n} traverse steps"
            + (": " + ", ".join(f"{a:.0f}: {math.degrees(v[0]):+.1f}/{math.degrees(v[1]):+.1f}" for a, v in tight[::max(1, len(tight) // 12)]) if tight else ""))
    return out


def gun_limits(step=STEP, log=print):
    """Compute and store the table on every elevating node in the scene; returns {name: table}."""
    out = {}
    for g in [o for o in bpy.data.objects if o.get("control") == "elevate"]:
        t = table_for(g, step, log)
        g["limits_by_traverse"] = t
        g["traverse_step"] = step
        out[g.name] = t
    return out


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=sys.argv[1])
    gun_limits()
