import runpy, io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path("pcb/fc/gen.py")
from collections import defaultdict
nets = defaultdict(list)
for p in g["pads"]:
    nets[p["net"]].append(p["ref"])
for n in sorted(nets):
    print(f"{n:8s} {', '.join(sorted(nets[n]))}")
expect = {
 "VBAT": {"BAT+","C1.+","J.IN","M1+","M2+","M3+","M4+","D1.K","D2.K","D3.K","D4.K"},
 "GND": {"BAT-","C1.-","J.GND","J.TG","U2.GND","Q1.S","Q2.S","Q3.S","Q4.S","R1.2","R2.2","R3.2","R4.2"},
 "3V3": {"J.3V3","J.OUT","U2.VCC"}, "SCL": {"J.SCL","U2.SCL"}, "SDA": {"J.SDA","U2.SDA"}, "INT": {"J.INT","U2.INT"},
}
for m in range(1,5):
    expect[f"GATE{m}"] = {f"Q{m}.G", f"R{m}.1", f"J.G{m}"}
    expect[f"DRAIN{m}"] = {f"Q{m}.D", f"M{m}-", f"D{m}.A"}
bad = [n for n,s in expect.items() if set(nets[n]) != s]
print("NETLIST MATCHES DESIGN" if not bad else f"MISMATCH: {bad}")
# physical check: IRLB8721 standing with its tab toward the board edge, so the printed face looks
# at the center; seen from there the legs are G D S from left to right, with D in the middle
P = {p["ref"]: p for p in g["pads"]}
for m in range(1,5):
    G, D, S = P[f"Q{m}.G"], P[f"Q{m}.D"], P[f"Q{m}.S"]
    sx = 1 if D["x"] > 0 else -1                 # which edge
    left = sx * (G["y"] - D["y"]) > 0            # facing outward along x, left is +y on the right edge
    middle = min(G["y"], S["y"]) < D["y"] < max(G["y"], S["y"])
    print(f"Q{m}: gate on the {'LEFT' if left else 'RIGHT'} seen from the center, drain {'in the middle' if middle else 'NOT in the middle'} ({'ok' if left and middle else 'WRONG'})")
