from fractions import Fraction
from pathlib import Path
import random
import unittest

from vampires.budget import SearchTimeout
from vampires.certificates import dominant_stack, preserving_turn
from vampires.evaluation import evaluate
from vampires.growth import evaluate_growth, human_arrivals
from vampires.mcts import choose_mcts
from vampires.model import Board, Cell, Species, load_map
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig, chance_bounds, choose_turn, state_key
from vampires.simulation import (AmbiguousBattle, UnsupportedPopulation, iter_turn_outcomes,
                                 sample_turn, turn_outcomes)
from vampires.turns import candidate_turns

V, W = Species.VAMPIRES, Species.WEREWOLVES
ROOT = Path(__file__).resolve().parents[1]


class StreamingChanceTests(unittest.TestCase):
    def test_two_ply_bounds_and_cutoffs_match_an_independent_full_tree(self):
        from vampires.evaluation import terminal_value
        for own, enemy in ((1, 1), (2, 1), (1, 2), (2, 2)):
            board = Board(2, 2, {(0, 0): Cell(vampires=own), (1, 1): Cell(werewolves=enemy),
                                  (0, 1): Cell(humans=1)})
            values = {}
            for turn in candidate_turns(board, V).turns:
                value = 0.
                for outcome in turn_outcomes(board, V, turn):
                    terminal = terminal_value(outcome.board, V)
                    if terminal is not None:
                        reply_value = terminal
                    else:
                        reply_value = min(sum(float(o.probability) * evaluate(o.board, V, V)
                                              for o in turn_outcomes(outcome.board, W, reply))
                                          for reply in candidate_turns(outcome.board, W).turns)
                    value += float(outcome.probability) * reply_value
                values[turn] = value
            full = choose_turn(board, V, time_budget=10,
                               config=SearchConfig(max_depth=2, preserve_dominance=False))
            self.assertAlmostEqual(full.value, max(values.values()))
            limited = choose_turn(board, V, time_budget=10,
                                  config=SearchConfig(max_depth=2, max_outcomes=1, preserve_dominance=False))
            self.assertLessEqual(limited.value_lower, values[limited.moves])
            self.assertGreaterEqual(limited.value_upper, values[limited.moves])

    def test_stream_matches_eager_joint_reference_for_both_species(self):
        for species in Species:
            board = Board(1, 4, {(0, 0): Cell(**{species.value: 2}), (1, 0): Cell(humans=3),
                                  (2, 0): Cell(**{species.opponent.value: 2}),
                                  (3, 0): Cell(**{species.value: 2})})
            moves = (Move(0, 0, 1, 1, 0), Move(3, 0, 2, 2, 0))
            expected = {state_key(o.board): o.probability for o in turn_outcomes(board, species, moves)}
            actual = {state_key(o.board): o.probability for o in iter_turn_outcomes(board, species, moves)}
            self.assertEqual(actual, expected)
            self.assertEqual(sum(actual.values()), 1)

    def test_prefix_is_not_renormalized(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        first = next(iter_turn_outcomes(board, V, (Move(0, 0, 1, 1, 0),)))
        self.assertEqual(first.probability, Fraction(1, 2))
        self.assertFalse(first.board.cells)
        bounds = chance_bounds(0, 0, first.probability)
        self.assertLessEqual(bounds.lower, -.5)
        self.assertGreaterEqual(bounds.upper, .5)

    def test_sampled_successors_stay_in_exact_support_and_are_seeded(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=3)})
        moves = (Move(0, 0, 2, 1, 0),)
        support = {state_key(o.board) for o in turn_outcomes(board, V, moves)}
        a, b = random.Random(91), random.Random(91)
        first = [state_key(sample_turn(board, V, moves, a)) for _ in range(200)]
        self.assertEqual(first, [state_key(sample_turn(board, V, moves, b)) for _ in range(200)])
        self.assertTrue(set(first) <= support)
        self.assertGreater(len(set(first)), 2)

    def test_lazy_and_sampled_models_reject_ambiguity_and_overflow(self):
        for target, error in ((Cell(humans=4), AmbiguousBattle), (Cell(vampires=255), UnsupportedPopulation)):
            board = Board(2, 3, {(0, 0): Cell(vampires=3), (2, 0): Cell(vampires=3), (1, 1): target})
            moves = (Move(0, 0, 3, 1, 1), Move(2, 0, 3, 1, 1))
            with self.assertRaises(error):
                tuple(iter_turn_outcomes(board, V, moves))
            with self.assertRaises(error):
                sample_turn(board, V, moves, random.Random(1))

    def test_bounded_action_contains_independent_full_expectation(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1),
                              (2, 0): Cell(werewolves=1), (3, 0): Cell(vampires=1)})
        original = state_key(board)
        decision = choose_turn(board, V, time_budget=10,
                               config=SearchConfig(max_depth=1, max_outcomes=1, preserve_dominance=False))
        exact = sum(float(o.probability) * evaluate(o.board, V, W)
                    for o in turn_outcomes(board, V, decision.moves))
        self.assertLessEqual(decision.value_lower, exact)
        self.assertGreaterEqual(decision.value_upper, exact)
        self.assertEqual(decision.unsupported_actions, 0)
        self.assertGreater(decision.bounded_actions, 0)
        self.assertEqual(state_key(board), original)


class PartialGenerationTests(unittest.TestCase):
    def test_interrupted_generation_returns_completed_legal_candidates(self):
        board = Board(3, 4, {(0, 0): Cell(vampires=4), (3, 0): Cell(vampires=4), (2, 2): Cell(werewolves=4)})
        calls = 0
        def check():
            nonlocal calls
            calls += 1
            if calls == 12:
                raise SearchTimeout
        result = candidate_turns(board, V, check=check, allow_partial=True)
        self.assertTrue(result.truncated)
        self.assertTrue(result.selective)
        self.assertTrue(result.turns)
        for turn in result.turns:
            validate_moves(board, V, turn)

    def test_work_cap_still_preserves_single_moves_from_late_sources(self):
        board = Board(1, 5, {(0, 0): Cell(vampires=2), (4, 0): Cell(vampires=2)})
        result = candidate_turns(board, V, max_expansions=1)
        self.assertTrue(result.truncated)
        self.assertTrue(any(t[0].source == (4, 0) for t in result.turns))


class DominanceTests(unittest.TestCase):
    def test_certificate_uses_all_remaining_humans_and_enemies(self):
        for count in (8, 9):
            board = Board(2, 3, {(0, 0): Cell(vampires=count), (2, 0): Cell(werewolves=4), (2, 1): Cell(humans=2)})
            self.assertEqual(dominant_stack(board, V) is not None, count == 9)

    def test_preserving_turn_never_splits_or_gambles(self):
        for species in Species:
            board = Board(3, 3, {(1, 1): Cell(**{species.value: 9}),
                                  (2, 1): Cell(**{species.opponent.value: 4}), (0, 0): Cell(humans=2)})
            turn = preserving_turn(board, species)
            self.assertEqual(len(turn), 1)
            self.assertEqual(turn[0].count, 9)
            outcome, = turn_outcomes(board, species, turn)
            self.assertEqual(outcome.probability, 1)
            self.assertIsNotNone(dominant_stack(outcome.board, species))
            result = choose_turn(board, species, time_budget=1)
            self.assertTrue(result.preserved_dominance)
            self.assertEqual(result.moves, turn)

    def test_certificate_is_not_returned_without_a_supported_move(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=255), (1, 0): Cell(humans=1)})
        self.assertIsNotNone(dominant_stack(board, V))
        self.assertIsNone(preserving_turn(board, V))


class GrowthTests(unittest.TestCase):
    def test_chain_requires_growth_before_large_house(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=2), (3, 0): Cell(humans=4)})
        plan = human_arrivals(board, V)
        self.assertEqual(plan.arrivals, {(1, 0): 1, (3, 0): 3})
        self.assertTrue(plan.complete)
        blocked = human_arrivals(board, V, allowed={(3, 0)})
        self.assertFalse(blocked.arrivals)

    def test_opponent_capture_breaks_central_house_resource_chain(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        self.assertIn((14, 7), human_arrivals(board, V).arrivals)
        board.apply_updates(((10, 3, 0, 0, 14), (0, 0, 0, 0, 0)))
        self.assertNotIn((14, 7), human_arrivals(board, V).arrivals)

    def test_growth_score_is_bounded_and_perspective_symmetric(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        for side in Species:
            self.assertAlmostEqual(evaluate_growth(board, V, side), -evaluate_growth(board, W, side))
            self.assertLess(abs(evaluate_growth(board, V, side)), 1)

    def test_growth_work_limit_is_explicit(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        self.assertFalse(human_arrivals(board, V, max_states=1).complete)


class ChallengerTests(unittest.TestCase):
    def test_fixed_seed_simulations_are_reproducible_and_choose_certain_win(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=3), (1, 0): Cell(werewolves=2)})
        config = SearchConfig(max_depth=2, preserve_dominance=False)
        a = choose_mcts(board, V, time_budget=10, seed=31, config=config, max_simulations=200)
        b = choose_mcts(board, V, time_budget=10, seed=31, config=config, max_simulations=200)
        self.assertEqual(a.moves, b.moves)
        self.assertEqual(a.simulations, 200)
        self.assertEqual(a.moves, (Move(0, 0, 3, 1, 0),))

    def test_sampled_search_obeys_zero_budget_and_both_species(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        for species in Species:
            result = choose_mcts(board, species, time_budget=0)
            validate_moves(board, species, result.moves)
            self.assertTrue(result.timed_out)
            self.assertEqual(result.simulations, 0)


if __name__ == "__main__":
    unittest.main()
