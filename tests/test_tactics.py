from fractions import Fraction
import unittest

from tools.check_tactics import audit, positions
from vampires.model import Species
from vampires.rules import Move, validate_moves
from vampires.turns import candidate_turns


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

    def test_protection_restores_cutoff_gamble_under_small_candidate_budget(self):
        board, horizon = positions()["trailing_gamble"]
        before = audit(board, horizon, limit=8)
        after = audit(board, horizon, limit=8, protect_tactics=True)
        self.assertGreater(Fraction(before["decision_regret"]["exact"]), 0)
        self.assertEqual(after["decision_regret"]["exact"], "0")

    def test_protection_restores_dangerous_opponent_reply_under_small_budget(self):
        board, horizon = positions()["shared_attack"]
        before = audit(board, horizon, limit=8)
        after = audit(board, horizon, limit=8, protect_tactics=True)
        self.assertEqual(before["largest_reply_optimism"]["exact"], "21981/65536")
        self.assertEqual(after["largest_reply_optimism"]["exact"], "0")
        # Missing shared-target root combat remains conditional and unresolved.
        self.assertEqual(after["decision_regret"], before["decision_regret"])

    def test_protected_candidates_still_obey_budget_and_rules(self):
        for board, _ in positions().values():
            for species in Species:
                for limit in (1, 8, 64):
                    result = candidate_turns(board, species, limit=limit, protect_tactics=True)
                    self.assertLessEqual(len(result.turns), limit)
                    self.assertEqual(len(result.turns), len(set(result.turns)))
                    for turn in result.turns:
                        validate_moves(board, species, turn)

    def test_protected_search_switch_reaches_the_generator(self):
        from vampires.search import SearchConfig, choose_turn
        board, horizon = positions()["trailing_gamble"]
        result = choose_turn(board, Species.VAMPIRES, remaining_plies=horizon, time_budget=10,
                             config=SearchConfig(candidates=8, protect_tactics=True))
        self.assertEqual(result.moves, (Move(1, 0, 2, 0, 0),))


if __name__ == "__main__":
    unittest.main()
