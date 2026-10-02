"""The AH-64 crew helmet (HGU-56/P with the IHADSS helmet display) and where it puts things, in model axes:
metres, +Y up, +Z toward the front, +X to the wearer's left. The origin is the wearer's head centre: the
midpoint of the line between the ear canals, which is also the visors' pivot axis' height reference.

SPEC holds the published figures the model is measured against; positions marked "est." are estimated from
photographs and from the proportions of an average adult head, because the drawings aren't public."""
import math
import numpy as np

IN = 0.0254

SPEC = {
    "fovH": 40.0,  # degrees: the IHADSS display's field of view, 40 x 30, monocular, right eye
    "fovV": 30.0,
    "exitPupil": 0.010,  # 10 mm
    "crt": 1 * IN,  # a miniature 1 inch CRT image source
    "massKg": 1.338,  # the HGU-56/P helmet system, 2.95 lb
}

# ---- the wearer's head (a fit-check form, not part of the delivered model) -------------------------------------
# est.: an average adult head, 58 cm round, the ear canals' midpoint at the origin
HEAD = dict(
    vertex=0.130, glabella=(0.040, 0.105), opisthocranion=-0.092, half_breadth=0.0765,
    pupil=(0.0315, 0.026, 0.094),  # (x half the interpupillary distance, y, z)
    stomion=(0.0, -0.043, 0.100), menton=(0.0, -0.122, 0.088), nose_tip=(0.0, -0.012, 0.126),
)
EYE_R = np.array([-HEAD["pupil"][0], HEAD["pupil"][1], HEAD["pupil"][2]])  # the right eye: the HDU's
EYE_L = np.array([HEAD["pupil"][0], HEAD["pupil"][1], HEAD["pupil"][2]])

# ---- the shell ------------------------------------------------------------------------------------------------
SHELL_A = 0.1025  # half width at the ears
SHELL_BF, SHELL_BB = 0.140, 0.128  # front and back half length
SHELL_N = 2.3  # the plan outline's squareness (2 is an ellipse)
Y_TOP = 0.156  # the crown
Y_W = 0.005  # where the walls are widest
Q = 2.3
WALL = 0.0045  # the composite shell's thickness
# the lower edge's height round the head, by angle from straight ahead (degrees): above the brow, up over the
# temples, down round the ears and flared a little at the nape
RIM = [(0, 0.056), (25, 0.056), (45, 0.046), (62, 0.020), (75, -0.014), (88, -0.054), (100, -0.056), (115, -0.052), (140, -0.044), (180, -0.036)]

# ---- the visors and their housing: spherical, about the pivot axis through the shell's sides --------------------
PIV = np.array([0.0, 0.035, 0.012])  # a point on the visors' pivot axis, which runs along X
R_CLEAR, R_TINT = 0.1415, 0.1485  # the two visors' radii (the clear one is inner)
R_HOOD = 0.1555  # the housing's outer radius
VISOR_T = 0.0025
VISOR_HALF_X = 0.108

# ---- the display (HDU) on the right side ----------------------------------------------------------------------
EYE_RELIEF = 0.028  # est.: pupil to combiner
HDU_PIVOT = np.array([-0.1215, 0.040, 0.020])  # the adapter block on the right ear dome
COMBINER = EYE_R + np.array([-0.003, 0.0, EYE_RELIEF])  # centre of the combiner glass, a little outboard of the pupil

# ---- the boom microphone on the left -------------------------------------------------------------------------
MIC_PIVOT = np.array([0.1205, 0.002, 0.034])
MIC_AT = np.array([0.010, -0.044, 0.108])  # the capsule's face, 13 mm from the lips (est.)


def rim_y(phi):
    """The shell's lower edge height at angle phi (radians from straight ahead, either way round)."""
    p = abs(math.degrees(phi)) % 360
    if p > 180:
        p = 360 - p
    xs = [a for a, _ in RIM]
    ys = [y for _, y in RIM]
    from geom import pchip
    return float(pchip(xs, ys)(p))


def plan_r(phi):
    s, c = math.sin(phi), math.cos(phi)
    b = SHELL_BF if c >= 0 else SHELL_BB
    return (abs(s / SHELL_A) ** SHELL_N + abs(c / b) ** SHELL_N) ** (-1 / SHELL_N)


def rho(y):
    """The walls' size at height y, as a fraction of the plan outline."""
    if y >= Y_W:
        s = min((y - Y_W) / (Y_TOP - Y_W), 1.0)
        return (1 - s ** Q) ** (1 / Q)
    return 1 - 0.045 * ((Y_W - y) / 0.055) ** 2


def shell_point(phi, y):
    r = plan_r(phi) * rho(y)
    return np.array([r * math.sin(phi), y, r * math.cos(phi)])
