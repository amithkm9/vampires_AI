from fractions import Fraction
from itertools import combinations
import random
import unittest

from vampires.budget import Deadline, SearchTimeout
from vampires.model import Board, Cell, Species
from vampires.rules import Move, validate_moves
from vampires.simulation import (AmbiguousBattle, OutcomeLimit, UnsupportedPopulation,
                                 battle_distribution, single_move_outcomes, single_moves,
                                 turn_outcomes)
from vampires.turns import (GenerationLimit, NoLegalMove, candidate_turns, canonical,
                            exhaustive_turns, fallback_turn, significant_amounts)

V, W = Species.VAMPIRES, Species.WEREWOLVES


def packed(board):
    return tuple(sorted((p, c.humans, c.vampires, c.werewolves) for p, c in board.cells.items()))


def total(board):
    return sum(c.humans + c.vampires + c.werewolves for c in board.cells.values())


class JointTransitionTests(unittest.TestCase):
    def test_two_moves_debit_sources_and_preserve_remainders(self):
        board = Board(2, 4, {(0, 0): Cell(vampires=5), (3, 0): Cell(vampires=4)})
        moves = (Move(0, 0, 2, 1, 1), Move(3, 0, 3, 2, 1))
        outcome, = turn_outcomes(board, V, moves)
        self.assertEqual(outcome.probability, 1)
        self.assertEqual(outcome.board.groups(V), {(0, 0): 3, (3, 0): 1, (1, 1): 2, (2, 1): 3})
        self.assertEqual(board.groups(V), {(0, 0): 5, (3, 0): 4})

    def test_split_source_budget_is_applied_once(self):
        board = Board(2, 4, {(0, 0): Cell(vampires=7), (3, 0): Cell(vampires=1)})
        result, = turn_outcomes(board, V, (Move(0, 0, 2, 1, 0), Move(0, 0, 4, 0, 1)))
        self.assertEqual(result.board.groups(V), {(0, 0): 1, (3, 0): 1, (1, 0): 2, (0, 1): 4})

    def test_shared_empty_and_friendly_arrivals_merge(self):
        for existing in (0, 5):
            board = Board(2, 3, {(0, 0): Cell(werewolves=3), (2, 0): Cell(werewolves=4),
                                  (1, 1): Cell(werewolves=existing)})
            result, = turn_outcomes(board, W, (Move(0, 0, 3, 1, 1), Move(2, 0, 4, 1, 1)))
            self.assertEqual(result.board.groups(W), {(1, 1): 7 + existing})

    def test_shared_battles_require_explicit_assumption_even_when_deterministic(self):
        for target in (Cell(humans=4), Cell(werewolves=4)):
            board = Board(2, 3, {(0, 0): Cell(vampires=3), (2, 0): Cell(vampires=3), (1, 1): target})
            moves = (Move(0, 0, 3, 1, 1), Move(2, 0, 3, 1, 1))
            with self.assertRaises(AmbiguousBattle):
                turn_outcomes(board, V, moves)
            result, = turn_outcomes(board, V, moves, shared_target="aggregate")
            self.assertEqual(result.board.at((1, 1)).vampires, 6 + target.humans)

    def test_independent_random_battles_have_exact_product_distribution(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1),
                              (2, 0): Cell(werewolves=1), (3, 0): Cell(vampires=1)})
        moves = (Move(0, 0, 1, 1, 0), Move(3, 0, 1, 2, 0))
        outcomes = turn_outcomes(board, V, moves)
        self.assertEqual(len(outcomes), 9)
        self.assertEqual(sum(o.probability for o in outcomes), 1)
        for outcome in outcomes:
            probability = Fraction(1)
            for p in ((1, 0), (2, 0)):
                probability *= Fraction(1, 2) if outcome.board.at(p).empty else Fraction(1, 4)
            self.assertEqual(outcome.probability, probability)
        self.assertEqual(sum(o.probability for o in outcomes if not o.board.cells), Fraction(1, 4))
        reverse = turn_outcomes(board, V, tuple(reversed(moves)))
        self.assertEqual({packed(o.board): o.probability for o in outcomes},
                         {packed(o.board): o.probability for o in reverse})

    def test_branch_limit_does_not_return_a_truncated_distribution(self):
        board = Board(1, 4, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1),
                              (2, 0): Cell(werewolves=1), (3, 0): Cell(vampires=1)})
        with self.assertRaises(OutcomeLimit):
            turn_outcomes(board, V, (Move(0, 0, 1, 1, 0), Move(3, 0, 1, 2, 0)), max_outcomes=8)
        self.assertEqual(total(board), 4)

    def test_new_model_matches_independent_single_move_reference(self):
        for species in Species:
            for count in (1, 2, 4, 6):
                for cell in (Cell(), Cell(humans=4), Cell(**{species.value: 4}),
                             Cell(**{species.opponent.value: 4})):
                    board = Board(1, 2, {(0, 0): Cell(**{species.value: count}), (1, 0): cell})
                    for amount in range(1, count + 1):
                        move = Move(0, 0, amount, 1, 0)
                        expected = {packed(o.board): o.probability for o in single_move_outcomes(board, species, move)}
                        actual = {packed(o.board): o.probability for o in turn_outcomes(board, species, (move,))}
                        self.assertEqual(actual, expected)

    def test_each_successor_is_isolated_from_siblings_and_input(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=1)})
        results = turn_outcomes(board, V, (Move(0, 0, 1, 1, 0),))
        original = packed(board)
        others = [packed(o.board) for o in results[1:]]
        results[0].board.cells.clear()
        self.assertEqual(packed(board), original)
        self.assertEqual([packed(o.board) for o in results[1:]], others)

    def test_rules_reject_entire_turn_before_any_mutation(self):
        board = Board(2, 3, {(0, 0): Cell(vampires=3), (1, 0): Cell(vampires=2)})
        original = packed(board)
        invalid = [(), (Move(0, 0, 2, 1, 1), Move(0, 0, 2, 0, 1)),
                   (Move(0, 0, 3, 1, 0), Move(1, 0, 2, 2, 0)),
                   (Move(0, 0, 3, 1, 0), Move(1, 0, 2, 0, 0))]
        for moves in invalid:
            with self.assertRaises(ValueError):
                turn_outcomes(board, V, moves)
            self.assertEqual(packed(board), original)

    def test_overflow_and_exact_byte_boundary(self):
        for count in (127, 128):
            board = Board(2, 3, {(0, 0): Cell(vampires=count), (2, 0): Cell(vampires=128)})
            moves = (Move(0, 0, count, 1, 1), Move(2, 0, 128, 1, 1))
            if count == 127:
                result, = turn_outcomes(board, V, moves)
                self.assertEqual(result.board.at((1, 1)).vampires, 255)
            else:
                with self.assertRaises(UnsupportedPopulation):
                    turn_outcomes(board, V, moves)
        board = Board(1, 2, {(0, 0): Cell(vampires=128), (1, 0): Cell(humans=128)})
        with self.assertRaises(UnsupportedPopulation):
            turn_outcomes(board, V, (Move(0, 0, 128, 1, 0),))

    def test_full_255_record_turn(self):
        board = Board(2, 255, {(x, 0): Cell(vampires=1) for x in range(255)})
        moves = tuple(Move(x, 0, 1, x, 1) for x in range(255))
        result, = turn_outcomes(board, V, moves)
        self.assertEqual(total(result.board), 255)
        self.assertEqual(len(result.board.groups(V)), 255)
        self.assertTrue(all(y == 1 for x, y in result.board.cells))


class GenerationTests(unittest.TestCase):
    def test_exhaustive_generator_matches_independent_small_board_rule_filter(self):
        for species in Species:
            for a, b in ((1, 1), (2, 1), (2, 2)):
                board = Board(2, 2, {(0, 0): Cell(**{species.value: a}),
                                      (1, 0): Cell(**{species.value: b})})
                atoms = [Move(x, y, n, tx, ty) for (x, y), count in board.groups(species).items()
                         for tx, ty in board.neighbors((x, y)) for n in range(1, count + 1)]
                expected = set()
                for size in (1, 2):
                    for moves in combinations(atoms, size):
                        if len({(m.source, m.target) for m in moves}) != size:
                            continue
                        if {m.source for m in moves} & {m.target for m in moves}:
                            continue
                        if any(sum(m.count for m in moves if m.source == p) > n
                               for p, n in board.groups(species).items()):
                            continue
                        expected.add(canonical(moves))
                actual = list(exhaustive_turns(board, species))
                self.assertEqual(set(actual), expected)
                self.assertEqual(len(actual), len(set(actual)))

    def test_exhaustive_limit_is_explicit(self):
        board = Board(3, 3, {(1, 1): Cell(vampires=5)})
        with self.assertRaises(GenerationLimit):
            list(exhaustive_turns(board, V, max_nodes=5))

    def test_live_small_single_group_keeps_all_amounts_and_directions(self):
        board = Board(3, 3, {(1, 1): Cell(vampires=8)})
        candidates = candidate_turns(board, V)
        self.assertFalse(candidates.selective)
        self.assertEqual(set(candidates.turns), {(m,) for m in single_moves(board, V)})

    def test_live_combines_groups_without_shared_contested_arrivals(self):
        board = Board(3, 3, {(0, 0): Cell(vampires=3), (2, 0): Cell(vampires=3), (1, 1): Cell(humans=4)})
        candidates = candidate_turns(board, V, limit=200)
        self.assertTrue(any(len(t) == 2 for t in candidates.turns))
        self.assertTrue(candidates.selective)
        for turn in candidates.turns:
            validate_moves(board, V, turn)
            turn_outcomes(board, V, turn)

    def test_seeded_positions_obey_rules_limits_and_conservation(self):
        rng = random.Random(20261009)
        for _ in range(30):
            positions = rng.sample([(x, y) for x in range(4) for y in range(3)], 6)
            board = Board(3, 4, {p: Cell(**{field: rng.randrange(1, 4)})
                                 for p, field in zip(positions, ("vampires", "vampires", "werewolves", "werewolves", "humans", "humans"))})
            original = packed(board)
            for species in Species:
                candidates = candidate_turns(board, species, limit=12)
                self.assertTrue(0 < len(candidates.turns) <= 12)
                self.assertEqual(len(candidates.turns), len(set(candidates.turns)))
                for turn in candidates.turns:
                    validate_moves(board, species, turn)
                    outcomes = turn_outcomes(board, species, turn)
                    self.assertEqual(sum(o.probability for o in outcomes), 1)
                    self.assertTrue(all(total(o.board) <= total(board) for o in outcomes))
            self.assertEqual(packed(board), original)

    def test_critical_amount_thresholds_and_complements(self):
        self.assertTrue({9, 10, 20}.issubset(significant_amounts(30, Cell(humans=10), V)))
        self.assertTrue({15, 14, 7}.issubset(significant_amounts(30, Cell(werewolves=10), V)))

    def test_fallback_and_no_move_states(self):
        for species in Species:
            for shape in ((1, 2), (2, 1), (2, 3), (255, 255)):
                board = Board(*shape, {(0, 0): Cell(**{species.value: 255})})
                validate_moves(board, species, fallback_turn(board, species))
            for board in (Board(1, 1, {(0, 0): Cell(**{species.value: 1})}), Board(2, 2)):
                with self.assertRaises(NoLegalMove):
                    fallback_turn(board, species)
                self.assertEqual(candidate_turns(board, species).turns, ())

    def test_deadline_checked_inside_each_expensive_layer(self):
        checks = 0
        def expire():
            nonlocal checks
            checks += 1
            if checks >= 4:
                raise SearchTimeout
        board = Board(2, 2, {(0, 0): Cell(vampires=4), (1, 1): Cell(werewolves=4)})
        for action in (lambda: battle_distribution(20, 20, check=expire),
                       lambda: turn_outcomes(board, V, (Move(0, 0, 4, 1, 1),), check=expire),
                       lambda: candidate_turns(board, V, check=expire),
                       lambda: list(exhaustive_turns(board, V, check=expire))):
            checks = 0
            with self.assertRaises(SearchTimeout):
                action()
        with self.assertRaises(SearchTimeout):
            Deadline(1, clock=lambda: 1).check()


if __name__ == "__main__":
    unittest.main()
