"""AH-64D dimensions and where they put things, in model axes (metres; +Y up,
+Z toward the nose, +X to the crew's left; origin on the front cockpit floor,
on the centreline, under the gunner's seat back - the cockpit model's origin).

The published figures (SPEC) fix the aircraft's overall size; build.py
measures the finished model against every one of them."""

# Published AH-64D figures, metres.
SPEC = {
    "fuselageLength": 14.97,
    "lengthRotorsTurning": 17.73,
    "mainRotorDiameter": 14.63,
    "mainRotorChord": 0.533,
    "tailRotorDiameter": 2.79,
    "tailRotorChord": 0.253,
    "wingspan": 5.227,
    "wheelTrack": 2.03,
    "wheelbase": 10.59,
    "heightToRotorHead": 3.87,
    "heightToFcr": 4.95,
    "heightToTailRotor": 4.66,
}

GROUND_Y = -0.95  # the ground under the wheels
NOSE_Z = 2.54  # front of the TADS turret
TAIL_Z = NOSE_Z - SPEC["fuselageLength"]  # trailing edge of the fin
MAIN_WHEEL = (SPEC["wheelTrack"] / 2, -0.62, -1.6)  # left wheel centre
MAIN_WHEEL_R = 0.33
TAIL_WHEEL_Z = MAIN_WHEEL[2] - SPEC["wheelbase"]
TAIL_WHEEL_R = 0.2
R_MAIN = SPEC["mainRotorDiameter"] / 2
R_TAIL = SPEC["tailRotorDiameter"] / 2
HUB_H = 0.22
HUB_TOP_Y = GROUND_Y + SPEC["heightToRotorHead"]
TAIL_HUB = (0.29, GROUND_Y + SPEC["heightToTailRotor"] - R_TAIL, -11.9)
# The main rotor sits where the overall length with both rotors turning comes out right.
HUB = (0.0, HUB_TOP_Y - HUB_H / 2, TAIL_HUB[2] - R_TAIL + SPEC["lengthRotorsTurning"] - R_MAIN)
FCR_TOP_Y = GROUND_Y + SPEC["heightToFcr"]
WING_TIP_X = SPEC["wingspan"] / 2

# Weapon stations (pylon centrelines), left side; the right is the mirror image.
PYLON_INBOARD_X = 1.2
PYLON_OUTBOARD_X = 2.0
WING_Z = -2.66  # mid-chord of the stub wing
WING_Y = 0.62

# Driven parts the viewer (and a game) moves; pivots in model axes.
TADS_AZ = (0.0, 0.0, 2.2)
TADS_EL = (0.0, -0.04, 2.23)
PNVS = (0.0, 0.42, 2.14)
GUN_TURRET = (0.0, -0.46, 0.35)
GUN_PIVOT = (0.0, -0.6, 0.4)
GUN_MUZZLE = (0.0, -0.61, 2.02)

# Canopy corners, left side, shared with the cockpit model (lib/cockpit.mjs CAN).
CAN = {
    "A": (0.38, 0.8, 0.98),
    "B": (0.25, 1.4, 0.64),
    "C": (0.27, 1.46, -0.14),
    "Q": (0.45, 0.82, -0.14),
    "D": (0.26, 1.98, -0.52),
    "E": (0.27, 2.02, -1.72),
    "R1": (0.44, 1.08, -0.46),
    "R2": (0.47, 1.18, -1.84),
}
# Canopy sill (z, x, y), shared with lib/cockpit.mjs SILL.
SILL = [(0.98, 0.38, 0.8), (-0.14, 0.45, 0.82), (-0.46, 0.44, 1.08), (-1.84, 0.47, 1.18)]


def sill_at(z):
    if z >= SILL[0][0]:
        return SILL[0][1], SILL[0][2]
    for (z0, x0, y0), (z1, x1, y1) in zip(SILL, SILL[1:]):
        if z1 <= z <= z0:
            t = (z0 - z) / (z0 - z1)
            return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    return SILL[-1][1], SILL[-1][2]


def mir(p):
    return (-p[0], p[1], p[2])
