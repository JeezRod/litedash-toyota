# Renderiza los cuadros del giro de un auto con Blender (sin interfaz). SIN PROBAR: ajustar con la primera prueba.
#
#   blender -b -P tools/render-car.py -- MODELO.glb SALIDA/ [--body MATERIAL] [--frames 24] [--width 1144] [--start-deg 0]
#
# Escribe SALIDA/NN.png (auto, pintura gris, fondo transparente) y SALIDA/NN-pintura.png (máscara: blanco = pintura).
# Después: tools/make-car-package.py SALIDA/ ... (ver docs/ARCHITECTURE.md). El cuadro de reposo de la app es el
# (frames*3/8) = el 9 de 24: ajustar --start-deg para que ese cuadro sea el 3/4 delantero.
import argparse, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
a = argparse.ArgumentParser()
a.add_argument("model"); a.add_argument("out")
a.add_argument("--body", default="Default_OBJ_011", help="nombre del material de la carrocería (la pintura)")
a.add_argument("--frames", type=int, default=24); a.add_argument("--width", type=int, default=1144)
a.add_argument("--start-deg", type=float, default=0); a.add_argument("--elevation-deg", type=float, default=12)
o = a.parse_args(argv)
out = Path(o.out); out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=o.model)
meshes = [x for x in bpy.context.scene.objects if x.type == "MESH"]
body = bpy.data.materials.get(o.body)
if body is None: sys.exit("No hay material %r. Hay: %s" % (o.body, [m.name for m in bpy.data.materials]))

# Centro y tamaño del auto (todas las piezas).
pts = [x.matrix_world @ Vector(c) for x in meshes for c in x.bound_box]
lo = Vector(map(min, zip(*pts))); hi = Vector(map(max, zip(*pts))); mid = (lo + hi) / 2
radius = (hi - lo).length / 2

scene = bpy.context.scene
scene.render.engine = "CYCLES"; scene.cycles.samples = 48; scene.cycles.use_denoising = True
scene.render.resolution_x = o.width; scene.render.resolution_y = int(o.width * 0.5)
scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"

cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = radius * 2.1
cam = bpy.data.objects.new("cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3
sun.rotation_euler = (math.radians(50), 0, math.radians(30)); scene.collection.objects.link(sun)
scene.world = bpy.data.worlds.new("w"); scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0  # cielo parejo

def aim(deg):
    t = math.radians(deg); e = math.radians(o.elevation_deg); d = radius * 4
    cam.location = mid + Vector((math.cos(t) * math.cos(e), math.sin(t) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler()

def set_gray():
    n = body.node_tree.nodes.get("Principled BSDF")
    for l in list(body.node_tree.nodes["Principled BSDF"].inputs["Base Color"].links): body.node_tree.links.remove(l)
    n.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)

def emission(color):
    m = bpy.data.materials.new("mask"); m.use_nodes = True; t = m.node_tree; t.nodes.clear()
    e = t.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = color
    r = t.nodes.new("ShaderNodeOutputMaterial"); t.links.new(e.outputs[0], r.inputs[0]); return m

set_gray()
originals = {x: [s.material for s in x.material_slots] for x in meshes}
white, black = emission((1, 1, 1, 1)), emission((0, 0, 0, 1))
for i in range(o.frames):
    aim(o.start_deg + 360 * i / o.frames)
    for x, mats in originals.items():
        for s, m in zip(x.material_slots, mats): s.material = m
    scene.render.film_transparent = True; scene.cycles.samples = 48; scene.cycles.use_denoising = True
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    scene.render.filepath = str(out / ("%02d.png" % i)); bpy.ops.render.render(write_still=True)
    # Máscara: pintura blanca, todo lo demás negro, sin luces ni transparencia.
    for x, mats in originals.items():
        for s, m in zip(x.material_slots, mats): s.material = white if m == body else black
    scene.render.film_transparent = False; scene.cycles.samples = 8; scene.cycles.use_denoising = False
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    scene.render.filepath = str(out / ("%02d-pintura.png" % i)); bpy.ops.render.render(write_still=True)
print("Listo:", out)
