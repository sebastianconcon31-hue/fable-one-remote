"""Builds the AH-64 crew helmet in Blender (Python 3.11 with the bpy module: pip install bpy==5.0.1 pillow).

    python apache-helmet/build.py [--glb FILE] [--textures N] [--preview DIR [--views a,b]] [--blend FILE] [--head]"""
import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

import bpy
import numpy as np

from helmet import *
import parts
import look
import paint
import vehicle
from vehicle import principled, arg, localize, stats, points
from geom import empty, B
from staging import camera, render

ROOT = "AH64_Helmet"
NOTES = {
    "vehicle": "AH-64 crew helmet: HGU-56/P with the IHADSS display",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the wearer's left",
    "origin": "the wearer's head centre: midway between the ear canals",
    "stand": "bench",
    "blurb": "HGU-56/P with the IHADSS display and boom microphone, at 1:1.",
    "weapon": "Helmet",
    "display_fov_deg": [40.0, 30.0],
    "display_exit_pupil_m": 0.010,
    "display_eye_relief_m_est": 0.028,
    "published_mass_kg": 1.338,
}


def materials(display_png=None):
    M = {
        "shell": principled("Helmet_Shell", (0.105, 0.125, 0.062), 0.62),
        "shell_inner": principled("Helmet_Shell_Inner", (0.05, 0.055, 0.04), 0.7),
        "rubber": principled("Helmet_Rubber", (0.012, 0.012, 0.012), 0.8),
        "plastic": principled("Helmet_Plastic", (0.014, 0.014, 0.015), 0.42),
        "hdu": principled("HDU_Anodized", (0.016, 0.016, 0.017), 0.38, 0.5),
        "metal": principled("Helmet_Metal", (0.45, 0.45, 0.44), 0.36, 1.0),
        "foam": principled("Helmet_Foam", (0.010, 0.010, 0.010), 0.95),
        "fabric": principled("Helmet_Fabric", (0.022, 0.024, 0.019), 0.92),
        "liner": principled("Helmet_Liner", (0.30, 0.30, 0.28), 0.88),
        "visor_clear": principled("Visor_Clear", (0.9, 0.95, 0.95), 0.02, alpha=0.10),
        "visor_tint": principled("Visor_Tinted", (0.012, 0.013, 0.012), 0.02, alpha=0.82),
        "combiner": principled("HDU_Combiner", (0.04, 0.16, 0.06), 0.02, alpha=0.30),
        "display": principled("HDU_Display", (0.0, 0.0, 0.0), 0.5, emit=(0.2, 1.0, 0.3), strength=1.0),
        "led": principled("Light_IR", (0.07, 0.012, 0.02), 0.06),
    }
    if display_png:
        picture(M["display"], display_png)
    return M


def picture(mat, path):
    """The display's material: the picture, lit from within (the helmet display is a screen, not a surface)."""
    nt = mat.node_tree
    p = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    im = nt.nodes.new("ShaderNodeTexImage")
    im.image = bpy.data.images.load(path)
    im.image.colorspace_settings.name = "sRGB"
    im.extension = "CLIP"
    nt.links.new(uv.outputs["UV"], im.inputs["Vector"])
    nt.links.new(im.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.0
    p.inputs["Base Color"].default_value = (0, 0, 0, 1)


def build(M, root):
    sh, rings, nrm = parts.shell(M, root)
    parts.rim_trim(M, root, rings, nrm)
    parts.ear_domes(M, root)
    parts.liner(M, root, rings, nrm)
    parts.earcups(M, root)
    parts.visor_housing(M, root)
    parts.pivots(M, root)
    parts.visor(M, root, "Visor_Clear", R_CLEAR, "visor_clear")
    parts.visor(M, root, "Visor_Tinted", R_TINT, "visor_tint")
    parts.hdu(M, root)
    parts.mic_mount(M, root)
    parts.mic(M, root)
    parts.emitters(M, root)
    parts.chin_strap(M, root)
    parts.nape(M, root)
    parts.cords(M, root)
    parts.eyes(root)


VIEWS = {
    "front34": ((0.42, 0.20, 0.55), (0, 0.03, 0.04), 50),
    "right34": ((-0.45, 0.16, 0.52), (-0.02, 0.02, 0.04), 50),
    "side": ((0.8, 0.02, 0.05), (0, 0.02, 0.03), 50),
    "rightside": ((-0.8, 0.02, 0.05), (0, 0.02, 0.03), 50),
    "top": ((0.0, 0.9, 0.05), (0, 0.0, 0.0), 50),
    "back34": ((-0.45, 0.2, -0.55), (0, 0.0, -0.02), 50),
    "front": ((0.0, 0.03, 0.9), (0, 0.03, 0.0), 50),
}


def pose(spec):
    """--pose Node=radians,... : turn hinged nodes for a preview."""
    for item in (spec or "").split(","):
        if not item:
            continue
        name, v = item.split("=")
        o = bpy.data.objects[name]
        o.rotation_mode = "AXIS_ANGLE"
        o.rotation_axis_angle = (float(v), *B(list(o["axis"])))
    bpy.context.view_layer.update()


def measure():
    """The finished helmet against what is published: the display's field of view, seen from the right eye."""
    import fit
    pts = fit.world_points(bpy.data.objects["HDU_Screen"])  # top left, top right, bottom right, bottom left
    mid = lambda a, b: (pts[a] + pts[b]) / 2
    ang = lambda a, b: float(np.degrees(np.arccos(np.clip(np.dot((a - EYE_R) / np.linalg.norm(a - EYE_R), (b - EYE_R) / np.linalg.norm(b - EYE_R)), -1, 1))))
    return [
        ("Display field of view, horizontal (angle)", SPEC["fovH"], ang(mid(0, 3), mid(1, 2))),
        ("Display field of view, vertical (angle)", SPEC["fovV"], ang(mid(0, 1), mid(3, 2))),
    ]


def export_scene(path):
    vehicle.export(ROOT, path)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    glb = arg("--glb")
    tex = arg("--texdir", os.path.join(os.path.dirname(os.path.abspath(glb)), "textures") if glb else os.path.join(HERE, "textures"))
    os.makedirs(tex, exist_ok=True)
    import display
    M = materials(display.draw(os.path.join(tex, "hdu_display.png")))
    root = empty(ROOT, (0, 0, 0))
    for k, v in NOTES.items():
        root[k] = v
    build(M, root)
    bpy.context.view_layer.update()
    localize()
    n, tris = stats()
    print(f"built {n} meshes, {tris:,} triangles", flush=True)
    rows = measure()
    print("1:1 check (published / model; angles in degrees):")
    for k, want, got in rows:
        print(f"  {k:44s} {want:7.3f}  {got:7.3f}  {'ok' if abs(got - want) < 0.5 else 'OFF BY %.3f' % (got - want)}")
    pose(arg("--pose"))
    if "--fit" in sys.argv:
        import fit
        rr, problems = fit.head_clearance()
        print("closest each part comes to the head (mm; negative = inside):")
        for name, d in sorted(rr, key=lambda r: r[1])[:24]:
            print(f"  {name:34s} {d * 1000:7.1f}")
        problems += fit.hinge_clearance()
        print("problems:" if problems else "no problems")
        for x in problems:
            print("  ", x)
    paint.RESUME = "--resume" in sys.argv
    if glb:
        import json
        with open(os.path.join(os.path.dirname(os.path.abspath(glb)), "measurements.json"), "w") as f:
            json.dump({"units": "metres; angles in degrees", "published_vs_model": [{"dimension": k, "published": round(float(w), 4), "model": round(float(g), 4), "unit": "deg"} for k, w, g in rows],
                       "triangles": int(tris), "meshes": int(n)}, f, indent=1)
        if "--raw" not in sys.argv:
            bake_all(scene, M, tex, int(arg("--textures", 4096)))
        export_scene(glb)
    prev = arg("--preview")
    if prev:
        import studio
        studio.stage(scene)
        os.makedirs(prev, exist_ok=True)
        for name in (arg("--views") or ",".join(VIEWS)).split(","):
            loc, target, lens = VIEWS[name]
            scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
            t = time.time()
            render(scene, os.path.join(prev, name + ".png"), int(arg("--samples", 16)), (800, 600))
            print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)
    blend = arg("--blend")
    if blend:
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)


# the studio renders: (camera, target, lens, {hinge: radians}); the display's own view is from the eye
BEAUTY = {
    "hero": ((-0.30, 0.16, 0.78), (0.0, 0.03, 0.03), 52, {"Visor_Tinted": 0.73}),
    "front": ((0.0, 0.05, 0.9), (0.0, 0.03, 0.0), 50, {}),
    "right": ((-0.85, 0.06, 0.18), (0.0, 0.03, 0.02), 50, {"Visor_Tinted": 0.73, "Visor_Clear": 0.73}),
    "left": ((0.85, 0.05, 0.12), (0.0, 0.0, 0.03), 50, {}),
    "rear": ((-0.35, 0.18, -0.85), (0.0, 0.0, -0.02), 50, {}),
    "top": ((0.0, 0.95, 0.04), (0.0, 0.0, 0.0), 50, {}),
    "visors": ((0.55, 0.22, 0.6), (0.0, 0.05, 0.05), 50, {"Visor_Tinted": 0.73, "Visor_Clear": 0.73}),
    "monocle": ((-0.012, 0.034, 0.040), (-0.034, 0.026, 0.12), 38, {"Visor_Tinted": 0.73, "Visor_Clear": 0.73}),
    "mic": ((0.30, -0.02, 0.50), (0.02, -0.04, 0.10), 55, {"Visor_Tinted": 0.73}),
}

# ---- finish: the surface sets, baked ----------------------------------------------------------------------------------
# GROUPS: (label, [material keys], size divisor); the bake takes the build's --textures size divided by it
GROUPS = [
    ("Helmet_Shell", ["shell", "shell_inner"], 1),
    ("Helmet_Gear", ["plastic", "hdu", "metal", "rubber"], 1),
    ("Helmet_Soft", ["fabric", "foam", "liner"], 2),
]
SPECS = {
    # the composite shell's sage-green paint, rubbed at the edges and scuffed where a helmet bag and a cockpit rub it
    "shell": dict(c=(0.105, 0.125, 0.062), r=0.6, m=0.0, wear=(0.20, 0.19, 0.14), wm=0.0, scuff=0.55, grime=1.0),
    "shell_inner": dict(c=(0.045, 0.05, 0.036), r=0.72, m=0.0, wear=(0.12, 0.12, 0.1), wm=0.0, grime=1.4),
    "plastic": dict(c=(0.014, 0.014, 0.015), r=0.34, m=0.0, wear=(0.06, 0.06, 0.06), wm=0.0, scuff=0.45, grime=0.8),
    "hdu": dict(c=(0.016, 0.016, 0.017), r=0.4, m=0.55, wear=(0.18, 0.18, 0.18), wm=1.0, scuff=0.2, edge_r=0.0006),
    "metal": dict(c=(0.42, 0.42, 0.40), r=0.34, m=1.0, wear=(0.55, 0.55, 0.53), wm=1.0, scuff=0.3, edge_r=0.0006),
    "rubber": dict(c=(0.012, 0.012, 0.012), r=0.8, m=0.0, wear=(0.035, 0.035, 0.033), wm=0.0, scuff=0.25),
    "fabric": dict(c=(0.020, 0.022, 0.017), r=0.92, m=0.0, wear=(0.05, 0.052, 0.045), wm=0.0, weave=900.0, bump=0.8, bump_d=0.0006, grime=1.4, fine=1500.0),
    "foam": dict(c=(0.010, 0.010, 0.010), r=0.95, m=0.0, wear=(0.03, 0.03, 0.03), wm=0.0, fine=2500.0, bump=0.6),
    "liner": dict(c=(0.30, 0.30, 0.28), r=0.9, m=0.0, wear=(0.4, 0.4, 0.37), wm=0.0, fine=2200.0, bump=0.7, grime=0.8),
}
HIDE_MATS = {"Visor_Clear", "Visor_Tinted", "HDU_Combiner", "HDU_Display"}


def bake_all(scene, M, tex, size):
    t0 = time.time()
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 0.5
    hide = {o.name for o in bpy.data.objects if o.type == "MESH" and o.material_slots and all(s.material and s.material.name in HIDE_MATS for s in o.material_slots)}
    for label, keys, div in GROUPS:
        mats = [M[k] for k in keys]
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, mats, all_mats, size // div, tex, lambda ao, keys=keys: [look.surface(M[k], SPECS[k], ao) for k in keys], ao_samples=48, extra_hide=hide)
        paint.textured(mats[0], paths)
        mats[0].name = label
        paint.merge_slots(mats[0], mats[1:])
    print(f"baked in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
