from fractions import Fraction
import unittest

from vampires.budget import SearchTimeout
from vampires.endgame import ExactSolver, MatchOutcome, SolverLimit
from vampires.model import Board, Cell, Species
from vampires.rules import Move
from vampires.search import SearchConfig, choose_turn
from vampires.simulation import AmbiguousBattle, single_move_outcomes, single_moves
from vampires.turns import GenerationLimit

V, W = Species.VAMPIRES, Species.WEREWOLVES


class ExactEndgameTests(unittest.TestCase):
    def solver(self, species=V, **kwargs):
        return ExactSolver(species, shared_target="aggregate", **kwargs)

    def test_cutoff_scores_population_and_both_extinct_convention(self):
        for a, b in ((0, 0), (1, 2), (2, 1), (2, 2), (0, 2)):
            board = Board(1, 2, {(0, 0): Cell(vampires=a), (1, 0): Cell(werewolves=b)})
            for side in Species:
                result = self.solver(side).solve(board, side, 0)
                own, enemy = (a, b) if side == V else (b, a)
                self.assertEqual(result.outcome, MatchOutcome(Fraction(own > enemy),
                                 Fraction(own == enemy), Fraction(own < enemy)))
                self.assertFalse(result.moves)

    def test_winner_draws_and_individual_survival_give_exact_probabilities(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        result = self.solver().solve(board, V, 1)
        # Independent hand calculation: winner 1/2, surviving winner 1/2.
        self.assertEqual(result.outcome, MatchOutcome(Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)))
        self.assertEqual(result.outcome.score, Fraction(1, 2))

    def test_safe_win_draw_and_forced_loss(self):
        for a, b, expected in ((3, 2, 1), (1, 2, -1)):
            board = Board(1, 2, {(0, 0): Cell(vampires=a), (1, 0): Cell(werewolves=b)})
            self.assertEqual(self.solver().solve(board, V, 1).outcome.utility, expected)
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)})
        self.assertEqual(self.solver().solve(board, V, 1).outcome.draw, 1)

    def test_trailing_player_gambles_instead_of_accepting_certain_cutoff_loss(self):
        board = Board(2, 3, {(1, 0): Cell(vampires=2), (0, 0): Cell(humans=3),
                              (2, 1): Cell(werewolves=3)})
        solver = self.solver()
        result = solver.solve(board, V, 1)
        values = solver.action_values(board, V, 1)
        self.assertEqual(result.moves[0].target, (0, 0))
        self.assertGreater(result.outcome.score, 0)
        self.assertGreater(result.outcome.loss, 0)
        self.assertEqual(values[(Move(1, 0, 2, 2, 0),)].loss, 1)

    def test_leading_player_preserves_certain_win_and_tied_player_preserves_draw(self):
        for own, expected in ((3, 1), (2, 0)):
            board = Board(2, 3, {(1, 0): Cell(vampires=own), (0, 0): Cell(humans=4),
                                  (2, 1): Cell(werewolves=2)})
            result = self.solver().solve(board, V, 1)
            self.assertEqual(result.outcome.utility, expected)
            self.assertEqual(result.outcome.loss, 0)

    def test_cache_separates_horizon_and_side_to_move(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        solver = self.solver()
        self.assertEqual(solver.solve(board, V, 0).outcome.draw, 1)
        self.assertEqual(solver.solve(board, V, 1).outcome.draw, Fraction(1, 2))
        solver.solve(board, W, 1)
        self.assertTrue(any(key[-2:] == (W, 1) for key in solver.cache))

    def test_two_ply_value_matches_independent_nested_single_move_tree(self):
        # Counts of one cannot split, so single-record enumeration is complete.
        for size in (3, 4):
            board = Board(1, size, {(0, 0): Cell(vampires=1), (size - 1, 0): Cell(werewolves=1)})
            def cutoff(position):
                own = sum(position.groups(V).values())
                enemy = sum(position.groups(W).values())
                return (own > enemy) - (own < enemy)
            values = []
            for move in single_moves(board, V):
                value = Fraction(0)
                for branch in single_move_outcomes(board, V, move):
                    if not branch.board.groups(V) or not branch.board.groups(W):
                        reply_value = cutoff(branch.board)
                    else:
                        reply_value = min(sum(o.probability * cutoff(o.board)
                                              for o in single_move_outcomes(branch.board, W, reply))
                                          for reply in single_moves(branch.board, W))
                    value += branch.probability * reply_value
                values.append(value)
            self.assertEqual(self.solver().solve(board, V, 2).outcome.utility, max(values))

    def test_limits_and_unknown_combat_never_become_solved_values(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(vampires=2),
                              (1, 1): Cell(werewolves=2)})
        with self.assertRaises(SolverLimit):
            self.solver(max_states=1).solve(board, V, 2)
        with self.assertRaises(GenerationLimit):
            self.solver(max_generation_nodes=1).solve(board, V, 1)
        with self.assertRaises(AmbiguousBattle):
            ExactSolver(V, shared_target="reject").solve(board, V, 1)
        def expired():
            raise SearchTimeout
        with self.assertRaises(SearchTimeout):
            self.solver(check=expired).solve(board, V, 1)

    def test_bad_horizons_are_rejected(self):
        for horizon in (-1, True, 1.5, None):
            with self.assertRaises(ValueError):
                self.solver().solve(Board(1, 2), V, horizon)


class SearchHorizonTests(unittest.TestCase):
    def test_known_final_move_takes_useful_gamble_that_heuristic_avoids(self):
        board = Board(2, 3, {(1, 0): Cell(vampires=2), (0, 0): Cell(humans=3),
                              (2, 1): Cell(werewolves=3)})
        oracle = ExactSolver(V, shared_target="aggregate")
        values = oracle.action_values(board, V, 1)
        aware = choose_turn(board, V, remaining_plies=1, time_budget=10)
        unaware = choose_turn(board, V, time_budget=10, config=SearchConfig(max_depth=1))
        self.assertEqual(aware.moves[0].target, (0, 0))
        self.assertGreater(values[aware.moves].score, values[unaware.moves].score)
        self.assertAlmostEqual(aware.value, float(max(o.utility for o in values.values())))
        self.assertEqual(aware.completed_depth, 1)
        self.assertEqual(aware.remaining_plies, 1)
        self.assertIsNone(unaware.remaining_plies)

    def test_two_ply_search_matches_exact_outcomes_and_both_species(self):
        def no_heuristic(*args, **kwargs):
            raise AssertionError("Known cutoff within search must use outcomes")
        for species in Species:
            for count in (1, 2):
                board = Board(1, 3, {(0, 0): Cell(**{species.value: count}),
                                      (2, 0): Cell(**{species.opponent.value: 1})})
                oracle = ExactSolver(species, shared_target="aggregate")
                reference = oracle.solve(board, species, 2)
                decision = choose_turn(board, species, remaining_plies=2, time_budget=10,
                                       evaluator=no_heuristic)
                self.assertEqual(decision.completed_depth, 2)
                self.assertAlmostEqual(decision.value, float(reference.outcome.utility))
                self.assertAlmostEqual(decision.value, float(oracle.action_values(board, species, 2)[decision.moves].utility))

    def test_horizon_beyond_search_still_uses_heuristic_and_unknown_is_default(self):
        board = Board(1, 5, {(0, 0): Cell(vampires=2), (4, 0): Cell(werewolves=2)})
        config = SearchConfig(max_depth=2)
        a = choose_turn(board, V, time_budget=10, config=config)
        b = choose_turn(board, V, time_budget=10, config=config, remaining_plies=None)
        c = choose_turn(board, V, time_budget=10, config=config, remaining_plies=20)
        self.assertEqual((a.moves, a.value), (b.moves, b.value))
        self.assertEqual((a.moves, a.value), (c.moves, c.value))

    def test_ended_or_invalid_horizon_never_returns_a_move(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        for horizon in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                choose_turn(board, V, remaining_plies=horizon)


if __name__ == "__main__":
    unittest.main()
