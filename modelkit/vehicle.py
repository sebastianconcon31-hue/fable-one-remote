"""The build runner the ground vehicles share: materials, parenting clean-up,
measuring against the published dimensions, previews, paint and bake, glTF
export. Each vehicle's build.py hands run() a module (or any object) with:

  ROOT          name of the root node
  NOTES         dict of root extras (vehicle, units, axes, origin)
  materials()   -> {key: material}; "paint" is the painted skin
  build(M, root)
  measure()     -> (rows [(label, published, model)], lowest point)
  markings      module with VIEWS and draw_all(dir)
  PALETTE       paint palette (see paint.PALETTE); SCHEMES optional {name: palette overrides}
  PAINT_SETS    [(label, predicate(object name) or None)]: the paint's texture sets; the first takes what's left
  GROUPS        [(label, [material keys], size divisor)]: weathered material groups, each baked to one set
  SPECS         {material key: weathered spec} for the groups
  HIDE_MATS     material names left out of bakes (glass and other see-through things)
  VIEWS         {name: (camera, target, lens)} quick previews

Run it with --glb FILE (bake and export; --raw skips the bake), --preview DIR [--lookdev] [--views a,b], --blend FILE."""
import sys
import os
import math
import json
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

from geom import B
import paint
from staging import stage, camera, render


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


def lights_materials():
    return {
        "light_white": principled("Light_White", (0.8, 0.8, 0.78), 0.08, emit=(1, 0.97, 0.9), strength=1.0),
        "light_amber": principled("Light_Amber", (0.6, 0.3, 0.02), 0.08, emit=(1, 0.5, 0.05), strength=1.0),
        "light_red": principled("Light_Red", (0.5, 0.03, 0.02), 0.08, emit=(1, 0.05, 0.03), strength=1.0),
        "light_ir": principled("Light_IR", (0.05, 0.02, 0.03), 0.06),
    }


def drive(o, text, control=None, axis=None, limits=None, **extra):
    """Say how a node moves, as glTF extras: `drive` in words, `control` (wheel, sprocket, steer, track, hinge,
    slide, traverse, elevate, cargo) for viewers and game code, `axis` (local), `limits` and anything else."""
    o["drive"] = text
    if control:
        o["control"] = control
    if axis is not None:
        o["axis"] = [float(a) for a in axis]
    if limits is not None:
        o["limits"] = [float(a) for a in limits]
    for k, v in extra.items():
        o[k] = v


def localize():
    """Bake each mesh's parenting into its vertices, so every node's pivot is where its part turns.
    Instanced meshes (track links) keep their own transforms."""
    for o in bpy.data.objects:
        if o.type == "MESH" and o.parent is not None and o.data.users == 1:
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
    """Every vertex under a node, in model axes."""
    out = []
    def walk(o):
        if o.name in skip:
            return
        if o.type == "MESH":
            mw = o.matrix_world
            co = np.empty(len(o.data.vertices) * 3)
            o.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            w = (np.asarray(mw)[:3, :3] @ co.T).T + np.asarray(mw)[:3, 3]
            out.append(np.stack([w[:, 0], w[:, 2], -w[:, 1]], -1))
        for c in o.children:
            walk(c)
    walk(bpy.data.objects[under])
    return np.concatenate(out) if out else np.zeros((0, 3))


def centre(name):
    p = points(name)
    return (p.max(axis=0) + p.min(axis=0)) / 2


def node_pos(name):
    """Where a node (a wheel's hub, a pivot) sits, in model axes."""
    t = bpy.data.objects[name].matrix_world.translation
    return np.array([t.x, t.z, -t.y])


def span(p, axis):
    return float(p[:, axis].max() - p[:, axis].min())


def place(o, origin, x, y, z):
    """Put an object at a model-space frame (origin and axes): its Blender matrix, for instances."""
    bx, by, bz = Vector(B(x)), Vector(B(y)), Vector(B(z))
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0], m[r][1], m[r][2], m[r][3] = bx[r], -bz[r], by[r], B(origin)[r]
    o.matrix_basis = m


# ---- previews --------------------------------------------------------------------------------------------------------------
def previews(scene, out, views, which, res=(960, 540), samples=20):
    os.makedirs(out, exist_ok=True)
    for name in which:
        loc, target, lens = views[name]
        scene.camera = camera(scene, "Cam_" + name, loc, target, lens)
        t = time.time()
        render(scene, os.path.join(out, name + ".png"), samples, res)
        print(f"rendered {name} in {time.time() - t:.0f}s", flush=True)


# ---- paint and bake ----------------------------------------------------------------------------------------------------------
def paint_views(V, maps):
    if not os.path.exists(os.path.join(maps, "paint_left_lines.png")) or "--redraw" in sys.argv or arg("--glb"):
        V.markings.draw_all(maps)
    return {v: {k: paint.load_image(os.path.join(maps, f"paint_{v}_{k}.png")) for k in ("lines", "marks")} for v in V.markings.VIEWS}


def palette(V):
    p = dict(V.PALETTE)
    scheme = arg("--scheme")
    if scheme:
        p.update(V.SCHEMES[scheme])
    return p


def split_paint(V, M):
    """One paint material per texture set, each object's paint going to the first set that claims it."""
    sets = []
    base = M["paint"]
    for i, (label, pred) in enumerate(V.PAINT_SETS):
        if i == 0:
            continue
        mat = base.copy()
        mat.name = label
        for o in bpy.data.objects:
            if o.type == "MESH" and pred(o.name):
                for sl in o.material_slots:
                    if sl.material == base:
                        sl.material = mat
        sets.append((label, mat))
    base.name = V.PAINT_SETS[0][0]
    return [(V.PAINT_SETS[0][0], base)] + sets


def hinge_pose(f):
    """Swing every door, hatch and ramp to fraction f of its travel (0 shuts them again), so a bake sees their
    insides lit as they will be when someone opens them."""
    for o in bpy.data.objects:
        if o.get("control") == "hinge":
            lo, hi = o["limits"]
            a = o["axis"]
            o.rotation_mode = "AXIS_ANGLE"
            o.rotation_axis_angle = (lo + (hi - lo) * f, *B(a))
    bpy.context.view_layer.update()


def bake_all(V, scene, M, tex, size):
    t0 = time.time()
    views = paint_views(V, os.path.join(tex, "paint_maps"))
    pal = palette(V)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 1.0
    hide = {o.name for o in bpy.data.objects if o.type == "MESH" and o.material_slots and all(s.material and s.material.name in V.HIDE_MATS for s in o.material_slots)}
    hide |= {"Ground"}
    hinge_pose(0.5)
    for label, mat in split_paint(V, M):
        if not paint.faces_using([mat]):
            continue
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, [mat], all_mats, size, tex, lambda ao, mat=mat: [paint.paint_shader(mat, views, ao, V.markings.VIEWS, pal)], ao_samples=32, extra_hide=hide, metal=False)
        paint.textured(mat, paths)
    for label, keys, div in V.GROUPS:
        mats = [M[k] for k in keys]
        all_mats = [m for m in bpy.data.materials if m.users]
        paths = paint.bake_set(label, mats, all_mats, size // div, tex, lambda ao, keys=keys: [paint.weathered_shader(M[k], V.SPECS[k], ao) for k in keys], ao_samples=32, extra_hide=hide)
        paint.textured(mats[0], paths)
        mats[0].name = label
        paint.merge_slots(mats[0], mats[1:])
    hinge_pose(0.0)
    print(f"painted and baked in {time.time() - t0:.0f}s", flush=True)


def lookdev(V, M, maps):
    views = paint_views(V, maps)
    paint.paint_shader(M["paint"], views, None, V.markings.VIEWS, palette(V))
    for keys in [g[1] for g in V.GROUPS]:
        for k in keys:
            paint.weathered_shader(M[k], V.SPECS[k], None)


def export(root, path):
    bpy.ops.object.select_all(action="DESELECT")
    def walk(o):
        o.select_set(True)
        for c in o.children:
            walk(c)
    walk(bpy.data.objects[root])
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_extras=True, export_yup=True, export_apply=False,
        export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO",
        export_cameras=False, export_lights=False, export_animations=False)
    print(f"exported {path}: {os.path.getsize(path) / 1048576:.1f} MB", flush=True)


def report(rows, low):
    print("1:1 check (published / model, metres):")
    for k, want, got in rows:
        print(f"  {k:44s} {want:7.3f}  {got:7.3f}  {'ok' if abs(got - want) < 0.02 else 'OFF BY %.3f' % (got - want)}")
    print(f"  lowest point above the ground: {low:.4f} m")


def run(V):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    M = V.materials()
    t = time.time()
    from geom import empty
    root = empty(V.ROOT, (0, 0, 0))
    for k, v in V.NOTES.items():
        root[k] = v
    empty("Ground_Reference", (0, 0, 0), root)["marker"] = "ground level"
    V.build(M, root)
    bpy.context.view_layer.update()
    localize()
    n, tris = stats()
    print(f"built {n} meshes, {tris:,} triangles in {time.time() - t:.1f}s", flush=True)
    rows, low = V.measure()
    report(rows, low)
    paint.RESUME = "--resume" in sys.argv
    glb = arg("--glb")
    if glb:
        with open(os.path.join(os.path.dirname(os.path.abspath(glb)), "measurements.json"), "w") as f:
            json.dump({"units": "metres", "published_vs_model": [{"dimension": k, "published": round(float(w), 4), "model": round(float(g), 4)} for k, w, g in rows],
                       "on_the_ground": bool(abs(low) < 0.005), "triangles": int(tris), "meshes": int(n)}, f, indent=1)
        tex = arg("--texdir", os.path.join(os.path.dirname(os.path.abspath(glb)), "textures"))
        if "--raw" not in sys.argv:  # --raw: export with plain materials, unbaked (for testing)
            bake_all(V, scene, M, tex, int(arg("--textures", 4096)))
        export(V.ROOT, glb)
    elif "--lookdev" in sys.argv:
        lookdev(V, M, arg("--maps") or os.path.join(arg("--preview", "."), "paint_maps"))
    prev = arg("--preview")
    if prev:
        stage(scene, ground_y=0.0)
        which = (arg("--views") or ",".join(V.VIEWS)).split(",")
        previews(scene, prev, V.VIEWS, which, res=(960, 540), samples=int(arg("--samples", 20)))
    blend = arg("--blend")
    if blend:
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
