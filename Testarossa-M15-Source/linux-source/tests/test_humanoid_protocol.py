import copy
import unittest
import uuid
from testarossa_intelligence.blender_protocol import validate_plan

class HumanoidProtocolTests(unittest.TestCase):
    def plan(self):
        return {
            "schema_version": 1, "plan_id": str(uuid.uuid4()),
            "project_slug": "testarossa_humanoid_blockout",
            "steps": [
                {"step_id":"s1","operation":"create_collection","args":{"name":"Testarossa"}},
                {"step_id":"s2","operation":"build_humanoid_blockout","args":{
                    "name":"Testarossa_Body_Blockout","collection":"Testarossa",
                    "height":1.72,"shoulder_width":0.43,"hip_width":0.37,"voxel_size":0.045}},
                {"step_id":"s3","operation":"save_project","args":{}}
            ]
        }

    def test_accepts_bounded_humanoid_operation(self):
        self.assertEqual(len(validate_plan(self.plan())["steps"]), 3)

    def test_rejects_unbounded_voxel_resolution(self):
        p=self.plan()
        p["steps"][1]["args"]["voxel_size"]=0.001
        with self.assertRaises(ValueError): validate_plan(p)

    def test_rejects_extra_generator_arguments(self):
        p=self.plan()
        p["steps"][1]["args"]["python"]="bpy.ops.object.delete()"
        with self.assertRaises(ValueError): validate_plan(p)

    def test_requires_declared_collection(self):
        p=self.plan()
        p["steps"][0]["args"]["name"]="Other"
        with self.assertRaises(ValueError): validate_plan(p)

if __name__ == "__main__":
    unittest.main()
