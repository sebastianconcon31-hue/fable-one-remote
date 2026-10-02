"""A 5-inch freestyle FPV quadcopter: dimensions and where they put things, in
model axes: metres, +Y up, +Z toward the front, +X to the left. The origin is
the middle of the frame, on the centreline, halfway between the bottom and
top plates, where the motor diagonals cross.

SPEC holds the nominal figures of the class (a "220 mm" frame, 5 inch props, a
6S 1300 mAh pack, a 19 mm micro camera, a 30.5 mm stack); build.py measures the
finished model against every one of them. It is a generic quad, not a
particular product."""
import math

SPEC = {
    "motorDiagonal": 0.220,  # motor shaft to opposite motor shaft
    "propDiameter": 0.127,  # 5 inch
    "armThickness": 0.005,
    "stackMount": 0.0305,  # the 30.5 x 30.5 mm hole pattern
    "plateGap": 0.028,  # bottom plate to top plate, the standoffs' length
    "batteryLength": 0.076,
    "batteryWidth": 0.039,
    "batteryHeight": 0.036,
    "cameraWidth": 0.019,
    "cameraTilt": 25.0,  # degrees up
}
MASS_KG = 0.65  # with the pack, for a game's rigid body

# motors: at (+-A, +-A), so the diagonal is sqrt(2) * 2A
A = SPEC["motorDiagonal"] / 2 / math.sqrt(2)
ARM_L = SPEC["motorDiagonal"] / 2  # centre to motor, along the arm
PROP_R = SPEC["propDiameter"] / 2

# the stack, up from the middle (y = 0)
HALF_GAP = SPEC["plateGap"] / 2  # 0.014
BOT_Y0, BOT_Y1 = -HALF_GAP - SPEC["armThickness"], -HALF_GAP  # bottom plate and arms
TOP_Y0, TOP_Y1 = HALF_GAP, HALF_GAP + 0.0025  # top plate
SO = SPEC["stackMount"] / 2  # standoffs at (+-SO, +-SO)
ESC_Y, FC_Y, VTX_Y = -0.0085, 0.0045, 0.0100  # board centres

# motors: the base on the arm, the stator, the bell, the prop above it
BASE_Y0, BASE_Y1 = BOT_Y1, BOT_Y1 + 0.0035
BELL_Y0, BELL_Y1 = BASE_Y1 + 0.0030, BASE_Y1 + 0.0030 + 0.0140
PROP_Y = BELL_Y1 + 0.0016  # the prop hub's underside
ROTOR_PIVOT_Y = (BELL_Y0 + BELL_Y1) / 2

# battery, on top of the top plate on a rubber pad
PAD_T = 0.001
BAT_Y0 = TOP_Y1 + PAD_T
BAT_L, BAT_W, BAT_H = SPEC["batteryLength"], SPEC["batteryWidth"], SPEC["batteryHeight"]
BAT_Z = -0.004  # a little back of centre
BAT_Y1 = BAT_Y0 + BAT_H

# the camera, at the front between the plates, tilted up
CAM_Z = 0.064
CAM_Y = 0.0

# the plates' outline, the body between the arms (x, z)
BODY = [(-0.020, 0.056), (0.020, 0.056), (0.033, 0.030), (0.033, -0.030), (0.020, -0.056), (-0.020, -0.056), (-0.033, -0.030), (-0.033, 0.030)]

# motors, named by where they sit: front/rear, left/right; spin is +1 for counter-clockwise seen from above
MOTORS = {
    "FL": dict(pos=(+A, +A), spin=+1, order=4),
    "FR": dict(pos=(-A, +A), spin=-1, order=2),
    "RL": dict(pos=(+A, -A), spin=-1, order=3),
    "RR": dict(pos=(-A, -A), spin=+1, order=1),
}
