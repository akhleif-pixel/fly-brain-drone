"""
Fly-Brain Drone PCB frame generator.

The PCB is the drone's frame: an X-shaped 2-layer board with motor holes at the arm tips.
Every part is through-hole and hand-solderable. Run:

    pcb/.venv/Scripts/python pcb/gen.py

It writes Gerbers + drill files (pcb/out/fly-drone-gerbers.zip), preview images, a BOM,
and prints a design-rule and connectivity report. Coordinates are mm, top view,
x to the right (drone's right side), y toward the front.

Layers:
  top    = parts side: signals, MOSFET drain pads, GND pour
  bottom = battery side: VBAT pour (whole board), battery + buck-boost sit here
"""
import math, os, csv, zipfile
from collections import defaultdict
from shapely.geometry import Point, Polygon, LineString, MultiPolygon, box
from shapely.ops import unary_union
from shapely import affinity
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- rules
CLR = 0.25        # min copper to copper (different nets)
POUR_CLR = 0.40   # pour pulls back this far from other nets
EDGE_CLR = 0.40   # copper to board edge
THERMAL_GAP = 0.35
SPOKE = 0.45
RES = 12          # arc segments per quarter circle
THICKNESS = 1.0   # board thickness, mm

# ---------------------------------------------------------------- data
pads, traces, regions, npth, silk, notes = [], [], [], [], [], []

def pad(ref, net, x, y, d, drill=None, shape="circle", w=None, h=None, rot=0, layer="both", label=None):
    pads.append(dict(ref=ref, net=net, x=x, y=y, d=d, drill=drill, shape=shape, w=w or d, h=h or d, rot=rot, layer=layer))
    return pads[-1]

def trace(net, pts, width, layer="top"):
    traces.append(dict(net=net, pts=pts, w=width, layer=layer))

def region(net, poly, layer="top"):
    regions.append(dict(net=net, poly=poly, layer=layer))

def pad_shape(p):
    if p["shape"] == "circle":
        g = Point(p["x"], p["y"]).buffer(p["d"] / 2, RES)
    elif p["shape"] == "oval":
        l = max(p["w"], p["h"]) - min(p["w"], p["h"])
        r = min(p["w"], p["h"]) / 2
        if p["w"] >= p["h"]:
            g = LineString([(p["x"] - l / 2, p["y"]), (p["x"] + l / 2, p["y"])]).buffer(r, RES)
        else:
            g = LineString([(p["x"], p["y"] - l / 2), (p["x"], p["y"] + l / 2)]).buffer(r, RES)
        g = affinity.rotate(g, p["rot"], origin=(p["x"], p["y"]))
    else:
        g = box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
        g = affinity.rotate(g, p["rot"], origin=(p["x"], p["y"]))
    return g

def trace_shape(t):
    return LineString(t["pts"]).buffer(t["w"] / 2, RES)

# ---------------------------------------------------------------- outline
S2 = math.sqrt(0.5)
MOTOR_R = 47.5                     # center to motor axis (95 mm diagonal)
MC = MOTOR_R * S2                  # 33.588
BODY = box(-17, -31, 17, 31).buffer(3, RES).buffer(-3, RES)
arms = []
for sx, sy in [(1, 1), (1, -1), (-1, -1), (-1, 1)]:
    arms.append(LineString([(0, 0), (sx * MC, sy * MC)]).buffer(6.5, cap_style=2))
    arms.append(Point(sx * MC, sy * MC).buffer(8, RES))
TONGUE = box(-6, 28, 6, 40).buffer(1.5, RES).buffer(-1.5, RES)
REAR_TAB = box(-5, -37.5, 5, -28).buffer(1.5, RES).buffer(-1.5, RES)
outline = unary_union([BODY, TONGUE, REAR_TAB] + arms).buffer(1.2, RES).buffer(-1.2, RES)   # fillet inside corners
MOTOR_HOLE_D = 8.8
for sx, sy in [(1, 1), (1, -1), (-1, -1), (-1, 1)]:
    outline = outline.difference(Point(sx * MC, sy * MC).buffer(MOTOR_HOLE_D / 2, RES * 2))
BOARD = outline

# mounting holes: ESP32 spacers above, battery tray below, same M2 screws
for y in (25, -34.5):
    npth.append((0, y, 2.2))

# ---------------------------------------------------------------- motor channels
# local coordinates for the front-right quadrant, mirrored into the others
CH = [  # motor, sx, sy, spin, ESP pin, jumper pad
    dict(m=1, sx=1, sy=1, spin="CCW", gpio="GPIO 21"),
    dict(m=2, sx=1, sy=-1, spin="CW", gpio="GPIO 47"),
    dict(m=3, sx=-1, sy=-1, spin="CCW", gpio="GPIO 14"),
    dict(m=4, sx=-1, sy=1, spin="CW", gpio="GPIO 38"),
]

def uv(ch, a, b):
    """point at distance a along the arm, offset b across it, in board coordinates"""
    x, y = a * S2 - b * S2, a * S2 + b * S2          # local front-right
    return (ch["sx"] * x, ch["sy"] * y)

def L(ch, x, y):
    return (ch["sx"] * x, ch["sy"] * y)

QA = 20.5                 # MOSFET pad row distance
for ch in CH:
    m = ch["m"]
    # Lying metal side down with the legs toward the center, a TO-220's gate is on the LEFT
    # as seen from the center. Mirroring flips left and right, so the gate side alternates.
    inner = ch["sx"] * ch["sy"] > 0           # M1 and M3: gate on the +b side
    bG = 2.54 if inner else -2.54
    G, D, Sx = uv(ch, QA, bG), uv(ch, QA, 0), uv(ch, QA, -bG)
    ch["bG"] = bG; ch["inner"] = inner
    pad(f"Q{m}.G", f"GATE{m}", *G, 1.9, 1.1)
    pad(f"Q{m}.D", f"DRAIN{m}", *D, 1.9, 1.1)
    pad(f"Q{m}.S", "GND", *Sx, 1.9, 1.1)
    # drain copper: the MOSFET lies metal side down on it (the metal back is the drain)
    poly = Polygon([uv(ch, 22.2, -5.4), uv(ch, 33.5, -5.4), uv(ch, 33.5, 5.4), uv(ch, 22.2, 5.4)])
    neck = LineString([D, uv(ch, 22.6, 0)]).buffer(0.8, cap_style=2)
    region(f"DRAIN{m}", unary_union([poly, neck]))
    # motor pads
    MP, MN = uv(ch, 35.2, 1.9), uv(ch, 35.2, -1.9)
    pad(f"M{m}+", "VBAT", *MP, 2.2, 1.0)
    pad(f"M{m}-", f"DRAIN{m}", *MN, 2.2, 1.0)
    trace(f"DRAIN{m}", [uv(ch, 33.0, -1.9), MN], 1.6)
    # flyback diode across the motor, stripe (cathode) on VBAT
    DA, DK = uv(ch, 38.2, -5.08), uv(ch, 38.2, 5.08)
    pad(f"D{m}.A", f"DRAIN{m}", *DA, 2.0, 1.0)
    pad(f"D{m}.K", "VBAT", *DK, 2.0, 1.0, shape="rect", rot=45 if ch["sx"] * ch["sy"] > 0 else -45)
    trace(f"DRAIN{m}", [DA, MN], 0.8)
    trace("VBAT", [DK, MP], 0.8)
    # gate pull-down
    if inner:
        RG, RS = uv(ch, 17.3, 3.81), uv(ch, 17.3, -3.81)   # lies across the arm root, inside the pad row
    else:
        RG, RS = L(ch, 15.2, 10.4), L(ch, 15.2, 2.78)
    pad(f"R{m}.1", f"GATE{m}", *RG, 1.6, 0.8)
    pad(f"R{m}.2", "GND", *RS, 1.6, 0.8)
    trace(f"GATE{m}", [G, RG], 0.4)
    ch.update(G=G, D=D, S=Sx, MP=MP, MN=MN, DA=DA, DK=DK, RG=RG, RS=RS)

# ---------------------------------------------------------------- jumper pads to the ESP32 (wired up to its pins)
FRONT_Y, REAR_Y = 21.5, -16.6
JP = {}
for name, net, x, y in [
    ("G4", "GATE4", -7.62, FRONT_Y), ("3V3", "3V3", -5.08, FRONT_Y), ("SCL", "SCL", -2.54, FRONT_Y),
    ("SDA", "SDA", 0.0, FRONT_Y), ("INT", "INT", 2.54, FRONT_Y), ("GND", "GND", 5.08, FRONT_Y), ("G1", "GATE1", 7.62, FRONT_Y),
    ("G3", "GATE3", -7.62, REAR_Y), ("OUT", "3V3", -5.08, REAR_Y), ("TG", "GND", -2.54, REAR_Y), ("IN", "VBAT", 2.54, REAR_Y), ("G2", "GATE2", 7.62, REAR_Y),
]:
    JP[name] = pad("J." + name, net, x, y, 1.6, 0.8)

# gate traces from each pull-down resistor to its jumper pad
for ch in CH:
    m, sx, sy = ch["m"], ch["sx"], ch["sy"]
    tgt = JP[f"G{m}"]
    if m == 1:
        pts = [ch["RG"], (7.62, 17.6), (7.62, FRONT_Y)]
    elif m == 3:
        pts = [ch["RG"], (tgt["x"], tgt["y"])]
    elif m == 2:
        pts = [ch["RG"], (10.9, -14.6), (7.62, -16.0), (tgt["x"], tgt["y"])]
    else:
        pts = [ch["RG"], (-10.9, 15.0), (-7.62, 18.3), (tgt["x"], tgt["y"])]
    trace(f"GATE{m}", pts, 0.3)

# ---------------------------------------------------------------- MPU6050 (GY-521) on its 8-pin header, near the center
MPU_Y = -5.0
MPU_NAMES = ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"]
MPU_NETS = ["3V3", "GND", "SCL", "SDA", "NC1", "NC2", "NC3", "INT"]
MPU = {}
for i, (nm, net) in enumerate(zip(MPU_NAMES, MPU_NETS)):
    MPU[nm] = pad("U2." + nm, net, -8.89 + 2.54 * i, MPU_Y, 1.7, 1.0, shape="rect" if i == 0 else "circle")
trace("3V3", [(-8.89, MPU_Y), (-8.89, 11.0), (-5.08, 15.0), (-5.08, FRONT_Y)], 0.5, layer="bottom")
trace("3V3", [(-5.08, REAR_Y), (-5.08, -9.0), (-8.89, -7.2), (-8.89, MPU_Y)], 0.5, layer="bottom")
trace("SCL", [(-3.81, MPU_Y), (-3.81, 11.6), (-2.54, 12.9), (-2.54, FRONT_Y)], 0.3)
trace("SDA", [(-1.27, MPU_Y), (-1.27, 11.6), (0.0, 12.9), (0.0, FRONT_Y)], 0.3)
trace("INT", [(8.89, MPU_Y), (8.89, 11.0), (2.54, 17.35), (2.54, FRONT_Y)], 0.3)

# ---------------------------------------------------------------- power entry, capacitor
pad("BAT+", "VBAT", -13.8, -25.3, 2.5, 1.2, shape="rect")
pad("BAT-", "GND", -13.8, -28.5, 2.5, 1.2)
pad("C1.+", "VBAT", 15.0, -26.6, 1.6, 0.8, shape="rect")
pad("C1.-", "GND", 12.5, -26.6, 1.6, 0.8)

# ---------------------------------------------------------------- silkscreen helpers
FONT = FontProperties(family="DejaVu Sans", weight="bold")

def text_poly(s, x, y, size=1.3, anchor="c", rot=0):
    tp = TextPath((0, 0), s, size=size, prop=FONT)
    shape = None
    for ring in tp.to_polygons():
        if len(ring) < 3:
            continue
        p = Polygon(ring).buffer(0)
        shape = p if shape is None else shape.symmetric_difference(p)
    if shape is None:
        return None
    minx, miny, maxx, maxy = shape.bounds
    dx = {"c": -(minx + maxx) / 2, "l": -minx, "r": -maxx}[anchor]
    shape = affinity.translate(shape, dx, -(miny + maxy) / 2)
    shape = affinity.rotate(shape, rot, origin=(0, 0))
    return affinity.translate(shape, x, y)

# the same silkscreen is also kept as native primitives for the KiCad export
K_TEXT, K_LINE, K_FILL = [], [], []

MIN_TEXT = 1.2   # em size; gives about 0.85 mm tall capitals, above the 0.8 mm factory minimum

def stext(s, x, y, size=1.3, layer="top", anchor="c", rot=0):
    size = max(size, MIN_TEXT)
    g = text_poly(s, x, y, size, anchor, rot)
    if g is not None:
        if layer == "bottom":
            g = affinity.scale(g, -1, 1, origin=(x, y))   # read correctly from below
        silk.append((layer, g))
        K_TEXT.append(dict(s=s, x=x, y=y, size=size, layer=layer, rot=rot))

def sline(pts, w=0.18, layer="top", closed=False):
    if closed:
        pts = list(pts) + [pts[0]]
    silk.append((layer, LineString(pts).buffer(w / 2, RES)))
    K_LINE.append(dict(pts=list(pts), w=w, layer=layer))

def sfill(poly, layer="top"):
    silk.append((layer, poly))
    K_FILL.append(dict(pts=list(poly.exterior.coords)[:-1], layer=layer))

def scircle(x, y, r, w=0.18, layer="top"):
    silk.append((layer, Point(x, y).buffer(r + w / 2, RES).difference(Point(x, y).buffer(r - w / 2, RES))))

# part outlines and labels
for ch in CH:
    m = ch["m"]
    body = [uv(ch, 23.4, -5.1), uv(ch, 32.6, -5.1), uv(ch, 32.6, 5.1), uv(ch, 23.4, 5.1)]
    sline(body, closed=True)
    a = math.degrees(math.atan2(ch["sy"], ch["sx"]))
    rot = a - 90 if ch["sy"] > 0 else a + 90
    stext(f"Q{m}", *uv(ch, 28.0, 0), 1.6, rot=rot)
    stext("METAL DOWN", *uv(ch, 31.0, 0), 1.2, rot=rot)
    stext("G", *uv(ch, QA, ch["bG"] * 1.85), 1.0); stext("S", *uv(ch, QA, -ch["bG"] * 1.85), 1.0)
    # diode: body + stripe on the cathode end
    sline([uv(ch, 38.2, -2.6), uv(ch, 38.2, 2.6)], 2.4 * 0 + 0.18)
    sline([uv(ch, 37.0, -2.6), uv(ch, 39.4, -2.6), uv(ch, 39.4, 2.6), uv(ch, 37.0, 2.6)], closed=True)
    sfill(Polygon([uv(ch, 37.0, 1.9), uv(ch, 39.4, 1.9), uv(ch, 39.4, 2.6), uv(ch, 37.0, 2.6)]))
    stext(f"D{m}", *uv(ch, 40.6, 0), 1.0, rot=rot)
    stext("+", *uv(ch, 35.2, 3.85), 1.4)
    stext("-", *uv(ch, 35.2, -3.85), 1.6)
    # resistor
    (ax_, ay_), (bx_, by_) = ch["RG"], ch["RS"]
    mx_, my_ = (ax_ + bx_) / 2, (ay_ + by_) / 2
    ang = math.degrees(math.atan2(by_ - ay_, bx_ - ax_))
    rbox = affinity.rotate(box(mx_ - 2.6, my_ - 1.3, mx_ + 2.6, my_ + 1.3), ang, origin=(mx_, my_))
    sline(list(rbox.exterior.coords)[:-1], closed=True)
    if ch["inner"]:
        lx, ly = uv(ch, 14.9, 0)
        stext(f"R{m}", lx, ly, 1.0)
    else:
        stext(f"R{m}", mx_ - 3.7 * ch["sx"], my_, 1.0, rot=90)
    # motor label + spin arrow on the disc
    cx, cy = ch["sx"] * MC, ch["sy"] * MC
    stext(f"M{m}", cx, cy + (6.9 if ch["sy"] > 0 else -6.9), 1.5)
    arc = [(cx + 5.3 * math.cos(t), cy + 5.3 * math.sin(t)) for t in [math.radians(d) for d in range(200, 341, 10)]]
    if ch["sy"] > 0:
        arc = [(px, 2 * cy - py) for px, py in arc]     # outer side of the disc; this also flips the turning sense
    # point the arrow the way the motor spins, seen from above (positive area = counter-clockwise)
    turn = sum((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy) for (x1, y1), (x2, y2) in zip(arc, arc[1:]))
    if (turn > 0) != (ch["spin"] == "CCW"):
        arc = arc[::-1]
    ch["arc"] = arc
    sline(arc, 0.2)
    ex, ey = arc[-1]; px, py = arc[-2]
    ang = math.atan2(ey - py, ex - px)
    sfill(Polygon([(ex + 0.75 * math.cos(ang), ey + 0.75 * math.sin(ang)),
                                 (ex + 0.75 * math.cos(ang + 2.4), ey + 0.75 * math.sin(ang + 2.4)),
                                 (ex + 0.75 * math.cos(ang - 2.4), ey + 0.75 * math.sin(ang - 2.4))]))
    stext(ch["spin"], cx, cy + (-6.2 if ch["sy"] > 0 else 6.2), 1.1)

# MPU outline (body sits in front of the pin row) and pin names
sline([(-10.5, MPU_Y - 1.3), (10.5, MPU_Y - 1.3), (10.5, MPU_Y + 14.7), (-10.5, MPU_Y + 14.7)], closed=True)
for i, nm in enumerate(MPU_NAMES):
    stext(nm, -8.89 + 2.54 * i, MPU_Y - 3.4, 1.2, rot=90)
stext("MPU6050  GY-521", 0, MPU_Y + 7.5, 1.2)
stext("chips up, pins here", 0, MPU_Y + 5.8, 0.85)
# jumper labels
for name, p in JP.items():
    lbl = {"OUT": "3V3", "TG": "GND", "IN": "VIN"}.get(name, name)
    stext(lbl, p["x"], p["y"] + (-2.6 if p["y"] > 0 else 2.6), 0.75, rot=90)
# buck-boost module outline (on foam tape, under the ESP32 rear)
sline([(-10, -30.4), (10, -30.4), (10, -18.6), (-10, -18.6)], 0.15, closed=True)
stext("TPS63020 ON FOAM", 0, -24.0, 1.0)
stext("VIN GND VOUT  EN TO VIN", 0, -26.3, 1.2)
# ESP32 footprint (it sits above on spacers)
sline([(-12.5, -30.4), (12.5, -30.4), (12.5, 30.4), (-12.5, 30.4)], 0.15, closed=True)
stext("ESP32 ABOVE  USB TO REAR", 0, 28.9, 0.8)
# power entry and cap
stext("BAT", -16.1, -26.9, 1.2, rot=90); stext("+", -11.7, -25.3, 1.4); stext("-", -11.7, -28.5, 1.6)
stext("+", 15.0, -24.8, 1.2); stext("C1", 13.75, -28.6, 0.9)
# front
stext("FRONT", 0, 36.5, 1.6)
sline([(0, 38.4), (0, 39.2)], 0.25)
sfill(Polygon([(-1.0, 38.1), (1.0, 38.1), (0, 39.4)]))
stext("FLY-BRAIN DRONE  rev A", 0, -11.4, 1.3)
# bottom side: battery, buck-boost, screws
sline([(-10, -20), (10, -20), (10, 20), (-10, 20)], 0.18, "bottom", closed=True)
stext("BATTERY 1S 500mAh", 0, 12.0, 1.2, "bottom")
stext("IN PRINTED TRAY", 0, 9.8, 0.9, "bottom")

# ---------------------------------------------------------------- copper assembly
def layer_items(layer):
    """(net, geometry) for every copper item on a layer, before the pours"""
    items = []
    for p in pads:
        if p["layer"] in ("both", layer):
            items.append((p["net"], pad_shape(p), p))
    for t in traces:
        if t["layer"] == layer:
            items.append((t["net"], trace_shape(t), None))
    for r in regions:
        if r["layer"] == layer:
            items.append((r["net"], r["poly"], None))
    return items

holes_np = unary_union([Point(x, y).buffer(d / 2, RES) for x, y, d in npth])
POUR_AREA = BOARD.buffer(-EDGE_CLR, RES).difference(holes_np.buffer(EDGE_CLR, RES))

def make_pour(layer, net):
    items = layer_items(layer)
    others = unary_union([g.buffer(POUR_CLR, RES) for n, g, p in items if n != net])
    pour = POUR_AREA.difference(others)
    own_pads = [p for n, g, p in items if n == net and p is not None]
    for p in own_pads:                       # thermal reliefs for hand soldering
        g = pad_shape(p)
        pour = pour.difference(g.buffer(THERMAL_GAP, RES))
    pour = pour.buffer(-0.15, RES).buffer(0.15, RES)       # drop slivers
    spokes = []
    for p in own_pads:
        g = pad_shape(p)
        r = max(p["w"], p["h"]) / 2 + THERMAL_GAP + 0.6
        for a in (45, 135, 225, 315):
            s = LineString([(p["x"], p["y"]), (p["x"] + r * math.cos(math.radians(a)), p["y"] + r * math.sin(math.radians(a)))]).buffer(SPOKE / 2, cap_style=2)
            spokes.append(s.difference(others))
    own = unary_union([g for n, g, p in items if n == net])
    pour = unary_union([pour] + spokes).intersection(POUR_AREA.union(own))
    # keep only pour islands that touch this net's copper
    polys = list(pour.geoms) if isinstance(pour, MultiPolygon) else [pour]
    kept = [pp for pp in polys if pp.buffer(0.01).intersects(own) and pp.area > 1.0]
    dropped = sum(pp.area for pp in polys) - sum(pp.area for pp in kept)
    return unary_union(kept), dropped

pour_top, drop_top = make_pour("top", "GND")
pour_bot, drop_bot = make_pour("bottom", "VBAT")

def copper(layer):
    """final copper per net on a layer"""
    by = defaultdict(list)
    for n, g, p in layer_items(layer):
        by[n].append(g)
    by["GND" if layer == "top" else "VBAT"].append(pour_top if layer == "top" else pour_bot)
    return {n: unary_union(gs) for n, gs in by.items()}

CU = {"top": copper("top"), "bottom": copper("bottom")}

# ---------------------------------------------------------------- checks
report = []
def check():
    ok = True
    # clearance between nets
    for layer, nets in CU.items():
        names = sorted(nets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                d = nets[names[i]].distance(nets[names[j]])
                if d < CLR - 1e-3:
                    ok = False
                    report.append(f"CLEARANCE {layer}: {names[i]} to {names[j]} = {d:.3f} mm")
    # copper to board edge
    edge = BOARD.boundary
    for layer, nets in CU.items():
        for n, g in nets.items():
            d = g.distance(edge)
            if d < EDGE_CLR - 0.05:
                ok = False
                report.append(f"EDGE {layer}: {n} {d:.3f} mm from the board edge")
    # every copper item inside the board
    for layer, nets in CU.items():
        for n, g in nets.items():
            if not g.difference(BOARD).is_empty and g.difference(BOARD).area > 0.01:
                ok = False
                report.append(f"OUTSIDE {layer}: {n}")
    # drills: annular ring and spacing
    drills = [(p["x"], p["y"], p["drill"], p["ref"]) for p in pads if p["drill"]] + [(x, y, d, "NPTH") for x, y, d in npth]
    for p in pads:
        if p["drill"]:
            ring = (min(p["w"], p["h"]) - p["drill"]) / 2
            if ring < 0.15:
                ok = False; report.append(f"RING {p['ref']} {ring:.2f} mm")
    for i in range(len(drills)):
        for j in range(i + 1, len(drills)):
            a, b = drills[i], drills[j]
            gap = math.hypot(a[0] - b[0], a[1] - b[1]) - a[2] / 2 - b[2] / 2
            if gap < 0.5:
                ok = False; report.append(f"DRILL {a[3]} to {b[3]} gap {gap:.2f} mm")
    # connectivity: each net in one piece, top + bottom joined by plated holes
    for net in sorted({p["net"] for p in pads}):
        if net.startswith("NC"):
            continue
        comps = []
        for layer in ("top", "bottom"):
            g = CU[layer].get(net)
            if g is None or g.is_empty:
                continue
            for pc in (g.geoms if isinstance(g, MultiPolygon) else [g]):
                comps.append((layer, pc))
        parent = list(range(len(comps)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        net_pads = [p for p in pads if p["net"] == net]
        for p in net_pads:
            if p["layer"] == "both":
                c = Point(p["x"], p["y"])
                hit = [k for k, (ly, pc) in enumerate(comps) if pc.buffer(0.01).contains(c)]
                for k in hit[1:]:
                    parent[find(k)] = find(hit[0])
        groups = set()
        for p in net_pads:
            c = Point(p["x"], p["y"])
            hit = [k for k, (ly, pc) in enumerate(comps) if pc.buffer(0.01).contains(c)]
            if not hit:
                ok = False; report.append(f"OPEN {net}: pad {p['ref']} touches no copper")
                continue
            groups.add(find(hit[0]))
        if len(groups) > 1:
            ok = False
            report.append(f"OPEN {net}: split into {len(groups)} pieces")
    return ok

OK = check()

# ---------------------------------------------------------------- gerber writer
OX, OY = 60.0, 60.0          # shift so all coordinates are positive

def fmt(v):
    return f"{int(round(v * 1e6)):d}"

def xy(x, y):
    return f"X{fmt(x + OX)}Y{fmt(y + OY)}"

def gerber_header(name, func):
    return [f"%TF.FileFunction,{func}*%", "%FSLAX46Y46*%", "%MOMM*%", f"G04 {name}*", "%LPD*%", "%ADD10C,0.100000*%"]

def poly_lines(poly):
    out = []
    polys = list(poly.geoms) if isinstance(poly, MultiPolygon) else ([poly] if not poly.is_empty else [])
    polys.sort(key=lambda p: -p.area)
    for p in polys:
        for ring, dark in [(p.exterior, True)] + [(r, False) for r in p.interiors]:
            out.append("%LPD*%" if dark else "%LPC*%")
            pts = list(ring.coords)
            out.append("G36*")
            out.append(xy(*pts[0]) + "D02*")
            for q in pts[1:]:
                out.append(xy(*q) + "D01*")
            out.append("G37*")
    out.append("%LPD*%")
    return out

def write_gerber(fname, func, geom):
    lines = gerber_header(fname, func) + poly_lines(geom) + ["M02*"]
    with open(os.path.join(OUT, fname), "w") as f:
        f.write("\n".join(lines) + "\n")

def write_outline(fname):
    lines = gerber_header(fname, "Profile,NP") + ["D10*"]
    for ring in [BOARD.exterior] + list(BOARD.interiors):
        pts = list(ring.coords)
        lines.append(xy(*pts[0]) + "D02*")
        for q in pts[1:]:
            lines.append(xy(*q) + "D01*")
    lines.append("M02*")
    with open(os.path.join(OUT, fname), "w") as f:
        f.write("\n".join(lines) + "\n")

def write_drill(fname, holes, plated):
    sizes = sorted({round(d, 3) for x, y, d in holes})
    lines = ["M48", "; Fly-Brain Drone " + ("plated" if plated else "non-plated"), "FMAT,2", "METRIC,TZ"]
    for i, d in enumerate(sizes, 1):
        lines.append(f"T{i}C{d:.3f}")
    lines += ["%", "G90", "G05"]
    for i, d in enumerate(sizes, 1):
        lines.append(f"T{i}")
        for x, y, dd in holes:
            if round(dd, 3) == d:
                lines.append(f"X{x + OX:.3f}Y{y + OY:.3f}")
    lines.append("M30")
    with open(os.path.join(OUT, fname), "w") as f:
        f.write("\n".join(lines) + "\n")

mask_top = unary_union([pad_shape(p).buffer(0.05, RES) for p in pads if p["layer"] in ("both", "top")])
mask_bot = unary_union([pad_shape(p).buffer(0.05, RES) for p in pads if p["layer"] in ("both", "bottom")])
silk_top = unary_union([g for ly, g in silk if ly == "top"]).difference(mask_top.buffer(0.15, RES)).intersection(BOARD)
silk_bot = unary_union([g for ly, g in silk if ly == "bottom"]).difference(mask_bot.buffer(0.15, RES)).intersection(BOARD)
cu_top = unary_union(list(CU["top"].values()))
cu_bot = unary_union(list(CU["bottom"].values()))

files = {
    "fly-drone-F_Cu.gtl": ("Copper,L1,Top", cu_top),
    "fly-drone-B_Cu.gbl": ("Copper,L2,Bot", cu_bot),
    "fly-drone-F_Mask.gts": ("Soldermask,Top", mask_top),
    "fly-drone-B_Mask.gbs": ("Soldermask,Bot", mask_bot),
    "fly-drone-F_Silkscreen.gto": ("Legend,Top", silk_top),
    "fly-drone-B_Silkscreen.gbo": ("Legend,Bot", silk_bot),
}
for fn, (func, g) in files.items():
    write_gerber(fn, func, g)
write_outline("fly-drone-Edge_Cuts.gm1")
write_drill("fly-drone-PTH.drl", [(p["x"], p["y"], p["drill"]) for p in pads if p["drill"]], True)
write_drill("fly-drone-NPTH.drl", npth, False)
zpath = os.path.join(OUT, "fly-drone-gerbers.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for fn in list(files) + ["fly-drone-Edge_Cuts.gm1", "fly-drone-PTH.drl", "fly-drone-NPTH.drl"]:
        z.write(os.path.join(OUT, fn), fn)

# ---------------------------------------------------------------- previews
def draw(ax, g, color, z=1, alpha=1.0):
    polys = list(g.geoms) if isinstance(g, MultiPolygon) else ([g] if not g.is_empty else [])
    for p in polys:
        from matplotlib.path import Path
        from matplotlib.patches import PathPatch
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            c = list(ring.coords)
            verts += c; codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", zorder=z, alpha=alpha))

def preview(side, fname):
    fig, ax = plt.subplots(figsize=(9, 10.5), dpi=150)
    fig.patch.set_facecolor("#e9ece9")
    ax.set_facecolor("#e9ece9")
    mask_col, cu_under, exposed, silk_col = "#1b5e3a", "#2f7d4f", "#d9b65c", "#f4f4f0"
    cu = cu_top if side == "top" else cu_bot
    msk = mask_top if side == "top" else mask_bot
    slk = silk_top if side == "top" else silk_bot
    draw(ax, BOARD, mask_col, 1)
    draw(ax, cu, cu_under, 2)
    draw(ax, msk.intersection(cu), exposed, 3)
    draw(ax, slk, silk_col, 4)
    holes = unary_union([Point(p["x"], p["y"]).buffer(p["drill"] / 2, RES) for p in pads if p["drill"]] + [Point(x, y).buffer(d / 2, RES) for x, y, d in npth])
    draw(ax, holes, "#e9ece9", 5)
    ax.set_xlim(-46, 46); ax.set_ylim(-46, 46)
    if side == "bottom":
        ax.invert_xaxis()
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(("Top (parts side)" if side == "top" else "Bottom (battery side, seen from below)") + "  ·  94 × 94 mm max", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), facecolor=fig.get_facecolor())
    plt.close(fig)

preview("top", "preview-top.png")
preview("bottom", "preview-bottom.png")

# ---------------------------------------------------------------- BOM and summary
bom = [
    ("Q1-Q4", "IRLB8721 N-MOSFET, TO-220, lying flat metal side down on its drain pad", 4),
    ("D1-D4", "1N5819 Schottky, DO-41, stripe on the square pad", 4),
    ("R1-R4", "10 kOhm 1/4 W, lying flat, 7.62 mm pitch", 4),
    ("C1", "100 uF 16-25 V electrolytic, laid flat pointing backward, + on the square pad", 1),
    ("U2", "GY-521 MPU6050 on its 8-pin header, chips up", 1),
    ("ESP32", "ESP32-S3 CAM board on two 8 mm printed spacers, wired from the jumper pads", 1),
    ("TPS", "TPS63020 3.3 V buck-boost on foam tape under the rear, EN bridged to VIN", 1),
    ("M1-M4", "8520 motors through the arm holes, in printed collars", 4),
    ("BAT", "1S 500 mAh battery in a printed tray under the board", 1),
    ("Screws", "2x M2 x 16 mm through tray, board and ESP32 spacer", 2),
]
with open(os.path.join(OUT, "bom.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["Ref", "Part", "Qty"]); w.writerows(bom)

area_cm2 = BOARD.area / 100
mass = area_cm2 * THICKNESS / 10 * 1.85 + area_cm2 * 0.0035 * 8.96 * 0.75 * 2 / 1  # FR4 + 2 oz-ish copper share
minx, miny, maxx, maxy = BOARD.bounds
print(f"Board size: {maxx - minx:.1f} x {maxy - miny:.1f} mm, area {area_cm2:.1f} cm2, about {mass:.1f} g at {THICKNESS} mm")
print(f"Pads: {len(pads)}, plated holes: {sum(1 for p in pads if p['drill'])}, traces: {len(traces)}")
print(f"Pour islands dropped: top {drop_top:.1f} mm2, bottom {drop_bot:.1f} mm2")
print("CHECKS PASSED" if OK else "CHECKS FAILED")
for r in report:
    print("  " + r)

# ---------------------------------------------------------------- KiCad project
import sys
sys.path.insert(0, HERE)
import kicad_export
kpath, knets = kicad_export.write(globals())
if kpath:
    print(f"KiCad project: {os.path.relpath(kpath, HERE)} ({len(knets)} nets)")
