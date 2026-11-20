"""Run inside Blender 5.3: blender --background --factory-startup --python this_file.py."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy
import bmesh
from testarossa_humanoid import build_humanoid_blockout

# Match the production executor: run in an isolated factory scene.
for existing in list(bpy.data.objects):
    bpy.data.objects.remove(existing, do_unlink=True)

collection = bpy.data.collections.new("Testarossa_Runtime_QA")
bpy.context.scene.collection.children.link(collection)
body = build_humanoid_blockout(
    bpy, "Testarossa_Runtime_Body", collection.name,
    height=1.72, shoulder_width=0.43, hip_width=0.37, voxel_size=0.045
)

assert body.type == "MESH", "generator did not return a mesh"
assert len(body.data.vertices) > 500, "mesh is unexpectedly sparse"
assert len(body.data.vertices) <= 250000, "vertex budget exceeded"
assert 1.55 <= body.dimensions.z <= 1.90, "body height outside expected range"
assert 0.75 <= body.dimensions.x <= 1.50, "arm span outside expected range"
assert body.dimensions.y > 0.12, "body depth unexpectedly small"

# Inventory connected mesh islands and their local-space bounds.
bm = bmesh.new()
bm.from_mesh(body.data)
remaining = set(bm.verts)
component_bounds = []
while remaining:
    seed = remaining.pop()
    stack = [seed]
    component = [seed]
    while stack:
        vertex = stack.pop()
        for edge in vertex.link_edges:
            other = edge.other_vert(vertex)
            if other in remaining:
                remaining.remove(other)
                stack.append(other)
                component.append(other)
    coords = [v.co for v in component]
    component_bounds.append({
        "vertices": len(component),
        "min": [round(float(min(v.co[i] for v in component)), 4) for i in range(3)],
        "max": [round(float(max(v.co[i] for v in component)), 4) for i in range(3)]
    })
bm.free()
components = len(component_bounds)

report = {
    "status": "DIAGNOSTIC",
    "blender": bpy.app.version_string,
    "object": body.name,
    "vertices": len(body.data.vertices),
    "polygons": len(body.data.polygons),
    "dimensions": [round(float(v), 4) for v in body.dimensions],
    "connected_components": components,
    "component_bounds": component_bounds,
    "collection": collection.name,
    "saved": False,
}
print("TESTAROSSA_HUMANOID_RUNTIME=" + json.dumps(report, sort_keys=True))
