import runpy, math
g = runpy.run_path("pcb/gen.py")
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
# physical check: gate on the left seen from the center, legs toward the center
for m in range(1,5):
    P = {p["ref"]: p for p in g["pads"]}
    G, D, S = P[f"Q{m}.G"], P[f"Q{m}.D"], P[f"Q{m}.S"]
    ox, oy = D["x"], D["y"]; dx, dy = ox/math.hypot(ox,oy), oy/math.hypot(ox,oy)   # outward
    leftx, lefty = -dy, dx
    side = (G["x"]-ox)*leftx + (G["y"]-oy)*lefty
    print(f"Q{m}: gate on the {'LEFT' if side>0 else 'RIGHT'} seen from the center ({'ok' if side>0 else 'WRONG'})")
