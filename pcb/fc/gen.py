"""
Fly-Brain Drone flight-controller board (rev B) generator.

A small 46 x 44 mm 2-layer board that sits in the middle of a 3D-printed frame. The frame
holds the motors; their wires come in to pads at the board's corners. Every part is
through-hole and hand-solderable. The MOSFETs stand upright along the left and right edges,
metal tab facing outward. Run:

    pcb/.venv/Scripts/python pcb/fc/gen.py

It writes Gerbers + drill files (pcb/fc/out/fly-fc-gerbers.zip), preview images, a BOM,
a KiCad project in pcb/fc/kicad/, and prints a design-rule and connectivity report.
Coordinates are mm, top view, x to the right (drone's right side), y toward the front.

Layers:
  top    = parts side: signals, GND pour
  bottom = VBAT pour, gate traces

The TPS63020 module (27.5 x 18.7 mm, too big for the board) sits on foam under the ESP32. Its VIN and GND
wires come to the rear pads; its OUT goes straight to the ESP32's 3V3 pin, which feeds this board through
the front 3V3 pad.
"""
import math, os, csv, sys, zipfile
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
NAME = "fly-fc"

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

def pad(ref, net, x, y, d, drill=None, shape="circle", w=None, h=None, rot=0, layer="both", spoke=SPOKE):
    pads.append(dict(ref=ref, net=net, x=x, y=y, d=d, drill=drill, shape=shape, w=w or d, h=h or d, rot=rot, layer=layer, spoke=spoke))
    return pads[-1]

def trace(net, pts, width, layer="top"):
    traces.append(dict(net=net, pts=pts, w=width, layer=layer))

def pad_shape(p):
    if p["shape"] == "circle":
        g = Point(p["x"], p["y"]).buffer(p["d"] / 2, RES)
    else:
        g = box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
        g = affinity.rotate(g, p["rot"], origin=(p["x"], p["y"]))
    return g

def trace_shape(t):
    return LineString(t["pts"]).buffer(t["w"] / 2, RES)

# ---------------------------------------------------------------- outline
W, H = 46.0, 44.0
BOARD = box(-W / 2, -H / 2, W / 2, H / 2).buffer(-2.5, RES).buffer(2.5, RES)   # rounded corners

# M2 holes in the corners: screws or printed pins into the frame
HOLE_X, HOLE_Y = 20.0, 19.0
for sx in (1, -1):
    for sy in (1, -1):
        npth.append((sx * HOLE_X, sy * HOLE_Y, 2.2))

# ---------------------------------------------------------------- motor channels
CH = [
    dict(m=1, sx=1, sy=1, spin="CCW", where="front right"),
    dict(m=2, sx=1, sy=-1, spin="CW", where="rear right"),
    dict(m=3, sx=-1, sy=-1, spin="CCW", where="rear left"),
    dict(m=4, sx=-1, sy=1, spin="CW", where="front left"),
]
QX, QC = 19.4, 7.54        # MOSFET pad row x, and the drain (middle) pad's distance from the center line
DX, RX = 15.4, 12.2        # diode and resistor columns
TRX = 17.4                 # drain trace column

for ch in CH:
    m, sx, sy = ch["m"], ch["sx"], ch["sy"]
    # Standing upright, tab facing outward: seen from the center (the printed face), the legs are
    # G D S from left to right. On the right edge "left" is +y; on the left edge it is -y.
    c = sy * QC
    gy = c + 2.54 * sx
    ch.update(gy=gy, sy_src=c - 2.54 * sx)
    G = pad(f"Q{m}.G", f"GATE{m}", sx * QX, gy, 1.9, 1.2)
    D = pad(f"Q{m}.D", f"DRAIN{m}", sx * QX, c, 1.9, 1.2)
    S = pad(f"Q{m}.S", "GND", sx * QX, c - 2.54 * sx, 1.9, 1.2, spoke=0.8)
    # motor pads near the corner
    MP = pad(f"M{m}+", "VBAT", sx * 13.0, sy * 19.6, 2.2, 1.0, spoke=0.8)
    MN = pad(f"M{m}-", f"DRAIN{m}", sx * 16.0, sy * 19.6, 2.2, 1.0)
    # flyback diode lying flat along the edge, stripe (cathode) on VBAT toward the center line
    DA = pad(f"D{m}.A", f"DRAIN{m}", sx * DX, sy * 16.0, 2.0, 1.0)
    DK = pad(f"D{m}.K", "VBAT", sx * DX, sy * 3.3, 2.0, 1.0, shape="rect")
    # drain: MOSFET -> up the drain column -> motor minus, with the diode tapped off
    trace(f"DRAIN{m}", [(D["x"], D["y"]), (sx * TRX, c), (sx * TRX, sy * 17.6), (MN["x"], MN["y"])], 0.8)
    trace(f"DRAIN{m}", [(DA["x"], DA["y"]), (sx * TRX, sy * 16.0)], 0.8)
    # gate pull-down lying flat, 7.62 mm pitch, gate end level with the gate leg, ground end
    # toward the rear on the right edge and toward the front on the left (away from the next resistor)
    ry = gy - 7.62 * sx
    RG = pad(f"R{m}.1", f"GATE{m}", sx * RX, gy, 1.6, 0.8)
    RS = pad(f"R{m}.2", "GND", sx * RX, ry, 1.6, 0.8)
    trace(f"GATE{m}", [(G["x"], G["y"]), (RG["x"], RG["y"])], 0.4, layer="bottom")
    ch.update(G=G, D=D, S=S, MP=MP, MN=MN, DA=DA, DK=DK, RG=RG, RS=RS)

# ---------------------------------------------------------------- wire pads to the ESP32, front edge
JY = 20.2
JP = {}
for name, net, x in [("G4", "GATE4", -10.16), ("G3", "GATE3", -7.62), ("3V3", "3V3", -5.08), ("SCL", "SCL", -2.54),
                     ("SDA", "SDA", 0.0), ("GND", "GND", 2.54), ("INT", "INT", 5.08), ("G2", "GATE2", 7.62), ("G1", "GATE1", 10.16)]:
    JP[name] = pad("J." + name, net, x, JY, 1.6, 0.8)

C = {ch["m"]: ch for ch in CH}
# G1 and G4 on the bottom, G2 and G3 on top, so the pairs don't cross
trace("GATE1", [(RX, C[1]["gy"]), (RX, 16.4), (10.16, 18.44), (10.16, JY)], 0.3, layer="bottom")
trace("GATE4", [(-RX, C[4]["gy"]), (-10.6, C[4]["gy"] + 1.6), (-10.6, 17.0), (-10.16, 17.44), (-10.16, JY)], 0.3, layer="bottom")
trace("GATE2", [(RX, C[2]["gy"]), (10.6, C[2]["gy"] + 1.6), (10.6, 17.6), (7.62, JY)], 0.3)
trace("GATE3", [(-RX, C[3]["gy"]), (-10.6, C[3]["gy"] + 1.6), (-10.6, 17.6), (-7.62, JY)], 0.3)

# ---------------------------------------------------------------- MPU6050 (GY-521) on its 8-pin header, body toward the rear
MPU_Y = 16.0
MPU_NAMES = ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"]
MPU_NETS = ["3V3", "GND", "SCL", "SDA", "NC1", "NC2", "NC3", "INT"]
MPU = {}
for i, (nm, net) in enumerate(zip(MPU_NAMES, MPU_NETS)):
    MPU[nm] = pad("U2." + nm, net, -8.89 + 2.54 * i, MPU_Y, 1.7, 1.0, shape="rect" if i == 0 else "circle")
trace("3V3", [(-8.89, MPU_Y), (-8.89, 17.4), (-6.35, 17.4), (-5.08, 18.67), (-5.08, JY)], 0.4)
trace("SCL", [(-3.81, MPU_Y), (-2.54, 17.27), (-2.54, JY)], 0.3)
trace("SDA", [(-1.27, MPU_Y), (0.0, 17.27), (0.0, JY)], 0.3)
trace("INT", [(8.89, MPU_Y), (8.89, 17.4), (6.35, 17.4), (5.08, 18.67), (5.08, JY)], 0.3)
# the ESP32 ground pad reaches the ground pour between the XDA and XCL pins
trace("GND", [(2.54, JY), (2.54, 14.0)], 0.3)

# ---------------------------------------------------------------- rear: battery, buck-boost input pads, capacitor
RY = -18.5
pad("BAT+", "VBAT", -9.0, RY, 2.5, 1.2, shape="rect", spoke=1.0)
pad("BAT-", "GND", -5.8, RY, 2.5, 1.2, spoke=1.0)
JP["TG"] = pad("J.TG", "GND", 0.0, RY, 1.6, 0.8)
JP["IN"] = pad("J.IN", "VBAT", 2.54, RY, 1.6, 0.8)
pad("C1.-", "GND", 5.6, RY, 1.6, 0.8)
pad("C1.+", "VBAT", 8.1, RY, 1.6, 0.8, shape="rect")

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

TEXT = False     # no text on the board for now: Ayham adds his own in KiCad

def stext(s, x, y, size=1.3, layer="top", anchor="c", rot=0):
    if not TEXT:
        return
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

def srect(x0, y0, x1, y1, w=0.18, layer="top"):
    sline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], w, layer, closed=True)

# part outlines and labels
for ch in CH:
    m, sx, sy = ch["m"], ch["sx"], ch["sy"]
    c = sy * QC
    # MOSFET body seen from above: 10 mm wide, metal tab on the outer side
    xin, xout = sx * (QX - 1.6), sx * (QX + 3.2)
    srect(min(xin, xout), c - 5.1, max(xin, xout), c + 5.1)
    tab = sx * (QX + 2.6)
    sfill(box(min(tab, xout), c - 5.1, max(tab, xout), c + 5.1))
    stext("G", sx * (QX + 1.75), ch["gy"], 1.2)
    stext(f"Q{m}", sx * 20.6, sy * 1.0, 1.3)
    # diode: body + stripe on the cathode end
    by0, by1 = sy * 7.05, sy * 12.25
    srect(sx * DX - 1.3, min(by0, by1), sx * DX + 1.3, max(by0, by1))
    sfill(box(sx * DX - 1.3, min(by0, by0 + sy * 0.8), sx * DX + 1.3, max(by0, by0 + sy * 0.8)))
    stext(f"D{m}", sx * DX, sy * 13.6, 1.2)
    # resistor
    ry0, ry1 = ch["RG"]["y"], ch["RS"]["y"]
    mid = (ry0 + ry1) / 2
    srect(sx * RX - 1.1, mid - 2.4, sx * RX + 1.1, mid + 2.4)
    stext(f"R{m}", sx * RX, mid, 1.2, rot=90)
    # motor pads: + and -, motor name and spin
    stext(f"M{m}+", sx * 12.8, sy * 17.75, 1.2)
    stext(ch["spin"], sx * 21.9, sy * 15.4, 1.2, rot=90)

# MPU outline (body behind the pin row) and pin names
# open on the pin side so it stays clear of the wire pad labels
sline([(-11.0, MPU_Y - 0.4), (-11.0, MPU_Y - 14.7), (11.0, MPU_Y - 14.7), (11.0, MPU_Y - 0.4)])
for i, nm in enumerate(MPU_NAMES):
    stext(nm, -8.89 + 2.54 * i, MPU_Y - 2.6, 1.2, rot=90)
stext("MPU6050 GY-521", 0, MPU_Y - 7.0, 1.3)
stext("CHIPS UP", 0, MPU_Y - 9.0, 1.2)
# front arrow
stext("FRONT", 0, MPU_Y - 12.0, 1.4)
sfill(Polygon([(-1.0, MPU_Y - 10.9), (1.0, MPU_Y - 10.9), (0, MPU_Y - 10.0)]))
# wire pad labels (to the ESP32)
for name, p in JP.items():
    if p["y"] > 0:
        stext(name, p["x"], JY - 2.35, 1.2, rot=90)
stext("FLY-BRAIN FC rev B", 0, -11.4, 1.2)
# rear row labels
stext("BAT", -7.4, RY + 2.3, 1.2)
stext("+", -9.0, RY - 2.3, 1.4); stext("-", -5.8, RY - 2.3, 1.6)
stext("GND", 0.0, RY + 2.3, 1.2, rot=90); stext("IN", 2.54, RY + 1.9, 1.2, rot=90)
stext("C1", 6.85, RY + 2.4, 1.2); stext("+", 8.1, RY - 2.2, 1.4)
# bottom side
stext("FLY-BRAIN FC rev B", 0, 0, 1.4, "bottom")
stext("ESP32 PADS AT FRONT", 0, 18.0, 1.2, "bottom")

# ---------------------------------------------------------------- copper assembly
def layer_items(layer):
    """(net, geometry, pad or None) for every copper item on a layer, before the pours"""
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
        pour = pour.difference(pad_shape(p).buffer(THERMAL_GAP, RES))
    pour = pour.buffer(-0.15, RES).buffer(0.15, RES)       # drop slivers
    spokes = []
    for p in own_pads:
        r = max(p["w"], p["h"]) / 2 + THERMAL_GAP + 0.6
        for a in (45, 135, 225, 315):
            s = LineString([(p["x"], p["y"]), (p["x"] + r * math.cos(math.radians(a)), p["y"] + r * math.sin(math.radians(a)))]).buffer(p["spoke"] / 2, cap_style=2)
            spokes.append(s.difference(others))
    own = unary_union([g for n, g, p in items if n == net])
    pour = unary_union([pour] + spokes).intersection(POUR_AREA.union(own))
    polys = list(pour.geoms) if isinstance(pour, MultiPolygon) else [pour]
    kept = [pp for pp in polys if pp.buffer(0.01).intersects(own) and pp.area > 1.0]
    dropped = sum(pp.area for pp in polys) - sum(pp.area for pp in kept)
    return unary_union(kept), dropped

pour_top, drop_top = make_pour("top", "GND")
pour_bot, drop_bot = make_pour("bottom", "VBAT")

def copper(layer):
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
    for layer, nets in CU.items():
        names = sorted(nets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                d = nets[names[i]].distance(nets[names[j]])
                if d < CLR - 1e-3:
                    ok = False
                    report.append(f"CLEARANCE {layer}: {names[i]} to {names[j]} = {d:.3f} mm")
    edge = BOARD.boundary
    for layer, nets in CU.items():
        for n, g in nets.items():
            if g.distance(edge) < EDGE_CLR - 0.05:
                ok = False
                report.append(f"EDGE {layer}: {n} {g.distance(edge):.3f} mm from the board edge")
            if g.difference(BOARD).area > 0.01:
                ok = False
                report.append(f"OUTSIDE {layer}: {n}")
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
    # NPTH holes clear of copper
    for x, y, d in npth:
        hole = Point(x, y).buffer(d / 2, RES)
        for layer, nets in CU.items():
            for n, g in nets.items():
                if g.distance(hole) < EDGE_CLR - 0.05:
                    ok = False; report.append(f"HOLE ({x}, {y}) {layer}: {n} {g.distance(hole):.2f} mm")
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
OX, OY = 30.0, 30.0          # shift so all coordinates are positive

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
    with open(os.path.join(OUT, fname), "w") as f:
        f.write("\n".join(gerber_header(fname, func) + poly_lines(geom) + ["M02*"]) + "\n")

def write_outline(fname):
    lines = gerber_header(fname, "Profile,NP") + ["D10*"]
    pts = list(BOARD.exterior.coords)
    lines.append(xy(*pts[0]) + "D02*")
    for q in pts[1:]:
        lines.append(xy(*q) + "D01*")
    lines.append("M02*")
    with open(os.path.join(OUT, fname), "w") as f:
        f.write("\n".join(lines) + "\n")

def write_drill(fname, holes, plated):
    sizes = sorted({round(d, 3) for x, y, d in holes})
    lines = ["M48", "; Fly-Brain Drone FC " + ("plated" if plated else "non-plated"), "FMAT,2", "METRIC,TZ"]
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
    f"{NAME}-F_Cu.gtl": ("Copper,L1,Top", cu_top),
    f"{NAME}-B_Cu.gbl": ("Copper,L2,Bot", cu_bot),
    f"{NAME}-F_Mask.gts": ("Soldermask,Top", mask_top),
    f"{NAME}-B_Mask.gbs": ("Soldermask,Bot", mask_bot),
    f"{NAME}-F_Silkscreen.gto": ("Legend,Top", silk_top),
    f"{NAME}-B_Silkscreen.gbo": ("Legend,Bot", silk_bot),
}
for fn, (func, g) in files.items():
    write_gerber(fn, func, g)
write_outline(f"{NAME}-Edge_Cuts.gm1")
write_drill(f"{NAME}-PTH.drl", [(p["x"], p["y"], p["drill"]) for p in pads if p["drill"]], True)
write_drill(f"{NAME}-NPTH.drl", npth, False)
zpath = os.path.join(OUT, f"{NAME}-gerbers.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for fn in list(files) + [f"{NAME}-Edge_Cuts.gm1", f"{NAME}-PTH.drl", f"{NAME}-NPTH.drl"]:
        z.write(os.path.join(OUT, fn), fn)

# ---------------------------------------------------------------- previews
def draw(ax, g, color, z=1):
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    polys = list(g.geoms) if isinstance(g, MultiPolygon) else ([g] if not g.is_empty else [])
    for p in polys:
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            c = list(ring.coords)
            verts += c; codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", zorder=z))

def preview(side, fname):
    fig, ax = plt.subplots(figsize=(8, 7.8), dpi=170)
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
    ax.set_xlim(-W / 2 - 2, W / 2 + 2); ax.set_ylim(-H / 2 - 2, H / 2 + 2)
    if side == "bottom":
        ax.invert_xaxis()
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(("Top (parts side)" if side == "top" else "Bottom (seen from below)") + f"  ·  {W:.0f} × {H:.0f} mm", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), facecolor=fig.get_facecolor())
    plt.close(fig)

preview("top", "preview-top.png")
preview("bottom", "preview-bottom.png")

# ---------------------------------------------------------------- BOM and summary
bom = [
    ("Q1-Q4", "IRLB8721 N-MOSFET, TO-220, standing upright, metal tab facing the board edge", 4),
    ("D1-D4", "1N5819 Schottky, DO-41, lying flat, stripe on the square pad (toward the center line)", 4),
    ("R1-R4", "10 kOhm 1/4 W, lying flat, 7.62 mm pitch", 4),
    ("C1", "100 uF 16-25 V electrolytic, standing, + on the square pad", 1),
    ("U2", "GY-521 MPU6050 on its 8-pin header, chips up, body toward the rear", 1),
    ("TPS", "TPS63020 3.3 V buck-boost (27.5 x 18.7 mm) on foam under the ESP32: VIN and GND to the rear IN and GND pads, OUT to the ESP32 3V3 pin, EN bridged to VIN, 3V3 pad bridged", 1),
    ("ESP32", "ESP32-S3 CAM board held above by the printed frame, wired from the front pads", 1),
    ("M1-M4", "8520 motors in the printed frame, wires to the corner pads", 4),
    ("BAT", "1S 500 mAh battery pigtail into BAT+ and BAT-", 1),
    ("Screws", "4x M2 through the corner holes into the frame", 4),
]
with open(os.path.join(OUT, "bom.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["Ref", "Part", "Qty"]); w.writerows(bom)

area_cm2 = BOARD.area / 100
mass = area_cm2 * THICKNESS / 10 * 1.85 + area_cm2 * 0.0035 * 8.96 * 0.75 * 2
print(f"Board size: {W:.1f} x {H:.1f} mm, area {area_cm2:.1f} cm2, about {mass:.1f} g at {THICKNESS} mm")
print(f"Pads: {len(pads)}, plated holes: {sum(1 for p in pads if p['drill'])}, traces: {len(traces)}")
print(f"Pour islands dropped: top {drop_top:.1f} mm2, bottom {drop_bot:.1f} mm2")
print("CHECKS PASSED" if OK else "CHECKS FAILED")
for r in report:
    print("  " + r)

# ---------------------------------------------------------------- KiCad project
sys.path.insert(0, os.path.dirname(HERE))
import kicad_export
kpath, knets = kicad_export.write(globals())
if kpath:
    print(f"KiCad project: {os.path.relpath(kpath, HERE)} ({len(knets)} nets)")
