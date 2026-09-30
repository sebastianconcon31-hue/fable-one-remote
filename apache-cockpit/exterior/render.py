"""Beauty renders of the finished aircraft (the merged glTF, exactly as delivered),
on a concrete pad under a physical sky, in Cycles.

    python exterior/render.py apache_ah64d.glb OUT_DIR [--views a,b] [--samples N] [--res WxH] [--blend FILE]"""
import sys
import os
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector

from geom import B
import ah64


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def concrete(name="Concrete_Pad"):
    """Weathered concrete: slab joints every 5 m, cracks, tyre and fluid stains."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.35
    noise.inputs["Detail"].default_value = 8
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    fine = N.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 60
    fine.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Object"], fine.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.13, 0.125, 0.115, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.24, 0.23, 0.21, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    # slab joints: dark lines on a 5 m grid
    grid = N.new("ShaderNodeTexBrick")
    grid.inputs["Scale"].default_value = 0.2
    grid.inputs["Mortar Size"].default_value = 0.004
    grid.inputs["Mortar Smooth"].default_value = 0.2
    grid.offset = 0.0
    grid.squash = 1.0
    grid.inputs["Brick Width"].default_value = 1.0
    grid.inputs["Row Height"].default_value = 1.0
    grid.inputs["Color1"].default_value = (1, 1, 1, 1)
    grid.inputs["Color2"].default_value = (1, 1, 1, 1)
    grid.inputs["Mortar"].default_value = (0.25, 0.25, 0.25, 1)
    L.new(tc.outputs["Object"], grid.inputs["Vector"])
    stains = N.new("ShaderNodeTexNoise")
    stains.inputs["Scale"].default_value = 0.9
    stains.inputs["Detail"].default_value = 3
    L.new(tc.outputs["Object"], stains.inputs["Vector"])
    sramp = N.new("ShaderNodeValToRGB")
    sramp.color_ramp.elements[0].position = 0.55
    sramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    sramp.color_ramp.elements[1].position = 0.7
    sramp.color_ramp.elements[1].color = (0.6, 0.58, 0.55, 1)
    L.new(stains.outputs["Fac"], sramp.inputs["Fac"])
    mix1 = N.new("ShaderNodeMix")
    mix1.data_type = "RGBA"
    mix1.blend_type = "MULTIPLY"
    mix1.inputs["Factor"].default_value = 1.0
    L.new(ramp.outputs["Color"], mix1.inputs[6])
    L.new(grid.outputs["Color"], mix1.inputs[7])
    mix2 = N.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.blend_type = "MULTIPLY"
    mix2.inputs["Factor"].default_value = 1.0
    L.new(mix1.outputs[2], mix2.inputs[6])
    L.new(sramp.outputs["Color"], mix2.inputs[7])
    L.new(mix2.outputs[2], bsdf.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.72
    rr.inputs["To Max"].default_value = 0.95
    L.new(fine.outputs["Fac"], rr.inputs["Value"])
    L.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    L.new(fine.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def stage(scene, sun_elev=38, sun_az=215, strength=1.0):
    world = bpy.data.worlds.new("Sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_az)
    sky.altitude = 200
    nt.links.new(sky.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 0.22 * strength
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 3.6 * strength
    sd.angle = math.radians(0.6)
    sun = bpy.data.objects.new("Sun", sd)
    # point the sun along the sky's sun direction
    el, az = math.radians(sun_elev), math.radians(sun_az)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, ah64.GROUND_Y))
    g = bpy.context.active_object
    g.name = "Ground"
    g.data.materials.append(concrete())


def camera(scene, name, loc, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.dof.use_dof = False
    co = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(co)
    co.location = B(loc)
    co.rotation_euler = (Vector(B(target)) - Vector(B(loc))).to_track_quat("-Z", "Y").to_euler()
    return co


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
