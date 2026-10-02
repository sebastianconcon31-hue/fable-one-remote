"""Studio renders of the finished helmet (its exported glTF, as delivered) in Cycles.

    python apache-helmet/render.py MODEL.glb OUT_DIR [--views a,b] [--samples N] [--res WxH]

The cameras and poses come from BEAUTY in build.py: each (camera, target, lens[, {node: radians}])."""
import sys
import os
import time
import ast
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))
sys.path.insert(0, HERE)
import bpy

from geom import B
from staging import camera, render
import studio


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def beauty():
    tree = ast.parse(open(os.path.join(HERE, "build.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "BEAUTY":
            return ast.literal_eval(node.value)


def pose(poses):
    for o in bpy.data.objects:
        if "axis" in o.keys() and o.get("control") == "hinge":
            o.rotation_mode = "AXIS_ANGLE"
            o.rotation_axis_angle = (poses.get(o.name, 0.0), *B(list(o["axis"])))
    bpy.context.view_layer.update()


def main():
    glb, out = sys.argv[1], sys.argv[2]
    views = beauty()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb)
    studio.stage(scene)
    os.makedirs(out, exist_ok=True)
    w, h = (int(v) for v in arg("--res", "1600x1200").split("x"))
    for name in (arg("--views") or ",".join(views)).split(","):
        v = views[name]
        loc, target, lens = v[:3]
        pose(v[3] if len(v) > 3 else {})
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        t = time.time()
        render(scene, os.path.join(out, name + ".png"), int(arg("--samples", 96)), (w, h))
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
