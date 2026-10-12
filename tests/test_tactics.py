from fractions import Fraction
import unittest

from tools.check_tactics import audit, positions
from vampires.model import Species


class CoverageAuditTests(unittest.TestCase):
    def test_omitted_shared_capture_is_lost_win_under_declared_aggregation(self):
        board, horizon = positions()["shared_capture"]
        result = audit(board, horizon)
        self.assertTrue(result["complete"])
        self.assertEqual(Fraction(result["root_omission_regret"]["exact"]), Fraction(1, 2))
        self.assertEqual(result["missing_optimal_root_reason"], "unverified_shared_target")
        self.assertIsNone(result["missing_reply_example"])

    def test_small_complete_tree_has_no_pruning_regret_for_either_species(self):
        board, horizon = positions()["preserve_draw"]
        for species in Species:
            result = audit(board, horizon, perspective=species)
            self.assertEqual(result["decision_regret"]["exact"], "0")
            self.assertEqual(result["largest_reply_optimism"]["exact"], "0")
            self.assertEqual(result["legal_root_turns"], result["retained_root_turns"])


if __name__ == "__main__":
    unittest.main()
