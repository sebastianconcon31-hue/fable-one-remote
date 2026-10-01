"""Builds the M2A3 Bradley in Blender (Python 3.11 with the bpy module:
pip install bpy==5.0.1 pillow).

    python m2a3-bradley/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]] [--scheme tan]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

from bradley import *
import parts
import markings
import vehicle
from vehicle import principled, lights_materials, points, span

ROOT = "M2A3_Bradley"
NOTES = {
    "vehicle": "M2A3 Bradley infantry fighting vehicle",
    "blurb": "25 mm Bushmaster, twin TOW, rear ramp for seven infantry, at 1:1.",
    "weapon": "Turret, 25 mm gun",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the left",
    "origin": "on the ground, on the centreline, midway between the first and last road wheels",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M2A3_Paint", GREEN, 0.62),
        "chassis": principled("M2A3_Running_Gear", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M2A3_Rubber", (0.016, 0.016, 0.015), 0.86),
        "track": principled("M2A3_Track_Steel", (0.05, 0.048, 0.045), 0.55, 0.6),
        "gun": principled("M2A3_Gun_Metal", (0.03, 0.03, 0.03), 0.45, 0.6),
        "canvas": principled("M2A3_Canvas", (0.12, 0.11, 0.07), 0.85),
        "strap": principled("M2A3_Strap", (0.05, 0.05, 0.035), 0.8),
        "duffel": principled("M2A3_Duffel", (0.06, 0.065, 0.04), 0.82),
        "optic": principled("M2A3_Optic_Glass", (0.01, 0.02, 0.03), 0.04, 0.6),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    parts.hull(M, root)
    parts.turret(M, root)


def measure():
    allp = points(ROOT, skip={"Antennas"})
    belly = points("Hull_Armour")
    link = points("Track_Left_Link_000")
    w1, w6 = points("Road_Wheel_Left_1_Mesh"), points("Road_Wheel_Left_6_Mesh")
    rows = [
        ("Length", SPEC["length"], span(allp, 2)),
        ("Width (over the add-on armour)", SPEC["width"], span(allp, 0)),
        ("Height (to the top of the CIV)", SPEC["height"], float(allp[:, 1].max())),
        ("Ground clearance", SPEC["groundClearance"], float(belly[:, 1].min())),
        ("Track width (T157)", SPEC["trackWidth"], span(link, 0)),
        ("Track on the ground (wheel 1 to 6)", SPEC["groundContact"], float((w1[:, 2].max() + w1[:, 2].min()) / 2 - (w6[:, 2].max() + w6[:, 2].min()) / 2)),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((7.0, 2.6, 8.0), (0, 1.3, 0.3), 30),
    "side": ((13.0, 1.6, 0.0), (0, 1.35, 0.0), 30),
    "rear34": ((-6.0, 3.2, -8.5), (0, 1.3, -0.6), 30),
    "top": ((0.01, 14.0, 0.0), (0, 0, 0.0), 30),
    "turret": ((4.0, 4.0, 3.5), (0, 2.3, 0.4), 30),
    "ramp": ((-2.6, 2.0, -7.5), (0, 1.2, -3.0), 30),
}

BEAUTY = {
    "hero": ((7.0, 2.4, 8.2), (0, 1.35, 0.4), 32),
    "side": ((13.0, 1.6, 0.0), (0, 1.35, 0.0), 30),
    "rear": ((-4.4, 2.6, -9.0), (0, 1.2, -2.4), 30, ["Ramp", "Ramp door"]),
    "turret": ((4.0, 4.0, 3.5), (0, 2.3, 0.2), 30, ["TOW launcher", "Hatches"]),
    "running": ((4.6, 0.75, 2.4), (1.4, 0.6, 0.3), 28),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.035, 0.035, 0.033),
    low_y=1.0, low_gain=1.8, dust=0.8, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=0.25, rough=0.62,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [
    ("M2A3_Paint_Hull", None),
    ("M2A3_Paint_Turret", lambda n: n.startswith(("Turret", "Gun", "TOW", "IBAS", "CIV", "Commander", "Gunner"))),
]
GROUPS = [
    ("M2A3_Running_Gear", ["chassis", "rubber", "track"], 1),
    ("M2A3_Kit", ["gun", "canvas", "strap", "duffel"], 4),
]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.6, m=0.0, wear=(0.12, 0.11, 0.09), wm=0.6, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.3),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.1),
    "track": dict(c=(0.05, 0.047, 0.043), r=0.5, m=0.7, wear=(0.42, 0.42, 0.4), wm=1.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.4),
    "gun": dict(c=(0.03, 0.03, 0.03), r=0.45, m=0.6, wear=(0.3, 0.3, 0.3), wm=1.0),
    "canvas": dict(c=(0.12, 0.11, 0.07), r=0.88, m=0.0, wear=(0.18, 0.16, 0.11), wm=0.0),
    "strap": dict(c=(0.05, 0.05, 0.035), r=0.8, m=0.0, wear=(0.1, 0.1, 0.08), wm=0.0),
    "duffel": dict(c=(0.06, 0.065, 0.04), r=0.84, m=0.0, wear=(0.12, 0.12, 0.09), wm=0.0),
}
HIDE_MATS = {"M2A3_Optic_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
