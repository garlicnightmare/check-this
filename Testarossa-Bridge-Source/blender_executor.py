#!/usr/bin/env python3
"""Blender-side interpreter for the closed Testarossa plan vocabulary."""
from __future__ import annotations
import json, math, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out: raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("non-finite JSON")))


def _link_object(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def resolve_render_engine(requested, available):
    """Resolve protocol engine identifiers across Blender API generations.

    The protocol uses Blender 4.x+'s BLENDER_EEVEE_NEXT identifier. Blender
    5.3 still exposes the same engine as BLENDER_EEVEE. Prefer the exact
    identifier when available, otherwise use this single explicit alias.
    """
    available = set(available)
    if requested in available:
        return requested
    if requested == "BLENDER_EEVEE_NEXT" and "BLENDER_EEVEE" in available:
        return "BLENDER_EEVEE"
    raise ValueError(f"render engine {requested!r} is unavailable in this Blender build")


def execute(plan, project_path):
    import bpy
    import blender_protocol
    blender_protocol.validate_plan(plan)
    # Factory-startup is mandatory at the process layer; clear its default scene too.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Keep Blender's factory default collection as a valid active context for mesh operators.
    # Created objects are immediately moved into their explicitly requested collections.
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    scene = bpy.context.scene
    collections = {}
    objects = {}
    materials = {}
    executed = []
    primitive_ops = {
        "CUBE": bpy.ops.mesh.primitive_cube_add,
        "UV_SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
        "ICO_SPHERE": bpy.ops.mesh.primitive_ico_sphere_add,
        "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
        "CONE": bpy.ops.mesh.primitive_cone_add,
        "TORUS": bpy.ops.mesh.primitive_torus_add,
        "PLANE": bpy.ops.mesh.primitive_plane_add,
    }
    for step in plan["steps"]:
        op, a = step["operation"], step["args"]
        if op == "create_collection":
            c = bpy.data.collections.new(a["name"])
            scene.collection.children.link(c)
            collections[a["name"]] = c
        elif op == "add_mesh":
            primitive_ops[a["primitive"]](location=a["location"], rotation=a["rotation"])
            obj = bpy.context.object
            obj.name = a["name"]
            _link_object(obj, collections[a["collection"]])
            obj.scale = a["scale"]
            objects[a["name"]] = obj
        elif op == "build_humanoid_blockout":
            from testarossa_humanoid import build_humanoid_blockout
            obj = build_humanoid_blockout(
                bpy, a["name"], a["collection"], a["height"],
                a["shoulder_width"], a["hip_width"], a["voxel_size"]
            )
            objects[a["name"]] = obj
        elif op == "create_material":
            mat = bpy.data.materials.new(a["name"])
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf is None: raise RuntimeError("Principled BSDF unavailable")
            bsdf.inputs["Base Color"].default_value = a["base_color"]
            bsdf.inputs["Metallic"].default_value = a["metallic"]
            bsdf.inputs["Roughness"].default_value = a["roughness"]
            materials[a["name"]] = mat
        elif op == "assign_material":
            objects[a["object"]].data.materials.append(materials[a["material"]])
        elif op == "set_transform":
            obj = objects[a["object"]]
            obj.location = a["location"]
            obj.rotation_euler = a["rotation"]
            obj.scale = a["scale"]
        elif op == "add_camera":
            data = bpy.data.cameras.new(a["name"])
            data.lens = a["lens"]
            obj = bpy.data.objects.new(a["name"], data)
            collections[a["collection"]].objects.link(obj)
            obj.location = a["location"]
            obj.rotation_euler = a["rotation"]
            objects[a["name"]] = obj
            scene.camera = obj
        elif op == "add_light":
            data = bpy.data.lights.new(a["name"], type=a["kind"])
            data.color = a["color"]
            data.energy = a["energy"]
            data.shape = "DISK" if a["kind"] == "AREA" else data.shape
            if a["kind"] == "AREA": data.size = a["size"]
            elif a["kind"] == "POINT": data.shadow_soft_size = a["size"]
            obj = bpy.data.objects.new(a["name"], data)
            collections[a["collection"]].objects.link(obj)
            obj.location = a["location"]
            objects[a["name"]] = obj
        elif op == "set_render":
            engine_items = scene.render.bl_rna.properties["engine"].enum_items
            available_engines = [item.identifier for item in engine_items]
            scene.render.engine = resolve_render_engine(a["engine"], available_engines)
            scene.render.resolution_x = a["resolution_x"]
            scene.render.resolution_y = a["resolution_y"]
            scene.render.resolution_percentage = 100
            scene.render.fps = a["fps"]
        elif op == "save_project":
            # Destination is injected by the trusted bridge, never supplied by the plan.
            bpy.ops.wm.save_as_mainfile(filepath=str(project_path))
        else:
            raise RuntimeError("operation escaped protocol allowlist")
        executed.append({"step_id": step["step_id"], "operation": op})
    return {"ok": True, "plan_id": plan["plan_id"], "project_slug": plan["project_slug"],
            "executed_steps": executed, "object_count": len(bpy.data.objects),
            "collection_count": len(bpy.data.collections), "material_count": len(bpy.data.materials),
            "blender_version": bpy.app.version_string}


def main():
    if "--" not in sys.argv: raise SystemExit("missing Blender argument separator")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 3: raise SystemExit("expected plan, result, and trusted project paths")
    plan_path, result_path, project_path = args
    plan = _load(plan_path)
    result = execute(plan, project_path)
    Path(result_path).write_text(json.dumps(result, allow_nan=False), encoding="utf-8")

if __name__ == "__main__":
    main()
