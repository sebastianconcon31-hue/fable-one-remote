"""M1126 Stryker ICV dimensions and where they put things, in model axes:
metres, +Y up, +Z toward the front, +X to the left. The origin is on the
ground, on the centreline, midway between the first and last axles.

SPEC holds the published figures; build.py measures the finished vehicle
against every one of them. Positions marked "est." are estimated from the
vehicle's proportions."""

IN = 0.0254

SPEC = {
    "length": 6.95,
    "width": 2.72,
    "height": 2.64,  # to the top of the remote weapon station
    "groundClearance": 0.53,
    "tyreDiameter": 44.5 * IN,  # Michelin 12.00R20 XML
    "tyreWidth": 12.2 * IN,
}

# wheels (est.: the LAV III's axle spacing)
AXLES_Z = [2.1, 1.0, -0.9, -2.1]
TYRE_R = SPEC["tyreDiameter"] / 2
TYRE_W = SPEC["tyreWidth"]
WHEEL_X = 1.145  # wheel centres either side (est.)

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
