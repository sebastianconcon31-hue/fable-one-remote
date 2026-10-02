"""T-72B3 dimensions and where they put things, in model axes: metres, +Y up,
+Z toward the front, +X to the left. The origin is on the ground, on the
centreline, midway between the first and last road wheels.

SPEC holds the published figures; build.py measures the finished tank
against every one of them. Positions marked "est." are estimated from the
tank's proportions."""

SPEC = {
    "lengthGunForward": 9.53,
    "hullLength": 6.86,
    "width": 3.60,  # over the side skirts
    "height": 2.26,  # to the turret roof
    "trackWidth": 0.58,  # RMSh
    "groundContact": 4.27,
    "tread": 2.79,  # track centre to centre
    "roadWheelDiameter": 0.75,
}

# running gear: six road wheels, the idler at the front, the sprocket at the back (est. around the published track)
WHEELS_Z = [SPEC["groundContact"] / 2 - k * SPEC["groundContact"] / 5 for k in range(6)]
TRACK_X = SPEC["tread"] / 2
TRACK_W = SPEC["trackWidth"]
WHEEL_R = SPEC["roadWheelDiameter"] / 2
T_IN, T_OUT = 0.03, 0.05
WHEEL_Y = WHEEL_R + T_IN + T_OUT
PITCH = 0.137  # RMSh link pitch (est.)
IDLER = (WHEELS_Z[0] + 0.72, 0.54, 0.3)
SPROCKET = (WHEELS_Z[-1] - 0.68, 0.6)
SPROCKET_TEETH = 13
ROLLERS = [(1.42, 0.86, 0.11), (0.0, 0.86, 0.11), (-1.42, 0.86, 0.11)]

# hull (est.)
FRONT_Z = IDLER[0] + 0.3
REAR_Z = FRONT_Z - SPEC["hullLength"]  # the back of the fuel drums
REAR_PLATE_Z = REAR_Z + 0.6  # the hull's back plate; the drums hang behind it
BELLY_Y = 0.49
DECK_Y = 1.42
FENDER_Y = 1.1  # the fenders over the tracks
LOWER_HALF_W = 1.03
FENDER_HALF_W = 1.72
SKIRT_X = SPEC["width"] / 2
NOSE_Y = 0.98
GLACIS_TOP_Z = FRONT_Z - 1.16  # the upper front plate, 68 degrees from upright

# turret (est.)
TURRET_Z = -0.08
TURRET_BASE_Y = DECK_Y + 0.02
TURRET_ROOF_Y = SPEC["height"]
MUZZLE_Z = REAR_Z + SPEC["lengthGunForward"]
TRUNNION = (0.0, 1.86, TURRET_Z + 0.78)
