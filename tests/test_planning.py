"""Strategic invariants and independent outcome checks for the new evaluators."""

from fractions import Fraction
import unittest

from vampires.budget import SearchTimeout
from vampires.endgame import ExactSolver
from vampires.engines import choose_engine
from vampires.evaluation import evaluate
from vampires.model import Board, Cell, Species
from vampires.planning import conversion_race, evaluate_outcome, evaluate_strategic
from vampires.rules import validate_moves
from vampires.search import SearchConfig, state_key


V, W = Species.VAMPIRES, Species.WEREWOLVES


class ConversionRaceTests(unittest.TestCase):
    def test_growth_unlocks_later_capture_without_borrowing_population(self):
        board = Board(1, 10, {(0, 0): Cell(vampires=3), (1, 0): Cell(humans=2),
                              (3, 0): Cell(humans=5), (9, 0): Cell(werewolves=2)})
        before = state_key(board)
        race = conversion_race(board, V)
        self.assertTrue(race.complete)
        self.assertEqual(race.populations, {V: 10, W: 2})
        self.assertEqual([(c.before, c.after, c.arrival_ply) for c in race.captures],
                         [(3, 5, 1), (5, 10, 5)])
        self.assertEqual(state_key(board), before)

    def test_house_is_exclusive_and_initiative_breaks_symmetric_race(self):
        board = Board(1, 5, {(0, 0): Cell(vampires=3), (2, 0): Cell(humans=2),
                             (4, 0): Cell(werewolves=3)})
        for side in Species:
            race = conversion_race(board, side)
            self.assertEqual(len(race.captures), 1)
            self.assertEqual(race.captures[0].species, side)
            self.assertEqual(sum(race.populations.values()), 8)

    def test_separate_groups_cannot_spend_each_others_conversions(self):
        board = Board(2, 10, {(0, 0): Cell(vampires=2), (0, 1): Cell(vampires=2),
                              (1, 0): Cell(humans=1), (2, 0): Cell(humans=4),
                              (9, 0): Cell(werewolves=1)})
        race = conversion_race(board, V)
        self.assertEqual(len(race.captures), 1)
        self.assertEqual(race.populations[V], 5)

    def test_overflow_is_not_credited(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=250), (1, 0): Cell(humans=10),
                             (2, 0): Cell(werewolves=1)})
        self.assertEqual(conversion_race(board, V).captures, ())

    def test_large_feature_set_falls_back_explicitly(self):
        cells = {(0, 0): Cell(vampires=2), (14, 0): Cell(werewolves=2)}
        cells.update({(x, 0): Cell(humans=1) for x in range(1, 14)})
        board = Board(1, 15, cells)
        self.assertFalse(conversion_race(board, V).complete)
        self.assertEqual(evaluate_strategic(board, V, V), evaluate(board, V, V))


class OutcomeStrategyTests(unittest.TestCase):
    def test_evaluations_are_bounded_antisymmetric_and_do_not_mutate(self):
        for humans in (0, 2):
            board = Board(2, 5, {(0, 0): Cell(vampires=3), (0, 1): Cell(vampires=2),
                                 (4, 0): Cell(werewolves=6), (2, 1): Cell(humans=humans)})
            before = state_key(board)
            for evaluator in (evaluate_outcome, evaluate_strategic):
                for side in Species:
                    value = evaluator(board, V, side)
                    self.assertAlmostEqual(value, -evaluator(board, W, side))
                    self.assertTrue(-.95 <= value <= .95)
            self.assertEqual(state_key(board), before)

    def test_outcome_ablation_leaves_human_positions_unchanged(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=3), (1, 0): Cell(humans=2),
                             (2, 0): Cell(werewolves=3)})
        self.assertEqual(evaluate_outcome(board, V, V), evaluate(board, V, V))

    def test_no_human_standing_rewards_closing_only_when_behind(self):
        close = Board(2, 7, {(1, 0): Cell(vampires=6), (0, 0): Cell(werewolves=7)})
        far = Board(2, 7, {(6, 0): Cell(vampires=6), (0, 0): Cell(werewolves=7)})
        self.assertGreater(evaluate_outcome(close, V, V), evaluate_outcome(far, V, V))
        self.assertLess(evaluate_outcome(close, W, V), evaluate_outcome(far, W, V))

    def test_recorded_trailing_cycle_approaches_a_possible_battle_both_species(self):
        for side in Species:
            board = Board(3, 7, {(2, 0): Cell(**{side.value: 6}),
                                 (0, 0): Cell(**{side.opponent.value: 7})})
            result = choose_engine(board, side, engine="outcome", time_budget=2,
                                   config=SearchConfig(max_depth=3))
            self.assertEqual(result.completed_depth, 3)
            self.assertEqual(result.moves[0].target_x, 1)
            self.assertGreater(result.value, -.5)
            validate_moves(board, side, result.moves)

    def test_known_cutoff_retains_safe_lead_and_tie_against_exact_reference(self):
        for count in (2, 3):
            board = Board(1, 4, {(1, 0): Cell(vampires=count), (2, 0): Cell(werewolves=2)})
            exact = ExactSolver(V, shared_target="reject").action_values(board, V, 1)
            for engine in ("outcome", "strategic", "tactical"):
                result = choose_engine(board, V, engine=engine, time_budget=1, remaining_plies=1)
                self.assertEqual(exact[result.moves].score, max(v.score for v in exact.values()))
                self.assertEqual(exact[result.moves].loss, Fraction(0))

    def test_terminal_scores_and_expired_deadlines(self):
        terminal = Board(1, 2, {(0, 0): Cell(vampires=2)})
        for evaluator in (evaluate_outcome, evaluate_strategic):
            self.assertEqual(evaluator(terminal, V, V), 1)
            self.assertEqual(evaluator(terminal, W, V), -1)
        board = Board(1, 3, {(0, 0): Cell(vampires=2), (1, 0): Cell(humans=1),
                             (2, 0): Cell(werewolves=2)})
        def expired():
            raise SearchTimeout
        for function in (conversion_race, evaluate_outcome, evaluate_strategic):
            args = (board, V) if function is conversion_race else (board, V, V)
            with self.assertRaises(SearchTimeout):
                function(*args, check=expired)
        for engine in ("outcome", "strategic", "tactical"):
            decision = choose_engine(board, V, engine=engine, time_budget=0)
            validate_moves(board, V, decision.moves)
            self.assertTrue(decision.timed_out)

    def test_tactical_mode_recovers_exact_split_capture_witness(self):
        board = Board(1, 6, {(2, 0): Cell(vampires=4), (1, 0): Cell(humans=2),
                             (3, 0): Cell(humans=2), (5, 0): Cell(werewolves=7)})
        exact = ExactSolver(V, shared_target="reject").action_values(board, V, 3)
        result = choose_engine(board, V, engine="tactical", time_budget=2,
                               remaining_plies=3, config=SearchConfig(max_depth=3))
        self.assertEqual(result.completed_depth, 3)
        self.assertEqual(exact[result.moves].win, 1)
        self.assertEqual(result.moves[0].count, 2)


if __name__ == "__main__":
    unittest.main()
