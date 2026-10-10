"""
Sketch Cage — by Hope Abeacan

Builds the Sketch Cage model in Blender: two parallel rings of seven spheres,
joined to their neighbours, with two Smartie-shaped plates on the centre line.

Run it inside Blender (Scripting tab > Open > Run Script). It makes a new scene
called "Sketch Cage", so nothing in your current scene is touched.

Or from a terminal:
    blender --background --python build_sketch_cage.py
"""
import math
import bmesh
import bpy
from mathutils import Vector

# ---- shape -----------------------------------------------------------------
SPHERES_PER_RING = 7
RING_RADIUS = 1.8          # m, centre line to sphere centre
RING_Z = 0.835             # rings sit at +RING_Z and -RING_Z (1.67 m apart)
SPHERE_RADIUS = 0.16       # m
PLATE_DIAMETER = 1.5       # m
PLATE_THICKNESS = PLATE_DIAMETER * 0.42   # Smartie proportions
PLATE_Z = 0.5              # plates at +PLATE_Z and -PLATE_Z (1.0 m apart)
STRUT_RADIUS = 0.035       # m

# ---- render ----------------------------------------------------------------
RES_X, RES_Y = 1080, 1920  # 9:16 vertical; set both to 1080 for square
TURNTABLE_FRAMES = 240     # one full turn, 8 s at 30 fps


def _material(name, colour, roughness, metallic=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return m


def _uv_sphere_mesh(name, segments, rings, radius=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def ring_points():
    rings = []
    for z in (RING_Z, -RING_Z):
        ring = []
        for i in range(SPHERES_PER_RING):
            a = 2 * math.pi * i / SPHERES_PER_RING + math.pi / 2
            ring.append(Vector((RING_RADIUS * math.cos(a), RING_RADIUS * math.sin(a), z)))
        rings.append(ring)
    return rings


def strut_segments(rings):
    """Every strut as a (start, end) pair: ring neighbours, posts, spokes, spine."""
    segs = []
    n = SPHERES_PER_RING
    rim = PLATE_DIAMETER / 2 * 0.9
    for r_i, ring in enumerate(rings):
        plate_z = PLATE_Z if r_i == 0 else -PLATE_Z
        for i in range(n):
            segs.append((ring[i], ring[(i + 1) % n]))          # neighbour round the ring
        for p in ring:
            d = Vector((p.x, p.y, 0)).normalized()
            segs.append((p, Vector((d.x * rim, d.y * rim, plate_z))))  # spoke to its plate
    for a, b in zip(rings[0], rings[1]):
        segs.append((a, b))                                    # post to the sphere beneath
    segs.append((Vector((0, 0, PLATE_Z)), Vector((0, 0, -PLATE_Z))))  # spine
    return segs


def build():
    scene = bpy.data.scenes.new("Sketch Cage")
    win = bpy.context.window or (bpy.context.window_manager.windows[0]
                                 if bpy.context.window_manager.windows else None)
    if win:
        win.scene = scene
    col = scene.collection

    m_sphere = _material("Cage_Node", (0.82, 0.80, 0.76), 0.45)
    m_plate = _material("Cage_Plate", (0.86, 0.84, 0.80), 0.18)
    m_strut = _material("Cage_Strut", (0.03, 0.03, 0.035), 0.3, 0.6)
    m_floor = _material("Cage_Floor", (0.75, 0.75, 0.74), 0.9)

    rig = bpy.data.objects.new("Cage", None)
    col.objects.link(rig)

    sphere_mesh = _uv_sphere_mesh("CageNode", 32, 16, SPHERE_RADIUS)
    sphere_mesh.materials.append(m_sphere)
    rings = ring_points()
    k = 0
    for ring in rings:
        for p in ring:
            k += 1
            o = bpy.data.objects.new(f"Node_{k}", sphere_mesh)
            o.location = p
            o.parent = rig
            col.objects.link(o)

    plate_mesh = _uv_sphere_mesh("SmartiePlate", 64, 32)
    plate_mesh.materials.append(m_plate)
    for k, z in enumerate((PLATE_Z, -PLATE_Z)):
        o = bpy.data.objects.new(f"Plate_{k + 1}", plate_mesh)
        o.location = (0, 0, z)
        o.scale = (PLATE_DIAMETER / 2, PLATE_DIAMETER / 2, PLATE_THICKNESS / 2)
        o.parent = rig
        col.objects.link(o)

    cu = bpy.data.curves.new("Struts", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = STRUT_RADIUS
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    for a, b in strut_segments(rings):
        sp = cu.splines.new('POLY')
        sp.points.add(1)
        sp.points[0].co = (*a, 1)
        sp.points[1].co = (*b, 1)
    cu.materials.append(m_strut)
    struts = bpy.data.objects.new("Struts", cu)
    struts.parent = rig
    col.objects.link(struts)

    # seamless curved backdrop
    z0, prof = -2.9, [(-40, -2.9), (4, -2.9)]
    for s in range(1, 17):
        a = -math.pi / 2 + (math.pi / 2) * s / 16
        prof.append((4 + 8 * math.cos(a), z0 + 8 + 8 * math.sin(a)))
    prof[-1] = (12, z0 + 8)
    prof.append((12, 40))
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-50, 50)]
    for s in range(len(prof) - 1):
        bm.faces.new((rows[0][s], rows[0][s + 1], rows[1][s + 1], rows[1][s])).smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bd_mesh = bpy.data.meshes.new("Backdrop")
    bm.to_mesh(bd_mesh)
    bm.free()
    bd_mesh.materials.append(m_floor)
    bd = bpy.data.objects.new("Backdrop", bd_mesh)
    col.objects.link(bd)
    if bd.data.polygons[0].normal.z < 0:
        bd.data.flip_normals()

    world = bpy.data.worlds.new("Cage_World")
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.86, 0.86, 0.85, 1)
    bg.inputs[1].default_value = 0.5
    scene.world = world

    def area_light(name, loc, energy, size):
        light = bpy.data.lights.new(name, 'AREA')
        light.energy, light.size = energy, size
        o = bpy.data.objects.new(name, light)
        o.location = loc
        t = o.constraints.new('TRACK_TO')
        t.target, t.track_axis, t.up_axis = rig, 'TRACK_NEGATIVE_Z', 'UP_Y'
        col.objects.link(o)

    area_light("Key", (4.5, -4.5, 6.5), 900, 4)
    area_light("Fill", (-6, -3, 2.5), 250, 6)
    area_light("Rim", (0, 6, 5), 500, 3)

    cam_data = bpy.data.cameras.new("CageCam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("CageCam", cam_data)
    cam.location = (0, -13.5, 2.4)
    t = cam.constraints.new('TRACK_TO')
    t.target, t.track_axis, t.up_axis = rig, 'TRACK_NEGATIVE_Z', 'UP_Y'
    col.objects.link(cam)
    scene.camera = cam

    fc = rig.driver_add("rotation_euler", 2)
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = f"(frame - 1) * {2 * math.pi / TURNTABLE_FRAMES:.8f}"
    scene.frame_start, scene.frame_end = 1, TURNTABLE_FRAMES
    scene.render.fps = 30

    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = RES_X, RES_Y, 100
    engines = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items.keys()
    r.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
    try:
        scene.eevee.taa_render_samples = 64
    except Exception:
        pass
    scene.frame_set(1)
    return scene


if __name__ == "__main__":
    build()
