import json
import tempfile
import unittest
from pathlib import Path
from poseforge.schema import load_config


SAMPLE = {
    "model": "humanoid",
    "pose": {"action": "pinch", "hand": "right", "object": "card", "objectPoint": "top_right_corner", "fingers": ["thumb", "index"]},
    "cameras": ["front", "back"],
    "render": {"width": 128, "height": 128, "transparent": True},
    "output": "output",
}


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "pose.json"

    def load(self, value):
        self.file.write_text(json.dumps(value), encoding="utf-8")
        return load_config(self.file)

    def test_valid(self):
        self.assertEqual(self.load(SAMPLE)["cameras"], ["front", "back"])

    def test_invalid_action(self):
        bad = json.loads(json.dumps(SAMPLE))
        bad["pose"]["action"] = "grab"
        with self.assertRaises(ValueError):
            self.load(bad)

    def test_duplicate_camera(self):
        bad = json.loads(json.dumps(SAMPLE))
        bad["cameras"] = ["front", "front"]
        with self.assertRaises(ValueError):
            self.load(bad)

    def test_width_bool_rejected(self):
        bad = json.loads(json.dumps(SAMPLE))
        bad["render"]["width"] = True
        with self.assertRaises(ValueError):
            self.load(bad)


if __name__ == "__main__":
    unittest.main()
