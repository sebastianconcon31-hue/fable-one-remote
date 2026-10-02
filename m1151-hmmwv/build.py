"""Builds the M1151A1 HMMWV in Blender (Python 3.11 with the bpy module:
pip install bpy==5.0.1 pillow).

    python m1151-hmmwv/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]] [--scheme tan]"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))

from hmmwv import *
import parts
import markings
import vehicle
from vehicle import principled, lights_materials, points, span, node_pos, tangent_angle
import numpy as np

ROOT = "M1151A1_HMMWV"
NOTES = {
    "vehicle": "M1151A1 HMMWV, up-armoured",
    "blurb": "Four armoured doors and a gunner's turret with an M2, at 1:1.",
    "weapon": "Gunner's turret",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the driver's left",
    "origin": "on the ground, on the centreline, midway between the axles",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M1151_Paint", GREEN, 0.62),
        "chassis": principled("M1151_Chassis", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M1151_Rubber", (0.016, 0.016, 0.015), 0.86),
        "gun": principled("M1151_Gun_Metal", (0.03, 0.03, 0.03), 0.45, 0.6),
        "interior": principled("M1151_Cab_Interior", (0.012, 0.012, 0.012), 0.6),
        "glass": principled("M1151_Glass", (0.02, 0.025, 0.025), 0.02, alpha=0.55),
        "mirror": principled("M1151_Mirror", (0.85, 0.85, 0.85), 0.03, 1.0),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    parts.body(M, root)
    parts.turret(M, root)
    parts.chassis(M, root)
    parts.wheels(M, root)


def measure():
    allp = points(ROOT)
    cab = points(ROOT, skip={"Turret", "Turret_Ring"})
    w1l, w1r, w2l = node_pos("Wheel_1_Left"), node_pos("Wheel_1_Right"), node_pos("Wheel_2_Left")
    rows = [
        ("Length", SPEC["length"], span(allp, 2)),
        ("Width (over the mirrors)", SPEC["width"], span(allp, 0)),
        ("Height (to the cab roof)", SPEC["height"], float(cab[:, 1].max())),
        ("Wheelbase", SPEC["wheelbase"], w1l[2] - w2l[2]),
        ("Track", SPEC["track"], w1l[0] - w1r[0]),
        ("Tyre diameter (37 in)", SPEC["tyreDiameter"], span(points("Wheel_1_Left"), 1)),
    ]
    # off the road: the ramp angles over the ends and the clearance under the differentials (the wheels and hubs aside)
    body = points(ROOT, skip={"Wheels"})
    zy = body[:, [2, 1]]
    under = body[(np.abs(body[:, 0]) < 0.6) & ((np.abs(body[:, 2] - w1l[2]) < 0.3) | (np.abs(body[:, 2] - w2l[2]) < 0.3))]
    rows += [
        ("Ground clearance (under the differentials)", SPEC["groundClearance"], float(under[:, 1].min())),
        ("Approach angle", SPEC["approachAngle"], tangent_angle(zy, w1l[2], TYRE_R, +1)[0]),
        ("Departure angle", SPEC["departureAngle"], tangent_angle(zy, w2l[2], TYRE_R, -1)[0]),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((5.4, 2.0, 6.4), (0, 1.1, 0.2), 30),
    "side": ((10.0, 1.4, 0.0), (0, 1.15, 0.0), 30),
    "rear34": ((-4.6, 2.6, -6.4), (0, 1.1, -0.4), 30),
    "top": ((0.01, 11.0, 0.0), (0, 0, 0.0), 30),
    "turret": ((2.6, 3.4, 2.4), (0, 2.2, -0.2), 30),
}

BEAUTY = {
    "hero": ((5.4, 2.0, 6.6), (0, 1.15, 0.2), 32),
    "side": ((10.0, 1.4, 0.0), (0, 1.15, 0.0), 30),
    "rear": ((-4.6, 2.6, -6.6), (0, 1.15, -0.5), 30),
    "turret": ((2.6, 3.4, 2.6), (0, 2.25, -0.2), 30),
    "doors": ((4.4, 1.8, 3.4), (0.6, 1.3, 0.0), 30, ["Doors"]),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.035, 0.035, 0.033),
    low_y=1.0, low_gain=1.7, dust=0.75, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=0.25, rough=0.62,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [("M1151_Paint", None)]
GROUPS = [("M1151_Chassis", ["chassis", "rubber", "gun"], 2)]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.62, m=0.0, wear=(0.09, 0.08, 0.06), wm=0.0, mud=(0.085, 0.064, 0.04), mud_y=1.0, mud_amount=1.2),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.068, 0.043), mud_y=1.0, mud_amount=1.0),
    "gun": dict(c=(0.03, 0.03, 0.03), r=0.45, m=0.6, wear=(0.3, 0.3, 0.3), wm=1.0),
}
HIDE_MATS = {"M1151_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
