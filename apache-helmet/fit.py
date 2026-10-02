"""Checks that need a head: does anything on the helmet stand inside the wearer's face, and do the parts that
move clear everything else through their travel. Run from build.py (--fit)."""
import sys
import os
import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelkit"))
from geom import B
import clearance
from helmet import *

# the head as ellipsoids (centre, half axes) and the neck (a cylinder about Y)
ELL = {
    "cranium": ((0.0, 0.030, 0.0065), (0.0765, 0.100, 0.0985)),  # above the brow only (see depth_in_head)
    "eye_l": ((0.0315, 0.026, 0.082), (0.016, 0.014, 0.013)),
    "eye_r": ((-0.0315, 0.026, 0.082), (0.016, 0.014, 0.013)),
    "occiput": ((0.0, -0.020, -0.040), (0.062, 0.055, 0.052)),
    "face": ((0.0, -0.035, 0.046), (0.062, 0.088, 0.050)),
    "chin": ((0.0, -0.108, 0.070), (0.032, 0.020, 0.020)),
    "nose": ((0.0, -0.010, 0.112), (0.013, 0.026, 0.016)),
    "ear_l": ((0.0775, -0.003, -0.004), (0.012, 0.032, 0.018)),
    "ear_r": ((-0.0775, -0.003, -0.004), (0.012, 0.032, 0.018)),
}
NECK = dict(c=(0.0, -0.040), r=0.055, y_top=-0.07)

# parts that are meant to touch the wearer
CONTACT = ("Liner", "Comfort_Pad", "Earcup_", "Chin_", "Nape_Strap")


def world_points(o):
    co = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    mw = np.asarray(o.matrix_world)
    w = (mw[:3, :3] @ co.reshape(-1, 3).T).T + mw[:3, 3]
    return np.stack([w[:, 0], w[:, 2], -w[:, 1]], -1)  # model axes


def depth_in_head(p):
    """How far each point is inside the head (metres, + inside, - outside), approximately."""
    best = np.full(len(p), -9.0)
    for name, (c, s) in ELL.items():
        q = (p - np.asarray(c)) / np.asarray(s)
        f = np.linalg.norm(q, axis=1)
        d = (1 - f) * float(np.mean(s))  # roughly metres
        if name == "cranium":  # the brow ridge is the cranium's lowest front; below it the face is recessed
            d = np.where((p[:, 1] < 0.034) & (p[:, 2] > 0.0), -9.0, d)
        best = np.maximum(best, d)
    dxz = np.linalg.norm(p[:, [0, 2]] - np.asarray(NECK["c"])[None, [0, 1]] * np.array([1.0, 1.0]), axis=1)
    neck = np.where(p[:, 1] < NECK["y_top"], NECK["r"] - np.linalg.norm(np.stack([p[:, 0], p[:, 2] - NECK["c"][1]], -1), axis=1), -9.0)
    return np.maximum(best, neck)


def head_clearance(report=print):
    """Every part's closest approach to the head. Returns (rows, problems)."""
    rows, problems = [], []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        p = world_points(o)
        d = depth_in_head(p)
        deepest, nearest = float(d.max()), float(-d.max())
        contact = any(o.name.startswith(c) for c in CONTACT)
        rows.append((o.name, nearest))
        if deepest > 0.0035 and not contact:
            problems.append(f"{o.name} is {deepest * 1000:.1f} mm inside the head")
    return rows, problems


def tree_of(objs):
    v, t, own = clearance._tris(objs)
    if not len(t):
        return None, []
    return BVHTree.FromPolygons([Vector(p) for p in v], t.tolist()), own


def overlap_pairs(a_objs, b_objs):
    ta, oa = tree_of(a_objs)
    tb, ob = tree_of(b_objs)
    if ta is None or tb is None:
        return set()
    return {(oa[i], ob[j]) for i, j in ta.overlap(tb)}


def set_pose(node, angle):
    node.rotation_mode = "AXIS_ANGLE"
    node.rotation_axis_angle = (angle, *B(list(node["axis"])))
    bpy.context.view_layer.update()


def descendants(o):
    out = []
    for c in o.children:
        out += [c] + descendants(c)
    return out


def hinge_clearance(report=print):
    """Each hinged part at its limits and half way: what it newly touches that it didn't at rest."""
    problems = []
    hinges = [o for o in bpy.data.objects if o.get("control") == "hinge"]
    mesh = lambda objs: [x for x in objs if x.type == "MESH"]
    for h in hinges:
        mine = mesh([h] + descendants(h))
        rest = [o for o in bpy.data.objects if o.type == "MESH" and o not in mine]
        for node in hinges:
            set_pose(node, 0.0)
        base = overlap_pairs(mine, rest)
        lo, hi = h["limits"]
        for f in (0.5, 1.0):
            set_pose(h, lo + (hi - lo) * f)
            new = overlap_pairs(mine, rest) - base
            names = sorted({f"{a}~{b}" for a, b in new})
            report(f"  {h.name} at {f:.0%} of its travel: {len(new)} new overlapping pairs" + (": " + ", ".join(names[:6]) if names else ""))
            if new:
                problems.append(f"{h.name} at {f:.0%}: touches {', '.join(sorted({b for _, b in new})[:5])}")
        set_pose(h, 0.0)
    return problems


def max_clear_angle(node, step=math.radians(2), report=print, direction=1):
    """How far a hinged part turns (direction +1 or -1) before it first touches something it didn't at rest, or
    reaches its limit; returns (angle, what it touches)."""
    mine = [x for x in [node] + descendants(node) if x.type == "MESH"]
    rest = [o for o in bpy.data.objects if o.type == "MESH" and o not in mine]
    set_pose(node, 0.0)
    base = overlap_pairs(mine, rest)
    lo, hi = node["limits"]
    limit = hi if direction > 0 else lo
    a = 0.0
    while abs(a) < abs(limit):
        nxt = a + direction * step
        if abs(nxt) > abs(limit):
            nxt = limit
        set_pose(node, nxt)
        new = overlap_pairs(mine, rest) - base
        if new:
            set_pose(node, 0.0)
            return a, sorted({b for _, b in new})
        a = nxt
    set_pose(node, 0.0)
    return limit, []
