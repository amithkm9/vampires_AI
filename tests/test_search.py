from fractions import Fraction
from pathlib import Path
import unittest

from vampires.evaluation import evaluate, terminal_value
from vampires.model import Board, Cell, Species, load_map
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig, choose_turn, state_key
from vampires.simulation import single_move_outcomes
from vampires.turns import NoLegalMove, candidate_turns, fallback_turn

ROOT = Path(__file__).resolve().parents[1]
V, W = Species.VAMPIRES, Species.WEREWOLVES


class CountingClock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return float(self.calls)


class EvaluationTests(unittest.TestCase):
    def test_terminal_scores_and_explicit_both_extinct_convention(self):
        self.assertEqual(terminal_value(Board(1, 2), V), 0)
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        self.assertEqual(terminal_value(board, V), 1)
        self.assertEqual(terminal_value(board, W), -1)

    def test_nonterminal_is_bounded_and_perspective_antisymmetric(self):
        for name in ("thetrap", "testmap2"):
            board = load_map(ROOT / "maps" / (name + ".xml"))
            for side in Species:
                a, b = evaluate(board, V, side), evaluate(board, W, side)
                self.assertLess(abs(a), 1)
                self.assertAlmostEqual(a, -b)

    def test_current_population_must_satisfy_human_threshold(self):
        risky = Board(1, 5, {(0, 0): Cell(vampires=19), (1, 0): Cell(humans=20),
                            (4, 0): Cell(werewolves=19)})
        certain = Board(1, 5, {(0, 0): Cell(vampires=20), (1, 0): Cell(humans=20),
                              (4, 0): Cell(werewolves=19)})
        self.assertGreater(evaluate(certain, V, V), evaluate(risky, V, V))

    def test_side_to_move_changes_equal_arrival_race(self):
        board = Board(1, 5, {(0, 0): Cell(vampires=4), (2, 0): Cell(humans=4),
                             (4, 0): Cell(werewolves=4)})
        self.assertGreater(evaluate(board, V, V), evaluate(board, V, W))


class SearchTests(unittest.TestCase):
    def test_opponent_lookahead_changes_exposed_trap_choice(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        greedy = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=1))
        aware = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=2))
        self.assertEqual(greedy.moves, (Move(4, 3, 4, 3, 2),))
        self.assertEqual(aware.moves, (Move(4, 3, 4, 3, 3),))
        self.assertEqual(aware.completed_depth, 2)
        self.assertEqual(aware.selective_nodes, 0)
        self.assertEqual(aware.unsupported_actions, 0)
        # The other species also selects its safe approach.
        other = choose_turn(board, W, time_budget=10, config=SearchConfig(max_depth=2))
        self.assertEqual(other.moves, (Move(4, 1, 4, 3, 1),))

    def test_complete_two_ply_search_matches_independent_nested_reference(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        def leaf(position):
            result = terminal_value(position, V)
            return result if result is not None else evaluate(position, V, V)
        values = {}
        for turn in candidate_turns(board, V).turns:
            expected = 0
            for outcome in single_move_outcomes(board, V, turn[0]):
                terminal = terminal_value(outcome.board, V)
                if terminal is not None:
                    reply_value = terminal
                else:
                    reply_value = min(sum(float(reply_outcome.probability) * leaf(reply_outcome.board)
                                          for reply_outcome in single_move_outcomes(outcome.board, W, reply[0]))
                                      for reply in candidate_turns(outcome.board, W).turns)
                expected += float(outcome.probability) * reply_value
            values[turn] = expected
        result = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=2))
        self.assertAlmostEqual(result.value, max(values.values()))
        self.assertAlmostEqual(result.value, values[result.moves])

    def test_chance_is_expectation_not_adversarial_selection(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        result = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=2))
        # 1/4 win, 1/4 loss, 1/2 both extinct under the explicit neutral convention.
        self.assertEqual(result.value, 0)
        self.assertEqual(result.chance_outcomes, 3)
        self.assertEqual(result.completed_depth, 2)

    def test_expired_budget_returns_immediate_legal_fallback(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        result = choose_turn(board, V, time_budget=0)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.moves, fallback_turn(board, V))
        self.assertIsNone(result.value)
        self.assertEqual(result.completed_depth, 0)
        validate_moves(board, V, result.moves)

    def test_timeout_during_deeper_iteration_preserves_completed_shallower_result(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=2), (2, 1): Cell(werewolves=2)})
        reference_clock = CountingClock()
        reference = choose_turn(board, V, time_budget=10**9, clock=reference_clock,
                                config=SearchConfig(max_depth=2))
        interrupted = choose_turn(board, V, time_budget=10**9, expires_at=reference_clock.calls + 3,
                                  clock=CountingClock(), config=SearchConfig(max_depth=3))
        self.assertTrue(interrupted.timed_out)
        self.assertEqual(interrupted.completed_depth, 2)
        self.assertEqual(interrupted.moves, reference.moves)
        self.assertEqual(interrupted.value, reference.value)

    def test_partial_chance_calculation_never_becomes_a_finished_score(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=2), (1, 0): Cell(werewolves=2)})
        def interrupt(position, perspective, side, *, check=None):
            from vampires.budget import SearchTimeout
            raise SearchTimeout
        # A partial attacker leaves survivors at the source, causing a nonterminal
        # outcome; stop inside that evaluation rather than after the root action.
        result = choose_turn(board, V, time_budget=10, evaluator=interrupt,
                             config=SearchConfig(max_depth=2))
        self.assertTrue(result.timed_out)
        validate_moves(board, V, result.moves)
        self.assertEqual(result.completed_depth, 0)

    def test_large_distribution_retains_unvisited_mass_in_value_bounds(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        result = choose_turn(board, V, time_budget=10, config=SearchConfig(max_outcomes=1))
        self.assertEqual(result.unsupported_actions, 0)
        self.assertGreater(result.bounded_actions, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.completed_depth, 3)
        self.assertAlmostEqual(result.value_lower, -.5)
        self.assertAlmostEqual(result.value_upper, .5)
        validate_moves(board, V, result.moves)

    def test_input_is_not_mutated_and_repeated_search_is_deterministic(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=2), (2, 1): Cell(werewolves=2), (1, 0): Cell(humans=2)})
        original = state_key(board)
        a = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=2))
        b = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=2))
        self.assertEqual(a.moves, b.moves)
        self.assertEqual(a.value, b.value)
        self.assertEqual(state_key(board), original)

    def test_no_legal_move_and_bad_configuration_are_explicit(self):
        with self.assertRaises(NoLegalMove):
            choose_turn(Board(1, 1, {(0, 0): Cell(vampires=1)}), V)
        for kwargs in ({"max_depth": 0}, {"candidates": True}, {"max_outcomes": 0}, {"max_depth": 9}):
            with self.assertRaises(ValueError):
                SearchConfig(**kwargs)
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                choose_turn(board, V, time_budget=value)


if __name__ == "__main__":
    unittest.main()
