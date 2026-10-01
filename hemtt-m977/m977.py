"""HEMTT M977A4 dimensions and where they put things, in model axes: metres,
+Y up, +Z toward the front, +X to the driver's left (glTF's axes, as for
the Apache). The origin is on the ground, on the centreline, midway between
the front and rear axle pairs.

SPEC holds Oshkosh's published M977A4 figures; build.py measures the
finished truck against every one of them. Figures marked "est." are not
published; they are estimated from the truck's proportions."""

IN = 0.0254

SPEC = {
    "length": 402 * IN,  # overall, over the spare tyre
    "width": 96 * IN,
    "height": 118 * IN,  # over the spare tyre
    "wheelbase": 210 * IN,  # front axle pair centre to rear axle pair centre
    "track": 79 * IN,
    "tyreDiameter": 1.240,  # 16.00R20 Michelin XZL
    "tyreWidth": 0.430,
    "cargoBodyLength": 18 * 12 * IN,
}

AXLE_PAIR_SPACING = 60 * IN  # est.: the gap between the two axles of each pair
TYRE_R = SPEC["tyreDiameter"] / 2
TYRE_W = SPEC["tyreWidth"]
WHEEL_X = SPEC["track"] / 2
FRONT_PAIR_Z = SPEC["wheelbase"] / 2
REAR_PAIR_Z = -SPEC["wheelbase"] / 2
AXLES_Z = [FRONT_PAIR_Z + AXLE_PAIR_SPACING / 2, FRONT_PAIR_Z - AXLE_PAIR_SPACING / 2,
           REAR_PAIR_Z + AXLE_PAIR_SPACING / 2, REAR_PAIR_Z - AXLE_PAIR_SPACING / 2]
FRONT_Z = AXLES_Z[0] + 1.30  # est. front overhang: face of the bumper
REAR_Z = FRONT_Z - SPEC["length"]
HALF_W = SPEC["width"] / 2
# the overall length runs from the tow eyes to the pintle hook; the bumpers' faces sit inside that
BUMPER_FRONT_Z = FRONT_Z - 0.12
BUMPER_REAR_Z = REAR_Z + 0.17

# cab (est. from the truck's proportions)
CAB_FRONT_Z = FRONT_Z - 0.28
CAB_REAR_Z = 2.30
CAB_BOTTOM_Y = 1.40
CAB_ROOF_Y = 2.85
CAB_HALF_W = 1.15

# cargo body: 18 ft long, its floor and sides
BED_FRONT_Z = 1.05
BED_REAR_Z = BED_FRONT_Z - SPEC["cargoBodyLength"]
BED_FLOOR_Y = 1.56
BED_SIDE_H = 0.60
BED_HALF_W = 1.19

# frame rails
RAIL_X = 0.44
RAIL_Y0, RAIL_Y1 = 0.98, 1.32

# the spare tyre stands behind the cab; its top is the truck's highest point
SPARE = (0.72, SPEC["height"] - TYRE_R, 1.62)

# the material-handling crane at the rear right corner of the body
CRANE = (-0.78, BED_FLOOR_Y, BED_REAR_Z - 0.42)
