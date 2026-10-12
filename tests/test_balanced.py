from pathlib import Path
import random
import unittest

from vampires.balanced import choose_balanced
from vampires.budget import SearchTimeout
from vampires.evaluation import evaluate
from vampires.model import Board, Cell, Species, load_map
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig, choose_turn, state_key
from vampires.strategy import evaluate_resources, portfolio_turns, resource_projection
from vampires.turns import Candidates, candidate_turns, fallback_turn

V, W = Species.VAMPIRES, Species.WEREWOLVES
ROOT = Path(__file__).resolve().parents[1]


class CountingClock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.calls


class BalancedTests(unittest.TestCase):
    def test_complete_values_match_sequential_reference_both_species(self):
        for seed in range(6):
            rng = random.Random(seed)
            points = rng.sample([(x, y) for x in range(3) for y in range(2)], 3)
            board = Board(2, 3, {points[0]: Cell(vampires=rng.randint(1, 3)),
                                 points[1]: Cell(werewolves=rng.randint(1, 3)),
                                 points[2]: Cell(humans=2)})
            for side in Species:
                with self.subTest(seed=seed, side=side):
                    config = SearchConfig(max_depth=2, preserve_dominance=False)
                    reference = choose_turn(board, side, time_budget=10, config=config, remaining_plies=2)
                    result = choose_balanced(board, side, time_budget=10, config=config, remaining_plies=2)
                    self.assertEqual(result.completed_depth, 2)
                    self.assertAlmostEqual(result.value, reference.value)

    def test_opponent_reply_avoids_the_exposed_trap(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        for side, row in ((V, 3), (W, 1)):
            result = choose_balanced(board, side, time_budget=10, config=SearchConfig(max_depth=2))
            self.assertEqual(result.moves, (Move(4, row, 4, 3, row),))
            self.assertEqual(result.root_started, 32)

    def test_expensive_first_root_cannot_starve_the_second(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=20), (1, 0): Cell(werewolves=20)})
        roots = ((Move(0, 0, 19, 1, 0),), (Move(0, 0, 20, 0, 1),))
        def generate(position, side, **kwargs):
            return Candidates(roots, True) if position is board else candidate_turns(position, side, **kwargs)
        result = choose_balanced(board, V, time_budget=10**6, expires_at=1200,
                                 clock=CountingClock(), generator=generate,
                                 config=SearchConfig(max_depth=2))
        self.assertTrue(result.timed_out)
        self.assertEqual(result.root_started, 2)
        self.assertGreater(result.root_updates, 2)
        validate_moves(board, V, result.moves)

    def test_expired_budget_has_legal_fallback_and_unknown_value(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        result = choose_balanced(board, V, time_budget=0)
        self.assertEqual(result.moves, fallback_turn(board, V))
        self.assertIsNone(result.value)
        self.assertEqual(result.root_started, 0)

    def test_interrupted_deeper_search_keeps_completed_result(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=2), (2, 1): Cell(werewolves=2)})
        clock = CountingClock()
        reference = choose_balanced(board, V, time_budget=10**9, clock=clock,
                                    config=SearchConfig(max_depth=2))
        result = choose_balanced(board, V, time_budget=10**9, expires_at=clock.calls + 5,
                                 clock=CountingClock(), config=SearchConfig(max_depth=3))
        self.assertEqual(result.completed_depth, 2)
        self.assertEqual(result.moves, reference.moves)
        self.assertEqual(result.value, reference.value)

    def test_unexpanded_probability_mass_has_conservative_bounds(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        result = choose_balanced(board, V, time_budget=10, config=SearchConfig(max_outcomes=1))
        self.assertIsNone(result.value)
        self.assertAlmostEqual(result.value_lower, -.5)
        self.assertAlmostEqual(result.value_upper, .5)

    def test_input_unchanged_and_ample_budget_reproducible(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(werewolves=2)})
        before = state_key(board)
        a = choose_balanced(board, V, time_budget=10)
        b = choose_balanced(board, V, time_budget=10)
        self.assertEqual(a.moves, b.moves)
        self.assertEqual(a.value, b.value)
        self.assertEqual(before, state_key(board))

    def test_invalid_inputs_are_rejected(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        for kwargs in ({"time_budget": -1}, {"time_budget": float("nan")},
                       {"expires_at": float("inf")}, {"remaining_plies": 0}):
            with self.assertRaises(ValueError):
                choose_balanced(board, V, **kwargs)


class StrategyTests(unittest.TestCase):
    def test_resource_race_counts_house_once_and_initiative_breaks_tie(self):
        board = Board(1, 5, {(0, 0): Cell(vampires=4), (2, 0): Cell(humans=4),
                             (4, 0): Cell(werewolves=4)})
        projected = resource_projection(board, V)
        self.assertEqual(projected[W], 4)
        self.assertAlmostEqual(projected[V], 4 + 4 / 1.06)
        self.assertGreater(evaluate_resources(board, V, V), evaluate_resources(board, V, W))

    def test_unaffordable_and_overflow_houses_are_not_credited(self):
        for count, humans in ((3, 4), (200, 100)):
            board = Board(1, 3, {(0, 0): Cell(vampires=count), (1, 0): Cell(humans=humans),
                                 (2, 0): Cell(werewolves=1)})
            self.assertEqual(resource_projection(board, V), {V: float(count), W: 1.})

    def test_apparent_lead_can_hide_losing_resource_allocation(self):
        board = Board(1, 12, {(0, 0): Cell(vampires=8), (8, 0): Cell(werewolves=4),
                              (9, 0): Cell(humans=2), (10, 0): Cell(humans=1), (11, 0): Cell(humans=2)})
        self.assertGreater(evaluate(board, V, W), 0)
        self.assertLess(evaluate_resources(board, V, W), 0)

    def test_resource_evaluation_is_bounded_and_antisymmetric(self):
        for name in ("thetrap", "testmap2"):
            board = load_map(ROOT / "maps" / (name + ".xml"))
            for side in Species:
                a, b = evaluate_resources(board, V, side), evaluate_resources(board, W, side)
                self.assertLess(abs(a), 1)
                self.assertAlmostEqual(a, -b)

    def test_complete_small_candidate_sets_are_preserved(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        self.assertEqual(portfolio_turns(board, V), candidate_turns(board, V))

    def test_portfolio_turns_are_legal_and_avoid_shared_battles(self):
        board = Board(3, 4, {(0, 0): Cell(vampires=3), (0, 2): Cell(vampires=4),
                             (3, 1): Cell(werewolves=5), (1, 1): Cell(humans=3)})
        before = state_key(board)
        result = portfolio_turns(board, V, limit=8)
        self.assertEqual(len(result.turns), 8)
        self.assertEqual(len(set(result.turns)), 8)
        for turn in result.turns:
            validate_moves(board, V, turn)
            contested = [m.target for m in turn if board.at(m.target).humans or board.at(m.target).werewolves]
            self.assertEqual(len(contested), len(set(contested)))
        self.assertEqual(state_key(board), before)


if __name__ == "__main__":
    unittest.main()
