import copy
import json
import tempfile
import unittest
from pathlib import Path
from poseforge.schema import load_config
from poseforge.rig import classify_bones, semantic_bones, mpfb_skin_groups

SAMPLE = {"model": {"type": "mpfb", "source": "human.blend"},
          "pose": {"action": "neutral"}, "cameras": ["front", "back"],
          "render": {"width": 128, "height": 128, "transparent": True},
          "output": "output"}

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "pose.json"
        (self.path.parent / "human.blend").touch()

    def load(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return load_config(self.path)

    def test_valid(self):
        self.assertEqual(self.load(SAMPLE)["cameras"], ["front", "back"])

    def test_missing_model(self):
        data = copy.deepcopy(SAMPLE)
        data["model"]["source"] = "missing.blend"
        with self.assertRaises(ValueError):
            self.load(data)

    def test_duplicate_camera(self):
        data = copy.deepcopy(SAMPLE)
        data["cameras"] = ["front", "front"]
        with self.assertRaises(ValueError):
            self.load(data)

    def test_bad_width(self):
        data = copy.deepcopy(SAMPLE)
        data["render"]["width"] = True
        with self.assertRaises(ValueError):
            self.load(data)

    def test_unsupported_action(self):
        data = copy.deepcopy(SAMPLE)
        data["pose"]["action"] = "grab"
        with self.assertRaises(ValueError):
            self.load(data)

    def test_reach_target(self):
        import copy
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "reach", "targets": [
            {"effector": "right_index", "position": [-0.48, -0.36, 0.94]}]}
        self.assertEqual(self.load(data)["pose"]["targets"][0]["effector"], "right_index")

    def test_reach_invalid_target(self):
        import copy
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "reach", "targets": [
            {"effector": "right_index", "position": [True, 0, 1]}]}
        with self.assertRaises(ValueError):
            self.load(data)

    def test_reach_hand_valid(self):
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "reach_hand", "hand": "right",
                        "target_position": [-0.3, -0.2, 1.05]}
        self.assertEqual(self.load(data)["pose"]["hand"], "right")

    def test_reach_hand_invalid(self):
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "reach_hand", "hand": "left",
                        "target_position": [True, 0, 1]}
        with self.assertRaises(ValueError):
            self.load(data)

    def test_grasp_card_valid(self):
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "grasp_card", "hand": "right",
                        "card": {"position": [-0.47, -0.35, 0.87],
                                 "size": [0.18, 0.006, 0.25]}}
        self.assertEqual(self.load(data)["pose"]["action"], "grasp_card")

    def test_grasp_card_invalid(self):
        data = copy.deepcopy(SAMPLE)
        data["pose"] = {"action": "grasp_card", "hand": "right",
                        "card": {"position": [True, 0, 1],
                                 "size": [0.18, 0.006, 0.25]}}
        with self.assertRaises(ValueError):
            self.load(data)

    def test_mpfb_skin_groups(self):
        self.assertIn("joint-r-finger-1-3", mpfb_skin_groups("right", "thumb"))
        self.assertIn("joint-l-finger-2-4", mpfb_skin_groups("left", "index"))
        with self.assertRaises(ValueError):
            mpfb_skin_groups("right", "elbow")

    def test_mpfb_fingers(self):
        bones = ["finger1-1.R", "finger2-3.L", "upperleg01.R", "wrist.R"]
        groups = classify_bones(bones)
        self.assertEqual(groups["thumb"], ["finger1-1.R"])
        self.assertEqual(groups["index"], ["finger2-3.L"])
        self.assertEqual(groups["thigh"], ["upperleg01.R"])
        self.assertEqual(semantic_bones(bones)["right_thumb_1"], "finger1-1.R")

if __name__ == "__main__":
    unittest.main()
