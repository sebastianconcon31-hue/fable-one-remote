"""HEMTT M978A4 fuel servicing truck: the M977A4's cab, frame and running
gear (shared with ../hemtt-m977) under a 2,500 US gallon tank and a rear
pump module. Model axes as for the M977: metres, +Y up, +Z toward the front,
+X to the driver's left; the origin on the ground, on the centreline, midway
between the front and rear axle pairs.

SPEC holds Oshkosh's published M978A4 figures; build.py measures the
finished truck against every one of them. Positions marked "est." are not
published; they are estimated from the truck's proportions."""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hemtt-m977"))  # last, so this folder's own modules come first
from m977 import *  # noqa: E402,F401  the shared cab, frame and wheel positions
import m977  # noqa: E402

GAL = 0.003785411784

SPEC = dict(m977.SPEC)
SPEC.update({
    "length": 409 * IN,  # overall, bumper to pintle
    "tankCapacity": 2500 * GAL,  # m3
})
REAR_Z = FRONT_Z - SPEC["length"]
BUMPER_REAR_Z = REAR_Z + 0.17

# the tank: a squared-off oval (superellipse, exponent 4) on cradles over the frame (est.)
TANK_N = 4.0
TANK_A = 1.12  # half width
TANK_B = 0.56  # half height
TANK_BOTTOM_Y = 1.47
TANK_Y = TANK_BOTTOM_Y + TANK_B
TANK_FRONT_Z = 1.02  # tip of the front head
TANK_HEAD = 0.16  # depth of each dished head
TANK_LEN = 4.18  # head tip to head tip; sized so the shell holds 2,500 gal (see build.py)
TANK_REAR_Z = TANK_FRONT_Z - TANK_LEN

# the pump module behind the tank: pump, filter-separator, two hose reels and the meters (est.)
PUMP_FRONT_Z = TANK_REAR_Z - 0.08
PUMP_REAR_Z = REAR_Z + 0.24
PUMP_HALF_W = 1.16
PUMP_BOTTOM_Y = 1.36
PUMP_TOP_Y = 2.56
