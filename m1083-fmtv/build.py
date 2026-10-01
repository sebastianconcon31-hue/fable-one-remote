"""Builds the M1083A1P2 FMTV cargo truck in Blender (Python 3.11 with the bpy
module: pip install bpy==5.0.1 pillow). The pallet loads reuse the HEMTT's
builders (../hemtt-m977/truck.py).

    python m1083-fmtv/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]] [--scheme tan]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

from fmtv import *
import parts
import markings
import vehicle
from vehicle import principled, lights_materials, points, span, node_pos

ROOT = "M1083A1P2_FMTV"
NOTES = {
    "vehicle": "M1083A1P2 FMTV 5-ton cargo truck",
    "blurb": "6×6 medium tactical truck with six pallets of supplies, at 1:1.",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the driver's left",
    "origin": "on the ground, on the centreline, midway between the front axle and the centre of the rear pair",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M1083_Paint", GREEN, 0.62),
        "chassis": principled("M1083_Chassis", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M1083_Rubber", (0.016, 0.016, 0.015), 0.86),
        "interior": principled("M1083_Cab_Interior", (0.012, 0.012, 0.012), 0.6),
        "glass": principled("M1083_Glass", (0.02, 0.025, 0.025), 0.02, alpha=0.55),
        "mirror": principled("M1083_Mirror", (0.85, 0.85, 0.85), 0.03, 1.0),
        "exhaust": principled("M1083_Exhaust", (0.03, 0.025, 0.02), 0.7, 0.4),
        "wood": principled("M1083_Cargo_Wood", (0.3, 0.2, 0.11), 0.78),
        "drum": principled("M1083_Cargo_Drum", (0.05, 0.055, 0.03), 0.5),
        "ammo_can": principled("M1083_Cargo_Ammo_Can", (0.042, 0.048, 0.026), 0.45),
        "crate": principled("M1083_Cargo_Crate", (0.2, 0.135, 0.07), 0.8),
        "strap": principled("M1083_Cargo_Strap", (0.55, 0.16, 0.02), 0.72),
        "cardboard": principled("M1083_Cargo_Cardboard", (0.36, 0.26, 0.15), 0.85),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    parts.cab(M, root)
    parts.front(M, root)
    parts.chassis(M, root)
    parts.wheels(M, root)
    parts.mid_body(M, root)
    parts.cargo_body(M, root)
    parts.cargo(M, root)
    parts.lights(M, root)


def measure():
    allp = points(ROOT, skip={"Mirrors_And_Trim", "Mirror_Glass"})
    w1, w2, w3 = node_pos("Wheel_1_Left"), node_pos("Wheel_2_Left"), node_pos("Wheel_3_Left")
    bed = points("Cargo_Body_Mesh")
    rows = [
        ("Length", SPEC["length"], span(allp, 2)),
        ("Width (without mirrors)", SPEC["width"], span(allp, 0)),
        ("Height (to the cab roof)", SPEC["height"], float(allp[:, 1].max())),
        ("Wheelbase (to the rear pair's centre)", SPEC["wheelbase"], w1[2] - (w2[2] + w3[2]) / 2),
        ("Tyre diameter (395/85R20)", SPEC["tyreDiameter"], span(points("Wheel_1_Left"), 1)),
        ("Cargo bed, inside length", SPEC["bedLength"], float(BED_FRONT_Z - 0.05 - (BED_REAR_Z + 0.04))),
        ("Cargo bed, inside width", SPEC["bedWidth"], 2 * (BED_HALF_W - 0.045)),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((6.6, 2.4, 8.8), (0, 1.4, 0.4), 30),
    "side": ((13.0, 1.6, -0.3), (0, 1.4, -0.3), 30),
    "rear34": ((-6.0, 3.6, -10.0), (0, 1.4, -1.0), 30),
    "top": ((0.01, 15.0, -0.3), (0, 0, -0.3), 30),
    "cab": ((3.2, 2.2, 6.4), (0, 1.8, 2.6), 30),
}

BEAUTY = {
    "hero": ((6.8, 2.5, 9.0), (0, 1.45, 0.4), 32),
    "side": ((13.0, 1.6, -0.3), (0, 1.4, -0.3), 30),
    "rear": ((-5.4, 3.8, -10.4), (0, 1.5, -1.6), 30, ["Tailgate"]),
    "cab": ((3.2, 2.2, 6.6), (0, 1.8, 2.6), 30),
    "cargo": ((-3.2, 5.4, -6.4), (0, 1.6, -1.6), 30),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.5, 0.34, 0.01),
    low_y=1.35, low_gain=1.6, dust=0.7, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=-0.05, rough=0.6,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [
    ("M1083_Paint_Front", None),
    ("M1083_Paint_Back", lambda n: n.startswith(("Cargo_Body", "Tailgate", "Rear_End", "Fuel_Tank", "Battery"))),
]
GROUPS = [
    ("M1083_Chassis", ["chassis", "rubber", "exhaust"], 2),
    ("M1083_Cargo", ["wood", "drum", "ammo_can", "crate", "strap", "cardboard"], 2),
]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.62, m=0.0, wear=(0.09, 0.08, 0.06), wm=0.0, mud=(0.085, 0.064, 0.04), mud_y=1.3, mud_amount=1.2),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.068, 0.043), mud_y=1.25, mud_amount=1.0),
    "exhaust": dict(c=(0.035, 0.026, 0.02), r=0.72, m=0.4, wear=(0.08, 0.05, 0.03), wm=0.6),
    "wood": dict(c=(0.3, 0.2, 0.11), r=0.8, m=0.0, wear=(0.38, 0.28, 0.17), wm=0.0),
    "drum": dict(c=(0.05, 0.055, 0.03), r=0.5, m=0.0, wear=(0.25, 0.25, 0.24), wm=1.0),
    "ammo_can": dict(c=(0.042, 0.048, 0.026), r=0.45, m=0.0, wear=(0.25, 0.25, 0.24), wm=1.0),
    "crate": dict(c=(0.2, 0.135, 0.07), r=0.82, m=0.0, wear=(0.3, 0.22, 0.13), wm=0.0),
    "strap": dict(c=(0.55, 0.16, 0.02), r=0.72, m=0.0, wear=(0.4, 0.15, 0.04), wm=0.0),
    "cardboard": dict(c=(0.36, 0.26, 0.15), r=0.86, m=0.0, wear=(0.42, 0.32, 0.2), wm=0.0),
}
HIDE_MATS = {"M1083_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
