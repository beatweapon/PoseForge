"""Check that missing samples and penetration can never look like ideal grip."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ci"))
from grip_quality import score_skin_samples, compare_skin_candidates


def hand(gap, deep=0, close=None):
    row = {
        "sample_count": 10 if gap is not None else 0,
        "nearest_abs_gap_m": gap,
        "sampled_inside_over_2mm": deep,
        "sampled_within_5mm": int(gap is not None and gap <= 0.005)
        if close is None else close,
    }
    return {"fingers": {"thumb": dict(row), "index": dict(row)}}


class GripQualityTest(unittest.TestCase):
    def test_close_nonpenetrating_beats_distant(self):
        near = score_skin_samples({"hands": {"left": hand(0.003),
                                             "right": hand(0.003)}})
        far = score_skin_samples({"hands": {"left": hand(0.025),
                                            "right": hand(0.025)}})
        self.assertLess(near["score"], far["score"])
        self.assertTrue(near["passes_screening"])
        self.assertFalse(near["surface_contact_verified"])

    def test_penetration_has_penalty(self):
        safe = score_skin_samples({"hands": {"left": hand(0.004),
                                             "right": hand(0.004)}})
        deep = score_skin_samples({"hands": {"left": hand(0.001, deep=2),
                                             "right": hand(0.001, deep=2)}})
        self.assertGreater(deep["score"], safe["score"])
        self.assertFalse(deep["passes_screening"])

    def test_no_samples_are_unknown_not_contact(self):
        missing = score_skin_samples({"hands": {"left": hand(None),
                                                "right": hand(None)}})
        self.assertFalse(missing["proxy_eligible"])
        self.assertFalse(missing["passes_screening"])
        self.assertIsNone(compare_skin_candidates(
            [{"variant": "missing", "skin_quality": missing}]))

    def test_requires_two_hands(self):
        with self.assertRaises(ValueError):
            score_skin_samples({"hands": {"left": hand(0.001)}})


if __name__ == "__main__":
    unittest.main()
