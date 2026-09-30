"""Builds the AH-64D's outside in Blender (run with Python 3.11 and the bpy
module: pip install bpy==5.0.1 pillow).

    python exterior/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]]

--glb bakes the paint and exports the model (and measurements.json beside it);
--blend saves the Blender scene; --preview renders quick look-dev views
(--lookdev shows the procedural paint without baking). Beauty renders of the
finished aircraft come from exterior/render.py."""
import sys
import os
import math
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np
from mathutils import Vector, Matrix

from geom import B, empty
import ah64
import airframe
import systems
import decals
import paint


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


# ---- look-dev materials (the paint shader replaces "paint"; see paint.py) ------------------------------------------------
def principled(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=1.0, transmission=0.0, coat=0.0, ior=1.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["IOR"].default_value = ior
    if transmission:
        p.inputs["Transmission Weight"].default_value = transmission
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.05
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        p.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


def materials():
    return {
        "paint": principled("AH64_Paint", (0.072, 0.078, 0.05), 0.62),
        "interior": principled("AH64_Interior", (0.018, 0.019, 0.02), 0.7),
        "dark": principled("AH64_Dark", (0.015, 0.016, 0.015), 0.6),
        "glass": principled("AH64_Canopy_Glass", (0.8, 0.84, 0.82), 0.02, alpha=0.14, ior=1.49),
        "mech": principled("AH64_Mech", (0.03, 0.032, 0.03), 0.5),
        "steel": principled("AH64_Steel", (0.62, 0.62, 0.6), 0.22, 1.0),
        "gun": principled("AH64_Gun", (0.05, 0.05, 0.05), 0.38, 0.85),
        "engine": principled("AH64_Engine_Face", (0.06, 0.06, 0.06), 0.4, 0.8),
        "exhaust": principled("AH64_Exhaust", (0.02, 0.018, 0.016), 0.75, 0.3),
        "rubber": principled("AH64_Rubber", (0.014, 0.014, 0.014), 0.88),
        "blade": principled("AH64_Blade", (0.022, 0.023, 0.022), 0.45),
        "blade_le": principled("AH64_Blade_Erosion_Strip", (0.55, 0.55, 0.53), 0.28, 1.0),
        "blade_tip": principled("AH64_Blade_Tip", (0.4, 0.4, 0.38), 0.35, 1.0),
        "sensor_glass": principled("AH64_Sensor_Glass", (0.01, 0.012, 0.018), 0.04, 0.4, coat=1.0),
        "stores": principled("AH64_Stores", (0.055, 0.06, 0.038), 0.5),
        "stores_dark": principled("AH64_Stores_Dark", (0.02, 0.02, 0.02), 0.6),
        "band_yellow": principled("AH64_Band_Yellow", (0.55, 0.38, 0.02), 0.5),
        "band_brown": principled("AH64_Band_Brown", (0.13, 0.06, 0.02), 0.55),
        # lenses carry their light's colour as emission; a game (or the viewer) scales it to switch the light
        "nav_red": principled("Light_Nav_Red", (0.5, 0.03, 0.02), 0.08, emit=(1, 0.06, 0.03), strength=1.0),
        "nav_green": principled("Light_Nav_Green", (0.03, 0.4, 0.1), 0.08, emit=(0.06, 1, 0.3), strength=1.0),
        "nav_white": principled("Light_Nav_White", (0.75, 0.75, 0.72), 0.08, emit=(1, 1, 0.95), strength=1.0),
        "beacon": principled("Light_Anticollision", (0.5, 0.03, 0.02), 0.08, emit=(1, 0.05, 0.02), strength=1.0),
        "formation": principled("Light_Formation", (0.25, 0.3, 0.2), 0.4, emit=(0.3, 1, 0.4), strength=0.0),
        "searchlight": principled("Light_Search", (0.7, 0.72, 0.7), 0.05, 0.6),
    }


# ---- the aircraft ---------------------------------------------------------------------------------------------------------------
def build(M):
    root = empty("Exterior", (0, 0, 0))
    empty("Ground_Reference", (0, ah64.GROUND_Y, 0), root)
    objs = []
    objs += airframe.fuselage(M, root)
    objs += airframe.efab(M, root)
    objs += airframe.pylon(M, root)
    objs += airframe.nacelles(M, root)
    objs += airframe.wings(M, root)
    objs += airframe.tail(M, root)
    can, doors = airframe.canopy(M, root)
    objs += can
    mr, o = systems.main_rotor(M, root)
    objs += o
    objs += systems.rotor_fixed(M, root)
    tr, o = systems.tail_rotor(M, root)
    objs += o
    objs += systems.sensors(M, root)
    objs += systems.gun(M, root)
    objs += systems.gear(M, root)
    wing_nodes = {s: bpy.data.objects[f"Wing_{s}"] for s in ("Left", "Right")}
    objs += systems.stores(M, wing_nodes)
    objs += systems.lights(M, root)
    objs += systems.details(M, root)
    bpy.context.view_layer.update()
    localize()
    return root, doors


def localize():
    """Move each mesh's vertices into its parent's frame, so every node's pivot is where it turns (clean for engines)."""
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


# ---- measuring against the published figures -------------------------------------------------------------------------------
def world_points(names=None, under=None, skip=()):
    """Model-axis points of every mesh under the named node (or the whole aircraft)."""
    dg = bpy.context.evaluated_depsgraph_get()
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
    S = ah64.SPEC
    body = world_points(under="Exterior", skip={"Main_Rotor", "Tail_Rotor", "Lights", "FCR_Radome", "Swashplate", "Ground_Reference"})
    z_front, z_back = body[:, 2].max(), body[:, 2].min()
    hub = np.array(ah64.HUB)
    mr = world_points(under="Main_Rotor")
    rmain = np.hypot(mr[:, 0] - hub[0], mr[:, 2] - hub[2]).max()
    near = np.hypot(mr[:, 0] - hub[0], mr[:, 2] - hub[2]) < 0.35
    hub_top = mr[near, 1].max()
    th = np.array(ah64.TAIL_HUB)
    trp = world_points(under="Tail_Rotor")
    rtail = np.hypot(trp[:, 1] - th[1], trp[:, 2] - th[2]).max()
    wings = np.vstack([world_points(under="Wing_Left"), world_points(under="Wing_Right")])
    span = np.abs(wings[:, 0]).max() * 2
    fcr = world_points(under="FCR_Radome")[:, 1].max()
    gear = world_points(under="Landing_Gear")
    lowest = gear[:, 1].min()
    centre = lambda n: (lambda p: (p.max(axis=0) + p.min(axis=0)) / 2)(world_points(under=n))
    wl, wr, wt = centre("Main_Wheel_Left"), centre("Main_Wheel_Right"), centre("Tail_Wheel")
    track = wl[0] - wr[0]
    base = wl[2] - wt[2]
    g = ah64.GROUND_Y
    rows = [
        ("Fuselage length", S["fuselageLength"], z_front - z_back),
        ("Length, rotors turning", S["lengthRotorsTurning"], hub[2] + rmain - min(z_back, th[2] - rtail)),
        ("Main rotor diameter", S["mainRotorDiameter"], rmain * 2),
        ("Tail rotor diameter", S["tailRotorDiameter"], rtail * 2),
        ("Wingspan", S["wingspan"], span),
        ("Wheel track", S["wheelTrack"], track),
        ("Wheelbase", S["wheelbase"], base),
        ("Height to top of rotor head", S["heightToRotorHead"], hub_top - g),
        ("Height to top of radome", S["heightToFcr"], fcr - g),
        ("Height to top of tail rotor", S["heightToTailRotor"], th[1] + rtail - g),
    ]
    return rows, lowest - g


# ---- look-dev renders ----------------------------------------------------------------------------------------------------------
def stage(scene, strength=1.0):
    world = bpy.data.worlds.new("Sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(34)
    sky.sun_rotation = math.radians(210)
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.25 * strength
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 3.2 * strength
    sd.angle = math.radians(0.8)
    sun = bpy.data.objects.new("Sun", sd)
    sun.rotation_euler = (math.radians(56), 0, math.radians(210 - 180))
    scene.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, ah64.GROUND_Y))
    gnd = bpy.context.active_object
    gnd.name = "Ground"
    gm = principled("Ground", (0.075, 0.072, 0.066), 0.9)
    gnd.data.materials.append(gm)
    return gnd


def camera(scene, name, loc, target, lens=35):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    co = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(co)
    co.location = B(loc)
    d = Vector(B(target)) - Vector(B(loc))
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return co


def render_views(scene, out, views, res=(1280, 720), samples=32):
    os.makedirs(out, exist_ok=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    for name, loc, target, lens in views:
        cam = camera(scene, "Cam_" + name, loc, target, lens)
        scene.camera = cam
        scene.render.filepath = os.path.join(out, name + ".png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


VIEWS = {
    "front34": ((7.5, 1.4, 7.0), (0, 0.9, -2.2), 32),
    "side": ((13.5, 1.2, -4.6), (0, 1.0, -4.6), 26),
    "rear34": ((-8.5, 3.2, -15.0), (0, 1.2, -5.0), 30),
    "top": ((0.01, 22, -4.5), (0, 0, -4.5), 30),
    "nose": ((2.2, 0.9, 4.2), (0, 0.4, 1.2), 32),
    "head": ((2.0, 4.0, 0.2), (0, 2.7, -2.9), 32),
    "engine": ((3.2, 2.2, -6.2), (0.8, 1.35, -3.8), 30),
    "tail": ((-3.2, 2.4, -14.5), (0, 1.6, -11.8), 30),
    "front": ((0.0, 1.2, 12.0), (0, 1.2, 0), 24),
}


def backface_check():
    """Colour back faces red in every material, to find surfaces facing the wrong way."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        out = nt.nodes.get("Material Output")
        if out is None or not out.inputs["Surface"].links:
            continue
        src = out.inputs["Surface"].links[0].from_socket
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        red = nt.nodes.new("ShaderNodeEmission")
        red.inputs["Color"].default_value = (1, 0, 0, 1)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
        nt.links.new(src, mix.inputs[1])
        nt.links.new(red.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])


def main():
    scene = reset()
    M = materials()
    t = time.time()
    root, doors = build(M)
    n, tris = stats()
    print(f"built {n} meshes, {tris:,} triangles in {time.time() - t:.1f}s", flush=True)
    rows, clearance = measure()
    print("1:1 check (published / model, metres):")
    for k, want, got in rows:
        print(f"  {k:30s} {want:7.3f}  {got:7.3f}  {'ok' if abs(got - want) < 0.02 else 'OFF BY %.3f' % (got - want)}")
    print(f"  lowest point of the gear above the ground: {clearance:.4f} m")
    if arg("--glb"):
        with open(os.path.join(os.path.dirname(os.path.abspath(arg("--glb"))), "measurements.json"), "w") as f:
            json.dump({"units": "metres", "published_vs_model": [{"dimension": k, "published": float(w), "model": round(float(g), 4)} for k, w, g in rows],
                       "wheels_on_ground": bool(abs(clearance) < 0.005), "triangles": int(tris), "meshes": int(n)}, f, indent=1)
    glb = arg("--glb")
    if glb:
        tex = arg("--texdir", os.path.join(os.path.dirname(os.path.abspath(glb)), "exterior_textures"))
        size = int(arg("--textures", 4096))
        paint_and_bake(scene, M, tex, size)
        export(glb)
    if "--lookdev" in sys.argv and not arg("--glb"):
        maps = arg("--maps") or os.path.join(HERE, "..", "exterior_textures", "paint_maps")
        if not os.path.exists(os.path.join(maps, "paint_left_lines.png")):
            decals.draw_all(maps)
        views = {v: {k: paint.load_image(os.path.join(maps, f"paint_{v}_{k}.png")) for k in ("lines", "marks")} for v in decals.VIEWS}
        paint.paint_shader(M["paint"], views, None)
        for k, spec in paint.MECH.items():
            paint.weathered_shader(M[k], spec, None)
    prev = arg("--preview")
    if prev:
        stage(scene)
        if "--backfaces" in sys.argv:
            backface_check()
        which = (arg("--views") or ",".join(VIEWS)).split(",")
        render_views(scene, prev, [(k, *VIEWS[k]) for k in which], res=(960, 540), samples=int(arg("--samples", 24)))
    blend = arg("--blend")
    if blend:
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)


def paint_and_bake(scene, M, tex, size):
    """Draw the paint maps, weather everything procedurally, bake it to PBR textures and switch to the baked materials."""
    t0 = time.time()
    maps = os.path.join(tex, "paint_maps")
    decals.draw_all(maps)
    views = {v: {k: paint.load_image(os.path.join(maps, f"paint_{v}_{k}.png")) for k in ("lines", "marks")} for v in decals.VIEWS}
    print(f"paint maps drawn in {time.time() - t0:.0f}s", flush=True)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 1.2
    glass = {o.name for o in bpy.data.objects if o.type == "MESH" and any(s.material and s.material.name in ("AH64_Canopy_Glass",) for s in o.material_slots)}
    glass |= {o.name for o in bpy.data.objects if o.name == "Ground"}
    all_mats = [m for m in bpy.data.materials if m.users]
    # the skin, in two atlases: forward (nose, cockpit, bays, sensors, engines, pylon) and aft (body, boom, tail, wings)
    aft = {"Fuselage_Aft", "Fin", "Stabilator", "Wing_Left_Skin", "Wing_Right_Skin", "Drive_Shaft_Cover", "Tail_Rotor_Gearbox_Fairing",
           "Wing_Left_Tip_Station", "Wing_Right_Tip_Station", "Pylon_Left_Inboard", "Pylon_Left_Outboard", "Pylon_Right_Inboard", "Pylon_Right_Outboard"}
    M["paint_b"] = M["paint"].copy()
    M["paint"].name, M["paint_b"].name = "AH64_Paint_Fwd", "AH64_Paint_Aft"
    for name in aft:
        for sl in bpy.data.objects[name].material_slots:
            if sl.material == M["paint"]:
                sl.material = M["paint_b"]
    for key, label in (("paint", "AH64_Paint_Fwd"), ("paint_b", "AH64_Paint_Aft")):
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, [M[key]], all_mats, size, tex, lambda ao, key=key: [paint.paint_shader(M[key], views, ao)], extra_hide=glass, metal=False)
        paint.textured(M[key], paths)
    # mechanical parts, and the stores
    for label, keys, sz in (("AH64_Mech", ["mech", "steel", "gun", "rubber", "exhaust", "engine", "stores_dark"], size // 2), ("AH64_Stores", ["stores", "band_yellow", "band_brown"], size // 2)):
        mats = [M[k] for k in keys]
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, mats, all_mats, sz, tex, lambda ao, keys=keys: [paint.weathered_shader(M[k], paint.MECH[k], ao) for k in keys], ao_samples=32, extra_hide=glass)
        target = mats[0]
        paint.textured(target, paths)
        target.name = label
        paint.merge_slots(target, mats[1:])
    print(f"painted and baked in {time.time() - t0:.0f}s", flush=True)


def aircraft_objects():
    out = []
    def walk(o):
        out.append(o)
        for c in o.children:
            walk(c)
    walk(bpy.data.objects["Exterior"])
    return out


def export(path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in aircraft_objects():
        o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_extras=False, export_yup=True, export_apply=False,
        export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO",
        export_cameras=False, export_lights=False, export_animations=False)
    print(f"exported {path}: {os.path.getsize(path) / 1048576:.1f} MB", flush=True)



if __name__ == "__main__":
    main()
