"""Independent edge checks for live candidate construction and strategic policies."""

from itertools import product
import random
import unittest
from unittest.mock import patch

from vampires.budget import SearchTimeout
from vampires.model import Board, Cell, Species
from vampires.rules import Move, validate_moves
from vampires.simulation import (UnsupportedPopulation, iter_turn_outcomes,
                                 single_moves, turn_outcomes)
from vampires.strategy import cohesive_turns, portfolio_turns, resource_projection
from vampires.turns import (Candidates, candidate_turns, compatible_extension,
                            fallback_turn, significant_amounts)

V, W = Species.VAMPIRES, Species.WEREWOLVES


class MoveEdgeTests(unittest.TestCase):
    def test_capacity_boundary_partials_survive_amount_abstraction(self):
        for side in Species:
            for count, target, capacity in (
                    (20, Cell(**{side.value: 250}), 5),
                    (255, Cell(**{side.value: 253}), 2),
                    (200, Cell(humans=100), 155)):
                amounts = significant_amounts(count, target, side)
                self.assertIn(capacity, amounts)
                self.assertIn(count, amounts)  # Unresolved legal overflow remains explicit.
                board = Board(1, 2, {(0, 0): Cell(**{side.value: count}), (1, 0): target})
                turn = (Move(0, 0, capacity, 1, 0),)
                self.assertIn(turn, candidate_turns(board, side).turns)
                self.assertTrue(all(o.board.at((1, 0)).count(side) <= 255
                                    for o in iter_turn_outcomes(board, side, turn)))

    def test_fallback_prefers_representable_full_movement(self):
        for side in Species:
            board = Board(2, 2, {(0, 0): Cell(**{side.value: 200}),
                                 (1, 0): Cell(**{side.value: 100})})
            turn = fallback_turn(board, side)
            self.assertEqual(turn[0].count, 200)
            self.assertNotEqual(turn[0].target, (1, 0))
            turn_outcomes(board, side, turn)

    def test_fallback_can_use_partial_capacity_without_inventing_pass(self):
        for side in Species:
            board = Board(1, 2, {(0, 0): Cell(**{side.value: 255}),
                                 (1, 0): Cell(**{side.value: 253})})
            turn = fallback_turn(board, side)
            self.assertEqual(turn, (Move(0, 0, 2, 1, 0),))
            result, = turn_outcomes(board, side, turn)
            self.assertEqual(result.board.groups(side), {(0, 0): 253, (1, 0): 255})
            saturated = Board(1, 2, {(0, 0): Cell(**{side.value: 255}),
                                     (1, 0): Cell(**{side.value: 255})})
            unresolved = fallback_turn(saturated, side)
            validate_moves(saturated, side, unresolved)
            with self.assertRaises(UnsupportedPopulation):
                turn_outcomes(saturated, side, unresolved)

    def test_extension_matches_full_validator_and_live_shared_target_rule(self):
        for side, target in product(Species, (Cell(), Cell(humans=2), Cell(werewolves=2))):
            board = Board(2, 3, {(0, 0): Cell(**{side.value: 2}),
                                 (2, 0): Cell(**{side.value: 2}), (1, 1): target})
            atoms = list(single_moves(board, side))
            for old, new in product(atoms, repeat=2):
                try:
                    validate_moves(board, side, (old, new))
                    expected = old.source != new.source
                except ValueError:
                    expected = False
                contested = board.at(new.target).humans or board.at(new.target).count(side.opponent)
                expected &= not (contested and old.target == new.target)
                self.assertEqual(compatible_extension(board, side, (old,), new), expected,
                                 (side, old, new))

    def test_extension_enforces_the_255_record_packet_limit(self):
        board = Board(2, 255, {(x, 0): Cell(vampires=1) for x in range(255)})
        previous = tuple(Move(x, 0, 1, x, 1) for x in range(254))
        last = Move(254, 0, 1, 254, 1)
        self.assertTrue(compatible_extension(board, V, previous, last))
        validate_moves(board, V, previous + (last,))
        self.assertFalse(compatible_extension(board, V, previous + (last,), last))

    def test_seeded_boundary_positions_generate_unique_legal_whole_turns(self):
        rng = random.Random(2026101203)
        values = (1, 2, 8, 9, 127, 128, 254, 255)
        for case in range(12):
            positions = rng.sample([(x, y) for x in range(4) for y in range(3)], 7)
            board = Board(3, 4, {position: Cell(**{field: rng.choice(values)})
                                  for position, field in zip(positions, (
                                      "vampires", "vampires", "vampires", "werewolves",
                                      "werewolves", "humans", "humans"))})
            before = dict(board.cells)
            for side, generate in product(Species, (candidate_turns, cohesive_turns, portfolio_turns)):
                result = generate(board, side, limit=8)
                self.assertTrue(0 < len(result.turns) <= 8)
                self.assertEqual(len(result.turns), len(set(result.turns)))
                for turn in result.turns:
                    with self.subTest(case=case, side=side, generator=generate.__name__, turn=turn):
                        validate_moves(board, side, turn)
                        contested = [m.target for m in turn if board.at(m.target).humans or
                                     board.at(m.target).count(side.opponent)]
                        self.assertEqual(len(contested), len(set(contested)))
                        self.assertEqual(len({m.source for m in turn}), len(turn))
                        if generate is cohesive_turns:
                            self.assertTrue(result.selective)
                            self.assertTrue(all(m.count == board.at(m.source).count(side) for m in turn))
            self.assertEqual(board.cells, before)

    def test_thin_and_maximum_coordinate_boards(self):
        for rows, columns in ((1, 255), (255, 1), (255, 255)):
            for side in Species:
                board = Board(rows, columns, {(columns - 1, rows - 1): Cell(**{side.value: 255})})
                for generate in (candidate_turns, cohesive_turns, portfolio_turns):
                    for turn in generate(board, side, limit=4).turns:
                        validate_moves(board, side, turn)

    def test_flags_limits_and_amount_inputs_reject_malformed_values(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=1)})
        for name in ("limit", "per_group", "max_expansions"):
            for value in (True, 0, -1, 1.5, None):
                with self.assertRaises(ValueError):
                    candidate_turns(board, V, **{name: value})
        for name in ("whole_groups", "allow_partial", "protect_tactics"):
            for value in (1, None, "false"):
                with self.assertRaises(ValueError):
                    candidate_turns(board, V, **{name: value})
        for value in (True, 0, -1, 256, 1.5):
            with self.assertRaises(ValueError):
                significant_amounts(value, Cell(), V)
        self.assertEqual(significant_amounts(9, Cell(), "vampires"), significant_amounts(9, Cell(), V))

    def test_whole_group_abstraction_is_always_identified(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        self.assertTrue(cohesive_turns(board, V).selective)

    def test_portfolio_timeout_retains_valid_base_without_boardwide_revalidation(self):
        board = Board(30, 30, {(x, y): Cell(vampires=1) for x in range(30) for y in range(30)})
        base = Candidates(((Move(0, 0, 1, 1, 0),),), True)
        checks = 0
        def expire():
            nonlocal checks
            checks += 1
            if checks >= 4:
                raise SearchTimeout
        with patch("vampires.strategy.candidate_turns", return_value=base):
            result = portfolio_turns(board, V, check=expire, allow_partial=True)
        self.assertEqual(checks, 4)
        self.assertTrue(result.truncated)
        self.assertEqual(result.turns, base.turns)
        validate_moves(board, V, result.turns[0])

    def test_resource_scan_honors_expired_deadline_before_board_work(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        with patch.object(board, "groups", side_effect=AssertionError("Must check deadline first")):
            with self.assertRaises(SearchTimeout):
                resource_projection(board, V, check=lambda: (_ for _ in ()).throw(SearchTimeout()))


if __name__ == "__main__":
    unittest.main()
