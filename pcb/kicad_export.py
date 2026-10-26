"""
Writes the board from gen.py as a native KiCad project (pcb/kicad/), so it can be opened
and edited in KiCad 8 or newer (KiCad 10 upgrades the file when it is saved).

Everything is real KiCad data: footprints with numbered pads and nets, tracks,
copper zones (GND on top, VBAT on the bottom, one drain zone per MOSFET),
the board outline on Edge.Cuts and the silkscreen as text, lines and filled shapes.
KiCad's Y axis points down, so y is negated.
"""
import json, os, uuid
from collections import OrderedDict

def U():
    return str(uuid.uuid4())

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def n(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def write(G):
    pads, traces, regions, npth = G["pads"], G["traces"], G["regions"], G["npth"]
    BOARD, RES = G["BOARD"], G["RES"]
    K_TEXT, K_LINE, K_FILL = G["K_TEXT"], G["K_LINE"], G["K_FILL"]
    out_dir = os.path.join(G["HERE"], "kicad")
    os.makedirs(out_dir, exist_ok=True)
    base = G.get("NAME", "fly-drone")
    pcb_path = os.path.join(out_dir, base + ".kicad_pcb")
    # once someone has saved the board in KiCad, that file is the master copy: leave it alone
    if os.path.exists(pcb_path):
        with open(pcb_path, encoding="utf-8") as fh:
            head = fh.read(400)
        if '(generator "fly_drone_gen")' not in head:
            print(f"KiCad file {pcb_path} was saved in KiCad; not overwriting it. Make changes there.")
            return None, {}
    X = lambda x: n(x)
    Y = lambda y: n(-y)
    LAYER = {"top": "F.SilkS", "bottom": "B.SilkS"}

    # nets
    names = ["GND", "VBAT", "3V3"] + sorted({p["net"] for p in pads} - {"GND", "VBAT", "3V3"})
    NET = {nm: i + 1 for i, nm in enumerate(names)}

    lines = ['(kicad_pcb', '  (version 20240108)', '  (generator "fly_drone_gen")', '  (generator_version "8.0")',
             f'  (general (thickness {n(G["THICKNESS"])}) (legacy_teardrops no))', '  (paper "A4")', '  (layers']
    for num, name, kind, user in [(0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
                                  (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
                                  (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
                                  (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
                                  (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
                                  (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
                                  (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
                                  (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
                                  (48, "B.Fab", "user", None), (49, "F.Fab", "user", None)]:
        lines.append(f'    ({num} {q(name)} {kind}' + (f' {q(user)}' if user else '') + ')')
    lines += ['  )', '  (setup', '    (pad_to_mask_clearance 0.05)', '    (allow_soldermask_bridges_in_footprints no)', '  )',
              '  (net 0 "")']
    for nm in names:
        lines.append(f'  (net {NET[nm]} {q(nm)})')

    # footprints: group pads by part reference
    groups = OrderedDict()
    for p in pads:
        ref = p["ref"]
        if ref.startswith("J."):
            part, num = "J_" + ref[2:], "1"
        elif ref.startswith("BAT"):
            part, num = "BAT", "1" if ref.endswith("+") else "2"
        elif "." in ref:
            part, num = ref.split(".", 1)
            num = {"+": "1", "-": "2", "A": "A", "K": "K"}.get(num, num)
        else:   # motor pads like M1+ / M1-
            part, num = ref[:-1], "1" if ref.endswith("+") else "2"
        groups.setdefault(part, []).append((num, p))
    VALUES = {"Q": "IRLB8721", "D": "1N5819", "R": "10k", "C": "100uF", "U": "GY-521 MPU6050", "M": "8520 motor", "J": "wire pad", "BAT": "battery pigtail"}
    for part, plist in groups.items():
        cx = sum(p["x"] for _, p in plist) / len(plist)
        cy = sum(p["y"] for _, p in plist) / len(plist)
        val = next((v for k, v in VALUES.items() if part.startswith(k)), part)
        lines += [f'  (footprint {q("FlyDrone:" + part)}', '    (layer "F.Cu")', f'    (uuid {q(U())})', f'    (at {X(cx)} {Y(cy)})',
                  f'    (property "Reference" {q(part)} (at 0 -2.5 0) (layer "F.Fab") (uuid {q(U())}) (effects (font (size 1 1) (thickness 0.15))))',
                  f'    (property "Value" {q(val)} (at 0 2.5 0) (layer "F.Fab") (uuid {q(U())}) (effects (font (size 1 1) (thickness 0.15))))',
                  '    (attr through_hole)']
        for num, p in plist:
            dx, dy = p["x"] - cx, p["y"] - cy
            shape = {"circle": "circle", "rect": "rect", "oval": "oval"}[p["shape"]]
            ang = f' {n(p["rot"])}' if p["rot"] else ''
            lines.append(f'    (pad {q(num)} thru_hole {shape} (at {X(dx)} {Y(dy)}{ang}) (size {n(p["w"])} {n(p["h"])}) (drill {n(p["drill"])}) '
                         f'(layers "*.Cu" "*.Mask") (remove_unused_layers no) (net {NET[p["net"]]} {q(p["net"])}) (uuid {q(U())}))')
        lines.append('  )')
    for i, (x, y, d) in enumerate(npth, 1):
        lines += [f'  (footprint "FlyDrone:MountingHole_M2"', '    (layer "F.Cu")', f'    (uuid {q(U())})', f'    (at {X(x)} {Y(y)})',
                  f'    (property "Reference" {q("H" + str(i))} (at 0 -2.5 0) (layer "F.Fab") (uuid {q(U())}) (effects (font (size 1 1) (thickness 0.15))))',
                  f'    (property "Value" "M2" (at 0 2.5 0) (layer "F.Fab") (uuid {q(U())}) (effects (font (size 1 1) (thickness 0.15))))',
                  '    (attr exclude_from_pos_files exclude_from_bom)',
                  f'    (pad "" np_thru_hole circle (at 0 0) (size {n(d)} {n(d)}) (drill {n(d)}) (layers "*.Cu" "*.Mask") (uuid {q(U())}))', '  )']

    # tracks
    for t in traces:
        layer = "F.Cu" if t["layer"] == "top" else "B.Cu"
        for (x1, y1), (x2, y2) in zip(t["pts"], t["pts"][1:]):
            lines.append(f'  (segment (start {X(x1)} {Y(y1)}) (end {X(x2)} {Y(y2)}) (width {n(t["w"])}) (layer {q(layer)}) (net {NET[t["net"]]}) (uuid {q(U())}))')

    # zones
    def zone(net, layer, ring, priority, solid):
        pts = " ".join(f"(xy {X(x)} {Y(y)})" for x, y in ring)
        connect = '(connect_pads yes (clearance 0.4))' if solid else '(connect_pads (clearance 0.4))'
        return [f'  (zone (net {NET[net]}) (net_name {q(net)}) (layer {q(layer)}) (uuid {q(U())}) (name {q(net + " " + layer)}) (hatch edge 0.5)',
                f'    (priority {priority})', f'    {connect}', '    (min_thickness 0.25) (filled_areas_thickness no)',
                '    (fill yes (thermal_gap 0.35) (thermal_bridge_width 0.45) (island_removal_mode 0) (island_area_min 1))',
                f'    (polygon (pts {pts}))', '  )']
    outer = list(BOARD.exterior.coords)[:-1]
    lines += zone("GND", "F.Cu", outer, 0, False)
    lines += zone("VBAT", "B.Cu", outer, 0, False)
    for r in regions:
        lines += zone(r["net"], "F.Cu" if r["layer"] == "top" else "B.Cu", list(r["poly"].exterior.coords)[:-1], 1, True)

    # board outline: outer edge as a polygon, motor holes as circles
    pts = " ".join(f"(xy {X(x)} {Y(y)})" for x, y in outer)
    lines.append(f'  (gr_poly (pts {pts}) (stroke (width 0.1) (type solid)) (fill none) (layer "Edge.Cuts") (uuid {q(U())}))')
    for hole in BOARD.interiors:
        hx = sum(x for x, y in hole.coords) / len(hole.coords)
        hy = sum(y for x, y in hole.coords) / len(hole.coords)
        r = max(((x - hx) ** 2 + (y - hy) ** 2) ** 0.5 for x, y in hole.coords)
        lines.append(f'  (gr_circle (center {X(hx)} {Y(hy)}) (end {X(hx + G["MOTOR_HOLE_D"] / 2)} {Y(hy)}) (stroke (width 0.1) (type solid)) (fill none) (layer "Edge.Cuts") (uuid {q(U())}))')

    # silkscreen
    for t in K_TEXT:
        h = round(t["size"] * 0.72, 2)
        th = round(max(0.15, h * 0.16), 2)
        mirror = ' (justify mirror)' if t["layer"] == "bottom" else ''
        lines.append(f'  (gr_text {q(t["s"])} (at {X(t["x"])} {Y(t["y"])} {n(t["rot"])}) (layer {q(LAYER[t["layer"]])}) (uuid {q(U())}) '
                     f'(effects (font (size {n(h)} {n(h)}) (thickness {n(th)})){mirror}))')
    for l in K_LINE:
        for (x1, y1), (x2, y2) in zip(l["pts"], l["pts"][1:]):
            lines.append(f'  (gr_line (start {X(x1)} {Y(y1)}) (end {X(x2)} {Y(y2)}) (stroke (width {n(l["w"])}) (type solid)) (layer {q(LAYER[l["layer"]])}) (uuid {q(U())}))')
    for f in K_FILL:
        pts = " ".join(f"(xy {X(x)} {Y(y)})" for x, y in f["pts"])
        lines.append(f'  (gr_poly (pts {pts}) (stroke (width 0.05) (type solid)) (fill solid) (layer {q(LAYER[f["layer"]])}) (uuid {q(U())}))')
    lines.append(')')

    with open(pcb_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    pro = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2, "silk_line_width": 0.15, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.2, "min_copper_edge_clearance": 0.3, "min_track_width": 0.2, "min_through_hole_diameter": 0.3, "min_hole_to_hole": 0.25, "min_via_diameter": 0.5},
            "track_widths": [0.3, 0.5, 0.8, 1.6], "via_dimensions": []}},
        "meta": {"filename": base + ".kicad_pro", "version": 1},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.25, "track_width": 0.3, "via_diameter": 0.8, "via_drill": 0.4,
                                      "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)"}],
                         "meta": {"version": 3}},
        "pcbnew": {"last_paths": {"gerber": "../out/"}},
    }
    with open(os.path.join(out_dir, base + ".kicad_pro"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(pro, fh, indent=2)
    return pcb_path, NET
