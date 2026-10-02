"""Beauty renders of a finished vehicle (its exported glTF, exactly as
delivered) on the concrete pad under a physical sky, in Cycles.

    python modelkit/beauty.py VEHICLE_DIR MODEL.glb OUT_DIR [--views a,b] [--samples N] [--res WxH]

The cameras come from VEHICLE_DIR/build.py: BEAUTY if it has one, else VIEWS,
each (camera, target, lens[, groups to open[, {node: amount}]]). Doors,
hatches and ramps open by the `group` in their glTF extras; the dict poses
anything else that moves (a crane slewed and raised, its hook let down): an
angle about the node's `axis`, or for a `slide` a distance along it."""
import sys
import os
import time
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector, Matrix

from geom import B
from staging import stage, camera, render


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def views_of(vdir):
    """Read the cameras out of the vehicle's build.py without running its build."""
    import ast
    src = open(os.path.join(vdir, "build.py")).read()
    tree = ast.parse(src)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) in ("VIEWS", "BEAUTY"):
            found[node.targets[0].id] = ast.literal_eval(node.value)
    return found.get("BEAUTY") or found["VIEWS"]


REST = {}
HANG = []


def hang(o, drop):
    """A hook on its cable: plumb under the point it hangs from at rest, `drop` metres down, upright."""
    w0 = REST[o.name + "#"]["world"]
    o.location = REST[o.name]
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = (1, 0, 0, 0)
    bpy.context.view_layer.update()
    at = o.matrix_world.translation.copy() - Vector((0, 0, drop))  # Blender's Z is up
    o.matrix_world = Matrix.Translation(at) @ w0.to_3x3().to_4x4()


def open_groups(groups, poses=None):
    poses = poses or {}
    HANG.clear()
    for o in bpy.data.objects:  # where each hook hangs at rest, before anything moves
        if o.get("gravity") and o.name + "#" not in REST:
            REST[o.name + "#"] = {"world": o.matrix_world.copy()}
    for o in bpy.data.objects:
        if "axis" not in o.keys():
            continue
        REST.setdefault(o.name, o.location.copy())
        a = list(o["axis"])
        if o.get("control") == "slide":
            v = poses.get(o.name, 0.0) if o.name in poses else (o["limits"][1] if o.get("group") in groups else 0.0)
            if o.get("gravity"):
                HANG.append((o, v))  # placed once everything above it has moved
                continue
            o.location = REST[o.name] + Vector(B(a)) * v
            continue
        if o.name in poses:
            angle = poses[o.name]
        elif o.get("control") == "hinge":
            lo, hi = o["limits"]
            angle = hi if o.get("group") in groups else lo
        else:
            continue
        o.rotation_mode = "AXIS_ANGLE"
        o.rotation_axis_angle = (angle, *B(a))
    bpy.context.view_layer.update()
    for o, v in HANG:
        hang(o, v)
    bpy.context.view_layer.update()


def main():
    vdir, glb, out = sys.argv[1], sys.argv[2], sys.argv[3]
    views = views_of(vdir)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb)
    stage(scene, ground_y=0.0)
    os.makedirs(out, exist_ok=True)
    w, h = (int(v) for v in arg("--res", "1600x900").split("x"))
    for name in (arg("--views") or ",".join(views)).split(","):
        v = views[name]
        loc, target, lens = v[:3]
        open_groups(v[3] if len(v) > 3 else [], v[4] if len(v) > 4 else None)
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        t = time.time()
        render(scene, os.path.join(out, name + ".png"), int(arg("--samples", 64)), (w, h))
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
