"""Hybrid legality, deadline and exact finite-horizon split regressions."""

from fractions import Fraction
from itertools import product
import random
import unittest
from unittest.mock import patch

from vampires.budget import SearchTimeout
from vampires.endgame import ExactSolver
from vampires.experimental.hybrid import hybrid_turns
from vampires.model import Board, Cell, Species
from vampires.rules import Move, validate_moves
from vampires.search import state_key
from vampires.strategy import cohesive_turns
from vampires.turns import Candidates

V, W = Species.VAMPIRES, Species.WEREWOLVES


class HybridGenerationTests(unittest.TestCase):
    def test_partial_human_captures_keep_the_whole_backbone(self):
        for side in Species:
            board = Board(1, 6, {(2, 0): Cell(**{side.value: 4}),
                                 (1, 0): Cell(humans=2), (3, 0): Cell(humans=2),
                                 (5, 0): Cell(**{side.opponent.value: 7})})
            result = hybrid_turns(board, side)
            self.assertTrue(set(cohesive_turns(board, side).turns) <= set(result.turns))
            self.assertIn((Move(2, 0, 2, 1, 0),), result.turns)
            self.assertIn((Move(2, 0, 2, 3, 0),), result.turns)
            self.assertTrue(result.selective)
            self.assertFalse(result.truncated)

    def test_risky_and_guaranteed_partial_attack_thresholds(self):
        for side in Species:
            board = Board(1, 2, {(0, 0): Cell(**{side.value: 20}),
                                 (1, 0): Cell(**{side.opponent.value: 10})})
            turns = hybrid_turns(board, side).turns
            for amount in (7, 10, 14, 15, 19, 20):
                self.assertIn((Move(0, 0, amount, 1, 0),), turns)

    def test_small_risky_human_and_monster_partials_remain_legal_options(self):
        for target in (Cell(humans=5), Cell(werewolves=5)):
            board = Board(1, 2, {(0, 0): Cell(vampires=4), (1, 0): target})
            turns = hybrid_turns(board, V).turns
            for amount in range(1, 5):
                self.assertIn((Move(0, 0, amount, 1, 0),), turns)

    def test_reinforcement_uses_capture_and_combat_thresholds(self):
        board = Board(3, 3, {(0, 1): Cell(vampires=20), (1, 1): Cell(vampires=3),
                             (2, 0): Cell(werewolves=5), (2, 2): Cell(humans=9)})
        turns = hybrid_turns(board, V, limit=128).turns
        self.assertIn((Move(0, 1, 5, 1, 1),), turns)  # Stack 3 -> 8, dominates 5.
        self.assertIn((Move(0, 1, 6, 1, 1),), turns)  # Stack 3 -> 9, affords house.

    def test_local_two_house_race_can_separate_toward_empty_cell(self):
        board = Board(4, 5, {(1, 1): Cell(vampires=8), (3, 1): Cell(humans=2),
                             (0, 2): Cell(humans=3), (4, 3): Cell(werewolves=1)})
        self.assertIn((Move(1, 1, 2, 2, 1),), hybrid_turns(board, V).turns)

    def test_threatened_source_can_keep_a_reserve_when_separating(self):
        board = Board(3, 3, {(1, 1): Cell(vampires=8), (2, 1): Cell(werewolves=6)})
        turns = hybrid_turns(board, V).turns
        self.assertIn((Move(1, 1, 7, 0, 1),), turns)
        self.assertIn((Move(1, 1, 3, 0, 1),), turns)  # Retain 5, avoids certain loss to 6.

    def test_partial_record_can_refine_a_legal_joint_turn(self):
        board = Board(1, 6, {(1, 0): Cell(vampires=4), (0, 0): Cell(humans=2),
                             (4, 0): Cell(vampires=2), (5, 0): Cell(werewolves=1)})
        self.assertIn((Move(1, 0, 2, 0, 0), Move(4, 0, 2, 5, 0)), hybrid_turns(board, V).turns)

    def test_capacity_boundary_partials_are_supported_without_removing_whole_moves(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=200), (1, 0): Cell(humans=100)})
        turns = hybrid_turns(board, V).turns
        for amount in (100, 155, 200):
            self.assertIn((Move(0, 0, amount, 1, 0),), turns)

    def test_cohesive_backbone_survives_a_full_cap_and_tiny_caps(self):
        board = Board(3, 4, {(0, 0): Cell(vampires=4), (3, 0): Cell(vampires=3),
                             (1, 1): Cell(humans=2), (2, 1): Cell(werewolves=3)})
        for limit in (1, 2, 8, 16, 64):
            base = cohesive_turns(board, V, limit=limit)
            hybrid = hybrid_turns(board, V, limit=limit)
            preserved = min(len(base.turns), limit - min(limit - 1, max(1, limit // 4)))
            self.assertTrue(set(base.turns[:preserved]) <= set(hybrid.turns))
            self.assertTrue(0 < len(hybrid.turns) <= limit)
            self.assertEqual(len(hybrid.turns), len(set(hybrid.turns)))

    def test_deadline_and_work_cap_preserve_finished_legal_candidates(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=4), (1, 0): Cell(humans=2),
                             (2, 0): Cell(werewolves=3)})
        base = Candidates(((Move(0, 0, 4, 1, 0),),), True)
        calls = 0
        def expire():
            nonlocal calls
            calls += 1
            if calls >= 14:
                raise SearchTimeout
        with patch("vampires.experimental.hybrid.cohesive_turns", return_value=base):
            partial = hybrid_turns(board, V, check=expire, allow_partial=True)
            capped = hybrid_turns(board, V, max_expansions=1)
            calls = 0
            with self.assertRaises(SearchTimeout):
                hybrid_turns(board, V, check=expire)
        for result in (partial, capped):
            self.assertTrue(result.truncated)
            self.assertIn(base.turns[0], result.turns)
            for turn in result.turns:
                validate_moves(board, V, turn)

    def test_255_record_backbone_cannot_acquire_a_256th_record(self):
        cells = {(x, 0): Cell(vampires=1) for x in range(255)}
        cells.update({(0, 2): Cell(vampires=2), (1, 2): Cell(werewolves=1)})
        board = Board(3, 255, cells)
        whole = tuple(Move(x, 0, 1, x, 1) for x in range(255))
        base = Candidates((whole,), True)
        with patch("vampires.experimental.hybrid.cohesive_turns", return_value=base):
            result = hybrid_turns(board, V)
        self.assertIn(whole, result.turns)
        self.assertTrue(all(len(turn) <= 255 for turn in result.turns))
        for turn in result.turns:
            validate_moves(board, V, turn)

    def test_seeded_boundary_turns_obey_rules_and_live_semantic_limits(self):
        rng = random.Random(2026101301)
        for case in range(12):
            positions = rng.sample([(x, y) for x in range(4) for y in range(3)], 7)
            board = Board(3, 4, {position: Cell(**{field: rng.choice((1, 2, 8, 9, 127, 255))})
                                  for position, field in zip(positions, ("vampires", "vampires", "vampires",
                                                                       "werewolves", "werewolves", "humans", "humans"))})
            before = state_key(board)
            for side, limit in product(Species, (2, 8, 64)):
                result = hybrid_turns(board, side, limit=limit)
                self.assertTrue(0 < len(result.turns) <= limit)
                for turn in result.turns:
                    with self.subTest(case=case, side=side, limit=limit):
                        validate_moves(board, side, turn)
                        self.assertEqual(len(turn), len({m.source for m in turn}))
                        targets = [m.target for m in turn if board.at(m.target).humans or
                                   board.at(m.target).count(side.opponent)]
                        self.assertEqual(len(targets), len(set(targets)))
            self.assertEqual(before, state_key(board))

    def test_species_swap_is_equivariant_and_ample_work_is_reproducible(self):
        a = Board(2, 4, {(0, 0): Cell(vampires=5), (3, 0): Cell(werewolves=4),
                          (1, 1): Cell(humans=2), (2, 1): Cell(humans=3)})
        b = Board(2, 4, {p: Cell(c.humans, c.werewolves, c.vampires) for p, c in a.cells.items()})
        self.assertEqual(hybrid_turns(a, V), hybrid_turns(b, W))
        self.assertEqual(hybrid_turns(a, V), hybrid_turns(a, V))

    def test_no_pass_is_invented_on_unplayable_boards(self):
        for board in (Board(1, 1, {(0, 0): Cell(vampires=2)}), Board(2, 2)):
            self.assertEqual(hybrid_turns(board, V).turns, ())

    def test_public_limits_and_flags_validate_before_generation(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=2)})
        for name, value in (("limit", 0), ("per_group", True), ("max_expansions", 1.5),
                            ("protect_tactics", "yes"), ("allow_partial", 1)):
            with self.assertRaises(ValueError):
                hybrid_turns(board, V, **{name: value})


class ExactHybridRegressions(unittest.TestCase):
    def test_capture_reserve_repairs_a_joint_two_ply_split_omission(self):
        # Development seed 2114 from a fixed 2101..2132 sweep of 1x5 boards.
        # Two sources have disjoint neighborhoods, so the complete eager tree
        # needs no shared-contested-target aggregation assumption.
        board = Board(1, 5, {(1, 0): Cell(vampires=2), (4, 0): Cell(vampires=4),
                             (2, 0): Cell(werewolves=5), (3, 0): Cell(humans=3)})
        full = ExactSolver(V, shared_target="reject").action_values(board, V, 2)
        choices = []
        for generator in (cohesive_turns, hybrid_turns):
            solver = ExactSolver(V, shared_target="reject",
                                 turn_factory=lambda b, s: generator(b, s, limit=8).turns)
            choices.append(solver.solve(board, V, 2).moves)
        self.assertEqual(full[choices[0]].score, Fraction(6411411, 7529536))
        self.assertEqual(full[choices[1]].score, Fraction(2707859, 2985984))
        self.assertEqual(full[choices[1]].score, max(value.score for value in full.values()))
        self.assertEqual(choices[1], (Move(1, 0, 2, 0, 0), Move(4, 0, 3, 3, 0)))

    def test_two_house_split_fixes_exact_three_ply_omission_for_both_species(self):
        # Development witness. No shared-target battle occurs in this complete
        # tiny tree; 'reject' would fail if there were one. The cutoff is supplied
        # explicitly and does not model the live unknown daylight deadline.
        for side in Species:
            board = Board(1, 6, {(2, 0): Cell(**{side.value: 4}),
                                 (1, 0): Cell(humans=2), (3, 0): Cell(humans=2),
                                 (5, 0): Cell(**{side.opponent.value: 7})})
            full = ExactSolver(side, shared_target="reject").action_values(board, side, 3)
            best = max(value.score for value in full.values())
            whole = ExactSolver(side, shared_target="reject", turn_factory=lambda b, s: cohesive_turns(b, s).turns)
            hybrid = ExactSolver(side, shared_target="reject", turn_factory=lambda b, s: hybrid_turns(b, s).turns)
            previous = whole.solve(board, side, 3)
            improved = hybrid.solve(board, side, 3)
            self.assertEqual(best, 1)
            self.assertEqual(full[previous.moves].score, Fraction(2431995, 5764801))
            self.assertEqual(best - full[previous.moves].score, Fraction(3332806, 5764801))
            self.assertEqual(full[improved.moves].score, 1)
            self.assertEqual(improved.outcome.win, 1)
            self.assertEqual(improved.moves[0].count, 2)

    def test_same_partial_reply_is_seen_from_the_opponents_perspective(self):
        board = Board(1, 6, {(2, 0): Cell(vampires=4), (1, 0): Cell(humans=2),
                             (3, 0): Cell(humans=2), (5, 0): Cell(werewolves=7)})
        reference = ExactSolver(W, shared_target="reject").solve(board, V, 3)
        whole = ExactSolver(W, shared_target="reject", turn_factory=lambda b, s: cohesive_turns(b, s).turns)
        hybrid = ExactSolver(W, shared_target="reject", turn_factory=lambda b, s: hybrid_turns(b, s).turns)
        self.assertEqual(reference.outcome.score, 0)
        self.assertEqual(whole.solve(board, V, 3).outcome.score, Fraction(3332806, 5764801))
        self.assertEqual(hybrid.solve(board, V, 3).outcome.score, 0)


if __name__ == "__main__":
    unittest.main()
