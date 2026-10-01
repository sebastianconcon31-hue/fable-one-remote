"""Beauty-render staging shared by the models: a weathered concrete pad under a
physical sky with a sun, and cameras placed in model axes."""
import math
import bpy
from mathutils import Vector

from geom import B


def render(scene, out_path, samples=96, res=(1600, 900)):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.transparent_max_bounces = 16
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)


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


def stage(scene, ground_y=0.0, sun_elev=38, sun_az=215, strength=1.0):
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
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, ground_y))
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


