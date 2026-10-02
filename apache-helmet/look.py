"""The helmet's surface finish, at the helmet's scale: noise measured in millimetres rather than metres, edge
wear a fraction of a millimetre wide, a woven bump for the webbing. paint.bake_set turns it into textures."""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))
import bpy
from paint import NT

GRIME = (0.018, 0.017, 0.013)
DUST = (0.13, 0.12, 0.09)


def surface(mat, spec, ao_image):
    """spec: c base colour, r roughness, m metal, wear (edge colour), wm (metal at the edges), and optional
    mid / fine (noise scales per metre), grime (how much dirt gathers in the corners), scuff (how much of the surface
    is scuffed), weave (the webbing's weave, threads per metre)."""
    t = NT(mat)
    g = t.n("ShaderNodeNewGeometry")
    pos = g.outputs["Position"]
    mid = t.noise(pos, spec.get("mid", 30.0), 4.0)
    fine = t.noise(pos, spec.get("fine", 700.0), 4.0, 0.6)
    speck = t.noise(pos, spec.get("fine", 700.0) * 3.1, 2.0, 0.5)
    if ao_image is None:
        aon = t.n("ShaderNodeAmbientOcclusion", _samples=8)
        aon.inputs["Distance"].default_value = 0.03
        ao_v = aon.outputs["AO"]
    else:
        uv = t.n("ShaderNodeUVMap", _uv_map="UVMap")
        ao_v = t.xyz(t.image(ao_image, uv.outputs["UV"]).outputs["Color"])[0]
    c = t.vmath("SCALE", spec["c"], scale=t.madd(mid, 0.28, 0.86))
    c = t.vmath("SCALE", c, scale=t.madd(speck, 0.16, 0.92))
    grime = t.math("POWER", t.math("SUBTRACT", 1.0, ao_v, clamp=True), 1.4)
    c = t.mix(c, GRIME if spec["m"] < 0.5 else (0.02, 0.018, 0.015), t.clamp01(t.mul(t.mul(grime, t.madd(mid, 0.6, 0.5)), spec.get("grime", 1.0))))
    # a little dust where sweat and skin oil have not rubbed it off: upward-facing, in the hollows
    _, _, nzb = t.xyz(g.outputs["Normal"])
    up = t.math("MAXIMUM", nzb, 0.0)
    c = t.mix(c, DUST, t.mul(t.mul(up, t.smooth(mid, 0.45, 0.8)), 0.08 * spec.get("grime", 1.0)))
    # worn edges, scuffs and the places a gloved hand takes the finish off
    bev = t.n("ShaderNodeBevel", _samples=8)
    bev.inputs["Radius"].default_value = spec.get("edge_r", 0.0009)
    edge = t.math("SUBTRACT", 1.0, t.vmath("DOT_PRODUCT", bev.outputs[0], g.outputs["Normal"]))
    wear_noise = t.smooth(fine, 0.46, 0.62)
    wear = t.mul(t.smooth(edge, 0.015, 0.09), wear_noise)
    scuff_n = t.noise(pos, 260.0, 3.0, 0.65)
    scuff = t.mul(t.smooth(scuff_n, 0.60, 0.66), t.smooth(mid, 0.45, 0.62))
    scuff = t.mul(scuff, spec.get("scuff", 0.0))
    wearall = t.clamp01(t.add(wear, scuff))
    c = t.mix(c, spec["wear"], t.mul(wearall, 0.8))
    r = t.add(t.madd(mid, 0.12, spec["r"] - 0.06), t.mul(grime, 0.08))
    r = t.add(r, t.mul(wearall, 0.12 if spec["wm"] < 0.5 else -0.1))
    r = t.math("MAXIMUM", t.math("MINIMUM", r, 0.97), 0.1)
    m = t.madd(wearall, spec["wm"] - spec["m"], spec["m"])
    # the surface: the finish's orange-peel and, for webbing, a woven bump
    h = t.mul(fine, 0.5)
    if "weave" in spec:
        wv = spec["weave"]
        a = t.n("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", _wave_profile="SIN")
        a.inputs["Scale"].default_value = wv
        a.inputs["Distortion"].default_value = 0.6
        t.put(a.inputs["Vector"], pos)
        b = t.n("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="Z", _wave_profile="SIN")
        b.inputs["Scale"].default_value = wv
        b.inputs["Distortion"].default_value = 0.6
        t.put(b.inputs["Vector"], pos)
        wvh = t.mul(a.outputs["Fac"], b.outputs["Fac"])
        h = t.add(h, t.mul(wvh, 0.9))
        c = t.vmath("SCALE", c, scale=t.madd(wvh, 0.35, 0.8))
    bump = t.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = spec.get("bump", 0.35)
    bump.inputs["Distance"].default_value = spec.get("bump_d", 0.0004)
    t.put(bump.inputs["Height"], h)
    bsdf = t.n("ShaderNodeBsdfPrincipled")
    t.put(bsdf.inputs["Base Color"], c)
    t.put(bsdf.inputs["Roughness"], r)
    t.put(bsdf.inputs["Metallic"], m)
    t.put(bsdf.inputs["Normal"], bump.outputs["Normal"])
    out = t.out(bsdf)
    return dict(t=t, color=c, rough=r, metal=m, bsdf=bsdf, out=out)
