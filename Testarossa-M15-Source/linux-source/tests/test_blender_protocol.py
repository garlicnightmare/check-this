import copy
import unittest
import uuid

from testarossa_intelligence.blender_protocol import (
    validate_plan, summarize_plan, SCHEMAS
)

def valid_plan():
    return {
        "schema_version": 1,
        "plan_id": str(uuid.uuid4()),
        "project_slug": "testarossa_first_build",
        "steps": [
            {"step_id": "s1", "operation": "create_collection",
             "args": {"name": "Testarossa"}},
            {"step_id": "s2", "operation": "add_mesh",
             "args": {"name": "Torso_Blockout", "primitive": "UV_SPHERE",
                      "collection": "Testarossa", "location": [0, 0, 1],
                      "rotation": [0, 0, 0], "scale": [0.45, 0.3, 0.7]}},
            {"step_id": "s3", "operation": "create_material",
             "args": {"name": "Skin_Base", "base_color": [0.7, 0.45, 0.35, 1],
                      "metallic": 0, "roughness": 0.65}},
            {"step_id": "s4", "operation": "assign_material",
             "args": {"object": "Torso_Blockout", "material": "Skin_Base"}},
            {"step_id": "s5", "operation": "set_render",
             "args": {"engine": "BLENDER_EEVEE_NEXT",
                      "resolution_x": 1920, "resolution_y": 1080, "fps": 60}},
            {"step_id": "s6", "operation": "save_project", "args": {}}
        ]
    }

class ProtocolTests(unittest.TestCase):
    def rejects(self, mutate):
        plan = valid_plan()
        mutate(plan)
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_valid_plan(self):
        self.assertEqual(len(validate_plan(valid_plan())["steps"]), 6)

    def test_preview(self):
        preview = summarize_plan(valid_plan())
        self.assertFalse(preview["arbitrary_python"])
        self.assertFalse(preview["current_blender_scene_access"])

    def test_no_script_operations(self):
        for forbidden in ("python", "execute", "delete_object", "run_shell"):
            self.assertNotIn(forbidden, SCHEMAS)

    def test_extra_plan_field(self):
        self.rejects(lambda p: p.update(script="import bpy"))

    def test_bad_uuid(self):
        self.rejects(lambda p: p.update(plan_id="not-a-uuid"))

    def test_bad_slug(self):
        self.rejects(lambda p: p.update(project_slug="../outside"))

    def test_save_path_rejected(self):
        self.rejects(lambda p: p["steps"][-1]["args"].update(path="C:/outside"))

    def test_unknown_operation(self):
        self.rejects(lambda p: p["steps"][1].update(operation="execute_python"))

    def test_extra_nested_argument(self):
        self.rejects(lambda p: p["steps"][1]["args"].update(python="bpy.ops.object.delete()"))

    def test_boolean_number_rejected(self):
        self.rejects(lambda p: p["steps"][1]["args"].update(location=[True, 0, 1]))

    def test_nan_rejected(self):
        self.rejects(lambda p: p["steps"][1]["args"].update(location=[float("nan"), 0, 1]))

    def test_zero_scale_rejected(self):
        self.rejects(lambda p: p["steps"][1]["args"].update(scale=[0, 1, 1]))

    def test_unknown_primitive(self):
        self.rejects(lambda p: p["steps"][1]["args"].update(primitive="ARBITRARY"))

    def test_missing_collection(self):
        self.rejects(lambda p: p["steps"].pop(0))

    def test_duplicate_object(self):
        def mutate(p):
            duplicate = copy.deepcopy(p["steps"][1])
            duplicate["step_id"] = "s7"
            p["steps"].insert(-1, duplicate)
        self.rejects(mutate)

    def test_unknown_material(self):
        self.rejects(lambda p: p["steps"][3]["args"].update(material="Missing"))

    def test_unknown_object_transform(self):
        def mutate(p):
            p["steps"].insert(-1, {
                "step_id": "s7", "operation": "set_transform",
                "args": {"object": "Missing", "location": [0,0,0],
                         "rotation": [0,0,0], "scale": [1,1,1]}
            })
        self.rejects(mutate)

    def test_save_must_be_last(self):
        def mutate(p):
            p["steps"].append({
                "step_id": "s7", "operation": "create_collection",
                "args": {"name": "Late"}
            })
        self.rejects(mutate)

    def test_save_required(self):
        self.rejects(lambda p: p["steps"].pop())

    def test_duplicate_collection(self):
        def mutate(p):
            p["steps"].insert(1, {
                "step_id": "s7", "operation": "create_collection",
                "args": {"name": "Testarossa"}
            })
        self.rejects(mutate)

    def test_duplicate_material(self):
        def mutate(p):
            duplicate = copy.deepcopy(p["steps"][2])
            duplicate["step_id"] = "s7"
            p["steps"].insert(3, duplicate)
        self.rejects(mutate)

    def test_bad_resolution(self):
        self.rejects(lambda p: p["steps"][4]["args"].update(resolution_x=1))

    def test_bad_light_type(self):
        def mutate(p):
            p["steps"].insert(-1, {
                "step_id": "s7", "operation": "add_light",
                "args": {"name": "Key", "collection": "Testarossa",
                         "kind": "EXECUTE", "location": [0,0,0],
                         "color": [1,1,1], "energy": 100, "size": 1}
            })
        self.rejects(mutate)

    def test_too_many_steps(self):
        self.rejects(lambda p: p.update(steps=p["steps"] * 11))

    def test_bad_step_id(self):
        self.rejects(lambda p: p["steps"][1].update(step_id="bad id"))

    def test_duplicate_step_id(self):
        self.rejects(lambda p: p["steps"][2].update(step_id="s2"))

if __name__ == "__main__":
    unittest.main()