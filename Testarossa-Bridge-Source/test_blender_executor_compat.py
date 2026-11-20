import unittest
from blender_executor import resolve_render_engine

class RenderEngineCompatibilityTests(unittest.TestCase):
    def test_blender_53_eevee_alias(self):
        self.assertEqual(resolve_render_engine("BLENDER_EEVEE_NEXT", {"BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"}), "BLENDER_EEVEE")
    def test_newer_blender_exact_identifier(self):
        self.assertEqual(resolve_render_engine("BLENDER_EEVEE_NEXT", {"BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES"}), "BLENDER_EEVEE_NEXT")
    def test_other_engine_exact_identifier(self):
        self.assertEqual(resolve_render_engine("CYCLES", {"BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"}), "CYCLES")
    def test_unknown_engine_rejected(self):
        with self.assertRaises(ValueError):
            resolve_render_engine("BLENDER_GAME", {"BLENDER_EEVEE", "CYCLES"})

if __name__ == "__main__":
    unittest.main(verbosity=2)
