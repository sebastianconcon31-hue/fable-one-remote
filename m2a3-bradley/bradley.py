"""M2A3 Bradley dimensions and where they put things, in model axes: metres,
+Y up, +Z toward the front, +X to the left. The origin is on the ground, on
the centreline, midway between the first and last road wheels.

SPEC holds the published figures; build.py measures the finished vehicle
against every one of them. Positions marked "est." are estimated from the
vehicle's proportions."""

IN = 0.0254

SPEC = {
    "length": 6.55,
    "width": 3.60,  # over the add-on armour
    "height": 2.98,  # to the top of the commander's independent viewer
    "groundClearance": 0.46,
    "trackWidth": 21 * IN,  # T157
    "groundContact": 3.91,  # first to last road wheel centres
}

# running gear: six road wheels, the drive sprocket at the front, the idler at the back (est. around the published track)
WHEELS_Z = [SPEC["groundContact"] / 2 - k * SPEC["groundContact"] / 5 for k in range(6)]
TRACK_X = 1.34
TRACK_W = SPEC["trackWidth"]
WHEEL_R = 0.305  # 24 in road wheels (est.)
T_IN, T_OUT = 0.036, 0.05
WHEEL_Y = WHEEL_R + T_IN + T_OUT
PITCH = 6 * IN  # T157 shoe pitch
SPROCKET = (WHEELS_Z[0] + 0.74, 0.66)
SPROCKET_TEETH = 12
IDLER = (WHEELS_Z[-1] - 0.74, 0.56, 0.28)
ROLLERS = [(1.2, 0.86, 0.1), (0.0, 0.86, 0.1), (-1.2, 0.86, 0.1)]

# hull (est.)
FRONT_Z = SPROCKET[0] + 0.55
REAR_Z = FRONT_Z - SPEC["length"]
BELLY_Y = SPEC["groundClearance"]
ROOF_Y = 1.98
LOWER_HALF_W = 0.98  # between the tracks
HULL_HALF_W = 1.6  # over the tracks
ARMOUR_X = SPEC["width"] / 2  # outer face of the add-on armour
NOSE_Y = 1.12
GLACIS_TOP_Z = 1.9  # where the sloped front plate meets the roof

# turret (est.)
TURRET_Z = 0.12
TURRET_BASE_Y = ROOF_Y + 0.03
TURRET_ROOF_Y = 2.6
TRUNNION = (0.0, 2.3, TURRET_Z + 1.02)
REAR_PLATE_Z = REAR_Z + 0.08  # the hull's back; the ramp's outer face is at REAR_Z
SPONSON_Y = 1.1
