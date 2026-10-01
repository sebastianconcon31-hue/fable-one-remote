"""Builds the HEMTT M978A4 fuel servicing truck in Blender (Python 3.11 with
the bpy module: pip install bpy==5.0.1 pillow). The cab, frame and running
gear are the M977A4's (../hemtt-m977/truck.py); the tank and pump module are
in tanker.py.

    python hemtt-m978/build.py [--glb FILE] [--textures N] [--blend FILE] [--preview DIR [--lookdev] [--views a,b]]"""
import sys
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "modelkit"))
sys.path.append(os.path.join(HERE, "..", "hemtt-m977"))  # last: markings.py here must win over the M977's

import numpy as np

import m978
from m978 import SPEC, TYRE_R
import truck
import tanker
import markings
import vehicle
from vehicle import principled, lights_materials, drive, points, centre, span

# the M977's parts, with the M978's longer rear end
truck.SPEC = SPEC
truck.REAR_Z = m978.REAR_Z
truck.BUMPER_REAR_Z = m978.BUMPER_REAR_Z

ROOT = "HEMTT_M978A4"
NOTES = {
    "vehicle": "HEMTT M978A4 fuel servicing truck",
    "blurb": "8×8 tanker carrying 2,500 US gallons of fuel, with its pump module, at 1:1.",
    "units": "metres",
    "axes": "glTF: +Y up, +Z toward the front, +X to the driver's left",
    "origin": "on the ground, on the centreline, midway between the front and rear axle pairs",
}
GREEN = (0.044, 0.054, 0.031)  # CARC green 383, linear


def materials():
    M = {
        "paint": principled("M978_Paint", GREEN, 0.62),
        "chassis": principled("M978_Chassis", (0.036, 0.041, 0.027), 0.6),
        "rubber": principled("M978_Rubber", (0.016, 0.016, 0.015), 0.86),
        "interior": principled("M978_Interior", (0.012, 0.012, 0.012), 0.6),
        "glass": principled("M978_Glass", (0.02, 0.025, 0.025), 0.02, alpha=0.55),
        "mirror": principled("M978_Mirror", (0.85, 0.85, 0.85), 0.03, 1.0),
        "exhaust": principled("M978_Exhaust", (0.03, 0.025, 0.02), 0.7, 0.4),
        "steel": principled("M978_Steel", (0.62, 0.62, 0.6), 0.18, 1.0),
        "hazard": principled("M978_Hazard_Yellow", (0.5, 0.33, 0.01), 0.55),
        "hose": principled("M978_Hose", (0.012, 0.012, 0.012), 0.7),
        "extinguisher": principled("M978_Extinguisher_Red", (0.4, 0.015, 0.01), 0.4),
    }
    M.update(lights_materials())
    return M


def build(M, root):
    truck.cab(M, root)
    truck.front(M, root)
    truck.chassis(M, root)
    truck.wheels(M, root)
    truck.mid_body(M, root)
    truck.lights(M, root)
    tanker.tank(M, root)
    tanker.pump_module(M, root)
    tanker.rear_end(M, root)
    notes()


def notes():
    import bpy
    O = bpy.data.objects
    for i in range(1, 5):
        for s in ("Left", "Right"):
            drive(O[f"Wheel_{i}_{s}"], "spin about local X; + rolls the truck forward", control="wheel", axis=[1, 0, 0], radius=round(TYRE_R, 4))
    lock1, lock2 = truck.steer_limits()
    for i, lim in ((1, lock1), (2, lock2)):
        for s in ("Left", "Right"):
            drive(O[f"Steer_{i}_{s}"], f"steer about local Y; + turns left. Full lock ({math.degrees(lock1):.0f} degrees on the first axle, "
                  f"{math.degrees(lock2):.0f} on the second) is the inner wheels' for the published 100 ft turning circle.",
                  control="steer", axis=[0, 1, 0], limits=[-round(lim, 4), round(lim, 4)])
    for s in ("Left", "Right"):
        d = O[f"Door_{s}"]
        d["control"] = "hinge"
        d["group"] = "Cab doors"
    for o in O:
        if o.name.startswith("Light_") and o.type == "EMPTY":
            o["light"] = o.name[6:].replace("_", " ").lower()


def tank_volume():
    """The shell's volume from its rings (trapezoids between cross-sections)."""
    rings = tanker.tank_rings()
    zs, areas = [], []
    for r in rings:
        xy = np.array([(p[0], p[1]) for p in r])
        x, y = xy[:, 0], xy[:, 1]
        areas.append(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)))
        zs.append(r[0][2])
    return float(sum((areas[i] + areas[i + 1]) / 2 * abs(zs[i] - zs[i + 1]) for i in range(len(zs) - 1)))


def measure():
    allp = points(ROOT, skip={"Mirrors_And_Trim", "Mirror_Glass"})
    w1l, w1r = centre("Wheel_1_Left"), centre("Wheel_1_Right")
    w2l, w3l, w4l = centre("Wheel_2_Left"), centre("Wheel_3_Left"), centre("Wheel_4_Left")
    rows = [
        ("Length", SPEC["length"], span(allp, 2)),
        ("Width (without mirrors)", SPEC["width"], span(allp, 0)),
        ("Height (over the spare tyre)", SPEC["height"], span(allp, 1)),
        ("Wheelbase (axle pair to axle pair)", SPEC["wheelbase"], (w1l[2] + w2l[2]) / 2 - (w3l[2] + w4l[2]) / 2),
        ("Track", SPEC["track"], w1l[0] - w1r[0]),
        ("Tyre diameter (16.00R20)", SPEC["tyreDiameter"], span(points("Wheel_1_Left"), 1)),
        ("Tank, m3 (2,500 US gal)", SPEC["tankCapacity"], tank_volume()),
    ]
    return rows, float(allp[:, 1].min())


VIEWS = {
    "front34": ((7.2, 2.2, 10.5), (0, 1.3, 0.3), 30),
    "side": ((15.0, 1.6, -0.5), (0, 1.45, -0.5), 30),
    "rear34": ((-6.8, 3.6, -12.4), (0, 1.4, -1.4), 30),
    "top": ((0.01, 18.0, -0.5), (0, 0, -0.5), 30),
    "pump": ((-3.4, 2.4, -9.6), (0, 1.8, -4.8), 30),
    "tank": ((5.5, 4.4, 2.5), (0, 2.2, -1.2), 30),
}

BEAUTY = {
    "hero": ((7.4, 2.4, 10.6), (0, 1.35, 0.2), 32),
    "side": ((15.5, 1.7, -0.5), (0, 1.45, -0.5), 30),
    "rear": ((-4.4, 2.6, -11.0), (0, 1.6, -4.6), 30, ["Pump doors"]),
    "tank": ((5.5, 4.4, 2.5), (0, 2.2, -1.2), 30),
    "pump": ((-3.6, 2.2, -8.6), (-0.4, 1.8, -4.8), 30, ["Pump doors"]),
}

PALETTE = dict(
    PAINT=GREEN, PAINT_VARIANT=(0.05, 0.057, 0.038), FADED=(0.075, 0.083, 0.057), GRIME=(0.028, 0.025, 0.018),
    DUST=(0.2, 0.17, 0.12), STENCIL=(0.008, 0.008, 0.007), SOOT=(0.006, 0.0055, 0.005), OIL=(0.085, 0.064, 0.04),
    WORN=(0.1, 0.105, 0.085), WALK=(0.42, 0.018, 0.012),
    low_y=1.35, low_gain=1.6, dust=0.7, grime=1.0, oil_mix=1.0, oil_rough=0.25, soot_rough=0.15, walk_rough=-0.05, rough=0.6,
    rivet=0.06, line_depth=0.8)
SCHEMES = {"tan": dict(PAINT=(0.38, 0.29, 0.17), PAINT_VARIANT=(0.36, 0.275, 0.16), FADED=(0.45, 0.37, 0.25), WORN=(0.3, 0.26, 0.2))}

PAINT_SETS = [
    ("M978_Paint_Front", None),
    ("M978_Paint_Back", lambda n: n.startswith(("Tank", "Catwalk", "Manholes", "Pump", "Rear_", "Hose_Reel"))),
]
GROUPS = [("M978_Chassis", ["chassis", "rubber", "exhaust", "steel", "hazard", "hose", "extinguisher"], 2)]
SPECS = {
    "chassis": dict(c=(0.034, 0.039, 0.026), r=0.62, m=0.0, wear=(0.09, 0.08, 0.06), wm=0.0, mud=(0.085, 0.064, 0.04), mud_y=1.3, mud_amount=1.2),
    "rubber": dict(c=(0.018, 0.017, 0.016), r=0.88, m=0.0, wear=(0.06, 0.05, 0.04), wm=0.0, mud=(0.09, 0.068, 0.043), mud_y=1.25, mud_amount=1.0),
    "exhaust": dict(c=(0.035, 0.026, 0.02), r=0.72, m=0.4, wear=(0.08, 0.05, 0.03), wm=0.6),
    "steel": dict(c=(0.62, 0.62, 0.6), r=0.18, m=1.0, wear=(0.5, 0.5, 0.48), wm=1.0),
    "hazard": dict(c=(0.5, 0.33, 0.01), r=0.55, m=0.0, wear=(0.08, 0.07, 0.05), wm=0.0),
    "hose": dict(c=(0.014, 0.014, 0.013), r=0.7, m=0.0, wear=(0.05, 0.045, 0.04), wm=0.0),
    "extinguisher": dict(c=(0.4, 0.015, 0.01), r=0.4, m=0.0, wear=(0.3, 0.3, 0.29), wm=1.0),
}
HIDE_MATS = {"M978_Glass"}

if __name__ == "__main__":
    vehicle.run(sys.modules[__name__])
