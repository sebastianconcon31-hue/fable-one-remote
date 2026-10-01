"""M1083A1P2 FMTV (5-ton MTV) cargo truck dimensions and where they put
things, in model axes: metres, +Y up, +Z toward the front, +X to the
driver's left. The origin is on the ground, on the centreline, midway
between the front axle and the centre of the rear pair.

SPEC holds the published figures; build.py measures the finished truck
against every one of them. Positions marked "est." are estimated from the
truck's proportions."""

IN = 0.0254

SPEC = {
    "length": 283.7 * IN,
    "width": 96 * IN,  # without mirrors
    "height": 112 * IN,  # operational, to the cab roof
    "wheelbase": 161.4 * IN,  # front axle to the rear pair's centre
    "tyreDiameter": 2 * 0.395 * 0.85 + 20 * IN,  # 395/85R20 Michelin XML
    "tyreWidth": 0.395,
    "bedLength": 170 * IN,  # inside the cargo body
    "bedWidth": 91 * IN,
}

TANDEM = 54 * IN  # est.: the rear pair's axle spacing
AXLES_Z = [SPEC["wheelbase"] / 2, -SPEC["wheelbase"] / 2 + TANDEM / 2, -SPEC["wheelbase"] / 2 - TANDEM / 2]
TYRE_R = SPEC["tyreDiameter"] / 2
TYRE_W = SPEC["tyreWidth"]
WHEEL_X = 0.99  # est.: track 1.98 m, the tyres inside the published width
HALF_W = SPEC["width"] / 2

FRONT_Z = AXLES_Z[0] + 1.24  # the bumper's face (est.)
REAR_Z = FRONT_Z - SPEC["length"]

# cab, over the engine (est.)
CAB_FRONT_Z = FRONT_Z - 0.2
CAB_BACK_Z = AXLES_Z[0] - 0.85
CAB_FLOOR_Y = 1.3
CAB_ROOF_Y = SPEC["height"]
CAB_HALF_W = 1.16

# frame and cargo body
RAIL_X = 0.43
RAIL_Y0, RAIL_Y1 = 0.92, 1.2
BED_FLOOR_Y = 1.42
BED_HALF_IN = SPEC["bedWidth"] / 2
BED_HALF_W = BED_HALF_IN + 0.045  # the sides' inner faces are 45 mm in from their outer
BED_REAR_Z = REAR_Z + 0.12
BED_FRONT_Z = BED_REAR_Z + SPEC["bedLength"] + 0.09  # the tailgate and bulkhead take 40 and 50 mm
BED_SIDE_H = 0.56
