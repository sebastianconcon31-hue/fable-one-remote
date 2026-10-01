"""M1151A1 HMMWV dimensions and where they put things, in model axes:
metres, +Y up, +Z toward the front, +X to the driver's left. The origin is on
the ground, on the centreline, midway between the axles.

SPEC holds AM General's published figures; build.py measures the finished
vehicle against every one of them. Positions marked "est." are estimated
from the vehicle's proportions."""

import math

IN = 0.0254

SPEC = {
    "length": 194 * IN,  # 16 ft 2 in
    "width": 101 * IN,  # 8 ft 5 in, over the mirrors
    "height": 79 * IN,  # 6 ft 7 in, to the cab roof (the gunner's turret stands above it)
    "wheelbase": 130 * IN,
    "track": 71.6 * IN,
    "tyreDiameter": 37 * IN,  # 37 x 12.50 R16.5
    "tyreWidth": 12.5 * IN,
    "groundClearance": 17.2 * IN,
    "approachAngle": 48.8,  # degrees
    "departureAngle": 37.0,
    "turningRadius": 25 * 12 * IN,  # 25 ft, curb to curb
}

AXLES_Z = [SPEC["wheelbase"] / 2, -SPEC["wheelbase"] / 2]
TYRE_R = SPEC["tyreDiameter"] / 2
TYRE_W = SPEC["tyreWidth"]
RIM_R = 16.5 * IN / 2
WHEEL_X = SPEC["track"] / 2

# the axles' centre line: the portal hubs lift the differentials and half shafts above the wheels' centres
AXLE_Y = TYRE_R + 0.12

# steering: the inner front wheel's full lock for the published 25 ft turning radius (Ackermann: the outer one turns
# asin(wheelbase / radius), the inner one about the same centre)
_outer = math.asin(SPEC["wheelbase"] / SPEC["turningRadius"])
STEER_LOCK = math.atan(SPEC["wheelbase"] / (SPEC["turningRadius"] * math.cos(_outer) - SPEC["track"]))

# body (est.): the front and rear overhangs share out the published length so the bumper (its underside 0.725 m up)
# and the pintle hook (0.46 m) give the published approach and departure angles
FRONT_Z = AXLES_Z[0] + 0.86  # the bumper's face
REAR_Z = FRONT_Z - SPEC["length"]
BODY_HALF_W = 1.09
SILL_Y = 0.72
HOOD_FRONT_Z = FRONT_Z - 0.16
HOOD_BACK_Z = 0.92  # the windshield's foot
HOOD_Y_FRONT, HOOD_Y_BACK = 1.17, 1.33
ROOF_Y = SPEC["height"]
CAB_BACK_Z = -1.05  # behind the rear doors
TURRET_Z = -0.32
