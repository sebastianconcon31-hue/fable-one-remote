"""Builds the 5-inch freestyle FPV quad in Blender (Python 3.11 with the bpy
module: pip install bpy==5.0.1 pillow shapely).

    python3.11 fpv-drone/build.py [--glb FILE] [--blend FILE] [--preview DIR [--views a,b] [--samples N] [--res WxH]]

--glb exports the game model and writes measurements.json beside it; --preview renders the views below."""
import sys
import os
import json
import math
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

import bpy
import numpy as np

from drone import *
import parts
import textures
import vehicle
from vehicle import principled, lights_materials, points, node_pos, span, localize, stats, export, arg
from geom import empty
from staging import stage

ROOT = "FPV_Quad"
NOTES = {
    "vehicle": "5-inch freestyle FPV quadcopter",
    "blurb": "Carbon frame, four 2306 motors with tri-blade props, a 6S pack, a 19 mm camera, at 1:1.",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front (the camera), +X to the left",
    "origin": "the middle of the frame: on the centreline, halfway between the plates, where the motor diagonals cross",
    "mass_kg": MASS_KG,
    "motor_diagonal_m": SPEC["motorDiagonal"],
    "prop_diameter_m": SPEC["propDiameter"],
    "camera_tilt_deg": SPEC["cameraTilt"],
    "rotors": "Rotor_FL, Rotor_FR, Rotor_RL, Rotor_RR: each turns about its local Y; extras `spin` is +1 for counter-clockwise seen from above",
}


def textured(name, path, rough=0.5, metal=0.0):
    m = principled(name, (0.5, 0.5, 0.5), rough, metal)
    nt = m.node_tree
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(path)
    img.image.colorspace_settings.name = "sRGB"
    nt.links.new(img.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m


def materials(texdir):
    T = textures.make(texdir)
    M = {
        "carbon": textured("Quad_Carbon", T["carbon"], 0.36),
        "battery": textured("Quad_Battery_Label", T["battery"], 0.55),
        "alu_black": principled("Quad_Alu_Black", (0.012, 0.012, 0.014), 0.34, 0.9),
        "titanium": principled("Quad_Titanium", (0.45, 0.42, 0.38), 0.3, 1.0),
        "gold": principled("Quad_Gold", (0.80, 0.55, 0.12), 0.3, 1.0),
        "copper": principled("Quad_Copper", (0.65, 0.26, 0.10), 0.4, 1.0),
        "pcb": principled("Quad_PCB", (0.006, 0.02, 0.012), 0.5),
        "chip": principled("Quad_Chip", (0.006, 0.006, 0.007), 0.4),
        "cap": principled("Quad_Capacitor", (0.02, 0.02, 0.025), 0.35, 0.5),
        "connector": principled("Quad_Connector", (0.55, 0.55, 0.5), 0.5),
        "bell": principled("Quad_Motor_Bell", (0.01, 0.07, 0.55), 0.28, 0.9),
        "bell_dark": principled("Quad_Motor_Vent", (0.004, 0.004, 0.005), 0.6),
        "rubber": principled("Quad_Rubber", (0.012, 0.012, 0.012), 0.9),
        "strap": principled("Quad_Strap", (0.008, 0.008, 0.009), 0.92),
        "strap_tab": principled("Quad_Strap_Tab", (0.42, 0.09, 0.006), 0.7),
        "wire": principled("Quad_Wire", (0.01, 0.01, 0.011), 0.55),
        "wire_red": principled("Quad_Wire_Red", (0.55, 0.02, 0.02), 0.5),
        "connector_yellow": principled("Quad_XT60", (0.55, 0.32, 0.0), 0.45),
        "tpu": principled("Quad_TPU", (0.5, 0.1, 0.004), 0.55),
        "cam_plastic": principled("Quad_Camera", (0.01, 0.01, 0.012), 0.45),
        "optic": principled("Quad_Optic_Glass", (0.01, 0.015, 0.04), 0.04, 0.6),
        "prop_front": principled("Quad_Prop_Front", (0.46, 0.48, 0.47), 0.45),
        "prop_rear": principled("Quad_Prop_Rear", (0.02, 0.022, 0.025), 0.45),
    }
    L = lights_materials()
    M["light_white"], M["light_red"] = L["light_white"], L["light_red"]
    return M


def measure():
    allp = points(ROOT)
    fl, rr, fr = node_pos("Rotor_FL"), node_pos("Rotor_RR"), node_pos("Rotor_FR")
    pr = points("Rotor_FL_Prop")
    rad = np.hypot(pr[:, 0] - fl[0], pr[:, 2] - fl[2]).max()
    so = {k: points(f"Standoff_{k}") for k in ("FL", "FR", "RL", "RR")}
    ctr = {k: (p.max(axis=0) + p.min(axis=0)) / 2 for k, p in so.items()}
    bat, cam, plate = points("Battery"), points("Camera_Body"), points("Frame_Bottom")
    rows = [
        ("Motor to motor, diagonal", SPEC["motorDiagonal"], float(np.hypot(*(fl - rr)[[0, 2]]))),
        ("Motor to motor, side by side", SPEC["motorDiagonal"] / math.sqrt(2), float(abs(fl[0] - fr[0]))),
        ("Prop diameter", SPEC["propDiameter"], float(2 * rad)),
        ("Stack mount (standoff to standoff)", SPEC["stackMount"], float(abs(ctr["FL"][0] - ctr["FR"][0]))),
        ("Plate gap (standoff length)", SPEC["plateGap"], span(so["FL"], 1)),
        ("Arm thickness", SPEC["armThickness"], span(plate, 1)),
        ("Battery length", SPEC["batteryLength"], span(bat, 2)),
        ("Battery width", SPEC["batteryWidth"], span(bat, 0)),
        ("Battery height", SPEC["batteryHeight"], span(bat, 1)),
        ("Camera width", SPEC["cameraWidth"], span(cam, 0)),
    ]
    return rows, float(allp[:, 1].min()), allp


def report(rows, low):
    print("size check (nominal / model, metres):")
    for k, want, got in rows:
        print(f"  {k:40s} {want:7.4f}  {got:7.4f}  {'ok' if abs(got - want) < 0.0006 else 'OFF BY %.4f' % (got - want)}")
    print(f"  lowest point below the origin: {low:.4f} m")


# ---- audit ---------------------------------------------------------------------------------------------------------------------
def audit():
    """What a game engine will run into. Returns a list of problems (empty if none)."""
    import bmesh
    bad = []
    names = [o.name for o in bpy.data.objects]
    if len(names) != len(set(names)):
        bad.append("duplicate node names")
    roots = [o for o in bpy.data.objects if o.parent is None]
    if len(roots) != 1 or roots[0].name != ROOT:
        bad.append(f"expected one root, found {[o.name for o in roots]}")
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        vol = bm.calc_volume(signed=True)
        tiny = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)  # walls and caps carry their own vertices, for flat shading
        open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        bm.free()
        if vol < 0:
            bad.append(f"{o.name}: faces point inward (signed volume {vol:.3e})")
        if tiny:
            bad.append(f"{o.name}: {tiny} zero-area faces")
        if open_edges and "Vent" not in o.name and not o.name.endswith("_Bell"):
            bad.append(f"{o.name}: {open_edges} open edges")
        if any(s.material and s.material.node_tree and any(n.type == "TEX_IMAGE" for n in s.material.node_tree.nodes) for s in o.material_slots) and not me.uv_layers:
            bad.append(f"{o.name}: wears an image but has no UVs")
    for tag, mo in MOTORS.items():
        r = bpy.data.objects[f"Rotor_{tag}"]
        for part in ("Bell", "Prop", "Nut"):
            ch = bpy.data.objects[f"Rotor_{tag}_{part}"]
            co = np.array([v.co[:] for v in ch.data.vertices])
            c = co.mean(axis=0)  # a 3-blade prop's bounding box is off its axis; its vertices' mean is not
            if abs(c[0]) > 0.001 or abs(c[1]) > 0.001:  # Blender x, y: the model's x and z, relative to the rotor's pivot
                bad.append(f"Rotor_{tag}_{part}: off its motor axis by ({c[0] * 1000:.1f}, {-c[1] * 1000:.1f}) mm")
        if r.get("spin") != mo["spin"]:
            bad.append(f"Rotor_{tag}: no spin extra")
    # the props must clear one another, and the camera and battery
    for a in MOTORS.values():
        for b2 in MOTORS.values():
            if a is not b2:
                d = math.hypot(a["pos"][0] - b2["pos"][0], a["pos"][1] - b2["pos"][1])
                if d < SPEC["propDiameter"] + 0.005:
                    bad.append(f"props {d * 1000:.0f} mm apart: they overlap")
    return bad


# ---- previews ------------------------------------------------------------------------------------------------------------------
VIEWS = {
    "hero": ((0.30, 0.20, 0.40), (0.0, 0.012, -0.004), 55),
    "side": ((0.62, 0.016, 0.0), (0.0, 0.016, -0.012), 60),
    "front": ((0.0, 0.05, 0.62), (0.0, 0.012, 0.0), 60),
    "rear": ((-0.28, 0.17, -0.36), (0.0, 0.012, -0.015), 55),
    "top": ((0.001, 0.62, 0.0), (0.0, 0.0, -0.01), 60),
    "under": ((0.24, -0.30, 0.26), (0.0, -0.005, 0.0), 55),
    "motor": ((0.14, 0.07, 0.19), (0.078, 0.0, 0.078), 70),
    "stack": ((0.10, 0.15, 0.115), (0.0, 0.0, 0.0), 75),
    "camera": ((0.07, 0.05, 0.16), (0.0, 0.003, 0.064), 70),
}


NO_FLOOR = {"under"}  # seen from below, with the floor taken away
CUTAWAY = {"stack": ["Frame_Top", "Battery", "Battery_Pad", "Battery_Strap", "Battery_Lead", "Battery_XT60"]}  # taken off to show the stack


def render_views(scene, out, which, res, samples):
    from staging import camera, render
    os.makedirs(out, exist_ok=True)
    ground = bpy.data.objects["Ground"]
    for name in which:
        loc, target, lens = VIEWS[name]
        ground.hide_render = name in NO_FLOOR
        for part in sum(CUTAWAY.values(), []):
            bpy.data.objects[part].hide_render = part in CUTAWAY.get(name, [])
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        render(scene, os.path.join(out, name + ".png"), samples, res)
        print(f"rendered {name}", flush=True)


def studio(ground):
    """Replace the pad with a plain, matte, mid-grey floor, so the small thing reads against it."""
    mat = principled("Studio_Floor", (0.16, 0.165, 0.17), 0.78)
    ground.data.materials.clear()
    ground.data.materials.append(mat)


def run():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    texdir = arg("--texdir") or tempfile.mkdtemp(prefix="quad_tex_")
    M = materials(texdir)
    root = empty(ROOT, (0, 0, 0))
    for k, v in NOTES.items():
        root[k] = v
    ground_ref = empty("Ground_Reference", (0, 0, 0), root)
    ground_ref["marker"] = "the lowest point: where the quad rests on a floor"
    parts.build(M, root)
    bpy.context.view_layer.update()
    localize()
    n, tris = stats()
    print(f"built {n} meshes, {tris:,} triangles", flush=True)
    rows, low, allp = measure()
    report(rows, low)
    from geom import B
    ground_ref.location = B((0, low, 0))
    root["height_m"] = round(float(allp[:, 1].max() - low), 4)
    root["length_m"] = round(float(allp[:, 2].max() - allp[:, 2].min()), 4)
    root["width_m"] = round(float(allp[:, 0].max() - allp[:, 0].min()), 4)
    print(f"  overall: {root['width_m']:.3f} wide x {root['length_m']:.3f} long x {root['height_m']:.3f} high (with the antennas)")
    bpy.context.view_layer.update()

    problems = audit()
    print(f"audit: {len(problems)} problems" + "".join(f"\n  - {p}" for p in problems), flush=True)

    glb = arg("--glb")
    if glb:
        with open(os.path.join(os.path.dirname(os.path.abspath(glb)), "measurements.json"), "w") as f:
            json.dump({"units": "metres", "nominal_vs_model": [{"dimension": k, "nominal": round(float(w), 4), "model": round(float(g), 4), "unit": "m"} for k, w, g in rows],
                       "lowest_point_below_origin": round(low, 4), "overall": {"width": root["width_m"], "length": root["length_m"], "height": root["height_m"]},
                       "triangles": int(tris), "meshes": int(n)}, f, indent=1)
        export(ROOT, glb)

    prev = arg("--preview")
    if prev:
        stage(scene, ground_y=low)
        studio(bpy.data.objects["Ground"])
        res = tuple(int(v) for v in (arg("--res") or "960x540").split("x"))
        which = (arg("--views") or ",".join(VIEWS)).split(",")
        render_views(scene, prev, which, res, int(arg("--samples", 24)))
    blend = arg("--blend")
    if blend:
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)


if __name__ == "__main__":
    run()
