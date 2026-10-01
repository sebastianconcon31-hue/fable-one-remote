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


def world_tris(objs, owners=None):
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
        if owners is not None:
            owners += [o.name] * len(me.loop_triangles)
    return verts, polys


def bvh(objs):
    v, p = world_tris(objs)
    return BVHTree.FromPolygons(v, p) if p else None, v


def overlaps(a_objs, b_objs):
    """Overlapping triangle pairs between a_objs and b_objs, counted by the pair of meshes they belong to."""
    from collections import Counter
    bpy.context.view_layer.update()
    na, nb = [], []
    va, pa = world_tris(a_objs, na)
    vb, pb = world_tris(b_objs, nb)
    if not pa or not pb:
        return Counter()
    A, Bt = BVHTree.FromPolygons(va, pa), BVHTree.FromPolygons(vb, pb)
    return Counter((na[i], nb[j]) for i, j in A.overlap(Bt))


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


def named_pts(objs):
    """Every vertex of objs in model axes, and the name of the mesh it belongs to."""
    pts, names = [], []
    for o in objs:
        p = model_pts([o])
        pts.append(p)
        names += [o.name] * len(p)
    return (np.vstack(pts) if pts else np.zeros((0, 3))), np.array(names)


def tangent_angle(points, zc, r, sign):
    """Approach (sign +1, ahead of the front axle) or departure (sign -1) angle: the steepest line from the tyre's
    contact that clears every point of the vehicle beyond the axle; and the index of the point that limits it."""
    z = sign * (points[:, 0] - zc)
    y = points[:, 1]
    keep = np.nonzero(z > 0.05)[0]
    z, y = z[keep], y[keep]
    for d in np.arange(1.0, 89.9, 0.1):
        t = math.radians(d)
        # tangent point on the tyre's lower leading side, and the line's direction
        T = np.array([r * math.sin(t), r - r * math.cos(t)])
        dirv = np.array([math.cos(t), math.sin(t)])
        below = ((z - T[0]) * dirv[1] - (y - T[1]) * dirv[0] > 1e-4) & (z > T[0])
        if below.any():
            return d - 0.1, int(keep[np.nonzero(below)[0][0]])
    return 89.9, None


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
    def test(node, poses, label, mount=False):
        parts = meshes_under(node)
        others = [m for m in meshes if m not in parts]
        base = overlaps(parts, others)
        if mount:  # a gun moves through its mounting (the gun port, the armour round the mantlet) by design
            held = {b for (_, b) in base}
            others = [m for m in others if m.name not in held]
            base = overlaps(parts, others)
        worst, where, below = 0, None, 0.0
        for desc, fn in poses:
            fn()
            c = overlaps(parts, others)
            new = {k: v - base.get(k, 0) for k, v in c.items() if v > base.get(k, 0)}
            n = sum(new.values())
            gp = model_pts(parts)
            below = min(below, float(gp[:, 1].min()) if len(gp) else 0.0)
            if n > worst:
                top = sorted(new.items(), key=lambda kv: -kv[1])[:3]
                worst, where = n, desc + "; " + ", ".join(f"{a} into {b} {v}" for (a, b), v in top)
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
        table, step = (list(g["limits_by_traverse"]), float(g.get("traverse_step", 5))) if "limits_by_traverse" in g.keys() else (None, None)
        for a in range(0, 360, 30):
            ends = (lim[0], lim[1])
            if table:  # the gun's own limits at this traverse
                ends = tuple(table[int(round(a / step)) % len(table)])
            for e in ends:
                def f(a=a, e=e):
                    if t is not None:
                        pose(t, math.radians(a))
                    pose(g, e)
                poses.append((f"traverse {a} deg, elevation {math.degrees(e):.0f} deg", f))
        base, worst, where, below = test(g, poses, name, mount=True)
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
        body, owner = named_pts([m for m in meshes if m not in wheel_meshes and not m.name.startswith("Spare")])
        zy = body[:, [2, 1]]
        a, ia = tangent_angle(zy, wz[-1], r, +1)
        d, idp = tangent_angle(zy, wz[0], r, -1)
        R["approach"], R["departure"] = a, d
        R["approachLimitedBy"] = owner[ia] if ia is not None else None
        R["departureLimitedBy"] = owner[idp] if idp is not None else None
        ok(f"approach {a:.1f} deg (limited by {R['approachLimitedBy']}), departure {d:.1f} deg (limited by {R['departureLimitedBy']})")
        mid = (body[:, 2] < wz[-1] - 0.3) & (body[:, 2] > wz[0] + 0.3)
        lowest = int(np.argmin(body[:, 1]))
        R["clearance"] = float(body[lowest, 1])
        R["clearanceAt"] = owner[lowest]
        if mid.any():
            i = np.nonzero(mid)[0][int(np.argmin(body[mid, 1]))]
            R["clearanceBetweenAxles"], R["clearanceBetweenAxlesAt"] = float(body[i, 1]), owner[i]
        # under each axle (within a tyre's width of its centre), the lowest point that isn't a wheel
        under = []
        for zc in wz:
            near = (np.abs(body[:, 2] - zc) < 0.25) & (np.abs(body[:, 0]) < 0.6)
            if near.any():
                i = np.nonzero(near)[0][int(np.argmin(body[near, 1]))]
                under.append((round(zc, 3), round(float(body[i, 1]), 3), owner[i]))
        R["underAxles"] = under
        ok(f"lowest point off the wheels {R['clearance']:.3f} m ({R['clearanceAt']}), between the axles {R.get('clearanceBetweenAxles', float('nan')):.3f} m ({R.get('clearanceBetweenAxlesAt')})")
        ok("under the axles: " + "; ".join(f"z {z}: {y} m ({n})" for z, y, n in under))
    if "--json" in sys.argv:
        json.dump(R, open(arg("--json"), "w"), indent=1)
    print(f"{len(R['issues'])} issue(s)", flush=True)


if __name__ == "__main__":
    main()
