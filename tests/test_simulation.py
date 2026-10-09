from fractions import Fraction
from pathlib import Path
import unittest

from vampires.model import Board, Cell, Species, load_map
from vampires.rules import Move, battle_odds, validate_moves
from vampires.simulation import UnsupportedPopulation, battle_distribution, single_move_outcomes, single_moves
from tools.analyze_maps import distance, optimistic_capture_routes, trap_openings

ROOT = Path(__file__).resolve().parents[1]
V, W = Species.VAMPIRES, Species.WEREWOLVES


class ExactBattleTests(unittest.TestCase):
    def test_small_distributions_normalize_and_match_analytic_expectations(self):
        for humans in (False, True):
            for attackers in range(1, 13):
                for defenders in range(1, 13):
                    with self.subTest(a=attackers, d=defenders, humans=humans):
                        distribution = battle_distribution(attackers, defenders, humans=humans)
                        self.assertEqual(sum(distribution.values()), 1)
                        self.assertTrue(all(p > 0 and a*d == 0 for (a, d), p in distribution.items()))
                        expected = battle_odds(attackers, defenders, humans=humans)
                        self.assertAlmostEqual(float(sum(a*p for (a, d), p in distribution.items())), expected.expected_attackers)
                        self.assertAlmostEqual(float(sum(d*p for (a, d), p in distribution.items())), expected.expected_defenders)

    def test_equal_four_battle_has_empty_outcome_from_both_branches(self):
        distribution = battle_distribution(4, 4)
        self.assertEqual(distribution[0, 0], Fraction(1, 16))
        self.assertEqual(sum(p for (a, d), p in distribution.items() if a == 0), Fraction(17, 32))
        self.assertEqual(sum(p for (a, d), p in distribution.items() if a > 0), Fraction(15, 32))
        self.assertEqual(len(distribution), 9)

    def test_human_threshold_discontinuity(self):
        risky = battle_distribution(19, 20, humans=True)
        certain = battle_distribution(20, 20, humans=True)
        self.assertEqual(sum(a*p for (a, d), p in risky.items()), Fraction(14079, 1600))
        self.assertEqual(certain, {(40, 0): Fraction(1)})

    def test_combat_initiative_is_not_symmetric(self):
        # Being the attacker changes the battle-winning draw, even at the same counts.
        self.assertEqual(battle_odds(10, 8).attacker_win_probability, .75)
        self.assertEqual(battle_odds(8, 10).attacker_win_probability, .4)


class SingleMoveTests(unittest.TestCase):
    def test_partial_move_preserves_population_and_original_board(self):
        board = Board(3, 3, {(1, 1): Cell(vampires=4)})
        result, = single_move_outcomes(board, V, Move(1, 1, 3, 2, 2))
        self.assertEqual(result.probability, 1)
        self.assertEqual(result.board.groups(V), {(1, 1): 1, (2, 2): 3})
        self.assertEqual(board.groups(V), {(1, 1): 4})

    def test_friendly_merge(self):
        board = Board(2, 2, {(0, 0): Cell(werewolves=4), (1, 1): Cell(werewolves=5)})
        result, = single_move_outcomes(board, W, Move(0, 0, 4, 1, 1))
        self.assertEqual(result.board.groups(W), {(1, 1): 9})

    def test_human_conversion_preserves_total_population(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=4), (1, 1): Cell(humans=4)})
        result, = single_move_outcomes(board, V, Move(0, 0, 4, 1, 1))
        self.assertEqual(result.board.groups(V), {(1, 1): 8})
        self.assertEqual(result.board.at((1, 1)).humans, 0)

    def test_random_human_defenders_stay_human(self):
        board = Board(2, 2, {(0, 0): Cell(werewolves=2), (1, 1): Cell(humans=4)})
        outcomes = single_move_outcomes(board, W, Move(0, 0, 2, 1, 1))
        self.assertEqual(sum(o.probability for o in outcomes), 1)
        self.assertTrue(any(o.board.at((1, 1)).humans for o in outcomes))
        self.assertTrue(all(not o.board.groups(V) for o in outcomes))
        self.assertTrue(all(o.board.at((0, 0)).empty for o in outcomes))

    def test_monster_threshold_and_terminal_extinction(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=6), (1, 1): Cell(werewolves=4)})
        result, = single_move_outcomes(board, V, Move(0, 0, 6, 1, 1))
        self.assertEqual(result.board.groups(V), {(1, 1): 6})
        self.assertFalse(result.board.groups(W))

    def test_overflow_is_explicit_instead_of_clipping_or_losing_probability_mass(self):
        for target in (Cell(vampires=200), Cell(humans=200)):
            board = Board(2, 2, {(0, 0): Cell(vampires=200), (1, 1): target})
            with self.assertRaises(UnsupportedPopulation):
                single_move_outcomes(board, V, Move(0, 0, 200, 1, 1))

    def test_single_record_candidates_include_every_partial_amount(self):
        board = Board(3, 3, {(1, 1): Cell(vampires=4)})
        candidates = list(single_moves(board, V))
        self.assertEqual(len(candidates), 32)
        self.assertEqual(len(set(candidates)), 32)
        for move in candidates:
            validate_moves(board, V, (move,))


class MapAnalysisTests(unittest.TestCase):
    def test_forced_battle_proves_universal_win_guarantee_impossible(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        move, = list(single_moves(board, V))
        outcomes = single_move_outcomes(board, V, move)
        definite_loss = sum(o.probability for o in outcomes
                            if not o.board.groups(V) and o.board.groups(W))
        self.assertEqual(definite_loss, Fraction(1, 4))

    def test_chebyshev_distance_counts_diagonals(self):
        self.assertEqual(distance((0, 0), (10, 3)), 10)
        self.assertEqual(distance((4, 1), (2, 2)), 2)

    def test_trap_safe_and_exposed_openings_for_both_species(self):
        analysis = trap_openings(load_map(ROOT / "maps/thetrap.xml"))
        for species, safe, exposed in [(W, (3, 1), (3, 2)), (V, (3, 3), (3, 2))]:
            by_target = {tuple(entry["move"][-2:]): entry for entry in analysis[species.value]}
            self.assertEqual(by_target[safe]["distance_to_four_humans"], 1)
            self.assertEqual(by_target[exposed]["distance_to_four_humans"], 1)
            self.assertEqual(by_target[safe]["max_next_reply_extinction_probability"]["exact"], "0")
            self.assertEqual(by_target[exposed]["max_next_reply_extinction_probability"]["exact"], "17/32")

    def test_large_map_resource_bottleneck_and_optimistic_route(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        outside = sum(c.humans for p, c in board.cells.items() if p != (14, 7))
        self.assertEqual(outside, 12)
        self.assertLess(10 + outside - 4, 20)  # Opponent already took one 4-human house.
        for species in Species:
            routes = optimistic_capture_routes(board, species, (14, 7))
            self.assertEqual(routes[0]["arrival_own_turn_lower_bound"], 37)
            self.assertGreaterEqual(routes[0]["captures"][-1]["population_after"], 40)


if __name__ == "__main__":
    unittest.main()
