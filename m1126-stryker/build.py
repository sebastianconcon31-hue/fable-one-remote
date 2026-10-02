"""Builds the M1126 Stryker ICV in Blender (Python 3.11 with the bpy module:
pip install bpy==5.0.1 pillow).

    python m1126-stryker/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]] [--scheme tan]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

from stryker import *
import parts
import markings
import vehicle
from vehicle import principled, lights_materials, points, span, centre

ROOT = "M1126_Stryker"
NOTES = {
    "vehicle": "M1126 Stryker infantry carrier vehicle",
    "blurb": "8×8 carrier for nine infantry, M151 weapon station with an M2, at 1:1.",
    "weapon": "Weapon station",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the left",
    "origin": "on the ground, on the centreline, midway between the first and last axles",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M1126_Paint", GREEN, 0.62),
        "chassis": principled("M1126_Chassis", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M1126_Rubber", (0.016, 0.016, 0.015), 0.86),
        "gun": principled("M1126_Gun_Metal", (0.03, 0.03, 0.03), 0.45, 0.6),
        "optic": principled("M1126_Optic_Glass", (0.01, 0.02, 0.03), 0.04, 0.6),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    parts.hull(M, root)


def measure():
    allp = points(ROOT, skip={"Antennas"})
    belly = points("Hull_Armour")
    w1l, w1r, w4l = centre("Wheel_1_Left"), centre("Wheel_1_Right"), centre("Wheel_4_Left")
    rows = [
        ("Length", SPEC["length"], span(allp, 2)),
        ("Width", SPEC["width"], span(allp, 0)),
        ("Height (to the top of the weapon station)", SPEC["height"], float(allp[:, 1].max())),
        ("Ground clearance", SPEC["groundClearance"], float(belly[:, 1].min())),
        ("Tyre diameter (12.00R20)", SPEC["tyreDiameter"], span(points("Wheel_1_Left"), 1)),
        ("Tyre width", SPEC["tyreWidth"], span(points("Wheel_1_Left"), 0)),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((6.8, 2.5, 8.2), (0, 1.3, 0.3), 30),
    "side": ((13.0, 1.6, 0.0), (0, 1.35, 0.0), 30),
    "rear34": ((-6.0, 3.2, -8.6), (0, 1.3, -0.6), 30),
    "top": ((0.01, 14.0, 0.0), (0, 0, 0.0), 30),
    "rws": ((3.0, 3.6, 3.6), (0, 2.2, 0.6), 30),
    "wheels": ((3.4, 0.7, 3.8), (1.0, 0.6, 1.0), 28),
}

BEAUTY = {
    "hero": ((6.8, 2.4, 8.4), (0, 1.35, 0.3), 32),
    "side": ((13.0, 1.6, 0.0), (0, 1.35, 0.0), 30),
    "rear": ((-4.0, 2.6, -9.4), (0, 1.25, -2.8), 30, ["Ramp", "Hatches"]),
    "rws": ((3.0, 3.6, 3.6), (0, 2.25, 0.6), 30),
    "wheels": ((3.4, 0.7, 3.8), (1.0, 0.6, 1.0), 28),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.035, 0.035, 0.033),
    low_y=1.2, low_gain=1.7, dust=0.75, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=0.25, rough=0.62,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [("M1126_Paint", None)]
GROUPS = [("M1126_Chassis", ["chassis", "rubber", "gun"], 2)]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.62, m=0.0, wear=(0.09, 0.08, 0.06), wm=0.0, mud=(0.085, 0.064, 0.04), mud_y=1.2, mud_amount=1.2),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.068, 0.043), mud_y=1.2, mud_amount=1.0),
    "gun": dict(c=(0.03, 0.03, 0.03), r=0.45, m=0.6, wear=(0.3, 0.3, 0.3), wm=1.0),
}
HIDE_MATS = {"M1126_Optic_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
