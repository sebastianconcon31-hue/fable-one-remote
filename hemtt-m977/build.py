"""Builds the HEMTT M977A4 cargo truck in Blender (Python 3.11 with the bpy
module: pip install bpy==5.0.1 pillow).

    python hemtt-m977/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]]

--glb bakes the paint and exports the model (and measurements.json beside it);
--blend saves the Blender scene; --preview renders quick views (--lookdev
shows the procedural paint without baking)."""
import sys
import os
import math
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

import bpy
import numpy as np
from mathutils import Vector, Matrix

from geom import B, empty
import m977
from m977 import SPEC, AXLES_Z, TYRE_R
import truck
import markings
import paint


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def principled(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        p.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    return {
        "paint": principled("HEMTT_Paint", GREEN, 0.62),
        "chassis": principled("HEMTT_Chassis", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("HEMTT_Rubber", (0.016, 0.016, 0.015), 0.86),
        "interior": principled("HEMTT_Cab_Interior", (0.012, 0.012, 0.012), 0.6),
        "glass": principled("HEMTT_Glass", (0.02, 0.025, 0.025), 0.02, alpha=0.55),
        "mirror": principled("HEMTT_Mirror", (0.85, 0.85, 0.85), 0.03, 1.0),
        "exhaust": principled("HEMTT_Exhaust", (0.03, 0.025, 0.02), 0.7, 0.4),
        "steel": principled("HEMTT_Steel", (0.62, 0.62, 0.6), 0.18, 1.0),
        "hazard": principled("HEMTT_Hazard_Yellow", (0.5, 0.33, 0.01), 0.55),
        "light_white": principled("Light_White", (0.8, 0.8, 0.78), 0.08, emit=(1, 0.97, 0.9), strength=1.0),
        "light_amber": principled("Light_Amber", (0.6, 0.3, 0.02), 0.08, emit=(1, 0.5, 0.05), strength=1.0),
        "light_red": principled("Light_Red", (0.5, 0.03, 0.02), 0.08, emit=(1, 0.05, 0.03), strength=1.0),
        "wood": principled("HEMTT_Cargo_Wood", (0.3, 0.2, 0.11), 0.78),
        "drum": principled("HEMTT_Cargo_Drum", (0.05, 0.055, 0.03), 0.5),
        "ammo_can": principled("HEMTT_Cargo_Ammo_Can", (0.042, 0.048, 0.026), 0.45),
        "crate": principled("HEMTT_Cargo_Crate", (0.2, 0.135, 0.07), 0.8),
        "strap": principled("HEMTT_Cargo_Strap", (0.55, 0.16, 0.02), 0.72),
        "cardboard": principled("HEMTT_Cargo_Cardboard", (0.36, 0.26, 0.15), 0.85),
        "wrap": principled("HEMTT_Cargo_Stretch_Wrap", (0.8, 0.82, 0.82), 0.15, alpha=0.3),
    }


def build(M):
    root = empty("HEMTT_M977A4", (0, 0, 0))
    root["vehicle"] = "HEMTT M977A4 cargo truck with material-handling crane"
    root["blurb"] = "Ten tons of pallets, the crane to lift them, at 1:1."
    root["weapon"] = "Crane"
    root["units"] = "metres"
    root["axes"] = "glTF: +Y up, +Z toward the front, +X to the driver's left"
    root["origin"] = "on the ground, on the centreline, midway between the front and rear axle pairs"
    empty("Ground_Reference", (0, 0, 0), root)["marker"] = "ground level under the tyres"
    objs = []
    objs += truck.cab(M, root)
    objs += truck.front(M, root)
    objs += truck.chassis(M, root)
    objs += truck.wheels(M, root)
    objs += truck.mid_body(M, root)
    objs += truck.cargo_body(M, root)
    objs += truck.crane(M, root)
    objs += truck.lights(M, root)
    objs += truck.cargo(M, root)
    notes()
    bpy.context.view_layer.update()
    localize()
    return root


def notes():
    """What each driven node does - exported as glTF extras (Blender custom properties)."""
    O = bpy.data.objects
    for i in range(1, 5):
        for s in ("Left", "Right"):
            w = O[f"Wheel_{i}_{s}"]
            w["drive"] = "spin about local X; + rolls the truck forward"
            w["control"] = "wheel"
            w["axis"] = [1.0, 0.0, 0.0]
            w["radius"] = TYRE_R
    lock1, lock2 = truck.steer_limits()
    for i, lim in ((1, lock1), (2, lock2)):
        for s in ("Left", "Right"):
            st = O[f"Steer_{i}_{s}"]
            st["drive"] = (f"steer about local Y; + turns left. Full lock ({math.degrees(lock1):.0f} degrees on the first axle, "
                           f"{math.degrees(lock2):.0f} on the second) is the inner wheels' for the published 100 ft turning circle.")
            st["control"] = "steer"
            st["axis"] = [0.0, 1.0, 0.0]
            st["limits"] = [-round(lim, 4), round(lim, 4)]
    for s in ("Left", "Right"):
        O[f"Door_{s}"]["control"] = "hinge"
        O[f"Door_{s}"]["group"] = "Cab doors"
    O["Crane"]["drive"] = "slew about local Y (all the way round)"
    O["Crane"]["control"] = "traverse"
    O["Crane"]["axis"] = [0.0, 1.0, 0.0]
    O["Crane_Boom"]["drive"] = "luff about local `axis`; + raises the boom (to about 75 degrees)"
    O["Crane_Boom"]["control"] = "elevate"
    O["Crane_Boom"]["axis"] = [-1.0, 0.0, 0.0]
    O["Crane_Boom"]["limits"] = [0.0, 1.3]
    O["Crane_Boom_Extension"]["drive"] = "telescope along the boom, local +Z, up to 2.3 m"
    O["Crane_Boom_Extension"]["control"] = "slide"
    O["Crane_Boom_Extension"]["group"] = "Crane reach"
    O["Crane_Boom_Extension"]["axis"] = [0.0, 0.0, 1.0]
    O["Crane_Boom_Extension"]["limits"] = [0.0, 2.3]
    O["Crane_Hook"]["drive"] = "hoist: lower along local -Y on the cable, up to 3 m"
    O["Crane_Hook"]["control"] = "slide"
    O["Crane_Hook"]["group"] = "Crane reach"
    O["Crane_Hook"]["axis"] = [0.0, -1.0, 0.0]
    O["Crane_Hook"]["limits"] = [0.0, 3.0]
    O["Crane_Hook"]["capacity_kg"] = 2041
    for i in range(1, 9):
        O[f"Cargo_Pallet_{i}"]["cargo"] = "a pallet load; show, hide or lift it off on its own"
        O[f"Cargo_Pallet_{i}"]["control"] = "cargo"
    for o in O:
        if o.name.startswith("Light_") and o.type == "EMPTY":
            o["light"] = o.name[6:].replace("_", " ").lower()


def localize():
    for o in bpy.data.objects:
        if o.type == "MESH" and o.parent is not None:
            o.data.transform(o.matrix_parent_inverse @ o.matrix_basis)
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def stats():
    tris = 0
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in meshes:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    return len(meshes), tris


def points(under, skip=()):
    out = []
    def walk(o):
        if o.name in skip:
            return
        if o.type == "MESH":
            mw = o.matrix_world
            for v in o.data.vertices:
                w = mw @ v.co
                out.append((w.x, w.z, -w.y))
        for c in o.children:
            walk(c)
    walk(bpy.data.objects[under])
    return np.array(out)


def measure():
    allp = points("HEMTT_M977A4", skip={"Mirrors_And_Trim", "Mirror_Glass"})
    body = allp
    centre = lambda n: (lambda p: (p.max(axis=0) + p.min(axis=0)) / 2)(points(n))
    w1l, w1r, w4l = centre("Wheel_1_Left"), centre("Wheel_1_Right"), centre("Wheel_4_Left")
    w2l, w3l = centre("Wheel_2_Left"), centre("Wheel_3_Left")
    tyre = points("Wheel_1_Left")
    bed = points("Cargo_Body_Mesh")
    rows = [
        ("Length (over the spare tyre)", SPEC["length"], body[:, 2].max() - body[:, 2].min()),
        ("Width (without mirrors)", SPEC["width"], body[:, 0].max() - body[:, 0].min()),
        ("Height (over the spare tyre)", SPEC["height"], body[:, 1].max() - body[:, 1].min()),
        ("Wheelbase (axle pair to axle pair)", SPEC["wheelbase"], (w1l[2] + w2l[2]) / 2 - (w3l[2] + w4l[2]) / 2),
        ("Track", SPEC["track"], w1l[0] - w1r[0]),
        ("Tyre diameter (16.00R20)", SPEC["tyreDiameter"], tyre[:, 1].max() - tyre[:, 1].min()),
        ("Cargo body length (18 ft)", SPEC["cargoBodyLength"], bed[:, 2].max() - bed[:, 2].min()),
    ]
    return rows, body[:, 1].min()


# ---- previews ----------------------------------------------------------------------------------------------------------------
def stage(scene):
    world = bpy.data.worlds.new("Sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(36)
    sky.sun_rotation = math.radians(215)
    nt.links.new(sky.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 0.22
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 3.4
    sd.angle = math.radians(0.7)
    sun = bpy.data.objects.new("Sun", sd)
    el, az = math.radians(36), math.radians(215)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "Ground"
    g.data.materials.append(principled("Ground", (0.09, 0.085, 0.075), 0.92))


def camera(scene, name, loc, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    co = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(co)
    co.location = B(loc)
    co.rotation_euler = (Vector(B(target)) - Vector(B(loc))).to_track_quat("-Z", "Y").to_euler()
    return co


VIEWS = {
    "front34": ((7.2, 2.2, 10.5), (0, 1.3, 0.3), 30),
    "side": ((15.0, 1.6, -0.4), (0, 1.45, -0.4), 30),
    "rear34": ((-6.8, 3.6, -12.0), (0, 1.4, -1.2), 30),
    "front": ((0.0, 1.7, 13.0), (0, 1.5, 0), 30),
    "top": ((0.01, 18.0, -0.4), (0, 0, -0.4), 30),
    "cab": ((3.6, 2.4, 7.6), (0, 1.8, 3.4), 30),
    "wheels": ((3.4, 0.7, 4.6), (1.0, 0.65, 1.0), 28),
    "crane": ((-4.2, 3.4, -8.4), (-0.6, 2.0, -3.6), 30),
}


def render_views(scene, out, views, res=(1280, 720), samples=24):
    os.makedirs(out, exist_ok=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    for name in views:
        loc, target, lens = VIEWS[name]
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        scene.render.filepath = os.path.join(out, name + ".png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


# ---- paint, bake, export -----------------------------------------------------------------------------------------------------
PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.5, 0.34, 0.01),
    low_y=1.35, low_gain=1.6, dust=0.7, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=-0.05, rough=0.6,
    rivet=0.06, line_depth=0.8)


def bake_all(scene, M, tex, size):
    t0 = time.time()
    maps = os.path.join(tex, "paint_maps")
    markings.draw_all(maps)
    views = {v: {k: paint.load_image(os.path.join(maps, f"paint_{v}_{k}.png")) for k in ("lines", "marks")} for v in markings.VIEWS}
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 1.0
    hide = {o.name for o in bpy.data.objects if o.type == "MESH" and any(s.material and s.material.name in ("HEMTT_Glass", "HEMTT_Cargo_Stretch_Wrap") for s in o.material_slots)}
    hide |= {"Ground"}
    # the paint in two atlases: the front half (cab, front end, engine bay, wheels' paint) and the back (body, crane, tanks)
    back = {o.name for o in bpy.data.objects if o.type == "MESH" and any(o.name.startswith(p) for p in ("Cargo_Body", "Rear_End", "Crane", "Fuel_Tank", "Battery"))}
    M["paint_b"] = M["paint"].copy()
    M["paint"].name, M["paint_b"].name = "HEMTT_Paint_Front", "HEMTT_Paint_Back"
    for name in back:
        for sl in bpy.data.objects[name].material_slots:
            if sl.material == M["paint"]:
                sl.material = M["paint_b"]
    for key in ("paint", "paint_b"):
        label = M[key].name
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, [M[key]], all_mats, size, tex, lambda ao, key=key: [paint.paint_shader(M[key], views, ao, markings.VIEWS, PALETTE)], extra_hide=hide, metal=False)
        paint.textured(M[key], paths)
    groups = (
        ("HEMTT_Chassis", ["chassis", "rubber", "exhaust", "steel", "hazard"], size // 2),
        ("HEMTT_Cargo", ["wood", "drum", "ammo_can", "crate", "strap", "cardboard"], size // 2),
    )
    for label, keys, sz in groups:
        mats = [M[k] for k in keys]
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, mats, all_mats, sz, tex, lambda ao, keys=keys: [paint.weathered_shader(M[k], SPECS[k], ao) for k in keys], ao_samples=32, extra_hide=hide)
        paint.textured(mats[0], paths)
        mats[0].name = label
        paint.merge_slots(mats[0], mats[1:])
    print(f"painted and baked in {time.time() - t0:.0f}s", flush=True)


# weathered looks for the chassis and the cargo (colours linear)
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.62, m=0.0, wear=(0.09, 0.08, 0.06), wm=0.0, mud=(0.085, 0.064, 0.04), mud_y=1.3, mud_amount=1.2),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.068, 0.043), mud_y=1.25, mud_amount=1.0),
    "exhaust": dict(c=(0.035, 0.026, 0.02), r=0.72, m=0.4, wear=(0.08, 0.05, 0.03), wm=0.6),
    "steel": dict(c=(0.62, 0.62, 0.6), r=0.18, m=1.0, wear=(0.5, 0.5, 0.48), wm=1.0),
    "hazard": dict(c=(0.5, 0.33, 0.01), r=0.55, m=0.0, wear=(0.08, 0.07, 0.05), wm=0.0),
    "wood": dict(c=(0.3, 0.2, 0.11), r=0.8, m=0.0, wear=(0.38, 0.28, 0.17), wm=0.0),
    "drum": dict(c=(0.05, 0.055, 0.03), r=0.5, m=0.0, wear=(0.25, 0.25, 0.24), wm=1.0),
    "ammo_can": dict(c=(0.042, 0.048, 0.026), r=0.45, m=0.0, wear=(0.25, 0.25, 0.24), wm=1.0),
    "crate": dict(c=(0.2, 0.135, 0.07), r=0.82, m=0.0, wear=(0.3, 0.22, 0.13), wm=0.0),
    "strap": dict(c=(0.55, 0.16, 0.02), r=0.72, m=0.0, wear=(0.4, 0.15, 0.04), wm=0.0),
    "cardboard": dict(c=(0.36, 0.26, 0.15), r=0.86, m=0.0, wear=(0.42, 0.32, 0.2), wm=0.0),
}


def export(path):
    bpy.ops.object.select_all(action="DESELECT")
    def walk(o):
        o.select_set(True)
        for c in o.children:
            walk(c)
    walk(bpy.data.objects["HEMTT_M977A4"])
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_extras=True, export_yup=True, export_apply=False,
        export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO",
        export_cameras=False, export_lights=False, export_animations=False)
    print(f"exported {path}: {os.path.getsize(path) / 1048576:.1f} MB", flush=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    M = materials()
    t = time.time()
    build(M)
    n, tris = stats()
    print(f"built {n} meshes, {tris:,} triangles in {time.time() - t:.1f}s", flush=True)
    rows, low = measure()
    print("1:1 check (published / model, metres):")
    for k, want, got in rows:
        print(f"  {k:38s} {want:7.3f}  {got:7.3f}  {'ok' if abs(got - want) < 0.02 else 'OFF BY %.3f' % (got - want)}")
    print(f"  lowest point above the ground: {low:.4f} m")
    import clearance
    clearance.gun_limits()  # the crane's boom: how high it must lift to slew over the load
    paint.RESUME = "--resume" in sys.argv
    glb = arg("--glb")
    if glb:
        with open(os.path.join(os.path.dirname(os.path.abspath(glb)), "measurements.json"), "w") as f:
            json.dump({"units": "metres", "published_vs_model": [{"dimension": k, "published": round(float(w), 4), "model": round(float(g), 4)} for k, w, g in rows],
                       "tyres_on_ground": bool(abs(low) < 0.005), "triangles": int(tris), "meshes": int(n)}, f, indent=1)
        tex = arg("--texdir", os.path.join(os.path.dirname(os.path.abspath(glb)), "textures"))
        if "--raw" not in sys.argv:  # --raw: export with plain materials, unbaked (for testing)
            bake_all(scene, M, tex, int(arg("--textures", 4096)))
        export(glb)
    if "--lookdev" in sys.argv and not glb:
        maps = arg("--maps") or os.path.join(HERE, "textures", "paint_maps")
        if not os.path.exists(os.path.join(maps, "paint_left_lines.png")):
            markings.draw_all(maps)
        views = {v: {k: paint.load_image(os.path.join(maps, f"paint_{v}_{k}.png")) for k in ("lines", "marks")} for v in markings.VIEWS}
        paint.paint_shader(M["paint"], views, None, markings.VIEWS, PALETTE)
        for k, spec in SPECS.items():
            paint.weathered_shader(M[k], spec, None)
    prev = arg("--preview")
    if prev:
        stage(scene)
        which = (arg("--views") or ",".join(VIEWS)).split(",")
        render_views(scene, prev, which, res=(960, 540), samples=int(arg("--samples", 20)))
    blend = arg("--blend")
    if blend:
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)


if __name__ == "__main__":
    main()
