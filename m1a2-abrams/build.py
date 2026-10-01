"""Builds the M1A2 SEPv3 Abrams in Blender (Python 3.11 with the bpy module:
pip install bpy==5.0.1 pillow).

    python m1a2-abrams/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]] [--scheme tan]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

import bpy

from abrams import *
import hull
import turret
import markings
import vehicle
from vehicle import principled, lights_materials, points, span, centre

ROOT = "M1A2_SEPv3_Abrams"
NOTES = {
    "vehicle": "M1A2 SEPv3 Abrams main battle tank",
    "blurb": "120 mm main gun, CROWS-LP and the T158 track, at 1:1.",
    "weapon": "Turret and gun",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the left",
    "origin": "on the ground, on the centreline, midway between the first and last road wheels",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M1A2_Paint", GREEN, 0.62),
        "chassis": principled("M1A2_Running_Gear", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M1A2_Rubber", (0.016, 0.016, 0.015), 0.86),
        "track": principled("M1A2_Track_Steel", (0.05, 0.048, 0.045), 0.55, 0.6),
        "gun": principled("M1A2_Gun_Metal", (0.03, 0.03, 0.03), 0.45, 0.6),
        "canvas": principled("M1A2_Canvas", (0.12, 0.11, 0.07), 0.85),
        "strap": principled("M1A2_Strap", (0.05, 0.05, 0.035), 0.8),
        "duffel": principled("M1A2_Duffel", (0.06, 0.065, 0.04), 0.82),
        "jerrycan": principled("M1A2_Water_Can", (0.05, 0.06, 0.035), 0.5),
        "cip": principled("M1A2_Combat_ID_Panel", (0.03, 0.035, 0.03), 0.4),
        "optic": principled("M1A2_Optic_Glass", (0.01, 0.02, 0.03), 0.04, 0.6),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    hull.hull(M, root)
    turret.turret(M, root)


def measure():
    O = bpy.data.objects
    allp = points(ROOT)
    hullp = points("Hull")
    shell = points("Turret_Shell")
    link = points("Track_Left_Link_000")
    rw = points("Road_Wheel_Left_3_Mesh")
    belly = points("Hull_Armour")
    rows = [
        ("Length, gun forward", SPEC["lengthGunForward"], span(allp, 2)),
        ("Hull length", SPEC["hullLength"], span(hullp, 2)),
        ("Width (over the skirts)", SPEC["width"], span(allp, 0)),
        ("Height (to the turret roof)", SPEC["height"], float(shell[:, 1].max())),
        ("Ground clearance", SPEC["groundClearance"], float(belly[:, 1].min())),
        ("Track width (T158)", SPEC["trackWidth"], span(link, 0)),
        ("Road wheel diameter", SPEC["roadWheelDiameter"], span(rw, 1)),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((8.0, 2.6, 9.5), (0, 1.3, 0.6), 30),
    "side": ((15.0, 1.5, 0.6), (0, 1.25, 0.6), 30),
    "rear34": ((-7.0, 3.4, -10.5), (0, 1.3, -0.6), 30),
    "top": ((0.01, 16.0, 0.6), (0, 0, 0.6), 30),
    "turret": ((4.5, 4.2, 4.0), (0, 2.2, 0.4), 30),
    "running": ((5.2, 0.8, 2.6), (1.5, 0.6, 0.2), 28),
}

BEAUTY = {
    "hero": ((7.6, 2.3, 9.8), (0, 1.25, 0.8), 32),
    "side": ((15.5, 1.5, 0.8), (0, 1.25, 0.8), 30),
    "rear": ((-7.2, 3.4, -10.2), (0, 1.3, -0.6), 30),
    "turret": ((4.4, 4.2, 4.0), (0, 2.25, 0.3), 30, ["Hatches"]),
    "running": ((5.2, 0.75, 2.6), (1.5, 0.6, 0.2), 28),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.035, 0.035, 0.033),
    low_y=1.0, low_gain=1.8, dust=0.8, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=0.25, rough=0.62,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [
    ("M1A2_Paint_Hull", None),
    ("M1A2_Paint_Turret", lambda n: n.startswith(("Turret", "Gun", "GPS", "CITV", "Commander", "Loader", "CROWS", "Bustle", "Combat"))),
]
GROUPS = [
    ("M1A2_Running_Gear", ["chassis", "rubber", "track"], 1),
    ("M1A2_Kit", ["gun", "canvas", "strap", "duffel", "jerrycan", "cip"], 2),
]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.6, m=0.0, wear=(0.12, 0.11, 0.09), wm=0.6, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.3),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.1),
    "track": dict(c=(0.05, 0.047, 0.043), r=0.5, m=0.7, wear=(0.42, 0.42, 0.4), wm=1.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.4),
    "gun": dict(c=(0.03, 0.03, 0.03), r=0.45, m=0.6, wear=(0.3, 0.3, 0.3), wm=1.0),
    "canvas": dict(c=(0.12, 0.11, 0.07), r=0.88, m=0.0, wear=(0.18, 0.16, 0.11), wm=0.0),
    "strap": dict(c=(0.05, 0.05, 0.035), r=0.8, m=0.0, wear=(0.1, 0.1, 0.08), wm=0.0),
    "duffel": dict(c=(0.06, 0.065, 0.04), r=0.84, m=0.0, wear=(0.12, 0.12, 0.09), wm=0.0),
    "jerrycan": dict(c=(0.05, 0.06, 0.035), r=0.5, m=0.0, wear=(0.2, 0.2, 0.18), wm=1.0),
    "cip": dict(c=(0.03, 0.035, 0.03), r=0.4, m=0.0, wear=(0.1, 0.1, 0.09), wm=0.0),
}
HIDE_MATS = {"M1A2_Optic_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
