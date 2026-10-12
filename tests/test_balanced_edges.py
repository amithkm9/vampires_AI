"""Independent eager-tree checks for resumable search and its interrupted bounds."""

from fractions import Fraction
import random
import unittest
from unittest.mock import patch

from vampires.balanced import choose_balanced
from vampires.budget import SearchTimeout
from vampires.model import Board, Cell, Species
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig, choose_turn
from vampires.simulation import Outcome, iter_turn_outcome_steps, iter_turn_outcomes, turn_outcomes
from vampires.turns import Candidates, NoLegalMove, exhaustive_turns


V, W = Species.VAMPIRES, Species.WEREWOLVES


def all_supported_turns(board, side, **kwargs):
    """Full tiny action sets, excluding only the live unverified battle rule."""
    turns = []
    for turn in exhaustive_turns(board, side):
        contested = [move.target for move in turn
                     if board.at(move.target).humans or board.at(move.target).count(side.opponent)]
        if len(contested) == len(set(contested)):
            turns.append(turn)
    return Candidates(tuple(turns), False)


def eager_values(board, perspective, remaining):
    """Rational eager expectiminimax; no live search, evaluator or bounds reuse."""
    cache = {}

    def value(position, side, plies):
        own = sum(cell.count(perspective) for cell in position.cells.values())
        enemy = sum(cell.count(perspective.opponent) for cell in position.cells.values())
        if not own or not enemy or not plies:
            return Fraction((own > enemy) - (own < enemy))
        key = (tuple(sorted((point, cell.humans, cell.vampires, cell.werewolves)
                            for point, cell in position.cells.items())), side, plies)
        if key not in cache:
            choices = [action(position, side, turn, plies)
                       for turn in all_supported_turns(position, side).turns]
            cache[key] = (max if side == perspective else min)(choices)
        return cache[key]

    def action(position, side, turn, plies):
        return sum(outcome.probability * value(outcome.board, side.opponent, plies - 1)
                   for outcome in turn_outcomes(position, side, turn))

    return {turn: action(board, perspective, turn, remaining)
            for turn in all_supported_turns(board, perspective).turns}


class CountingClock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.calls


class BalancedEdgeTests(unittest.TestCase):
    def test_complete_search_matches_independent_rational_trees(self):
        for seed in range(6):
            rng = random.Random(53100 + seed)
            points = rng.sample([(0, 0), (1, 0), (2, 0)], 3)
            board = Board(1, 3, {points[0]: Cell(vampires=rng.randint(1, 2)),
                                 points[1]: Cell(werewolves=rng.randint(1, 2)),
                                 points[2]: Cell(humans=rng.randint(1, 2))})
            for side in Species:
                for horizon in (1, 2, 3):
                    with self.subTest(seed=seed, side=side, horizon=horizon):
                        exact = eager_values(board, side, horizon)
                        result = choose_balanced(
                            board, side, time_budget=10, remaining_plies=horizon,
                            config=SearchConfig(max_depth=horizon, preserve_dominance=False),
                            generator=all_supported_turns)
                        self.assertEqual(result.completed_depth, horizon)
                        self.assertAlmostEqual(result.value, float(max(exact.values())))
                        self.assertEqual(exact[result.moves], max(exact.values()))

    def test_capped_probability_bounds_contain_selected_full_tree_value(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=3),
                             (2, 0): Cell(werewolves=2)})
        for side in Species:
            exact = eager_values(board, side, 2)
            for cap in (1, 2, 3, 4):
                with self.subTest(side=side, cap=cap):
                    result = choose_balanced(
                        board, side, time_budget=10, remaining_plies=2,
                        config=SearchConfig(max_depth=2, max_outcomes=cap),
                        generator=all_supported_turns)
                    expected = float(exact[result.moves])
                    self.assertLessEqual(result.value_lower, expected + 1e-10)
                    self.assertGreaterEqual(result.value_upper, expected - 1e-10)
                    self.assertLessEqual(result.value_lower, result.value_upper)

    def test_interrupted_bounds_contain_selected_action_value(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=3),
                             (2, 0): Cell(werewolves=2)})
        for side in Species:
            exact = eager_values(board, side, 2)
            for expiration in (1, 3, 12, 30, 60, 120, 250, 500, 1000, 2000):
                with self.subTest(side=side, expiration=expiration):
                    result = choose_balanced(
                        board, side, time_budget=10**9, expires_at=expiration,
                        clock=CountingClock(), remaining_plies=2,
                        config=SearchConfig(max_depth=2), generator=all_supported_turns)
                    expected = float(exact[result.moves])
                    self.assertLessEqual(result.value_lower, expected + 1e-10)
                    self.assertGreaterEqual(result.value_upper, expected - 1e-10)
                    validate_moves(board, side, result.moves)

    def test_tiny_cache_preserves_complete_value(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(werewolves=2)})
        exact = eager_values(board, V, 3)
        result = choose_balanced(board, V, time_budget=10, remaining_plies=3,
                                 config=SearchConfig(max_depth=3, cache_entries=1),
                                 generator=all_supported_turns)
        self.assertEqual(exact[result.moves], max(exact.values()))
        self.assertAlmostEqual(result.value, float(max(exact.values())))

    def test_joint_moves_and_root_order_match_full_tiny_reference(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(vampires=1),
                             (0, 1): Cell(humans=1), (1, 1): Cell(werewolves=2)})
        for side in Species:
            exact = eager_values(board, side, 2)
            for reverse in (False, True):
                def generate(position, moving, **kwargs):
                    candidates = all_supported_turns(position, moving, **kwargs)
                    return Candidates(tuple(reversed(candidates.turns)), False) if reverse else candidates

                with self.subTest(side=side, reverse=reverse):
                    result = choose_balanced(board, side, time_budget=10, remaining_plies=2,
                                             config=SearchConfig(max_depth=2), generator=generate)
                    self.assertEqual(exact[result.moves], max(exact.values()))
                    self.assertAlmostEqual(result.value, float(max(exact.values())))

    def test_maximum_depth_with_cycles_keeps_horizon_in_cache_key(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        exact = eager_values(board, V, 8)
        result = choose_balanced(board, V, time_budget=10, remaining_plies=8,
                                 config=SearchConfig(max_depth=8), generator=all_supported_turns)
        self.assertEqual(result.completed_depth, 8)
        self.assertEqual(exact[result.moves], max(exact.values()))
        self.assertAlmostEqual(result.value, float(max(exact.values())))

    def test_invalid_evaluator_output_does_not_poison_intervals(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(werewolves=2)})
        for value in (float("nan"), float("inf"), -float("inf"), -1.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose_balanced(board, V, time_budget=10,
                                config=SearchConfig(max_depth=1),
                                evaluator=lambda *args, **kwargs: value)

    def test_interrupted_leaf_is_not_cached_as_a_score(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(werewolves=2)})

        def interrupt(*args, **kwargs):
            raise SearchTimeout

        result = choose_balanced(board, V, time_budget=10,
                                 config=SearchConfig(max_depth=1), evaluator=interrupt)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.completed_depth, 0)
        self.assertIsNone(result.value)
        self.assertEqual((result.value_lower, result.value_upper), (-1, 1))

    def test_unsupported_overflow_stays_unknown(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=200), (1, 0): Cell(humans=100),
                             (2, 0): Cell(werewolves=1)})
        turn = (Move(0, 0, 200, 1, 0),)
        result = choose_balanced(
            board, V, time_budget=10, remaining_plies=1,
            config=SearchConfig(max_depth=1),
            generator=lambda *args, **kwargs: Candidates((turn,), True))
        self.assertEqual(result.unsupported_actions, 1)
        self.assertEqual((result.value_lower, result.value_upper), (-1, 1))
        self.assertIsNone(result.value)

    def test_unverified_shared_target_stays_unknown(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(vampires=1),
                             (0, 1): Cell(humans=1), (1, 1): Cell(werewolves=1)})
        original = dict(board.cells)
        turn = (Move(0, 0, 1, 0, 1), Move(1, 0, 1, 0, 1))
        result = choose_balanced(
            board, V, time_budget=10, remaining_plies=1,
            config=SearchConfig(max_depth=1),
            generator=lambda *args, **kwargs: Candidates((turn,), True))
        self.assertEqual(result.unsupported_actions, 1)
        self.assertEqual((result.value_lower, result.value_upper), (-1, 1))
        self.assertEqual(board.cells, original)
        self.assertIsNone(result.value)

    def test_chance_cap_does_not_request_an_unused_successor(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})

        def stream(*args, **kwargs):
            yield Outcome(Fraction(1, 2), Board(1, 2))
            self.fail("The configured chance cap must stop before generating outcome N+1")

        for module, search in (("balanced", choose_balanced), ("search", choose_turn)):
            transition = "iter_turn_outcome_steps" if module == "balanced" else "iter_turn_outcomes"
            with self.subTest(module=module), patch(f"vampires.{module}.{transition}", stream):
                result = search(board, V, time_budget=10, remaining_plies=1,
                                config=SearchConfig(max_depth=1, max_outcomes=1))
            self.assertEqual(result.completed_depth, 1)
            self.assertEqual(result.chance_outcomes, 1)
            self.assertAlmostEqual(result.value_lower, -.5)
            self.assertAlmostEqual(result.value_upper, .5)

    def test_joint_battle_preparation_does_not_starve_other_roots(self):
        cells = {}
        for x in range(0, 255, 2):
            cells[x, 0] = Cell(vampires=255)
            cells[x, 1] = Cell(werewolves=255)
        board = Board(3, 255, cells)
        roots = (tuple(Move(x, 0, 255, x, 1) for x in range(0, 255, 2)),
                 (Move(0, 0, 255, 1, 0),))
        result = choose_balanced(
            board, V, time_budget=10**9, expires_at=3000, clock=CountingClock(), remaining_plies=1,
            config=SearchConfig(max_depth=1, preserve_dominance=False),
            generator=lambda *args, **kwargs: Candidates(roots, True))
        self.assertTrue(result.timed_out)
        self.assertEqual(result.root_started, 2)
        self.assertGreaterEqual(result.root_updates, 2)
        self.assertEqual(result.root_finished, 1)
        self.assertEqual(result.moves, roots[1])
        self.assertAlmostEqual(result.value, 0)
        validate_moves(board, V, result.moves)

    def test_preparation_steps_preserve_eager_transition_probabilities(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(vampires=1),
                             (0, 1): Cell(humans=3), (2, 1): Cell(werewolves=2)})
        turn = (Move(0, 0, 2, 0, 1), Move(2, 0, 1, 2, 1))

        def keyed(outcomes):
            return {tuple(sorted((point, cell.humans, cell.vampires, cell.werewolves)
                                 for point, cell in outcome.board.cells.items())): outcome.probability
                    for outcome in outcomes}

        steps = tuple(iter_turn_outcome_steps(board, V, turn))
        self.assertEqual(sum(step is None for step in steps), 2)
        eager = keyed(turn_outcomes(board, V, turn))
        self.assertEqual(keyed(step for step in steps if step is not None), eager)
        self.assertEqual(keyed(iter_turn_outcomes(board, V, turn)), eager)
        self.assertEqual(sum(eager.values()), 1)

    def test_absent_movement_is_explicit(self):
        for board in (Board(1, 1, {(0, 0): Cell(vampires=1)}), Board(1, 2)):
            with self.subTest(board=board), self.assertRaises(NoLegalMove):
                choose_balanced(board, V)


if __name__ == "__main__":
    unittest.main()
