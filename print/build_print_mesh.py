"""
Builds the print-ready Dendera mesh: one watertight solid in millimetres.

Same layout as the Blender model at 1 m = 30 mm, with two print-only changes:
  - struts are 3 mm thick instead of 2.1 mm, so they survive support removal
  - the bottom of each lower sphere is sliced flat to give it a foot on the bed

Needs: pip install manifold3d trimesh
Run:   python build_print_mesh.py   (writes dendera_print.stl and .3mf next to it)
"""
import math
import os

import numpy as np
import trimesh
from manifold3d import Manifold, OpType

SCALE = 30.0                      # mm per scene metre

SPHERES_PER_RING = 7
RING_RADIUS = 1.8 * SCALE         # 54 mm
RING_Z = 0.835 * SCALE            # rings at +/- 25.05 mm
SPHERE_R = 0.16 * SCALE           # 4.8 mm
PLATE_D = 1.5 * SCALE             # 45 mm
PLATE_T = PLATE_D * 0.42          # 18.9 mm
PLATE_Z = 0.5 * SCALE             # plates at +/- 15 mm
STRUT_R = 1.5                     # mm (3 mm thick)
FOOT_CUT = 0.8                    # mm sliced off the bottom spheres
SEG = 48                          # smoothness of round parts


def strut(a, b, r=STRUT_R):
    a, b = np.asarray(a, float), np.asarray(b, float)
    v = b - a
    length = float(np.linalg.norm(v))
    z = v / length
    helper = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    x = np.cross(helper, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.column_stack([x, y, z, a])          # 3x4: rotate z-axis onto v, move to a
    return Manifold.cylinder(length, r, r, SEG).transform(m)


def build():
    rings = []
    for zc in (RING_Z, -RING_Z):
        ring = []
        for i in range(SPHERES_PER_RING):
            ang = 2 * math.pi * i / SPHERES_PER_RING + math.pi / 2
            ring.append((RING_RADIUS * math.cos(ang), RING_RADIUS * math.sin(ang), zc))
        rings.append(ring)

    parts = []
    for ring in rings:
        for p in ring:
            parts.append(Manifold.sphere(SPHERE_R, SEG).translate(p))
    for zc in (PLATE_Z, -PLATE_Z):
        parts.append(Manifold.sphere(1.0, SEG * 2)
                     .scale([PLATE_D / 2, PLATE_D / 2, PLATE_T / 2])
                     .translate([0, 0, zc]))

    rim = PLATE_D / 2 * 0.9
    n = SPHERES_PER_RING
    for r_i, ring in enumerate(rings):
        plate_z = PLATE_Z if r_i == 0 else -PLATE_Z
        for i in range(n):
            parts.append(strut(ring[i], ring[(i + 1) % n]))              # ring neighbours
        for p in ring:
            d = np.array([p[0], p[1]]) / math.hypot(p[0], p[1])
            parts.append(strut(p, (d[0] * rim, d[1] * rim, plate_z)))   # spokes
    for a, b in zip(rings[0], rings[1]):
        parts.append(strut(a, b))                                        # posts
    parts.append(strut((0, 0, PLATE_Z), (0, 0, -PLATE_Z)))               # spine

    solid = Manifold.batch_boolean(parts, OpType.Add)

    zmin = -RING_Z - SPHERE_R
    solid = solid.trim_by_plane([0, 0, 1], zmin + FOOT_CUT)              # flat feet
    solid = solid.translate([0, 0, -(zmin + FOOT_CUT)])                  # sit on z = 0

    mg = solid.to_mesh()
    verts = np.asarray(mg.vert_properties)[:, :3]
    faces = np.asarray(mg.tri_verts)
    return trimesh.Trimesh(verts, faces, process=True)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    mesh = build()
    mesh.export(os.path.join(here, "dendera_print.stl"))
    mesh.export(os.path.join(here, "dendera_print.3mf"))
    ext = mesh.bounds[1] - mesh.bounds[0]
    print("watertight:", mesh.is_watertight, "| bodies:", mesh.body_count,
          "| size mm:", [round(float(v), 1) for v in ext],
          "| volume cm3:", round(mesh.volume / 1000, 1), "| tris:", len(mesh.faces))
