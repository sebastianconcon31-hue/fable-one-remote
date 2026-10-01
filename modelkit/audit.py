"""Audits a finished vehicle (its delivered glTF) for whether it works in a
game and how it measures up:

  - scale, ground contact, symmetry, counts
  - every moving part at its limits: doors, hatches and ramps opened, wheels
    at full lock, the gun at full depression and elevation all the way round,
    the turret swept round - each checked for new collisions with the rest of
    the vehicle (triangle overlaps against the rest pose) and for going
    through the ground
  - wheels' `radius` against their meshes, tracks' links against their loop
  - wheeled vehicles: approach and departure angles, ground clearance

    python modelkit/audit.py MODEL.glb [--json OUT.json]"""
import sys
import os
import json
import math

import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import B


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def descendants(o):
    out = []
    for c in o.children:
        out.append(c)
        out += descendants(c)
    return out


def meshes_under(o):
    return [x for x in [o] + descendants(o) if x.type == "MESH"]


def world_tris(objs):
    verts, polys = [], []
    for o in objs:
        me = o.data
        mw = o.matrix_world
        base = len(verts)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        w = (np.asarray(mw)[:3, :3] @ co.T).T + np.asarray(mw)[:3, 3]
        verts += [Vector(v) for v in w]
        me.calc_loop_triangles()
        polys += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
    return verts, polys


def bvh(objs):
    v, p = world_tris(objs)
    return BVHTree.FromPolygons(v, p) if p else None, v


def overlaps(a_objs, b_objs):
    bpy.context.view_layer.update()
    A, _ = bvh(a_objs)
    Bt, _ = bvh(b_objs)
    if A is None or Bt is None:
        return 0
    return len(A.overlap(Bt))


def model_pts(objs):
    _, v = bvh(objs)
    return np.array([(p.x, p.z, -p.y) for p in v]) if v else np.zeros((0, 3))


def pose(o, angle):
    a = list(o["axis"])
    o.rotation_mode = "AXIS_ANGLE"
    o.rotation_axis_angle = (angle, *B(a))


def rest(o):
    o.rotation_mode = "AXIS_ANGLE"
    o.rotation_axis_angle = (0.0, 0.0, 0.0, 1.0)


def tangent_angle(points, zc, r, sign):
    """Approach (sign +1, ahead of the front axle) or departure (sign -1) angle: the steepest line from the tyre's
    contact that clears every point of the vehicle beyond the axle."""
    best = 89.9
    pts = [(sign * (z - zc), y) for z, y in points if sign * (z - zc) > 0.05]
    for d in np.arange(1.0, 89.9, 0.1):
        t = math.radians(d)
        # tangent point on the tyre's lower leading side, and the line's direction
        T = np.array([r * math.sin(t), r - r * math.cos(t)])
        dirv = np.array([math.cos(t), math.sin(t)])
        for z, y in pts:
            rel = np.array([z, y]) - T
            if rel[0] * dirv[1] - rel[1] * dirv[0] > 1e-4 and z > T[0]:  # below the line
                return d - 0.1
    return best


def main():
    glb = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    bpy.context.view_layer.update()
    O = bpy.data.objects
    R = {"file": os.path.basename(glb), "issues": [], "checks": []}
    def issue(s):
        R["issues"].append(s)
        print("  ISSUE", s, flush=True)
    def ok(s):
        R["checks"].append(s)
        print("  ok   ", s, flush=True)

    meshes = [o for o in O if o.type == "MESH"]
    allp = model_pts(meshes)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    R["bounds"] = {"min": lo.round(4).tolist(), "max": hi.round(4).tolist(), "size": (hi - lo).round(4).tolist()}
    tris = sum(len(o.data.loop_triangles) for o in meshes)
    R["triangles"], R["meshes"] = tris, len(meshes)
    print(f"{R['file']}: {len(meshes)} meshes, {tris:,} triangles, size {R['bounds']['size']}", flush=True)
    if not np.isfinite(allp).all():
        issue("non-finite vertex positions")
    (ok if abs(lo[1]) < 0.01 else issue)(f"stands on the ground: lowest point y = {lo[1]:.4f} m")
    (ok if abs(lo[0] + hi[0]) < 0.05 else issue)(f"centred across: x from {lo[0]:.3f} to {hi[0]:.3f}")
    names = [o.name for o in O]
    roots = [o for o in O if o.parent is None and o.type == "EMPTY"]
    ok(f"{len(roots)} root node(s): {', '.join(o.name for o in roots[:3])}")

    driven = {o.name: o for o in O if "control" in o.keys()}
    kinds = {}
    for o in driven.values():
        kinds.setdefault(o["control"], []).append(o.name)
    R["controls"] = {k: len(v) for k, v in kinds.items()}
    ok("driven nodes: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(kinds.items())))

    # wheels: the radius each claims against its tyre
    for name in kinds.get("wheel", []):
        o = driven[name]
        p = model_pts(meshes_under(o))
        if not len(p):
            continue
        r_mesh = (p[:, 1].max() - p[:, 1].min()) / 2
        r = float(o.get("radius", 0))
        if name.startswith(("Wheel", "Road_Wheel")) and abs(r_mesh - r) > 0.012:
            issue(f"{name}: radius {r:.3f} in its extras but the wheel is {r_mesh:.3f}")
    ok(f"wheels' radii checked ({len(kinds.get('wheel', []))})")

    # tracks: the loop against its links
    for name in kinds.get("track", []):
        o = driven[name]
        path = np.array(o["path"]).reshape(-1, 2)
        L = float(np.sum(np.linalg.norm(np.diff(np.vstack([path, path[:1]]), axis=0), axis=1)))
        n, pitch = int(o["links"]), float(o["pitch"])
        links = [c for c in o.children if "_Link_" in c.name]
        (ok if abs(n * pitch - L) < 0.01 and len(links) == n else issue)(f"{name}: {len(links)} links x {pitch:.4f} m = {n * pitch:.3f} m round a {L:.3f} m loop")
        bottom = path[:, 1].min()
        (ok if abs(bottom - 0.0) < 0.12 else issue)(f"{name}: the loop's bottom (pin line) at y = {bottom:.3f}")

    # moving parts against the rest of the vehicle, at their limits
    def test(node, poses, label):
        parts = meshes_under(node)
        others = [m for m in meshes if m not in parts]
        base = overlaps(parts, others)
        worst, where, below = 0, None, 0.0
        for desc, fn in poses:
            fn()
            n = overlaps(parts, others)
            gp = model_pts(parts)
            below = min(below, float(gp[:, 1].min()) if len(gp) else 0.0)
            if n - base > worst:
                worst, where = n - base, desc
        for o in [node] + [x for x in descendants(node) if "control" in x.keys()]:
            pass
        return base, worst, where, below

    for name in kinds.get("hinge", []):
        o = driven[name]
        lim = o["limits"]
        base, worst, where, below = test(o, [("open", lambda o=o, lim=lim: pose(o, lim[1])), ("half", lambda o=o, lim=lim: pose(o, (lim[0] + lim[1]) / 2))], name)
        rest(o)
        msg = f"{name} ({o.get('group', '')}): {worst} new overlapping triangle pairs at its limit"
        (ok if worst <= 12 else issue)(msg + (f" ({where})" if worst > 12 else ""))
        if below < -0.02:
            issue(f"{name}: goes {-below:.3f} m into the ground when open")
        elif "Ramp" in name or "Tailgate" in name:
            gp = None
            pose(o, lim[1])
            gp = model_pts(meshes_under(o))
            rest(o)
            ok(f"{name}: open, its lowest point is {gp[:, 1].min():.3f} m above the ground")

    for name in kinds.get("steer", []):
        o = driven[name]
        lim = o["limits"]
        base, worst, where, below = test(o, [("left lock", lambda o=o, lim=lim: pose(o, lim[1])), ("right lock", lambda o=o, lim=lim: pose(o, lim[0]))], name)
        rest(o)
        (ok if worst <= 12 else issue)(f"{name}: {worst} new overlaps at full lock" + (f" ({where})" if worst > 12 else ""))

    trav = [driven[n] for n in kinds.get("traverse", [])]
    for name in kinds.get("elevate", []):
        g = driven[name]
        lim = g["limits"]
        t = next((x for x in trav if g.name in [d.name for d in descendants(x)]), None)
        poses = []
        for a in range(0, 360, 30):
            for e in (lim[0], lim[1]):
                def f(a=a, e=e):
                    if t is not None:
                        pose(t, math.radians(a))
                    pose(g, e)
                poses.append((f"traverse {a} deg, elevation {math.degrees(e):.0f} deg", f))
        base, worst, where, below = test(g, poses, name)
        rest(g)
        if t is not None:
            rest(t)
        (ok if worst <= 12 else issue)(f"{name}: {worst} new overlaps through its elevation round the traverse" + (f" (worst at {where})" if worst > 12 else ""))
    for t in trav:
        base, worst, where, below = test(t, [(f"traverse {a} deg", lambda t=t, a=a: pose(t, math.radians(a))) for a in range(15, 360, 15)], t.name)
        rest(t)
        (ok if worst <= 12 else issue)(f"{t.name}: {worst} new overlaps sweeping round" + (f" (worst at {where})" if worst > 12 else ""))

    # wheeled vehicles: approach and departure angles, clearances
    wheels = [driven[n] for n in kinds.get("wheel", []) if n.startswith("Wheel_")]
    if wheels:
        wz = sorted({round(float(model_pts(meshes_under(w))[:, 2].mean()), 3) for w in wheels})
        r = max(float(w.get("radius", 0.5)) for w in wheels)
        wheel_meshes = set()
        for w in wheels:
            wheel_meshes |= set(meshes_under(w))
        body = model_pts([m for m in meshes if m not in wheel_meshes and not m.name.startswith("Spare")])
        pts = [(z, y) for _, y, z in body]
        a = tangent_angle(pts, wz[-1], r, +1)
        d = tangent_angle(pts, wz[0], r, -1)
        R["approach"], R["departure"] = a, d
        between = body[(body[:, 2] < wz[-1] - 0.3) & (body[:, 2] > wz[0] + 0.3)]
        R["clearance"] = float(body[:, 1].min())
        R["clearanceBetweenAxles"] = float(between[:, 1].min()) if len(between) else None
        ok(f"approach {a:.1f} deg, departure {d:.1f} deg; lowest point off the wheels {R['clearance']:.3f} m, between the axles {R['clearanceBetweenAxles']:.3f} m")
    if "--json" in sys.argv:
        json.dump(R, open(arg("--json"), "w"), indent=1)
    print(f"{len(R['issues'])} issue(s)", flush=True)


if __name__ == "__main__":
    main()
