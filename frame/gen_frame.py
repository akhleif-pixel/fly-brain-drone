"""
Fly-Brain Drone printed frame for the rev B flight-controller board (pcb/fc).

One piece, printed flat side down with no supports. Run:

    pcb/.venv/Scripts/python frame/gen_frame.py

It writes frame/out/frame.stl and prints the weight, the clearances it checked, and the
part heights. Coordinates are mm: x to the right, y toward the front, z up from the print bed
(the bottom of the frame). The board's center is at x = y = 0.

What it holds:
  - four 8520 motors in clip tubes at the ends of an X, 95 mm motor to motor across the diagonal
  - the PCB on four posts with M2 holes (screw straight into the plastic)
  - the ESP32 on two bridges just outside the PCB's front and rear edges
  - the battery underneath, with a strap over the front and rear crossbars
"""
import math, os
import numpy as np
from manifold3d import Manifold, CrossSection, OpType

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
SEG = 64                     # segments per circle

# ---------------------------------------------------------------- parts we have to fit
MOTOR_R = 47.5               # center to motor axis (95 mm diagonal, same as rev A)
MC = MOTOR_R / math.sqrt(2)  # 33.59 in x and y
MOTOR_D, MOTOR_L = 8.5, 20.0 # 8520 coreless
PROP_D = 55.0
PCB_W, PCB_H, PCB_T = 46.0, 44.0, 1.0
PCB_HOLES = [(sx * 20.0, sy * 19.0) for sx in (1, -1) for sy in (1, -1)]
MOSFET_H = 18.5              # IRLB8721 standing, body + tab + lead stand-off
MOSFET_BOX = (17.8, 22.6, 2.4, 12.6)  # |x| and |y| range of each upright MOSFET
ESP_W, ESP_L = 25.0, 61.0    # ESP32-S3 CAM board, approximate
BATTERY = (20.0, 40.0, 7.0)  # w (x), l (y), thickness

# ---------------------------------------------------------------- frame parameters
T = 1.6                      # flat beam thickness
BEAM_W = 4.0                 # width of the X beams
RIB_W, RIB_H = 2.0, 6.0      # vertical rib on each arm, outside the PCB
POST_D, POST_H, POST_HOLE = 5.0, 4.0, 1.7    # PCB sits on top at z = POST_H; M2 self-taps into 1.7
TUBE_ID, TUBE_WALL, TUBE_H = 8.6, 1.1, 14.0  # motor clip; tune TUBE_ID to your printer (8.4-8.8)
SEAT_Z = 6.0                 # motor bottom rests here on an inner lip
LIP_ID = 6.4                 # hole under the motor for its wires
LIP_T = 0.8                  # flat lip the motor rests on; a 45-degree chamfer under it prints without supports
SLIT = 1.0                   # clamp slit on the outer side of each tube
ESP_Z = POST_H + PCB_T + 14.0  # ESP32 underside: 14 mm above the PCB, clears C1 (12 mm) and the MPU
BRIDGE_Y = 24.75             # center of the ESP32 bridges, just outside the PCB (edge at 22)
BRIDGE_X = 7.5               # bridge legs at +-BRIDGE_X; the strap runs between them
BRIDGE_LEG = (3.0, 2.5)      # leg cross-section, x by y
BAR_W = 2.5                  # crossbar width (y)

def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))

def cyl(x, y, z0, z1, d):
    return Manifold.cylinder(z1 - z0, d / 2, d / 2, SEG).translate((x, y, z0))

def beam(p0, p1, w, z0, z1):
    """flat-ended bar from p0 to p1 (x, y), width w, between heights z0 and z1"""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L * w / 2, (x1 - x0) / L * w / 2
    cs = CrossSection([[(x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny), (x0 + nx, y0 + ny)]])   # counter-clockwise
    return cs.extrude(z1 - z0).translate((0, 0, z0))

parts = []
corners = [(sx, sy) for sx in (1, -1) for sy in (1, -1)]

# X beams, flat under the PCB, motor to motor
for sx, sy in [(1, 1), (1, -1)]:
    parts.append(beam((-sx * MC, -sy * MC), (sx * MC, sy * MC), BEAM_W, 0, T))
# arm ribs outside the PCB outline, from the board corner out to the tube
RIB_START = 33.0             # distance from center along the diagonal, clear of the board's rounded corner
for sx, sy in corners:
    a = (sx * RIB_START / math.sqrt(2), sy * RIB_START / math.sqrt(2))
    parts.append(beam(a, (sx * MC, sy * MC), RIB_W, 0, RIB_H))
# spine along y under the board's middle, to the front and rear crossbars
parts.append(beam((0, -BRIDGE_Y - BAR_W / 2), (0, BRIDGE_Y + BAR_W / 2), 3.5, 0, T))
# PCB posts
for x, y in PCB_HOLES:
    parts.append(cyl(x, y, 0, POST_H, POST_D))
# ESP32 bridges: bottom crossbar (the battery strap goes over it), two legs, top crossbar
lx, ly = BRIDGE_LEG
for sy in (1, -1):
    yc = sy * BRIDGE_Y
    parts.append(box(-BRIDGE_X - lx / 2, BRIDGE_X + lx / 2, yc - BAR_W / 2, yc + BAR_W / 2, 0, T))
    for sx in (1, -1):
        parts.append(box(sx * BRIDGE_X - lx / 2, sx * BRIDGE_X + lx / 2, yc - ly / 2, yc + ly / 2, 0, ESP_Z))
    parts.append(box(-BRIDGE_X - lx / 2, BRIDGE_X + lx / 2, yc - BAR_W / 2, yc + BAR_W / 2, ESP_Z - T, ESP_Z))
# motor tubes
TUBE_OD = TUBE_ID + 2 * TUBE_WALL
for sx, sy in corners:
    parts.append(cyl(sx * MC, sy * MC, 0, TUBE_H, TUBE_OD))

frame = Manifold.batch_boolean(parts, OpType.Add)

# cuts
cuts = []
for x, y in PCB_HOLES:
    cuts.append(cyl(x, y, -1, POST_H + 1, POST_HOLE))
for sx, sy in corners:
    cx, cy = sx * MC, sy * MC
    cuts.append(cyl(cx, cy, SEAT_Z, TUBE_H + 1, TUBE_ID))        # motor seat
    cuts.append(cyl(cx, cy, -1, SEAT_Z + 0.5, LIP_ID))           # wire hole through the lip
    # hollow below the lip, closing in at 45 degrees so the lip needs no support
    cz = SEAT_Z - LIP_T - (TUBE_ID - LIP_ID) / 2
    cuts.append(cyl(cx, cy, -1, cz, TUBE_ID))
    cuts.append(Manifold.cylinder(SEAT_Z - LIP_T - cz, TUBE_ID / 2, LIP_ID / 2, SEG).translate((cx, cy, cz)))
    # clamp slit on the outer side, only through the seat so the lip ring stays whole
    ang = math.atan2(sy, sx)
    s = beam((cx, cy), (cx + math.cos(ang) * (TUBE_OD / 2 + 1), cy + math.sin(ang) * (TUBE_OD / 2 + 1)), SLIT, SEAT_Z + 1.0, TUBE_H + 1)
    cuts.append(s)
frame = frame - Manifold.batch_boolean(cuts, OpType.Add)

# ---------------------------------------------------------------- report
PLA = 1.24e-3                # g per mm3
vol = frame.volume()
mesh = frame.to_mesh()
verts = np.asarray(mesh.vert_properties)[:, :3]
tris = np.asarray(mesh.tri_verts)
lo, hi = verts.min(0), verts.max(0)
print(f"Frame: {hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} x {hi[2] - lo[2]:.1f} mm, {vol / 1000:.2f} cm3, about {vol * PLA:.1f} g in PLA at 100% (walls this thin print solid)")
print(f"Triangles: {len(tris)}, genus {frame.genus()}, status {frame.status()}")

checks = []
def need(ok, msg):
    checks.append((ok, msg))

prop_r = PROP_D / 2
adjacent = 2 * MC
need(adjacent - PROP_D >= 8, f"prop tip to prop tip: {adjacent - PROP_D:.1f} mm (want >= 8)")
motor_top = SEAT_Z + MOTOR_L
prop_z = motor_top + 2.0     # blades about 2 mm above the motor can
pcb_top = POST_H + PCB_T
mosfet_top = pcb_top + MOSFET_H
esp_top = ESP_Z + 1.6 + 3.0  # board + the tallest parts on it
need(prop_z - mosfet_top >= 3, f"props over the upright MOSFETs: {prop_z - mosfet_top:.1f} mm (want >= 3)")
need(prop_z - esp_top >= 3, f"props over the ESP32 and its parts: {prop_z - esp_top:.1f} mm (want >= 3)")
# tube and arm stay outside the board outline (rounded corner, r 2.5)
corner_c = (PCB_W / 2 - 2.5, PCB_H / 2 - 2.5)
d_tube = math.hypot(MC - corner_c[0], MC - corner_c[1]) - 2.5 - TUBE_OD / 2
need(d_tube >= 2, f"motor tube to board corner: {d_tube:.1f} mm (want >= 2)")
rs = RIB_START / math.sqrt(2)
d_rib = math.hypot(rs - corner_c[0], rs - corner_c[1]) - 2.5 - RIB_W / 2
need(d_rib >= 0.5, f"arm rib to board corner: {d_rib:.1f} mm (want >= 0.5)")
# ESP32 bridges clear the board edge and the front pads' wires (pads at y = 20.2)
need(BRIDGE_Y - BAR_W / 2 - PCB_H / 2 >= 1.0, f"bridge to board edge: {BRIDGE_Y - BAR_W / 2 - PCB_H / 2:.1f} mm")
need(ESP_Z - pcb_top >= 13, f"ESP32 underside above the PCB: {ESP_Z - pcb_top:.1f} mm (C1 is about 12 mm tall)")
need(2 * BRIDGE_X - BRIDGE_LEG[0] >= 10.5, f"room for the battery strap between bridge legs: {2 * BRIDGE_X - BRIDGE_LEG[0]:.1f} mm (10 mm strap)")
need(MOTOR_L - (TUBE_H - SEAT_Z) >= 8, f"motor held over {TUBE_H - SEAT_Z:.0f} mm of its {MOTOR_L:.0f} mm")
need(POST_H - T >= 2.0, f"room under the PCB for trimmed leads above the beams: {POST_H - T:.1f} mm (trim leads to 1.5 mm)")
for ok, msg in checks:
    print(("  ok    " if ok else "  FAIL  ") + msg)
print("CHECKS PASSED" if all(ok for ok, _ in checks) else "CHECKS FAILED")
print(f"Heights: PCB top {pcb_top:.1f}, MOSFET tops {mosfet_top:.1f}, ESP32 underside {ESP_Z:.1f}, motor top {motor_top:.1f}, props about {prop_z:.1f} mm")

# ---------------------------------------------------------------- STL (binary)
def write_stl(path, verts, tris):
    v = verts[tris]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, v
    with open(path, "wb") as f:
        f.write(b"Fly-Brain Drone frame".ljust(80, b" "))
        f.write(np.uint32(len(tris)).tobytes())
        f.write(rec.tobytes())

stl = os.path.join(OUT, "frame.stl")
write_stl(stl, verts, tris)
print(f"Wrote {os.path.relpath(stl, HERE)}")
