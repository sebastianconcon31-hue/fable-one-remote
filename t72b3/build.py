"""Builds the T-72B3 in Blender (Python 3.11 with the bpy module:
pip install bpy==5.0.1 pillow).

    python t72b3/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

from t72 import *
import parts
import markings
import vehicle
from vehicle import principled, lights_materials, points, span

ROOT = "T72B3"
NOTES = {
    "vehicle": "T-72B3 main battle tank",
    "blurb": "125 mm 2A46M-5, Kontakt-5 armour and the Sosna-U sight, at 1:1.",
    "weapon": "Turret and gun",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the left",
    "origin": "on the ground, on the centreline, midway between the first and last road wheels",
}
GREEN = (0.062, 0.078, 0.03)  # Russian protective green, linear


def materials():
    M = {
        "paint": principled("T72_Paint", GREEN, 0.6),
        "chassis": principled("T72_Running_Gear", (0.05, 0.062, 0.026), 0.6),
        "rubber": principled("T72_Rubber", (0.016, 0.016, 0.015), 0.86),
        "track": principled("T72_Track_Steel", (0.05, 0.047, 0.043), 0.55, 0.65),
        "canvas": principled("T72_Canvas", (0.07, 0.075, 0.04), 0.88),
        "drum": principled("T72_Fuel_Drum", (0.04, 0.05, 0.025), 0.55),
        "wood": principled("T72_Log", (0.15, 0.1, 0.06), 0.85),
        "optic": principled("T72_Optic_Glass", (0.01, 0.02, 0.03), 0.04, 0.6),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    parts.hull(M, root)
    parts.turret(M, root)


def measure():
    allp = points(ROOT, skip={"Antenna"})
    hullp = points("Hull")
    shell = points("Turret_Shell")
    link = points("Track_Left_Link_000")
    rw = points("Road_Wheel_Left_3_Mesh")
    w1, w6 = points("Road_Wheel_Left_1_Mesh"), points("Road_Wheel_Left_6_Mesh")
    t1, t2 = points("Track_Left"), points("Track_Right")
    rows = [
        ("Length, gun forward", SPEC["lengthGunForward"], span(allp, 2)),
        ("Hull length", SPEC["hullLength"], span(hullp, 2)),
        ("Width (over the skirts)", SPEC["width"], span(allp, 0)),
        ("Height (to the turret roof)", SPEC["height"], float(shell[:, 1].max())),
        ("Track width (RMSh)", SPEC["trackWidth"], span(link, 0)),
        ("Track on the ground (wheel 1 to 6)", SPEC["groundContact"], float((w1[:, 2].max() + w1[:, 2].min()) / 2 - (w6[:, 2].max() + w6[:, 2].min()) / 2)),
        ("Tread (track centres)", SPEC["tread"], float((t1[:, 0].max() + t1[:, 0].min()) / 2 - (t2[:, 0].max() + t2[:, 0].min()) / 2)),
        ("Road wheel diameter", SPEC["roadWheelDiameter"], span(rw, 1)),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((7.6, 2.4, 9.0), (0, 1.2, 0.5), 30),
    "side": ((14.5, 1.4, 0.8), (0, 1.15, 0.8), 30),
    "rear34": ((-6.6, 3.2, -9.6), (0, 1.2, -0.8), 30),
    "top": ((0.01, 15.0, 0.8), (0, 0, 0.8), 30),
    "turret": ((4.2, 3.8, 3.6), (0, 1.9, 0.0), 30),
    "running": ((5.0, 0.8, 2.4), (1.5, 0.6, 0.2), 28),
}

BEAUTY = {
    "hero": ((7.8, 2.3, 9.2), (0, 1.15, 0.6), 32),
    "side": ((14.5, 1.4, 0.8), (0, 1.15, 0.8), 30),
    "rear": ((-6.8, 3.2, -9.8), (0, 1.2, -0.8), 30),
    "turret": ((4.2, 3.8, 3.6), (0, 1.95, 0.0), 30, ["Hatches"]),
    "running": ((5.0, 0.8, 2.4), (1.5, 0.6, 0.2), 28),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.068, 0.082, 0.034), FADED=(0.095, 0.11, 0.06), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.62, 0.62, 0.58), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.11, 0.115, 0.09), WALK=(0.035, 0.035, 0.033),
    low_y=1.0, low_gain=1.8, dust=0.85, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=0.25, rough=0.6,
    rivet=0.06, line_depth=0.8)
SCHEMES = {}

PAINT_SETS = [
    ("T72_Paint_Hull", None),
    ("T72_Paint_Turret", lambda n: n.startswith(("Turret", "Gun", "Sight", "Commander", "Gunner"))),
]
GROUPS = [
    ("T72_Running_Gear", ["chassis", "rubber", "track"], 1),
    ("T72_Kit", ["canvas", "drum", "wood"], 4),
]
SPECS = {
    "chassis": dict(c=(0.05, 0.062, 0.026), r=0.6, m=0.0, wear=(0.12, 0.11, 0.09), wm=0.6, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.3),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.1),
    "track": dict(c=(0.05, 0.047, 0.043), r=0.5, m=0.7, wear=(0.42, 0.42, 0.4), wm=1.0, mud=(0.09, 0.07, 0.045), mud_y=1.1, mud_amount=1.4),
    "canvas": dict(c=(0.07, 0.075, 0.04), r=0.88, m=0.0, wear=(0.12, 0.12, 0.08), wm=0.0),
    "drum": dict(c=(0.04, 0.05, 0.025), r=0.55, m=0.0, wear=(0.25, 0.25, 0.24), wm=1.0),
    "wood": dict(c=(0.15, 0.1, 0.06), r=0.85, m=0.0, wear=(0.22, 0.16, 0.1), wm=0.0),
}
HIDE_MATS = {"T72_Optic_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
