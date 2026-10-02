"""Beauty renders of the finished truck (the exported glTF, exactly as delivered)
on a concrete pad under a physical sky, in Cycles.

    python hemtt-m977/render.py hemtt_m977a4.glb OUT_DIR [--views a,b] [--samples N] [--res WxH]"""
import sys
import os
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))
import bpy
from staging import stage, camera, render


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


VIEWS = {
    "hero": ((7.4, 1.5, 10.2), (0.0, 1.35, 0.2), 30),
    "side": ((15.5, 1.7, -0.4), (0, 1.45, -0.4), 30),
    "rear": ((-6.6, 3.8, -12.2), (0, 1.35, -1.4), 30),
    "cab": ((3.4, 2.1, 7.4), (0, 1.75, 3.3), 30),
    "wheels": ((3.4, 0.75, 4.4), (1.0, 0.68, 1.2), 28),
    "crane": ((-6.0, 2.6, -9.5), (-0.6, 2.4, -3.6), 30),
}


def working_pose():
    """Crane swung out with a pallet on the hook, for the crane shot."""
    O = bpy.data.objects
    def rot(name, axis, angle):
        o = O.get(name)
        if o is None:
            return
        o.rotation_mode = "AXIS_ANGLE"
        # glTF local axes (x, y, z) are Blender's (x, -z, y) once imported
        bx = {"x": (1, 0, 0), "y": (0, 0, 1), "z": (0, -1, 0)}[axis]
        o.rotation_axis_angle = (angle, *bx)
    rot("Crane", "y", -1.25)
    rot("Crane_Boom", "x", -0.62)
    rot("Crane_Hook", "x", 0.62)
    p = O.get("Cargo_Pallet_8")
    hook = O.get("Crane_Hook")
    if p and hook:
        bpy.context.view_layer.update()
        hw = hook.matrix_world.translation
        p.location = (hw.x - p.parent.matrix_world.translation.x, hw.y - p.parent.matrix_world.translation.y, hw.z - p.parent.matrix_world.translation.z - 0.9)


def main():
    glb, out = sys.argv[1], sys.argv[2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb)
    stage(scene, ground_y=0.0)
    os.makedirs(out, exist_ok=True)
    w, h = (int(v) for v in arg("--res", "1600x900").split("x"))
    for name in (arg("--views") or ",".join(VIEWS)).split(","):
        if name == "crane":
            working_pose()
        loc, target, lens = VIEWS[name]
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        t = time.time()
        render(scene, os.path.join(out, name + ".png"), int(arg("--samples", 96)), (w, h))
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
