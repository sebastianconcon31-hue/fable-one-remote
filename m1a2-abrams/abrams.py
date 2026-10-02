"""M1A2 SEPv3 Abrams dimensions and where they put things, in model axes:
metres, +Y up, +Z toward the front, +X to the left (glTF's axes, as for the
other models). The origin is on the ground, on the centreline, midway
between the first and last road wheels.

SPEC holds the published figures; build.py measures the finished tank
against every one of them. Positions marked "est." are not published; they
are estimated from the tank's proportions."""

IN = 0.0254

SPEC = {
    "lengthGunForward": 9.77,
    "hullLength": 7.93,
    "width": 3.66,  # over the side skirts
    "height": 2.44,  # to the turret roof
    "groundClearance": 0.48,
    "trackWidth": 25 * IN,  # T158
    "roadWheelDiameter": 25 * IN,
    "trackOnGround": 180 * IN,
}

# running gear: the published 180 in of track on the ground, first to last road wheel centres; the rest est. from the
# proportions, around the published track and wheels
CONTACT = 180 * IN
WHEELS_Z = [CONTACT / 2 - k * CONTACT / 6 for k in range(7)]
TRACK_X = 1.40  # track centres either side
TRACK_W = SPEC["trackWidth"]
WHEEL_R = SPEC["roadWheelDiameter"] / 2
T_IN, T_OUT = 0.042, 0.058  # pin centre to the shoe's inner face / to the pads' face
WHEEL_Y = WHEEL_R + T_IN + T_OUT
IDLER = (WHEELS_Z[0] + 0.974, 0.62, 0.32)  # z, y, r
SPROCKET = (WHEELS_Z[-1] - 0.934, 0.74)
SPROCKET_TEETH = 11
PITCH = 0.192  # T158 shoe pitch
ROLLERS = [(1.15, 0.86, 0.12), (-1.2, 0.86, 0.12)]

# hull
HULL_FRONT_Z = IDLER[0] + 1.0
HULL_REAR_Z = HULL_FRONT_Z - SPEC["hullLength"]
BELLY_Y = SPEC["groundClearance"]
DECK_Y = 1.62
SPONSON_Y = 1.1  # underside of the sponsons over the tracks
HULL_HALF_W = 0.98  # the lower hull between the tracks
SPONSON_HALF_W = 1.73
SKIRT_X = SPEC["width"] / 2  # the skirts' outer faces

# turret
TURRET_Z = 0.52  # ring centre
RING_R = 2.16 / 2
TURRET_BASE_Y = DECK_Y + 0.05
TURRET_ROOF_Y = SPEC["height"]
TRUNNION = (0.0, 2.02, TURRET_Z + 1.12)
BARREL = 5.28  # M256, L/44
MUZZLE_Z = HULL_REAR_Z + SPEC["lengthGunForward"]
REAR_PLATE_Z = HULL_REAR_Z + 0.10  # the rear armour; the grille, pintle and phone box stand out to HULL_REAR_Z
SKIRT_FACE = SKIRT_X - 0.0125  # the skirts' faces; their bolt heads stand out to SKIRT_X
