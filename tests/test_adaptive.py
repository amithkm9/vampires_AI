"""Exact values and interrupted-depth guarantees for optional work reuse."""

from pathlib import Path
import unittest

from vampires.balanced import choose_balanced
from vampires.endgame import ExactSolver
from vampires.evaluation import evaluate
from vampires.model import Board, Cell, Species, load_map
from vampires.rules import validate_moves
from vampires.search import SearchConfig, state_key
from vampires.simulation import single_moves
from vampires.strategy import cohesive_turns
from vampires.turns import Candidates


V, W = Species.VAMPIRES, Species.WEREWOLVES
ROOT = Path(__file__).resolve().parents[1]


def intact_turns(board, side, **kwargs):
    # These fixtures contain at most one group per species; moving intact keeps
    # that invariant. This is their full intact-group action set, with no ranking.
    assert len(board.groups(side)) <= 1
    return Candidates(tuple((move,) for move in single_moves(board, side, whole_groups_only=True)), False)


class CountingClock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.calls


class AdaptiveTests(unittest.TestCase):
    def test_depths_four_through_six_match_independent_exact_outcomes(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=2),
                             (3, 0): Cell(werewolves=2)})
        for side in Species:
            for depth in (4, 5, 6):
                with self.subTest(side=side, depth=depth):
                    solver = ExactSolver(side, shared_target="reject",
                                         turn_factory=lambda b, s: intact_turns(b, s).turns)
                    exact = solver.action_values(board, side, depth)
                    result = choose_balanced(
                        board, side, time_budget=10, remaining_plies=depth,
                        config=SearchConfig(max_depth=depth), generator=intact_turns,
                        reuse_work=True, collect_iterations=True)
                    expected = max(outcome.utility for outcome in exact.values())
                    self.assertEqual(result.completed_depth, depth)
                    self.assertAlmostEqual(result.value, float(expected))
                    self.assertEqual(exact[result.moves].utility, expected)
                    self.assertTrue(all(item.completed for item in result.iterations))

    def test_capped_values_still_enclose_exact_selected_action(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=3),
                             (2, 0): Cell(werewolves=2)})
        for side in Species:
            solver = ExactSolver(side, shared_target="reject",
                                 turn_factory=lambda b, s: intact_turns(b, s).turns)
            exact = solver.action_values(board, side, 4)
            for cap in (1, 2, 3):
                with self.subTest(side=side, cap=cap):
                    result = choose_balanced(
                        board, side, time_budget=10, remaining_plies=4,
                        config=SearchConfig(max_depth=4, max_outcomes=cap),
                        generator=intact_turns, reuse_work=True)
                    expected = float(exact[result.moves].utility)
                    self.assertLessEqual(result.value_lower, expected + 1e-10)
                    self.assertGreaterEqual(result.value_upper, expected - 1e-10)

    def test_interrupted_later_depth_retains_completed_move_and_bounds(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=2),
                             (3, 0): Cell(werewolves=2)})
        clock = CountingClock()
        reference = choose_balanced(
            board, V, time_budget=10**9, clock=clock, config=SearchConfig(max_depth=3),
            generator=intact_turns, reuse_work=True, collect_iterations=True)
        result = choose_balanced(
            board, V, time_budget=10**9, expires_at=clock.calls + 10, clock=CountingClock(),
            config=SearchConfig(max_depth=6), generator=intact_turns,
            reuse_work=True, collect_iterations=True)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.completed_depth, 3)
        self.assertEqual(result.moves, reference.moves)
        self.assertEqual((result.value_lower, result.value_upper),
                         (reference.value_lower, reference.value_upper))
        self.assertEqual([item.completed for item in result.iterations], [True, True, False])
        self.assertEqual(result.iterations[-1].depth, 4)

    def test_complete_generations_are_reused_but_truncated_ones_are_not(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=2), (3, 0): Cell(werewolves=2)})
        for truncated in (False, True):
            counts = {}

            def generate(position, side, **kwargs):
                key = state_key(position), side
                counts[key] = counts.get(key, 0) + 1
                result = intact_turns(position, side)
                return Candidates(result.turns, truncated, truncated)

            with self.subTest(truncated=truncated):
                result = choose_balanced(
                    board, V, time_budget=10, config=SearchConfig(max_depth=5),
                    generator=generate, reuse_work=True)
                self.assertEqual(result.completed_depth, 5)
                if truncated:
                    self.assertEqual(result.candidate_hits, 0)
                    self.assertGreater(max(counts.values()), 1)
                    self.assertEqual(result.truncated_generations, sum(counts.values()))
                else:
                    self.assertGreater(result.candidate_hits, 0)
                    self.assertEqual(max(counts.values()), 1)

    def test_reuse_reduces_repeated_evaluation_without_changing_finished_value(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        decisions, calls = {}, {}
        for reuse in (False, True):
            count = 0

            def counted(*args, **kwargs):
                nonlocal count
                count += 1
                return evaluate(*args, **kwargs)

            decisions[reuse] = choose_balanced(
                board, V, time_budget=10, config=SearchConfig(max_depth=4),
                generator=cohesive_turns, evaluator=counted, reuse_work=reuse)
            calls[reuse] = count
        self.assertEqual(decisions[False].completed_depth, 4)
        self.assertEqual(decisions[True].completed_depth, 4)
        self.assertAlmostEqual(decisions[False].value, decisions[True].value)
        self.assertGreater(decisions[True].evaluation_hits, 0)
        self.assertLess(calls[True], calls[False])

    def test_iteration_records_account_for_all_search_work(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=2), (3, 0): Cell(werewolves=2)})
        result = choose_balanced(board, V, time_budget=10, config=SearchConfig(max_depth=6),
                                 generator=intact_turns, reuse_work=True, collect_iterations=True)
        self.assertEqual([item.depth for item in result.iterations], list(range(2, 7)))
        for field in ("nodes", "chance_outcomes", "root_started", "root_finished", "root_pruned",
                      "cache_hits", "evaluation_hits", "candidate_hits"):
            self.assertEqual(sum(getattr(item, field) for item in result.iterations), getattr(result, field))
        self.assertLessEqual(sum(item.elapsed_seconds for item in result.iterations), result.elapsed_seconds)

    def test_tiny_cache_does_not_change_exact_value(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        solver = ExactSolver(V, shared_target="reject",
                             turn_factory=lambda b, s: intact_turns(b, s).turns)
        exact = solver.action_values(board, V, 6)
        result = choose_balanced(board, V, time_budget=10, remaining_plies=6,
                                 config=SearchConfig(max_depth=6, cache_entries=1),
                                 generator=intact_turns, reuse_work=True)
        self.assertAlmostEqual(result.value, float(max(outcome.utility for outcome in exact.values())))

    def test_zero_budget_reuse_and_collection_keep_legal_unknown_fallback(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        result = choose_balanced(board, V, time_budget=0, reuse_work=True, collect_iterations=True)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.value)
        self.assertEqual(result.iterations, ())
        self.assertEqual(result.evaluation_hits, 0)
        validate_moves(board, V, result.moves)

    def test_flags_require_actual_booleans(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        for kwargs in ({"reuse_work": 1}, {"reuse_work": "false"}, {"collect_iterations": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                choose_balanced(board, V, **kwargs)


if __name__ == "__main__":
    unittest.main()
