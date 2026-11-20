import copy
import unittest
from computer_observer import validate_result, ALLOWED_OPERATIONS


def valid_object():
    return {
        "name": "Cube", "type": "MESH", "collections": ["Collection"],
        "location": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0], "dimensions": [2.0, 2.0, 2.0],
        "parent": None, "parent_type": "OBJECT",
        "hidden_viewport": False, "hidden_render": False,
        "modifiers": [],
        "materials": ["Material"],
        "constraints": [],
        "animation": {
            "action": None, "keyframes": None,
            "keyframes_available": False, "layers": 0, "slots": 0
        },
        "geometry": {"vertices": 8, "edges": 12, "polygons": 6}
    }


def valid_scene():
    return {
        "schema_version": 1,
        "captured_at": 1795164368.95,
        "blender_version": "5.3.0",
        "scene": {
            "name": "Scene", "frame_current": 1, "frame_start": 1,
            "frame_end": 250, "render_engine": "BLENDER_EEVEE",
            "resolution_x": 1920, "resolution_y": 1080,
            "resolution_percentage": 100, "camera": "Camera",
            "active_object": "Cube"
        },
        "summary": {
            "object_count": 1, "object_type_counts": {"MESH": 1},
            "objects_truncated": False, "mesh_count": 1,
            "armature_count": 0, "camera_count": 0, "light_count": 0
        },
        "objects": [valid_object()],
        "read_only": True
    }


def valid_project():
    obj = valid_object()
    global_obj = copy.deepcopy(obj)
    global_obj["scenes"] = ["Scene"]
    return {
        "schema_version": 3,
        "captured_at": 1795164368.95,
        "blender_version": "5.3.0",
        "project": {
            "filepath": "", "filename": None,
            "is_saved": False, "is_dirty": False,
            "scene_count": 1, "collection_count": 1,
            "material_count": 1, "action_count": 0, "object_count": 1
        },
        "scenes": [{
            "name": "Scene", "frame_current": 1, "frame_start": 1,
            "frame_end": 250, "render_engine": "BLENDER_EEVEE",
            "resolution_x": 1920, "resolution_y": 1080,
            "resolution_percentage": 100, "camera": "Camera",
            "active_object": "Cube", "object_count": 1,
            "objects": [copy.deepcopy(obj)], "objects_truncated": False
        }],
        "scenes_truncated": False,
        "collections": [{
            "name": "Collection", "parent": None, "children": [],
            "objects": ["Cube"], "objects_truncated": False
        }],
        "collections_truncated": False,
        "materials": [{"name": "Material", "users": 1, "use_nodes": True}],
        "materials_truncated": False,
        "actions": [],
        "actions_truncated": False,
        "objects": [global_obj],
        "objects_truncated": False,
        "summary": {
            "scene_count": 1, "collection_count": 1,
            "material_count": 1, "action_count": 0,
            "object_count": 1, "mesh_count": 1,
            "armature_count": 0, "camera_count": 0,
            "light_count": 0, "objects_truncated": False
        },
        "read_only": True
    }


class ObserverValidationTests(unittest.TestCase):
    def test_allowed_operations(self):
        self.assertEqual(ALLOWED_OPERATIONS, {
            "workstation", "blender_status",
            "blender_scene_snapshot", "blender_project_snapshot"
        })

    def test_valid_workstation(self):
        data = {
            "hostname": "DESKTOP", "os": "Windows",
            "architecture": "AMD64", "processor": "CPU", "python": "3.13.0"
        }
        self.assertEqual(validate_result("workstation", data), data)

    def test_rejects_extra_workstation_fields(self):
        data = {
            "hostname": "DESKTOP", "os": "Windows",
            "architecture": "AMD64", "processor": "CPU",
            "python": "3.13.0", "extra": "unexpected"
        }
        with self.assertRaises(ValueError):
            validate_result("workstation", data)

    def test_valid_blender_status(self):
        data = {
            "installed": True, "executable": r"D:\blender\blender.exe",
            "version": "Blender 5.3.0", "version_error": None, "running": True
        }
        self.assertEqual(validate_result("blender_status", data), data)

    def test_rejects_non_boolean_blender_flags(self):
        data = {
            "installed": "true", "executable": r"D:\blender\blender.exe",
            "version": "Blender", "version_error": None, "running": False
        }
        with self.assertRaises(ValueError):
            validate_result("blender_status", data)

    def test_rejects_unknown_operation(self):
        with self.assertRaises(ValueError):
            validate_result("execute_command", {})

    def test_rejects_wrong_result_type(self):
        with self.assertRaises(ValueError):
            validate_result("workstation", [])

    def test_valid_blender_scene(self):
        data = valid_scene()
        self.assertEqual(validate_result("blender_scene_snapshot", data), data)

    def test_scene_accepts_constraints_and_blender_53_animation(self):
        data = valid_scene()
        data["objects"][0]["constraints"] = [{
            "name": "Track", "type": "TRACK_TO", "target": "Camera"
        }]
        data["objects"][0]["animation"] = {
            "action": "Walk", "keyframes": 24,
            "keyframes_available": True, "layers": 1, "slots": 1
        }
        self.assertEqual(validate_result("blender_scene_snapshot", data), data)

    def test_rejects_scene_not_read_only(self):
        data = valid_scene()
        data["read_only"] = False
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_rejects_unknown_scene_fields(self):
        data = valid_scene()
        data["scene"]["execute"] = "anything"
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_rejects_non_finite_transform(self):
        data = valid_scene()
        data["objects"][0]["location"][0] = float("nan")
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_rejects_invalid_mesh_geometry(self):
        data = valid_scene()
        data["objects"][0]["geometry"]["vertices"] = -1
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_rejects_duplicate_scene_object_names(self):
        data = valid_scene()
        data["summary"]["object_count"] = 2
        data["objects"].append(copy.deepcopy(data["objects"][0]))
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_rejects_scene_object_overflow(self):
        data = valid_scene()
        data["objects"] = [data["objects"][0]] * 501
        with self.assertRaises(ValueError):
            validate_result("blender_scene_snapshot", data)

    def test_valid_project_snapshot(self):
        data = valid_project()
        self.assertEqual(validate_result("blender_project_snapshot", data), data)

    def test_project_requires_read_only(self):
        data = valid_project()
        data["read_only"] = False
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_wrong_schema(self):
        data = valid_project()
        data["schema_version"] = 2
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_unknown_top_level_field(self):
        data = valid_project()
        data["execute"] = True
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_non_finite_timestamp(self):
        data = valid_project()
        data["captured_at"] = float("inf")
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_invalid_action_metadata(self):
        data = valid_project()
        data["actions"] = [{
            "name": "Walk", "users": 1, "layers": 1, "slots": 1,
            "keyframes": None, "keyframes_available": True
        }]
        data["project"]["action_count"] = 1
        data["summary"]["action_count"] = 1
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_inconsistent_counts(self):
        data = valid_project()
        data["summary"]["object_count"] = 9
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_bad_constraint(self):
        data = valid_project()
        data["objects"][0]["constraints"] = [{"name": "Bad"}]
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)

    def test_project_rejects_non_finite_transform(self):
        data = valid_project()
        data["objects"][0]["location"][1] = float("nan")
        with self.assertRaises(ValueError):
            validate_result("blender_project_snapshot", data)


if __name__ == "__main__":
    unittest.main()
