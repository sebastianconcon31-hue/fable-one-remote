"""Beauty renders of a finished vehicle (its exported glTF, exactly as
delivered) on the concrete pad under a physical sky, in Cycles.

    python modelkit/beauty.py VEHICLE_DIR MODEL.glb OUT_DIR [--views a,b] [--samples N] [--res WxH]

The cameras come from VEHICLE_DIR/build.py: BEAUTY if it has one, else VIEWS,
each (camera, target, lens[, groups to open]). Doors, hatches and ramps open
by the `group` in their glTF extras."""
import sys
import os
import time
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector

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


def open_groups(groups):
    for o in bpy.data.objects:
        if o.get("control") == "hinge":
            f = 1.0 if o.get("group") in groups else 0.0
            lo, hi = o["limits"]
            a = list(o["axis"])
            o.rotation_mode = "AXIS_ANGLE"
            o.rotation_axis_angle = (lo + (hi - lo) * f, *B(a))
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
        open_groups(v[3] if len(v) > 3 else [])
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        t = time.time()
        render(scene, os.path.join(out, name + ".png"), int(arg("--samples", 64)), (w, h))
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
