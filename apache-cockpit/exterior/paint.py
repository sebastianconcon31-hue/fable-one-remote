"""Paint, weathering and baking.

The skin's look is built procedurally in Cycles - the paint maps from
decals.py projected from four sides, plus fading, dust, grime from ambient
occlusion, rain streaks and worn edges - then baked into plain PBR textures
(base colour, occlusion-roughness-metallic, normal) that any engine can use."""
import math
import os
import time
import bpy
import bmesh
import numpy as np

import decals

# ---- node helpers -------------------------------------------------------------------------------------------------------------
class NT:
    def __init__(self, mat, clear=True):
        mat.use_nodes = True
        self.nt = mat.node_tree
        if clear:
            self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **inputs):
        node = self.nt.nodes.new(kind)
        node.location = (self.x, 0)
        self.x += 40
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(node, k[1:], v)
            else:
                self.put(node.inputs[k], v)
        return node

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.nt.links.new(v.outputs[0], sock)
        else:
            sock.default_value = v if not isinstance(v, (tuple, list)) or len(v) != 3 or sock.type != "RGBA" else (*v, 1.0)

    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        m = self.n("ShaderNodeMath", _operation=op, _use_clamp=clamp)
        self.put(m.inputs[0], a)
        self.put(m.inputs[1], b)
        self.put(m.inputs[2], c)
        return m.outputs[0]

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def add(self, a, b):
        return self.math("ADD", a, b)

    def madd(self, a, b, c):
        return self.math("MULTIPLY_ADD", a, b, c)

    def clamp01(self, a):
        return self.math("ADD", a, 0.0, clamp=True)

    def smooth(self, a, lo, hi):
        m = self.n("ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP", _clamp=True)
        self.put(m.inputs["Value"], a)
        m.inputs["From Min"].default_value = lo
        m.inputs["From Max"].default_value = hi
        return m.outputs["Result"]

    def vmath(self, op, a, b=None, scale=None):
        m = self.n("ShaderNodeVectorMath", _operation=op)
        self.put(m.inputs[0], a)
        if b is not None:
            self.put(m.inputs[1], b)
        if scale is not None:
            self.put(m.inputs["Scale"], scale)
        return m.outputs["Vector"] if op != "DOT_PRODUCT" else m.outputs["Value"]

    def mix(self, a, b, fac, blend="MIX"):
        m = self.n("ShaderNodeMix", _data_type="RGBA", _blend_type=blend)
        self.put(m.inputs["Factor"], fac)
        self.put(m.inputs[6], a)
        self.put(m.inputs[7], b)
        return m.outputs[2]

    def mixf(self, a, b, fac):
        m = self.n("ShaderNodeMix", _data_type="FLOAT")
        self.put(m.inputs["Factor"], fac)
        self.put(m.inputs[2], a)
        self.put(m.inputs[3], b)
        return m.outputs[0]

    def xyz(self, v):
        s = self.n("ShaderNodeSeparateXYZ")
        self.put(s.inputs[0], v)
        return s.outputs[0], s.outputs[1], s.outputs[2]

    def comb(self, x, y, z=0.0):
        c = self.n("ShaderNodeCombineXYZ")
        self.put(c.inputs[0], x)
        self.put(c.inputs[1], y)
        self.put(c.inputs[2], z)
        return c.outputs[0]

    def noise(self, vec, scale, detail=3.0, rough=0.55, dist=0.0):
        n = self.n("ShaderNodeTexNoise", _noise_dimensions="3D")
        self.put(n.inputs["Vector"], vec)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = dist
        return n.outputs["Fac"]

    def image(self, img, vec=None, interp="Linear", ext="CLIP"):
        t = self.n("ShaderNodeTexImage", _interpolation=interp, _extension=ext)
        t.image = img
        if vec is not None:
            self.put(t.inputs["Vector"], vec)
        return t

    def out(self, shader):
        o = self.n("ShaderNodeOutputMaterial")
        self.put(o.inputs["Surface"], shader)
        return o


def load_image(path, colorspace="Non-Color"):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    img.alpha_mode = "CHANNEL_PACKED"
    return img


# ---- the skin's shader ---------------------------------------------------------------------------------------------------------
PAINT = (0.056, 0.068, 0.036)  # FS 34031-ish aircraft green, linear
FADED = (0.086, 0.096, 0.064)
GRIME = (0.03, 0.029, 0.02)
DUST = (0.17, 0.155, 0.115)
STENCIL = (0.009, 0.009, 0.008)
SOOT = (0.006, 0.0055, 0.005)
OIL = (0.012, 0.01, 0.006)
WORN = (0.11, 0.118, 0.09)


def model_space(t):
    """World position and normal as model axes (x left, y up, z forward)."""
    g = t.n("ShaderNodeNewGeometry")
    px, py, pz = t.xyz(g.outputs["Position"])
    nx, ny, nz = t.xyz(g.outputs["Normal"])
    mz = t.mul(py, -1.0)
    nzm = t.mul(ny, -1.0)
    return g, (px, pz, mz), (nx, nz, nzm)


def projections(t, P, N, images):
    """Blend the four paint views by how squarely each surface faces them. Returns the eight channels."""
    mx, my, mz = P
    nx, ny, nz = N
    L, H, W = decals.Z1 - decals.Z0, decals.Y1 - decals.Y0, decals.X1 - decals.X0
    uv = {
        "left": (t.madd(mz, -1 / L, decals.Z1 / L), t.madd(my, 1 / H, -decals.Y0 / H)),
        "right": (t.madd(mz, 1 / L, -decals.Z0 / L), t.madd(my, 1 / H, -decals.Y0 / H)),
        "top": (t.madd(mx, -1 / W, decals.X1 / W), t.madd(mz, 1 / L, -decals.Z0 / L)),
        "bottom": (t.madd(mx, 1 / W, -decals.X0 / W), t.madd(mz, 1 / L, -decals.Z0 / L)),
    }
    pw = 4.0
    w = {
        "left": t.math("POWER", t.math("MAXIMUM", nx, 0.0), pw),
        "right": t.math("POWER", t.math("MAXIMUM", t.mul(nx, -1.0), 0.0), pw),
        "top": t.math("POWER", t.math("MAXIMUM", ny, 0.0), pw),
        "bottom": t.math("POWER", t.math("MAXIMUM", t.mul(ny, -1.0), 0.0), pw),
    }
    wf = t.math("POWER", t.math("ABSOLUTE", nz), pw)
    total = t.add(t.add(t.add(w["left"], w["right"]), t.add(w["top"], w["bottom"])), t.add(wf, 1e-4))
    lines_rgb, lines_a, marks_rgb, marks_a = None, t.mul(wf, 0.5), None, None
    for k in ("left", "right", "top", "bottom"):
        wk = t.math("DIVIDE", w[k], total)
        vec = t.comb(*uv[k])
        li = t.image(images[k]["lines"], vec)
        mk = t.image(images[k]["marks"], vec)
        lr = t.vmath("SCALE", li.outputs["Color"], scale=wk)
        mr = t.vmath("SCALE", mk.outputs["Color"], scale=wk)
        la = t.mul(li.outputs["Alpha"], wk)
        ma = t.mul(mk.outputs["Alpha"], wk)
        lines_rgb = lr if lines_rgb is None else t.vmath("ADD", lines_rgb, lr)
        marks_rgb = mr if marks_rgb is None else t.vmath("ADD", marks_rgb, mr)
        lines_a = t.add(lines_a, la)
        marks_a = ma if marks_a is None else t.add(marks_a, ma)
    lines_a = t.add(lines_a, t.mul(t.math("DIVIDE", wf, total), 0.0))
    line, halo, rivet = t.xyz(lines_rgb)
    mark, walk, oil = t.xyz(marks_rgb)
    return dict(line=line, halo=halo, rivet=rivet, tint=lines_a, mark=mark, walk=walk, oil=oil, soot=marks_a)


def paint_shader(mat, images, ao_image):
    """The skin. Returns the node tree helper and the colour, roughness and height sockets (for baking)."""
    t = NT(mat)
    g, P, N = model_space(t)
    mx, my, mz = P
    nx, ny, nz = N
    ch = projections(t, P, N, images)
    pos = g.outputs["Position"]
    big = t.noise(pos, 0.35, 2.0)
    mid = t.noise(pos, 2.2, 4.0)
    fine = t.noise(pos, 16.0, 6.0, 0.6)
    grain = t.noise(pos, 380.0, 2.0, 0.7)
    streak_vec = t.vmath("MULTIPLY", pos, (9.0, 9.0, 0.45))
    streak = t.smooth(t.noise(streak_vec, 1.0, 3.0, 0.6), 0.52, 0.72)
    if ao_image is None:  # look-dev: live occlusion instead of the baked map
        aon = t.n("ShaderNodeAmbientOcclusion", _samples=8)
        aon.inputs["Distance"].default_value = 1.2
        ao_v = aon.outputs["AO"]
    else:
        uv = t.n("ShaderNodeUVMap", _uv_map="UVMap")
        ao_v = t.xyz(t.image(ao_image, uv.outputs["UV"]).outputs["Color"])[0]
    # base paint, faded unevenly, panel by panel
    c = t.mix(PAINT, (0.066, 0.072, 0.05), t.mul(mid, 0.3))
    c = t.mix(c, t.vmath("SCALE", c, scale=t.madd(big, 0.3, 0.85)), 1.0)
    c = t.vmath("SCALE", c, scale=t.madd(t.add(ch["tint"], -0.5), 0.45, 1.0))
    up = t.math("MAXIMUM", ny, 0.0)
    fade = t.mul(t.math("POWER", up, 1.5), t.madd(big, 0.35, 0.2))
    c = t.mix(c, FADED, fade)
    # rain streaks down the vertical faces
    vert = t.math("SUBTRACT", 1.0, t.math("ABSOLUTE", ny))
    c = t.vmath("SCALE", c, scale=t.math("SUBTRACT", 1.0, t.mul(t.mul(vert, streak), 0.16)))
    # grime in the corners and round the panel lines
    grime = t.math("POWER", t.math("SUBTRACT", 1.0, ao_v, clamp=True), 1.3)
    c = t.mix(c, GRIME, t.clamp01(t.mul(grime, t.madd(mid, 0.4, 0.3))))
    c = t.mix(c, GRIME, t.mul(ch["halo"], 0.35))
    # dust: heavier low down and on top
    low = t.math("SUBTRACT", 0.35, my, clamp=True)
    dust = t.clamp01(t.add(t.mul(t.mul(low, 1.1), mid), t.mul(t.mul(up, t.smooth(mid, 0.45, 0.8)), 0.45)))
    c = t.mix(c, DUST, t.mul(dust, 0.4))
    # edges worn through the paint
    bev = t.n("ShaderNodeBevel", _samples=8)
    bev.inputs["Radius"].default_value = 0.006
    edge = t.math("SUBTRACT", 1.0, t.vmath("DOT_PRODUCT", bev.outputs[0], g.outputs["Normal"]))
    wear = t.mul(t.smooth(edge, 0.02, 0.12), t.smooth(fine, 0.5, 0.62))
    c = t.mix(c, WORN, t.mul(wear, 0.8))
    # panel lines, rivets, walkways, stencils, fluids, soot
    c = t.mix(c, (0.01, 0.01, 0.009), t.mul(ch["line"], 0.85))
    c = t.vmath("SCALE", c, scale=t.math("SUBTRACT", 1.0, t.mul(ch["rivet"], 0.12)))
    c = t.mix(c, (0.024, 0.025, 0.021), t.mul(ch["walk"], 0.9))
    c = t.mix(c, STENCIL, ch["mark"])
    c = t.mix(c, OIL, t.mul(ch["oil"], 0.75))
    c = t.mix(c, SOOT, t.clamp01(t.mul(ch["soot"], 1.15)))
    # roughness
    r = t.madd(mid, 0.14, 0.6)
    r = t.add(r, t.mul(fade, 0.12))
    r = t.add(r, t.mul(ch["walk"], 0.25))
    r = t.add(r, t.mul(ch["mark"], -0.12))
    r = t.add(r, t.mul(ch["oil"], -0.42))
    r = t.add(r, t.mul(ch["soot"], 0.15))
    r = t.add(r, t.mul(dust, 0.12))
    r = t.math("MAXIMUM", t.math("MINIMUM", r, 0.95), 0.18)
    # height: grooves, rivet heads, non-skid grit, a faint orange peel
    h = t.mul(ch["line"], -1.0)
    h = t.add(h, t.mul(ch["rivet"], 0.4))
    h = t.add(h, t.mul(t.mul(ch["walk"], grain), 0.5))
    h = t.add(h, t.mul(fine, 0.04))
    bump = t.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0012
    t.put(bump.inputs["Height"], h)
    bsdf = t.n("ShaderNodeBsdfPrincipled")
    t.put(bsdf.inputs["Base Color"], c)
    t.put(bsdf.inputs["Roughness"], r)
    bsdf.inputs["Metallic"].default_value = 0.0
    t.put(bsdf.inputs["Normal"], bump.outputs["Normal"])
    out = t.out(bsdf)
    return dict(t=t, color=c, rough=r, metal=0.0, bsdf=bsdf, out=out)


# ---- mechanical parts and stores: one weathered look, per-material base values -------------------------------------------------
MECH = {
    "mech": dict(c=(0.03, 0.032, 0.03), r=0.52, m=0.0, wear=(0.3, 0.3, 0.29), wm=1.0),
    "steel": dict(c=(0.6, 0.6, 0.58), r=0.2, m=1.0, wear=(0.6, 0.6, 0.58), wm=1.0),
    "gun": dict(c=(0.05, 0.05, 0.048), r=0.4, m=0.85, wear=(0.3, 0.3, 0.3), wm=1.0),
    "rubber": dict(c=(0.016, 0.016, 0.015), r=0.9, m=0.0, wear=(0.03, 0.03, 0.028), wm=0.0),
    "exhaust": dict(c=(0.018, 0.016, 0.014), r=0.78, m=0.3, wear=(0.05, 0.04, 0.035), wm=0.6),
    "engine": dict(c=(0.07, 0.07, 0.068), r=0.42, m=0.8, wear=(0.2, 0.2, 0.2), wm=1.0),
    "stores_dark": dict(c=(0.02, 0.02, 0.02), r=0.6, m=0.0, wear=(0.2, 0.2, 0.2), wm=1.0),
    "stores": dict(c=(0.052, 0.057, 0.036), r=0.55, m=0.0, wear=(0.13, 0.13, 0.11), wm=0.0),
    "band_yellow": dict(c=(0.52, 0.36, 0.02), r=0.5, m=0.0, wear=(0.3, 0.25, 0.1), wm=0.0),
    "band_brown": dict(c=(0.12, 0.055, 0.02), r=0.55, m=0.0, wear=(0.2, 0.15, 0.1), wm=0.0),
}


def weathered_shader(mat, spec, ao_image):
    t = NT(mat)
    g = t.n("ShaderNodeNewGeometry")
    pos = g.outputs["Position"]
    mid = t.noise(pos, 3.0, 4.0)
    fine = t.noise(pos, 22.0, 6.0, 0.6)
    if ao_image is None:
        aon = t.n("ShaderNodeAmbientOcclusion", _samples=8)
        aon.inputs["Distance"].default_value = 1.2
        ao_v = aon.outputs["AO"]
    else:
        uv = t.n("ShaderNodeUVMap", _uv_map="UVMap")
        ao_v = t.xyz(t.image(ao_image, uv.outputs["UV"]).outputs["Color"])[0]
    c = t.vmath("SCALE", spec["c"], scale=t.madd(mid, 0.3, 0.85))
    grime = t.math("POWER", t.math("SUBTRACT", 1.0, ao_v, clamp=True), 1.2)
    c = t.mix(c, GRIME if spec["m"] < 0.5 else (0.02, 0.018, 0.015), t.clamp01(t.mul(grime, t.madd(mid, 0.6, 0.5))))
    _, _, nzb = t.xyz(g.outputs["Normal"])
    up = t.math("MAXIMUM", nzb, 0.0)
    dust = t.mul(t.mul(up, t.smooth(mid, 0.4, 0.8)), 0.4)
    c = t.mix(c, DUST, dust)
    bev = t.n("ShaderNodeBevel", _samples=8)
    bev.inputs["Radius"].default_value = 0.004
    edge = t.math("SUBTRACT", 1.0, t.vmath("DOT_PRODUCT", bev.outputs[0], g.outputs["Normal"]))
    wear = t.mul(t.smooth(edge, 0.02, 0.1), t.smooth(fine, 0.48, 0.6))
    c = t.mix(c, spec["wear"], t.mul(wear, 0.85))
    r = t.add(t.madd(mid, 0.14, spec["r"] - 0.07), t.mul(dust, 0.2))
    r = t.add(r, t.mul(wear, 0.05 if spec["wm"] > 0.5 else 0.1))
    r = t.math("MAXIMUM", t.math("MINIMUM", r, 0.95), 0.12)
    m = t.madd(wear, spec["wm"] - spec["m"], spec["m"])
    bump = t.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    bump.inputs["Distance"].default_value = 0.001
    t.put(bump.inputs["Height"], t.mul(fine, 0.2))
    bsdf = t.n("ShaderNodeBsdfPrincipled")
    t.put(bsdf.inputs["Base Color"], c)
    t.put(bsdf.inputs["Roughness"], r)
    t.put(bsdf.inputs["Metallic"], m)
    t.put(bsdf.inputs["Normal"], bump.outputs["Normal"])
    out = t.out(bsdf)
    return dict(t=t, color=c, rough=r, metal=m, bsdf=bsdf, out=out)


# ---- UVs ----------------------------------------------------------------------------------------------------------------------
def faces_using(mats):
    """{object: [polygon indices]} for every face whose material is in mats."""
    names = {m.name for m in mats}
    out = {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        slots = [s.material.name if s.material else None for s in o.material_slots]
        idx = [p.index for p in o.data.polygons if p.material_index < len(slots) and slots[p.material_index] in names]
        if idx:
            out[o] = idx
    return out


def unwrap(group, margin=0.003, angle=58):
    """Smart-project the group's faces (across all its objects) into one shared 0-1 UV space."""
    bpy.ops.object.select_all(action="DESELECT")
    objs = list(group)
    for o in objs:
        me = o.data
        if "UVMap" not in me.uv_layers:
            me.uv_layers.new(name="UVMap")
        sel = set(group[o])
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.select_mode = {"FACE"}
        for f in bm.faces:
            f.select_set(False)
        for f in bm.faces:
            if f.index in sel:
                f.select_set(True)
        bm.select_flush_mode()
        bm.to_mesh(me)
        bm.free()
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.tool_settings.use_uv_select_sync = True
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    # pack every object's islands together into the 0-1 square, scaled uniformly (even texel density)
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, margin_method="FRACTION", margin=margin, shape_method="CONCAVE", scale=True, merge_overlap=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # report texel density
    area3, area2 = 0.0, 0.0
    for o, idx in group.items():
        me = o.data
        uvl = me.uv_layers["UVMap"].data
        mw = o.matrix_world
        for i in idx:
            p = me.polygons[i]
            area3 += p.area * mw.median_scale**2
            uvs = [uvl[li].uv for li in p.loop_indices]
            a = 0.0
            for k in range(1, len(uvs) - 1):
                u0, u1, u2 = uvs[0], uvs[k], uvs[k + 1]
                a += abs((u1.x - u0.x) * (u2.y - u0.y) - (u2.x - u0.x) * (u1.y - u0.y)) / 2
            area2 += a
    return area3, area2


# ---- baking -------------------------------------------------------------------------------------------------------------------
def new_image(name, size, float_buf=True, color=(0, 0, 0, 1)):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=float_buf)
    img.generated_color = color
    return img


def set_bake_target(mats_in, img, all_mats, dummy):
    """Make the group's materials bake into img and every other material into a throwaway image."""
    for m in all_mats:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        node = nt.nodes.get("__bake__")
        if node is None:
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = "__bake__"
        node.image = img if m in mats_in else dummy
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node


def clear_bake_nodes(all_mats):
    for m in all_mats:
        if m.use_nodes and "__bake__" in m.node_tree.nodes:
            m.node_tree.nodes.remove(m.node_tree.nodes["__bake__"])


def emit_rewire(shaders, key):
    """Route one channel (colour / roughness / metal) to an emission shader for an EMIT bake."""
    saved = []
    for sh in shaders:
        t = sh["t"]
        em = t.n("ShaderNodeEmission")
        v = sh[key]
        if isinstance(v, (int, float)):
            em.inputs["Color"].default_value = (v, v, v, 1)
        elif key == "color":
            t.put(em.inputs["Color"], v)
        else:
            t.put(em.inputs["Color"], v)
        em.inputs["Strength"].default_value = 1.0
        t.nt.links.new(em.outputs[0], sh["out"].inputs["Surface"])
        saved.append((t, em, sh))
    return saved


def emit_restore(saved):
    for t, em, sh in saved:
        t.nt.links.new(sh["bsdf"].outputs[0], sh["out"].inputs["Surface"])
        t.nt.nodes.remove(em)


def bake(objs, kind, samples, margin=16):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.bake.margin = margin
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    t = time.time()
    if kind == "NORMAL":
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=margin, use_clear=True)
    else:
        bpy.ops.object.bake(type=kind, margin=margin, use_clear=True)
    print(f"  baked {kind} ({samples} spp) in {time.time() - t:.0f}s", flush=True)


def pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def save_array(arr, path, colorspace, fmt, quality=92):
    """Write an HxWx4 float array (linear values) as an 8-bit image file through Blender, so colour management applies."""
    h, w = arr.shape[:2]
    name = os.path.splitext(os.path.basename(path))[0]
    img = bpy.data.images.new(name + "_out", w, h, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709" if colorspace == "sRGB" else "Non-Color"
    img.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    scene = bpy.context.scene
    s = scene.render.image_settings
    s.file_format = fmt
    s.color_mode = "RGB"
    s.color_depth = "8"
    if fmt == "JPEG":
        s.quality = quality
    if colorspace == "sRGB":
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.display_settings.display_device = "sRGB"
        img.save_render(path, scene=scene)
    else:
        prev = scene.view_settings.view_transform
        scene.view_settings.view_transform = "Raw"
        img.save_render(path, scene=scene)
        scene.view_settings.view_transform = prev
    bpy.data.images.remove(img)


def blur(a, r=1):
    """Tiny box blur (to settle bake noise)."""
    out = a.copy()
    k = 0
    acc = np.zeros_like(a)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            acc += np.roll(np.roll(a, dy, 0), dx, 1)
            k += 1
    return acc / k


def bake_set(label, group_mats, all_mats, size, out_dir, shaders_fn, ao_samples=40, color_samples=10, extra_hide=(), metal=True):
    """UV-unwrap a group of materials, bake AO, colour, roughness/metal and normals, save the textures.
    shaders_fn(ao_image) builds each material's weathered shader and returns them."""
    print(f"[{label}] unwrapping", flush=True)
    group = faces_using(group_mats)
    a3, a2 = unwrap(group)
    texel = math.sqrt(a3 / (a2 * size * size)) * 1000 if a2 else 0
    print(f"  {len(group)} objects, {a3:.1f} m2 of surface, {a2 * 100:.0f}% of the atlas used, {texel:.2f} mm per texel at {size}px", flush=True)
    objs = list(group)
    dummy = new_image("__dummy__", 8, False)
    hidden = [o for o in bpy.data.objects if o.type == "MESH" and (o.name in extra_hide)]
    for o in hidden:
        o.hide_render = True
    # 1. ambient occlusion (everything else in the scene occludes)
    ao = new_image(f"{label}_ao", size)
    set_bake_target(group_mats, ao, all_mats, dummy)
    bake(objs, "AO", ao_samples)
    ao_arr = blur(pixels(ao), 1)
    ao.pixels.foreach_set(ao_arr.ravel())
    # 2. the procedural look, now that it can read the occlusion
    shaders = shaders_fn(ao)
    res = {}
    for key, samples in (("color", color_samples), ("rough", 4), ("metal", 2)):
        if key == "metal" and not metal:
            res[key] = np.zeros_like(ao_arr)
            continue
        img = new_image(f"{label}_{key}", size)
        set_bake_target(group_mats, img, all_mats, dummy)
        saved = emit_rewire(shaders, key)
        bake(objs, "EMIT", samples)
        emit_restore(saved)
        res[key] = pixels(img)
    nimg = new_image(f"{label}_normal", size, color=(0.5, 0.5, 1, 1))
    set_bake_target(group_mats, nimg, all_mats, dummy)
    bake(objs, "NORMAL", 4)
    res["normal"] = pixels(nimg)
    clear_bake_nodes(all_mats)
    for o in hidden:
        o.hide_render = False
    # 3. save: colour (sRGB JPEG), occlusion-roughness-metallic packed (JPEG), normal (PNG)
    os.makedirs(out_dir, exist_ok=True)
    col = res["color"].copy()
    col[..., 3] = 1
    orm = np.stack([ao_arr[..., 0], res["rough"][..., 0], res["metal"][..., 0], np.ones_like(ao_arr[..., 0])], -1)
    paths = {
        "color": os.path.join(out_dir, f"{label}_basecolor.jpg"),
        "orm": os.path.join(out_dir, f"{label}_orm.jpg"),
        "normal": os.path.join(out_dir, f"{label}_normal.png"),
    }
    save_array(col, paths["color"], "sRGB", "JPEG", 92)
    save_array(orm, paths["orm"], "Non-Color", "JPEG", 92)
    nrm = res["normal"].copy()
    nrm[..., 3] = 1
    save_array(nrm, paths["normal"], "Non-Color", "PNG")
    for k in ("ao", "color", "rough", "metal", "normal"):
        n = f"{label}_{k}"
        if n in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[n])
    return paths


# ---- export materials ------------------------------------------------------------------------------------------------------
def gltf_output_group():
    name = "glTF Material Output"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    g = bpy.data.node_groups.new(name, "ShaderNodeTree")
    g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    g.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def textured(mat, paths):
    """Rebuild a material as a plain textured PBR one (what glTF carries)."""
    t = NT(mat)
    uv = t.n("ShaderNodeUVMap", _uv_map="UVMap")
    col = t.image(load_image(paths["color"], "sRGB"), uv.outputs["UV"], ext="EXTEND")
    orm_img = t.image(load_image(paths["orm"]), uv.outputs["UV"], ext="EXTEND")
    nrm = t.image(load_image(paths["normal"]), uv.outputs["UV"], ext="EXTEND")
    sep = t.n("ShaderNodeSeparateColor")
    t.put(sep.inputs[0], orm_img.outputs["Color"])
    nm = t.n("ShaderNodeNormalMap", _uv_map="UVMap")
    t.put(nm.inputs["Color"], nrm.outputs["Color"])
    bsdf = t.n("ShaderNodeBsdfPrincipled")
    t.put(bsdf.inputs["Base Color"], col.outputs["Color"])
    t.put(bsdf.inputs["Roughness"], sep.outputs[1])
    t.put(bsdf.inputs["Metallic"], sep.outputs[2])
    t.put(bsdf.inputs["Normal"], nm.outputs["Normal"])
    grp = t.n("ShaderNodeGroup")
    grp.node_tree = gltf_output_group()
    t.put(grp.inputs["Occlusion"], sep.outputs[0])
    t.out(bsdf)
    mat.use_backface_culling = True


def merge_slots(target, sources):
    """Faces using any of `sources` switch to `target` (the group's single baked material)."""
    src = {m.name for m in sources}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        slots = o.material_slots
        for i, s in enumerate(slots):
            if s.material and s.material.name in src:
                s.material = target
