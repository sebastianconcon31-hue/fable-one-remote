"""A plain studio for looking at the helmet: a grey sweep, three soft lights."""
import math
import bpy
from mathutils import Vector

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelkit"))
from geom import B


def stage(scene, strength=1.0):
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.20, 0.205, 0.21, 1)
    bg.inputs["Strength"].default_value = 0.9 * strength
    # a seamless floor under it
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, -0.20))
    g = bpy.context.active_object
    g.name = "Floor"
    m = bpy.data.materials.new("Floor")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.09, 0.092, 0.095, 1)
    p.inputs["Roughness"].default_value = 0.8
    g.data.materials.append(m)

    def area(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy * strength
        ld.size = size
        ld.color = color
        o = bpy.data.objects.new(name, ld)
        o.location = B(loc)
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(B(loc))).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(o)

    area("Key", (0.7, 0.9, 1.0), 90, 0.9, (1.0, 0.96, 0.9))
    area("Fill", (-1.0, 0.3, 0.7), 35, 1.2, (0.9, 0.95, 1.0))
    area("Rim", (0.2, 0.7, -1.1), 60, 0.8, (1, 1, 1))
