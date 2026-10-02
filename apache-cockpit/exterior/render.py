"""Beauty renders of the finished aircraft (the merged glTF, exactly as delivered),
on a concrete pad under a physical sky, in Cycles.

    python exterior/render.py apache_ah64d.glb OUT_DIR [--views a,b] [--samples N] [--res WxH] [--blend FILE]"""
import sys
import os
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "modelkit"))  # geometry, paint and baking shared with the other models
import bpy
from mathutils import Vector

from geom import B
import ah64
from staging import concrete, stage as _stage, camera


def stage(scene, **kw):
    return _stage(scene, ground_y=ah64.GROUND_Y, **kw)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


VIEWS = {
    "hero": ((8.6, 0.9, 7.4), (0.2, 0.9, -2.8), 30),
    "side": ((15.5, 1.3, -4.6), (0, 1.25, -4.6), 26),
    "rear": ((-9.0, 3.4, -16.0), (0, 1.3, -5.5), 30),
    "front": ((1.6, 1.25, 11.0), (0, 0.95, 0), 30),
    "nose": ((2.1, 1.15, 4.5), (0, 0.45, 1.3), 30),
    "rotorhead": ((2.6, 4.2, 0.4), (0, 2.75, -2.9), 30),
    "engine": ((3.6, 2.6, -6.6), (0.8, 1.4, -3.9), 30),
    "tail": ((-3.4, 2.1, -15.0), (0, 1.6, -11.8), 30),
    "weapons": ((3.7, 0.4, -0.6), (1.6, 0.25, -2.6), 30),
    "cockpit": ((-1.5, 1.75, 1.8), (0, 1.05, -0.3), 26),
    "top": ((0.01, 24, -4.5), (0, 0, -4.5), 30),
}


def main():
    glb, out = sys.argv[1], sys.argv[2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb)
    stage(scene)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(arg("--samples", 96))
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.transparent_max_bounces = 16
    w, h = (int(v) for v in arg("--res", "1600x900").split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    os.makedirs(out, exist_ok=True)
    for name in (arg("--views") or "hero,side,rear,nose,rotorhead,engine,tail,weapons,cockpit").split(","):
        loc, target, lens = VIEWS[name]
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        scene.render.filepath = os.path.join(out, name + ".png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)
    if arg("--blend"):
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=arg("--blend"), compress=True)


if __name__ == "__main__":
    main()
