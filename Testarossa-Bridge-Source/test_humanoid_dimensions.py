import unittest
from testarossa_humanoid import validate_dimensions

class HumanoidDimensionTests(unittest.TestCase):
    def test_default_dimensions(self):
        self.assertEqual(validate_dimensions(1.72, 0.43, 0.37, 0.045),
                         (1.72, 0.43, 0.37, 0.045))

    def test_rejects_boolean_dimensions(self):
        with self.assertRaises(ValueError):
            validate_dimensions(True, 0.43, 0.37, 0.045)

    def test_rejects_height_outside_budget(self):
        with self.assertRaises(ValueError):
            validate_dimensions(3.0, 0.43, 0.37, 0.045)

    def test_rejects_extreme_resolution(self):
        with self.assertRaises(ValueError):
            validate_dimensions(1.72, 0.43, 0.37, 0.001)

if __name__ == "__main__":
    unittest.main()
