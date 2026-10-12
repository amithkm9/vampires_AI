"""Bounded exhaustive invariants; these are local-model tests, not server parity.

Shared contested arrivals remain explicitly unverified. No sampled frequency is
used as an assertion: every seeded sample must lie in exact successor support.
"""

from fractions import Fraction
from itertools import product
import random
import unittest

from vampires.model import Board, Cell, Species
from vampires.rules import Move, sample_battle, validate_moves
from vampires.simulation import (AmbiguousBattle, UnsupportedPopulation,
                                 battle_distribution, iter_turn_outcomes,
                                 sample_turn, single_move_outcomes, single_moves,
                                 turn_outcomes)
from vampires.turns import exhaustive_turns


AUDIT_COUNTS = {}


def packed(board):
    return (board.rows, board.columns,
            tuple(sorted((p, c.humans, c.vampires, c.werewolves)
                         for p, c in board.cells.items())))


def population(board):
    return sum(c.humans + c.vampires + c.werewolves for c in board.cells.values())


def probability_map(outcomes):
    result = {}
    for outcome in outcomes:
        key = packed(outcome.board)
        result[key] = result.get(key, Fraction(0)) + outcome.probability
    return result


def written_expectations(a, d, humans):
    """Independent rational statement of the brief's threshold/expectation rules."""
    if humans and a >= d:
        return Fraction(a + d), Fraction(0)
    if not humans and 2 * a >= 3 * d:
        return Fraction(a), Fraction(0)
    if not humans and 2 * d >= 3 * a:
        return Fraction(0), Fraction(d)
    p = Fraction(a, 2 * d) if a <= d else Fraction(2 * a - d, 2 * d)
    return p * p * (a + (d if humans else 0)), (1 - p) ** 2 * d


def individual_event_oracle(a, d, humans):
    """Enumerate winner and every creature's survival, without binomial math."""
    if humans and a >= d:
        return {(a + d, 0): Fraction(1)}
    if not humans and 2 * a >= 3 * d:
        return {(a, 0): Fraction(1)}
    if not humans and 2 * d >= 3 * a:
        return {(0, d): Fraction(1)}
    p = Fraction(a, 2 * d) if a <= d else Fraction(2 * a - d, 2 * d)
    result = {}
    for attacking_winner, chance, creatures in ((True, p, a + (d if humans else 0)),
                                               (False, 1 - p, d)):
        for survivors in product((False, True), repeat=creatures):
            probability = chance
            for survived in survivors:
                probability *= chance if survived else 1 - chance
            count = sum(survivors)
            key = (count, 0) if attacking_winner else (0, count)
            result[key] = result.get(key, Fraction(0)) + probability
    return result


class CombatInvariantTests(unittest.TestCase):
    def test_full_individual_event_oracle_for_tiny_battles(self):
        cases = 0
        for humans, a, d in product((False, True), range(1, 5), range(1, 5)):
            with self.subTest(humans=humans, attackers=a, defenders=d):
                self.assertEqual(battle_distribution(a, d, humans=humans),
                                 individual_event_oracle(a, d, humans))
            cases += 1
        AUDIT_COUNTS["individual_event_battles"] = cases

    def test_threshold_neighbors_and_byte_extremes_have_exact_mass_and_expectations(self):
        pairs = set()
        for d in (*range(1, 25), 127, 128, 169, 170, 171, 254, 255):
            for threshold in (d, (3 * d + 1) // 2, (2 * d) // 3):
                for a in (threshold - 1, threshold, threshold + 1):
                    if 1 <= a <= 255:
                        pairs.add((a, d))
        pairs.update(((1, 255), (255, 1), (255, 255)))
        cases = 0
        for humans, (a, d) in product((False, True), sorted(pairs)):
            with self.subTest(humans=humans, attackers=a, defenders=d):
                actual = battle_distribution(a, d, humans=humans)
                self.assertEqual(sum(actual.values()), 1)
                self.assertTrue(all(p > 0 and (x == 0 or y == 0)
                                    for (x, y), p in actual.items()))
                expected_a, expected_d = written_expectations(a, d, humans)
                self.assertEqual(sum(x * p for (x, _), p in actual.items()), expected_a)
                self.assertEqual(sum(y * p for (_, y), p in actual.items()), expected_d)
                self.assertTrue(all(x + y <= a + d for x, y in actual))
            cases += 1
        AUDIT_COUNTS["threshold_and_byte_battles"] = cases

    def test_seeded_battle_samples_are_in_exact_support_for_both_defender_types(self):
        rng = random.Random(2026101201)
        cases = samples = 0
        for humans, a, d in product((False, True), range(1, 8), range(1, 8)):
            support = battle_distribution(a, d, humans=humans)
            for _ in range(16):
                self.assertIn(sample_battle(a, d, rng, humans=humans), support)
                samples += 1
            cases += 1
        AUDIT_COUNTS["sampled_battle_cases"] = cases
        AUDIT_COUNTS["battle_samples"] = samples


class JointModelInvariantTests(unittest.TestCase):
    def assert_safe_successor(self, source, successor, species):
        self.assertEqual((source.rows, source.columns), (successor.rows, successor.columns))
        self.assertLessEqual(population(successor), population(source))
        humans_before = sum(c.humans for c in source.cells.values())
        humans_after = sum(c.humans for c in successor.cells.values())
        self.assertLessEqual(humans_after, humans_before)
        self.assertLessEqual(sum(successor.groups(species.opponent).values()),
                             sum(source.groups(species.opponent).values()))
        self.assertLessEqual(sum(successor.groups(species).values()),
                             sum(source.groups(species).values()) + humans_before - humans_after)
        for position, cell in successor.cells.items():
            successor.check_position(position)
            self.assertEqual(sum(c > 0 for c in (cell.humans, cell.vampires, cell.werewolves)), 1)
            self.assertLessEqual(max(cell.humans, cell.vampires, cell.werewolves), 255)

    def test_exhaustive_tiny_joint_turns_match_stream_and_samples(self):
        rng = random.Random(2026101202)
        boards = turns = ambiguous = samples = successors = 0
        for species, a, b, h, d in product(Species, range(1, 3), range(1, 3), range(3), range(1, 3)):
            board = Board(2, 2, {(0, 0): Cell(**{species.value: a}),
                                 (1, 0): Cell(**{species.value: b}),
                                 (0, 1): Cell(humans=h),
                                 (1, 1): Cell(**{species.opponent.value: d})})
            original = packed(board)
            boards += 1
            for turn in exhaustive_turns(board, species):
                turns += 1
                validate_moves(board, species, turn)
                try:
                    eager = turn_outcomes(board, species, turn)
                except AmbiguousBattle:
                    ambiguous += 1
                    # We must fail consistently, including deterministic shared
                    # attacks; aggregation is a separate, unverified assumption.
                    with self.assertRaises(AmbiguousBattle):
                        tuple(iter_turn_outcomes(board, species, turn))
                    with self.assertRaises(AmbiguousBattle):
                        sample_turn(board, species, turn, rng)
                    self.assertEqual(packed(board), original)
                    continue
                support = probability_map(eager)
                self.assertEqual(sum(support.values()), 1)
                self.assertEqual(probability_map(iter_turn_outcomes(board, species, turn)), support)
                self.assertEqual(probability_map(turn_outcomes(board, species, tuple(reversed(turn)))), support)
                for outcome in eager:
                    self.assertGreater(outcome.probability, 0)
                    self.assert_safe_successor(board, outcome.board, species)
                    touched = {move.source for move in turn} | {move.target for move in turn}
                    for position in set(board.cells) | set(outcome.board.cells):
                        if position not in touched:
                            self.assertEqual(outcome.board.at(position), board.at(position))
                    for source in {move.source for move in turn}:
                        left = board.at(source).count(species) - sum(move.count for move in turn if move.source == source)
                        self.assertEqual(outcome.board.at(source), Cell(**{species.value: left}))
                    successors += 1
                if len(turn) == 1:
                    self.assertEqual(probability_map(single_move_outcomes(board, species, turn[0])), support)
                for _ in range(3):
                    sample = sample_turn(board, species, turn, rng)
                    self.assertIn(packed(sample), support)
                    samples += 1
                self.assertEqual(packed(board), original)
        AUDIT_COUNTS.update(exhaustive_boards=boards, exhaustive_joint_turns=turns,
                            rejected_ambiguous_turns=ambiguous, exact_joint_successors=successors,
                            joint_successor_samples=samples)

    def test_shared_empty_and_friendly_merges_conserve_population_exactly(self):
        cases = 0
        for species, a, b, resident in product(Species, range(1, 4), range(1, 4), range(3)):
            board = Board(2, 3, {(0, 0): Cell(**{species.value: a}),
                                 (2, 0): Cell(**{species.value: b}),
                                 (1, 1): Cell(**{species.value: resident})})
            for sent_a, sent_b in product(range(1, a + 1), range(1, b + 1)):
                moves = (Move(0, 0, sent_a, 1, 1), Move(2, 0, sent_b, 1, 1))
                result, = iter_turn_outcomes(board, species, moves)
                self.assertEqual(result.probability, 1)
                self.assertEqual(population(result.board), population(board))
                self.assertEqual(result.board.at((1, 1)).count(species), sent_a + sent_b + resident)
                self.assertEqual(result.board.at((0, 0)).count(species), a - sent_a)
                self.assertEqual(result.board.at((2, 0)).count(species), b - sent_b)
                cases += 1
        AUDIT_COUNTS["deterministic_merge_turns"] = cases

    def test_byte_boundary_accepts_255_and_rejects_every_possible_overflow(self):
        cases = 0
        for species in Species:
            for a, defender, expect_overflow in ((127, 128, False), (128, 127, False), (128, 128, True)):
                for field in (species.value, "humans"):
                    # 127 attacking 128 humans has a rare 255-survivor outcome;
                    # 128 attacking 128 must reject the certain 256 conversion.
                    board = Board(1, 2, {(0, 0): Cell(**{species.value: a}),
                                         (1, 0): Cell(**{field: defender})})
                    move = Move(0, 0, a, 1, 0)
                    original = packed(board)
                    operations = (lambda: single_move_outcomes(board, species, move),
                                  lambda: turn_outcomes(board, species, (move,)),
                                  lambda: tuple(iter_turn_outcomes(board, species, (move,))),
                                  lambda: sample_turn(board, species, (move,), random.Random(123)))
                    if expect_overflow:
                        for operation in operations:
                            with self.assertRaises(UnsupportedPopulation):
                                operation()
                    else:
                        expected = probability_map(operations[0]())
                        self.assertEqual(sum(expected.values()), 1)
                        self.assertEqual(probability_map(operations[1]()), expected)
                        self.assertEqual(probability_map(operations[2]()), expected)
                        self.assertIn(packed(operations[3]()), expected)
                        column = 2 if species == Species.VAMPIRES else 3
                        self.assertTrue(any(record[column] == 255
                                            for state in expected for record in state[2]))
                    self.assertEqual(packed(board), original)
                    cases += 1
        AUDIT_COUNTS["byte_boundary_transitions"] = cases

    def test_streamed_boards_remain_independent_when_consumed_incrementally(self):
        for species in Species:
            board = Board(1, 4, {(0, 0): Cell(**{species.value: 1}),
                                 (3, 0): Cell(**{species.value: 1}),
                                 (1, 0): Cell(**{species.opponent.value: 1}),
                                 (2, 0): Cell(**{species.opponent.value: 1})})
            moves = (Move(0, 0, 1, 1, 0), Move(3, 0, 1, 2, 0))
            original = packed(board)
            expected = probability_map(turn_outcomes(board, species, moves))
            stream = iter_turn_outcomes(board, species, moves)
            first = next(stream)
            first_identity = packed(first.board)
            first.board.cells.clear()
            remainder = probability_map(stream)
            remainder[first_identity] = remainder.get(first_identity, Fraction(0)) + first.probability
            self.assertEqual(remainder, expected)
            self.assertEqual(packed(board), original)
            partial = iter_turn_outcomes(board, species, moves)
            next(partial)
            partial.close()
            self.assertEqual(packed(board), original)

    def test_seeded_small_board_trajectories_remain_in_exact_support(self):
        total_plies = 0
        for seed in range(2026101210, 2026101222):
            rng = random.Random(seed)
            positions = rng.sample([(x, y) for x in range(4) for y in range(3)], 6)
            fields = ("vampires", "vampires", "werewolves", "werewolves", "humans", "humans")
            board = Board(3, 4, {p: Cell(**{field: rng.randint(1, 3)})
                                 for p, field in zip(positions, fields)})
            side = tuple(Species)[seed % 2]
            for _ in range(40):
                if not board.groups(side) or not board.groups(side.opponent):
                    break
                turn = (rng.choice(tuple(single_moves(board, side))),)
                original = packed(board)
                eager = probability_map(turn_outcomes(board, side, turn))
                self.assertEqual(probability_map(iter_turn_outcomes(board, side, turn)), eager)
                successor = sample_turn(board, side, turn, rng)
                self.assertIn(packed(successor), eager)
                self.assert_safe_successor(board, successor, side)
                self.assertEqual(packed(board), original)
                board = successor
                side = side.opponent
                total_plies += 1
        AUDIT_COUNTS["seeded_trajectories"] = 12
        AUDIT_COUNTS["trajectory_plies"] = total_plies


if __name__ == "__main__":
    unittest.main()
