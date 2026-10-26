"""
Builds the assets for the rev B 3D model page (docs/drone-3d-revb/index.html):
PCB top and bottom textures straight from pcb/fc/gen.py's copper, mask, silkscreen and drills,
and the printed frame's mesh as JSON. Run from the repo root:

    pcb/.venv/Scripts/python docs/drone-3d-revb/make_assets.py
"""
import io, os, contextlib, json, runpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from shapely.geometry import MultiPolygon, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path(os.path.join(ROOT, "pcb", "fc", "gen.py"))

W, H, BOARD, RES = g["W"], g["H"], g["BOARD"], g["RES"]
holes = unary_union([Point(p["x"], p["y"]).buffer(p["drill"] / 2, RES) for p in g["pads"] if p["drill"]] +
                    [Point(x, y).buffer(d / 2, RES) for x, y, d in g["npth"]])
PX_PER_MM = 40

def draw(ax, geom, color):
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else ([geom] if not geom.is_empty else [])
    for p in polys:
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            c = list(ring.coords)
            verts += c; codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", antialiased=True))

def texture(side, fname):
    cu = g["cu_top"] if side == "top" else g["cu_bot"]
    msk = g["mask_top"] if side == "top" else g["mask_bot"]
    slk = g["silk_top"] if side == "top" else g["silk_bot"]
    fig = plt.figure(figsize=(W * PX_PER_MM / 100, H * PX_PER_MM / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-W / 2, W / 2); ax.set_ylim(-H / 2, H / 2); ax.axis("off")
    fig.patch.set_alpha(0)
    draw(ax, BOARD.difference(holes), "#14532d")                       # solder mask over bare board
    draw(ax, cu.difference(holes), "#1d6b3c")                          # copper under the mask
    draw(ax, msk.intersection(cu).difference(holes), "#c9ccd1")        # lead-free HASL pads
    draw(ax, slk.difference(holes), "#f2f2ee")
    fig.savefig(os.path.join(HERE, fname), transparent=True)
    plt.close(fig)

texture("top", "pcb-top.png")
texture("bottom", "pcb-bottom.png")
# the printed frame as an indexed mesh in JSON (artifacts don't serve .stl): {"v": [x, y, z, ...], "i": [a, b, c, ...]}
import numpy as np
raw = np.fromfile(os.path.join(ROOT, "frame", "out", "frame.stl"), dtype=np.uint8)
n = int(raw[80:84].view("<u4")[0])
tri = np.frombuffer(raw[84:84 + n * 50].tobytes(), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])["v"].reshape(-1, 3)
uniq, idx = np.unique(np.round(tri, 3), axis=0, return_inverse=True)
with open(os.path.join(HERE, "frame.json"), "w") as f:
    json.dump({"v": [round(float(c), 3) for c in uniq.ravel()], "i": [int(k) for k in idx.ravel()]}, f, separators=(",", ":"))

# pad positions for the page (rounded), so wires land exactly on the copper
pads = {p["ref"]: [round(p["x"], 2), round(p["y"], 2)] for p in g["pads"]}
with open(os.path.join(HERE, "pads.json"), "w") as f:
    json.dump(pads, f, separators=(",", ":"))
print("wrote pcb-top.png, pcb-bottom.png, frame.json, pads.json")
