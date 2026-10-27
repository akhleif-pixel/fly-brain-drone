"""
Blender script: renders the printed frame on its own and with the drone's parts in place.

    blender --background --python frame/render_frame.py

Writes frame/out/frame.png and frame/out/assembly.png. Everything is in mm; the parts are
simple stand-in shapes at the heights frame/gen_frame.py checks.
"""
import math, os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
MC = 47.5 / math.sqrt(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1150
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("w"); sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.92, 0.93, 0.92, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc.view_settings.view_transform = "Standard"
    return sc

def mat(name, rgb, rough=0.5, metal=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m

def add(obj, m):
    obj.data.materials.append(m)
    return obj

def cube(x0, x1, y0, y1, z0, z1, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object; o.scale = (x1 - x0, y1 - y0, z1 - z0)
    return add(o, m)

def cylz(x, y, z0, z1, r, m, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=z1 - z0, location=(x, y, (z0 + z1) / 2))
    return add(bpy.context.object, m)

def frame(m):
    bpy.ops.wm.stl_import(filepath=os.path.join(OUT, "frame.stl"))
    o = bpy.context.selected_objects[0]
    bpy.ops.object.shade_auto_smooth() if hasattr(bpy.ops.object, "shade_auto_smooth") else None
    return add(o, m)

def lights_camera(sc, loc, target=(0, 0, 8), lens=50):
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 100))
    sun = bpy.context.object; sun.data.energy = 2.2; sun.rotation_euler = (math.radians(35), math.radians(10), math.radians(30))
    bpy.ops.object.light_add(type="AREA", location=(-80, -60, 90))
    a = bpy.context.object; a.data.energy = 6e4; a.data.size = 80
    a.rotation_euler = (math.radians(40), 0, math.radians(-50))
    bpy.ops.object.empty_add(location=target); tgt = bpy.context.object
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object
    cam.data.lens = lens
    c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    sc.camera = cam
    # ground shadow catcher
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, -8.2))
    add(bpy.context.object, mat("floor", (0.92, 0.93, 0.92), 0.9))

def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)

PLA = (0.95, 0.45, 0.12)

# ---------------------------------------------------------------- frame alone
sc = reset()
frame(mat("pla", PLA, 0.45))
lights_camera(sc, (95, -120, 110), target=(0, 0, 5), lens=60)
render(sc, "frame.png")

# ---------------------------------------------------------------- with the parts
sc = reset()
frame(mat("pla", PLA, 0.45))
green, black, metal = mat("pcb", (0.05, 0.32, 0.15), 0.4), mat("black", (0.03, 0.03, 0.03), 0.4), mat("metal", (0.75, 0.75, 0.78), 0.25, 1.0)
blue, silver = mat("blue", (0.08, 0.2, 0.6), 0.4), mat("battery", (0.55, 0.6, 0.7), 0.3, 0.6)
prop = mat("prop", (0.1, 0.1, 0.1), 0.3)
# PCB on its posts
cube(-23, 23, -22, 22, 4.0, 5.0, green)
# MOSFETs standing, tab outward
for sx in (1, -1):
    for c in (7.54, -7.54):
        x0, x1 = sorted((sx * 17.8, sx * 21.9))
        cube(x0, x1, c - 5, c + 5, 5.0, 14.5, black)
        t0, t1 = sorted((sx * 21.9, sx * 22.6))
        cube(t0, t1, c - 5, c + 5, 5.0, 23.5, metal)
# MPU6050 on its header, TPS63020, C1
cube(-10.6, 10.6, 1.3, 17.3, 7.5, 9.1, blue)
cylz(6.85, -18.5, 5.0, 17.0, 3.15, mat("cap", (0.1, 0.15, 0.4), 0.3))
# ESP32 on the bridges (28.5 x 51 mm, measured from a photo): module and antenna at the front, two USB-C at the rear,
# camera propped on the module looking forward
cube(-14.25, 14.25, -25.2, 25.8, 19.0, 20.6, mat("esp", (0.08, 0.08, 0.1), 0.4))
cube(-9, 9, 7.3, 32.8, 20.6, 21.4, black)
cube(-7.9, 7.9, 8.0, 25.6, 21.4, 23.7, metal)
for x in (-6.4, 4.7):
    cube(x - 4.5, x + 4.5, -26.0, -18.6, 20.6, 23.8, metal)
# TPS63020 on foam under the ESP32
cube(-9.35, 9.35, -13.5, 14.0, 18.0, 19.0, mat("foam", (0.85, 0.84, 0.8), 0.9))
cube(-9.35, 9.35, -13.5, 14.0, 17.0, 18.0, mat("tps", (0.05, 0.05, 0.06), 0.4))
cube(-2.5, 2.5, 6.0, 11.0, 14.0, 17.0, mat("ind", (0.35, 0.36, 0.38), 0.6))
cube(-4.25, 4.25, 14, 15.2, 23.7, 32.2, black)
cube(-4, 4, 15.2, 19, 24, 32, black)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=3.4, depth=3.5, location=(0, 20.7, 28), rotation=(math.radians(90), 0, 0))
add(bpy.context.object, black)
# battery under the frame, strap over the crossbars
cube(-10, 10, -20, 20, -7.0, 0.0, silver)
cube(-5, 5, -26, 26, -7.8, -7.0, black)
# motors and props
for sx in (1, -1):
    for sy in (1, -1):
        x, y = sx * MC, sy * MC
        cylz(x, y, 6.0, 26.0, 4.25, metal)
        cylz(x, y, 26.0, 29.5, 0.6, metal, 16)
        cylz(x, y, 27.0, 29.0, 2.6, prop, 24)
        ang = math.radians(30 if sx * sy > 0 else -30)
        for a in (ang, ang + math.pi):
            bx, by = x + math.cos(a) * 14, y + math.sin(a) * 14
            bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, 28.0), rotation=(math.radians(8), 0, a))
            o = bpy.context.object; o.scale = (27.5, 6.0, 0.7); add(o, prop)
lights_camera(sc, (120, -150, 140), target=(0, 0, 10), lens=55)
render(sc, "assembly.png")
