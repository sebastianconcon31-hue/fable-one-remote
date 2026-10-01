"""M1126 Stryker ICV dimensions and where they put things, in model axes:
metres, +Y up, +Z toward the front, +X to the left. The origin is on the
ground, on the centreline, midway between the first and last axles.

SPEC holds the published figures; build.py measures the finished vehicle
against every one of them. Positions marked "est." are estimated from the
vehicle's proportions."""

import math

IN = 0.0254

SPEC = {
    "length": 6.95,
    "width": 2.72,
    "height": 2.64,  # to the top of the remote weapon station
    "groundClearance": 0.53,
    "tyreDiameter": 44.5 * IN,  # Michelin 12.00R20 XML
    "tyreWidth": 12.2 * IN,
    "turningCircle": 52 * 12 * IN,  # diameter
}

# wheels (est.: the LAV III's axle spacing, each pair far enough apart that its 44.5 in tyres clear each other)
AXLES_Z = [2.1, 0.86, -0.86, -2.1]
TYRE_R = SPEC["tyreDiameter"] / 2
TYRE_W = SPEC["tyreWidth"]
WHEEL_X = 1.145  # wheel centres either side (est.)
AXLE_Y = SPEC["groundClearance"] + 0.16  # the differentials' centres: their undersides are the published ground clearance

# steering: the first two axles' full locks (their inner wheels') for the published turning circle, turning about one
# centre on the line through the rear pair (Ackermann)
_R, _rear = SPEC["turningCircle"] / 2, (AXLES_Z[2] + AXLES_Z[3]) / 2
_across = _R * math.cos(math.asin((AXLES_Z[0] - _rear) / _R)) - 2 * WHEEL_X
STEER_LOCK = [math.atan((AXLES_Z[0] - _rear) / _across), math.atan((AXLES_Z[1] - _rear) / _across)]

# hull (est.)
FRONT_Z = AXLES_Z[0] + 1.3
REAR_Z = FRONT_Z - SPEC["length"]
RAMP_Z = REAR_Z + 0.06  # the hull's back; the ramp's outer face is at REAR_Z
BELLY_Y = SPEC["groundClearance"]
ROOF_Y = 2.07
GLACIS_TOP_Z = 1.95
NOSE_TOP_Y, NOSE_BOT_Y = 1.16, 1.04
BELLY_FRONT_Z = 2.75
SHELF_Y = 1.22  # the sponsons over the wheels
HALF_W = 1.32  # the hull's sides; the armour tiles stand out to SPEC["width"] / 2
TILE_X = SPEC["width"] / 2

# the remote weapon station (M151 Protector with an M2) on the roof, ahead of the commander's hatch
RWS = (-0.25, ROOF_Y, 0.9)
