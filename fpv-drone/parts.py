"""The quad's geometry. Every function takes the materials dict M and the root
node and builds one group of parts, in model axes (see drone.py).

Plates are 2D outlines (shapely, so arms, slots and holes are exact) extruded
along Y. Everything round is a lathe; the props are lofted airfoil sections."""
import math
import numpy as np
import bpy
from mathutils import geometry, Vector
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from geom import Mesh, Frame, tube, path_tube, rbox, empty, airfoil, pchip, B
from vehicle import drive
from drone import *

S2 = math.sqrt(2)


# ---- 2D outlines ------------------------------------------------------------------------------------------------------------
def hole(x, z, r):
    return Point(x, z).buffer(r, quad_segs=6)


def slot(p0, p1, r):
    return LineString([p0, p1]).buffer(r, quad_segs=6)


def soften(g, concave=0.004, convex=0.0015):
    """Round an outline's inside corners (where arms meet the body) and its outside ones."""
    g = g.buffer(concave, quad_segs=8).buffer(-concave, quad_segs=8)
    return g.buffer(-convex, quad_segs=6).buffer(convex, quad_segs=6)


def arm_outline(sx, sz):
    """One arm, from the middle out to a round end that carries the motor: 25 mm at the root, 18 mm through the
    middle, flaring to 29 mm at the motor, in (x, z)."""
    L = ARM_L
    arm = unary_union([Polygon([(0.0, -0.0125), (L - 0.02, -0.0090), (L - 0.02, 0.0090), (0.0, 0.0125)]), Point(L, 0).buffer(0.0145, quad_segs=10)])
    ux, uz = sx / S2, sz / S2
    return affinity.affine_transform(arm, [ux, -uz, uz, ux, 0, 0])


def arm_point(sx, sz, u, v=0.0):
    """A point along an arm: u from the middle outward, v across it."""
    ux, uz = sx / S2, sz / S2
    return (ux * u - uz * v, uz * u + ux * v)


STRAP_Z = 0.0
STRAP_W = 0.016
STRAP_SLOT = [slot((x, STRAP_Z - 0.0075), (x, STRAP_Z + 0.0075), 0.0015) for x in (-0.021, 0.021)]


def bottom_outline():
    body = Polygon(BODY)
    g = unary_union([body] + [arm_outline(sx, sz) for sx in (-1, 1) for sz in (-1, 1)])
    g = soften(g, 0.006)
    cuts = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            cuts.append(slot(arm_point(sx, sz, 0.046), arm_point(sx, sz, 0.084), 0.0032))  # lightening slot in each arm
            mx, mz = sx * A, sz * A
            cuts.append(hole(mx, mz, 0.0050))  # the motor's shaft clearance
            cuts += [hole(mx + dx, mz + dz, 0.00165) for dx in (-0.008, 0.008) for dz in (-0.008, 0.008)]  # 16 x 16 mount
            cuts.append(hole(sx * SO, sz * SO, 0.00165))  # stack mount
    cuts += [hole(0, 0.044, 0.0042), hole(0, -0.044, 0.0042)] + STRAP_SLOT
    return g.difference(unary_union(cuts))


def top_outline():
    body = soften(Polygon(BODY).buffer(-0.0015), 0.003, 0.003)
    body = body.intersection(box(-1, -0.050, 1, 0.050))  # shorter than the bottom plate at both ends
    body = soften(body, 0.002, 0.004)
    cuts = [hole(sx * SO, sz * SO, 0.00165) for sx in (-1, 1) for sz in (-1, 1)]
    cuts += STRAP_SLOT
    cuts += [slot((x, -0.036), (x, -0.010), 0.0042) for x in (-0.0070, 0.0070)] + [slot((x, 0.012), (x, 0.034), 0.0042) for x in (-0.0070, 0.0070)]
    return body.difference(unary_union(cuts))


# ---- extruding an outline ---------------------------------------------------------------------------------------------------
def extrude(m, poly, F, depth, mat=0):
    """A shapely polygon (holes allowed) in frame F's XY plane, extruded `depth` along its Z, centred. Every face points
    out of the solid, whichever way the frame is handed. The walls share no vertices with the caps, so shading
    stays flat on the caps and smooth round a curved edge."""
    rings = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
    flat = [[Vector((x, y, 0)) for x, y in r] for r in rings]
    tris = geometry.tessellate_polygon(flat)
    pts2 = [p for r in rings for p in r]
    zdir = F.d((0, 0, 1))
    for z, sign in ((depth / 2, 1), (-depth / 2, -1)):
        ids = m.verts([F.p((x, y, z)) for x, y in pts2])
        for t in tris:
            a, b, c = (np.asarray(m.v[ids[i]]) for i in t)
            up = np.dot(np.cross(b - a, c - a), zdir) * sign > 0
            m.face([ids[i] for i in (t if up else t[::-1])], mat)
    for r in rings:
        n = len(r)
        lo = m.verts([F.p((x, y, -depth / 2)) for x, y in r])
        hi = m.verts([F.p((x, y, depth / 2)) for x, y in r])
        for i in range(n):
            a, b = np.asarray(r[i]), np.asarray(r[(i + 1) % n])
            d = b - a
            ln = np.linalg.norm(d)
            if ln < 1e-7:
                continue
            n2 = np.array([d[1], -d[0]]) / ln
            if poly.contains(Point(*((a + b) / 2 + n2 * 1e-5))):
                n2 = -n2
            want = F.d((n2[0], n2[1], 0))
            q = [lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]]
            p0, p1, p3 = (np.asarray(m.v[k]) for k in (q[0], q[1], q[3]))
            m.face(q if np.dot(np.cross(p1 - p0, p3 - p0), want) > 0 else q[::-1], mat)


def frame_y(y):
    """Frame at height y: local (x, y) are world (x, z); local Z is up."""
    return Frame((0, y, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))


def frame_z(z):
    """Frame at depth z: local (x, y) are world (x, y); local Z is forward."""
    return Frame((0, 0, z), (1, 0, 0), (0, 1, 0), (0, 0, 1))


# ---- UVs, for the two parts that wear an image ------------------------------------------------------------------------------
def uv_box(obj, scale, offset=(0.0, 0.0)):
    """Project each face along its dominant axis (model axes): top and bottom by (x, z), the sides by their own plane."""
    me = obj.data
    layer = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        n = np.array([p.normal.x, p.normal.z, -p.normal.y])  # to model axes
        k = int(np.argmax(np.abs(n)))
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            x, y, z = c.x, c.z, -c.y
            u, v = {0: (z, y), 1: (x, z), 2: (x, y)}[k]
            layer.data[li].uv = (u * scale + offset[0], v * scale + offset[1])


def uv_label(obj, cx, cz, length, width):
    """The battery: the label covers the top face, every other face samples the plain corner of the image."""
    me = obj.data
    layer = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        up = p.normal.z > 0.5  # Blender Z is model Y
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            x, z = c.x, -c.y
            layer.data[li].uv = (((z - cz) / length + 0.5), ((x - cx) / width + 0.5)) if up else (0.005, 0.005)


# ---- helpers ----------------------------------------------------------------------------------------------------------------
def revolve(m, F, prof, n=28, mats=None, caps=True):
    """Revolve (radius, along) pairs about F's Z. Run the profile from the bottom up, outer wall first, and the faces come
    out facing outward; end it at a radius above zero and the caps close it. mats: one material slot per segment of the
    profile. caps: True (both ends), "top", or False."""
    rings = [[F.p((r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), t)) for i in range(n)] for r, t in prof]
    pick = (lambda ri, j: mats[ri]) if mats else None
    ids = m.grid(rings, closed=True, orient=False, mats=pick)
    if caps in (True, "both") and prof[0][0] > 1e-6:
        m.cap(ids[0], mats[0] if mats else 0, flip=True)
    if caps and prof[-1][0] > 1e-6:
        m.cap(ids[-1], mats[-1] if mats else 0)
    return ids


def up_frame(x, y, z):
    """Frame at a point with its Z up: for parts that turn about a vertical axis."""
    return Frame((x, y, z), (1, 0, 0), (0, 0, -1), (0, 1, 0))


def down_frame(x, y, z):
    return Frame((x, y, z), (1, 0, 0), (0, 0, 1), (0, -1, 0))


# ---- frame -------------------------------------------------------------------------------------------------------------------
def frame(M, root):
    bot = Mesh()
    extrude(bot, bottom_outline(), frame_y((BOT_Y0 + BOT_Y1) / 2), BOT_Y1 - BOT_Y0)
    o = bot.to_object("Frame_Bottom", [M["carbon"]], parent=root, smooth=True, sharp_angle=35)
    uv_box(o, 1 / 0.024, (0.13, 0.31))
    o["drive"] = "the bottom plate and its four arms: 5 mm carbon"
    top = Mesh()
    extrude(top, top_outline(), frame_y((TOP_Y0 + TOP_Y1) / 2), TOP_Y1 - TOP_Y0)
    o = top.to_object("Frame_Top", [M["carbon"]], parent=root, smooth=True, sharp_angle=35)
    uv_box(o, 1 / 0.024, (0.57, 0.04))
    o["drive"] = "the top plate: 2.5 mm carbon, slotted for the battery strap"


def hardware(M, root):
    """Standoffs, and the screws that hold the stack together."""
    for sx in (-1, 1):
        for sz in (-1, 1):
            name = f"Standoff_{'F' if sz > 0 else 'R'}{'L' if sx > 0 else 'R'}"
            m = Mesh()
            tube(m, (sx * SO, BOT_Y1, sz * SO), (sx * SO, TOP_Y0, sz * SO), 0.0032, n=6, mat=0)
            m.to_object(name, [M["alu_black"]], parent=root, smooth=False)
            m = Mesh()
            revolve(m, up_frame(sx * SO, TOP_Y1, sz * SO), [(0.0029, 0.0), (0.0029, 0.0005), (0.0024, 0.0016), (0.0011, 0.0019)], n=14, mats=[0, 0, 0])
            revolve(m, down_frame(sx * SO, BOT_Y0, sz * SO), [(0.0029, 0.0), (0.0029, 0.0005), (0.0024, 0.0016), (0.0011, 0.0019)], n=14, mats=[0, 0, 0])
            m.to_object(name.replace("Standoff", "Screw"), [M["titanium"]], parent=root, smooth=True, sharp_angle=40)


# ---- the stack ------------------------------------------------------------------------------------------------------------------
def board(m, y, half, thick, mat=0, hole_r=0.00165, round_r=0.004):
    g = Polygon([(-half, -half), (half, -half), (half, half), (-half, half)])
    g = g.buffer(-round_r, quad_segs=4).buffer(round_r, quad_segs=4)
    g = g.difference(unary_union([hole(sx * SO, sz * SO, hole_r) for sx in (-1, 1) for sz in (-1, 1)]))
    extrude(m, g, frame_y(y), thick, mat)


def box_at(m, x, y, z, sx, sy, sz, mat=0, r=0.0003):
    rbox(m, Frame((x, y, z), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (sx, sy, sz), r=r, seg=1, mat=mat)


def stack(M, root):
    half = 0.0185
    # the 4-in-1 ESC: a dark board, two rows of power stages, the big capacitors at the back
    m = Mesh()
    board(m, ESC_Y, half, 0.0016, 0)
    top = ESC_Y + 0.0008
    for i, x in enumerate((-0.0105, -0.0035, 0.0035, 0.0105)):
        box_at(m, x, top + 0.0007, 0.0125, 0.0055, 0.0014, 0.0055, 1)
        box_at(m, x, top + 0.0007, -0.0125, 0.0055, 0.0014, 0.0055, 1)
    box_at(m, 0.0, top + 0.001, 0.0, 0.009, 0.002, 0.009, 1, 0.0005)  # the MCU
    for x in (-0.0085, 0.0085):
        revolve(m, up_frame(x, top, -0.0140), [(0.0036, 0.0), (0.0036, 0.0080), (0.0031, 0.0084), (0.0, 0.0084)], n=16, mats=[2, 2, 2])
    for sx in (-1, 1):  # solder pads along the sides, where the motor wires land
        for k in (-1, 0, 1):
            box_at(m, sx * (half - 0.0022), top + 0.00005, k * 0.0042, 0.0028, 0.0001, 0.0028, 3, 0.00004)
    m.to_object("Stack_ESC", [M["pcb"], M["chip"], M["cap"], M["gold"]], parent=root, smooth=True, sharp_angle=40)
    # the flight controller: a board with its processor, the USB-C port at the front and a few connectors
    m = Mesh()
    board(m, FC_Y, half, 0.0016, 0)
    top = FC_Y + 0.0008
    box_at(m, 0.0, top + 0.0009, 0.0, 0.009, 0.0018, 0.009, 1, 0.0005)
    box_at(m, -0.009, top + 0.0007, 0.008, 0.005, 0.0014, 0.005, 1)
    box_at(m, 0.009, top + 0.0007, -0.008, 0.005, 0.0014, 0.005, 1)
    box_at(m, 0.0, top + 0.0016, half - 0.0035, 0.0090, 0.0032, 0.0074, 2, 0.0004)  # USB-C, flush with the front edge
    for sx in (-1, 1):
        box_at(m, sx * (half - 0.0026), top + 0.0016, -0.006, 0.0050, 0.0032, 0.0088, 3, 0.0003)  # JST sockets
    m.to_object("Stack_FC", [M["pcb"], M["chip"], M["titanium"], M["connector"]], parent=root, smooth=True, sharp_angle=40)
    # the video transmitter, with its shield can and the U.FL socket
    m = Mesh()
    board(m, VTX_Y, 0.0165, 0.0016, 0)
    top = VTX_Y + 0.0008
    box_at(m, 0.0, top + 0.0019, 0.001, 0.0170, 0.0038, 0.0170, 1, 0.0004)
    m.to_object("Stack_VTX", [M["pcb"], M["titanium"]], parent=root, smooth=True, sharp_angle=40)


# ---- motors, rotors, props ----------------------------------------------------------------------------------------------------
def blade_rings(R=PROP_R, r0=0.0068, stations=20):
    """Cross-sections of one tri-blade prop's blade, root to tip, along +X, for a prop turning counter-clockwise seen from
    above: the leading edge toward -Z and higher than the trailing edge (the blade is pitched), the section's
    suction side up. Returns rings of (x, y, z) points."""
    sec = airfoil(0.10, n=9, camber=0.05)  # chord 0..1 from the leading edge; 18 points round
    chord = pchip([0.0, 0.12, 0.5, 0.86, 1.0], [0.0085, 0.0125, 0.0178, 0.0146, 0.0030])
    pitch = 0.105  # 4.1 inch of advance per turn
    rings = []
    for i in range(stations):
        s = (i / (stations - 1)) ** 0.85
        r = r0 + (R - r0) * s
        c = chord(s)
        beta = min(math.atan(pitch / (2 * math.pi * r)), math.radians(34))
        cd = np.array([0.0, -math.sin(beta), math.cos(beta)])  # leading edge -> trailing edge
        nd = np.array([0.0, math.cos(beta), math.sin(beta)])  # the suction side
        rings.append([np.array([r, 0.0, 0.0]) + cd * (xc - 0.35) * c + nd * yc * c for xc, yc in sec])
    return rings


def prop_mesh(front):
    m = Mesh()
    base = PROP_Y
    # the hub: a short drum with a domed top
    revolve(m, up_frame(0, base, 0), [(0.0088, 0.0), (0.0090, 0.0014), (0.0084, 0.0040), (0.0068, 0.0053), (0.0034, 0.0057)], n=36, mats=[0] * 4)
    rings0 = blade_rings()
    for k in range(3):
        psi = 2 * math.pi * k / 3
        cs, sn = math.cos(psi), math.sin(psi)
        rot = lambda p: np.array([p[0] * cs + p[2] * sn, p[1] + base + 0.0030, -p[0] * sn + p[2] * cs])
        ids = m.grid([[rot(p) for p in ring] for ring in rings0], closed=True, orient=False)
        m.cap(ids[0])
        m.cap(ids[-1])
    return m


def prop(M, rotor, name, spin, front, cx, cz):
    m = prop_mesh(front)
    if spin < 0:  # a clockwise prop is the other's mirror image
        m = m.mirrored()
    m = m.transformed(lambda p: p + np.array([cx, 0.0, cz]))
    return m.to_object(name, [M["prop_front" if front else "prop_rear"]], parent=rotor, smooth=True, sharp_angle=50, normals="recalc")


def motors(M, root):
    for tag, mo in MOTORS.items():
        mx, mz = mo["pos"]
        front = tag[0] == "F"
        # the stator and its base stay on the arm
        m = Mesh()
        revolve(m, up_frame(mx, BASE_Y0, mz), [(0.0132, 0.0), (0.0135, 0.0004), (0.0135, 0.0031), (0.0128, 0.0035)], n=32, mats=[0, 0, 0])
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            revolve(m, up_frame(mx + 0.0113 * math.cos(a), BASE_Y1, mz + 0.0113 * math.sin(a)), [(0.0016, 0.0), (0.0016, 0.0009), (0.0010, 0.0011)], n=8, mats=[2, 2, 2])
        revolve(m, up_frame(mx, BASE_Y1, mz), [(0.0104, 0.0), (0.0104, BELL_Y0 - BASE_Y1 + 0.001)], n=32, mats=[1])  # windings, seen under the bell
        m.to_object(f"Motor_{tag}_Stator", [M["alu_black"], M["copper"], M["titanium"]], parent=root, smooth=True, sharp_angle=40)

        # the rotor turns about the motor's axis: its bell, the prop and the prop nut
        rotor = empty(f"Rotor_{tag}", (mx, ROTOR_PIVOT_Y, mz), root, size=0.01)
        h = BELL_Y1 - BELL_Y0
        m = Mesh()
        bell = [(0.0128, 0.0), (0.0142, 0.0007), (0.0147, 0.0022), (0.0147, h - 0.0042), (0.0143, h - 0.0017), (0.0128, h - 0.0004), (0.0116, h), (0.0083, h), (0.0083, h - 0.0004), (0.0060, h - 0.0004), (0.0054, h + 0.0004)]
        revolve(m, up_frame(mx, BELL_Y0, mz), bell, n=36, mats=[0, 0, 0, 0, 0, 0, 0, 1, 1, 1])
        for k in range(6):  # six dark vent windows on the top, each a curved slot
            a0 = math.radians(60 * k + 8)
            pts = lambda r, t: [up_frame(mx, BELL_Y0, mz).p((r * math.cos(a0 + math.radians(44) * i / 6), r * math.sin(a0 + math.radians(44) * i / 6), t)) for i in range(7)]
            m.grid([pts(0.0108, h + 0.00012), pts(0.0094, h + 0.00012)], closed=False, mat=2, orient=False)
        o = m.to_object(f"Rotor_{tag}_Bell", [M["bell"], M["alu_black"], M["bell_dark"]], parent=rotor, smooth=True, sharp_angle=40)
        prop(M, rotor, f"Rotor_{tag}_Prop", mo["spin"], front, mx, mz)
        m = Mesh()
        revolve(m, up_frame(mx, PROP_Y + 0.0057, mz), [(0.0050, 0.0), (0.0050, 0.0028), (0.0036, 0.0036), (0.0036, 0.0044)], n=6, mats=[0] * 3)
        m.to_object(f"Rotor_{tag}_Nut", [M["alu_black"]], parent=rotor, smooth=False)
        drive(rotor, "spins about local Y: + is counter-clockwise seen from above; the whole rotor (bell, prop, nut) turns together",
              control="prop", axis=(0, 1, 0), spin=mo["spin"], motor=mo["order"], position=tag, max_rpm=32000, prop="5 x 4.1 x 3")


def lights(M, root):
    """An orientation light on each arm: white at the front, red at the back."""
    for tag, mo in MOTORS.items():
        sx, sz = (1 if mo["pos"][0] > 0 else -1), (1 if mo["pos"][1] > 0 else -1)
        u = arm_point(sx, sz, 0.064)
        m = Mesh()
        rbox(m, Frame((u[0], BOT_Y1 + 0.0013, u[1]), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.0065, 0.0026, 0.0045), r=0.0009, seg=2, mat=0)
        o = m.to_object(f"Light_{tag}", [M["light_white" if tag[0] == "F" else "light_red"]], parent=root, smooth=True, sharp_angle=40)
        drive(o, "an orientation LED: scale its emissive material to switch it", control="light")


def wires(M, root):
    """The three phase wires from each motor along its arm to the ESC."""
    m = Mesh()
    y0 = BOT_Y1
    for tag, mo in MOTORS.items():
        sx, sz = (1 if mo["pos"][0] > 0 else -1), (1 if mo["pos"][1] > 0 else -1)
        for dv in (-0.002, 0.0, 0.002):
            def P(u, dy):
                x, z = arm_point(sx, sz, u, dv * (0.55 + 0.45 * (u / ARM_L)))
                return np.array([x, y0 + dy, z])
            pts = [P(ARM_L - 0.0128, 0.0018), P(ARM_L - 0.0185, 0.0009), P(ARM_L - 0.03, 0.0009), P(0.050, 0.0009), P(0.036, 0.0030), P(0.030, ESC_Y - y0 - 0.0008)]
            path_tube(m, pts, 0.0008, n=6, mat=0)
    m.to_object("Motor_Wires", [M["wire"]], parent=root, smooth=True, sharp_angle=60)


# ---- battery -------------------------------------------------------------------------------------------------------------------
def battery(M, root):
    m = Mesh()
    cy = (BAT_Y0 + BAT_Y1) / 2
    rbox(m, Frame((0, BAT_Y0 - PAD_T / 2, BAT_Z), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.0300, PAD_T, 0.0640), r=0.0004, seg=1, mat=0)
    m.to_object("Battery_Pad", [M["rubber"]], parent=root, smooth=False)

    m = Mesh()
    rbox(m, Frame((0, cy, BAT_Z), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (BAT_W, BAT_H, BAT_L), r=0.0045, seg=3, mat=0)
    o = m.to_object("Battery", [M["battery"]], parent=root, smooth=True, sharp_angle=40)
    uv_label(o, 0.0, BAT_Z, BAT_L, BAT_W)
    o["drive"] = "6S 1300 mAh LiPo, shrink-wrapped"
    o["mass_kg"] = 0.215

    # the strap: a loop round the pack and the plates, through the strap slots, with a tab at the top
    m = Mesh()
    inner = box(-0.0198, BOT_Y0 - 0.0002, 0.0198, BAT_Y1 + 0.0004).buffer(-0.002, quad_segs=4).buffer(0.002, quad_segs=4)
    ring = inner.buffer(0.0012, quad_segs=6).difference(inner)
    extrude(m, ring, frame_z(STRAP_Z), STRAP_W, 0)
    extrude(m, Polygon([(-0.0045, BAT_Y1 + 0.0012), (0.0045, BAT_Y1 + 0.0012), (0.0045, BAT_Y1 + 0.0021), (-0.0045, BAT_Y1 + 0.0021)]), frame_z(STRAP_Z), 0.026, 1)
    m.to_object("Battery_Strap", [M["strap"], M["strap_tab"]], parent=root, smooth=True, sharp_angle=35)

    # the pack's lead: short stubs to an XT60 hanging behind it, and the pigtail dropping to the tail
    zb = BAT_Z - BAT_L / 2
    yl = BAT_Y0 + 0.0080
    xt_z = zb - 0.0085
    m = Mesh()
    for dx, mat in ((-0.0034, 1), (0.0034, 0)):
        path_tube(m, [np.array([dx, yl, zb + 0.0005]), np.array([dx, yl, xt_z + 0.0066])], 0.0017, n=8, mat=mat)
        path_tube(m, [np.array([dx, yl - 0.003, xt_z - 0.0066]), np.array([dx, yl - 0.008, xt_z - 0.0090]), np.array([dx, 0.0040, -0.0585])], 0.0017, n=8, mat=mat)
    m.to_object("Battery_Lead", [M["wire_red"], M["wire"]], parent=root, smooth=True, sharp_angle=60)
    m = Mesh()
    box_at(m, 0.0, yl, xt_z, 0.0160, 0.0080, 0.0132, 0, 0.0008)
    m.to_object("Battery_XT60", [M["connector_yellow"]], parent=root, smooth=True, sharp_angle=40)


# ---- camera -----------------------------------------------------------------------------------------------------------------
def camera(M, root):
    t = math.radians(SPEC["cameraTilt"])
    cy = CAM_Y + 0.002
    fwd = np.array([0.0, math.sin(t), math.cos(t)])
    F = Frame.along((0.0, cy, CAM_Z), fwd, up=(0, 1, 0))
    w = SPEC["cameraWidth"]
    m = Mesh()
    rbox(m, F, (w - 0.004, 0.019, 0.0150), r=0.001, seg=2, mat=0)  # the body, between its two side plates
    for sx in (-1, 1):
        rbox(m, Frame(F.p((sx * (w / 2 - 0.001), 0, 0)), F.x, F.y, F.z), (0.002, 0.019, 0.0150), r=0.0005, seg=1, mat=1)
    m.to_object("Camera_Body", [M["cam_plastic"], M["alu_black"]], parent=root, smooth=True, sharp_angle=40)
    m = Mesh()
    Fl = Frame(F.p((0, 0, 0.0075)), F.x, F.y, F.z)
    revolve(m, Fl, [(0.0074, 0.0), (0.0074, 0.0034), (0.0066, 0.0040), (0.0066, 0.0066), (0.0060, 0.0068), (0.0054, 0.0070)], n=28, mats=[0, 0, 0, 0, 1])
    revolve(m, Fl, [(0.0056, 0.0070), (0.0040, 0.0073), (0.0016, 0.0074)], n=28, mats=[2, 2])
    m.to_object("Camera_Lens", [M["cam_plastic"], M["alu_black"], M["optic"]], parent=root, smooth=True, sharp_angle=45)
    # the TPU cage: a tray on the bottom plate's nose and two cheeks, with a screw through each
    m = Mesh()
    tray_y = BOT_Y1 + 0.0015
    box_at(m, 0.0, tray_y, 0.0615, 0.0260, 0.0030, 0.0195, 0, 0.0008)
    for sx in (-1, 1):
        box_at(m, sx * 0.01175, 0.0020, 0.0625, 0.0025, 0.0320, 0.0190, 0, 0.0009)
        revolve(m, Frame((sx * 0.0130, cy, CAM_Z), (0, 0, -sx), (0, 1, 0), (sx, 0, 0)), [(0.0028, 0.0), (0.0028, 0.0006), (0.0021, 0.0012), (0.0009, 0.0014)], n=12, mats=[1, 1, 1])
    m.to_object("Camera_Mount", [M["tpu"], M["titanium"]], parent=root, smooth=True, sharp_angle=40)
    # where a first-person view looks from: the front of the lens, and the way it points
    pt = empty("FPV_Camera_Point", tuple(F.p((0, 0, 0.0148))), root, size=0.01)
    pt["drive"] = "the FPV camera: put a game camera here and point it along `forward`"
    pt["forward"] = [round(float(v), 5) for v in fwd]
    pt["tilt_deg"] = SPEC["cameraTilt"]


# ---- antennas ---------------------------------------------------------------------------------------------------------------
def antennas(M, root):
    m = Mesh()
    box_at(m, 0.0, 0.0, -0.0645, 0.0160, 0.0100, 0.0130, 0, 0.0012)
    m.to_object("Antenna_Mount", [M["tpu"]], parent=root, smooth=True, sharp_angle=40)
    # the VTX antenna: a coax up through the mount, a threaded base and a stiff, black dipole angled up and back
    base = np.array([0.0, 0.0050, -0.0660])
    d = np.array([0.0, 0.74, -0.67])
    d = d / np.linalg.norm(d)
    m = Mesh()
    tube(m, base - d * 0.0030, base + d * 0.0040, 0.0036, n=8, mat=0)
    tube(m, base + d * 0.0040, base + d * 0.0100, 0.0021, n=10, mat=1)
    tube(m, base + d * 0.0100, base + d * 0.0820, 0.0026, n=10, mat=2, r1=0.0021)
    m.to_object("Antenna_VTX", [M["gold"], M["titanium"], M["wire"]], parent=root, smooth=True, sharp_angle=50)
    m = Mesh()
    path_tube(m, [np.array([0.0, VTX_Y, -0.0160]), np.array([0.0, VTX_Y, -0.0480]), np.array([0.0, 0.0030, -0.0600]), np.array([0.0, 0.0050, -0.0660])], 0.0007, n=6, mat=0)
    m.to_object("Antenna_VTX_Coax", [M["wire"]], parent=root, smooth=True, sharp_angle=60)
    # the receiver's two wire dipoles, with their heat-shrunk ends
    for sx in (-1, 1):
        m = Mesh()
        path_tube(m, [np.array([sx * 0.0030, 0.0020, -0.0640]), np.array([sx * 0.0060, 0.0020, -0.0800]), np.array([sx * 0.0200, 0.0030, -0.1020]), np.array([sx * 0.0330, 0.0040, -0.1160])], 0.0007, n=6, mat=0)
        tube(m, np.array([sx * 0.0250, 0.0034, -0.1090]), np.array([sx * 0.0330, 0.0040, -0.1160]), 0.0013, n=8, mat=0)
        m.to_object(f"Antenna_RX_{'L' if sx > 0 else 'R'}", [M["wire"]], parent=root, smooth=True, sharp_angle=60)


def build(M, root):
    frame(M, root)
    hardware(M, root)
    stack(M, root)
    motors(M, root)
    wires(M, root)
    lights(M, root)
    battery(M, root)
    camera(M, root)
    antennas(M, root)
