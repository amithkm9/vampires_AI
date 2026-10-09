import io
from pathlib import Path
import random
import socket
import unittest

from vampires.model import Board, Cell, GameSession, Species, load_map
from vampires.protocol import (
    Client, ConnectionClosed, Message, ProtocolError, encode_moves,
    encode_name, read_message, recv_exact,
)
from vampires.rules import Move, battle_odds, sample_battle, validate_moves

ROOT = Path(__file__).resolve().parents[1]
V = Species.VAMPIRES
W = Species.WEREWOLVES


class FragmentedStream:
    def __init__(self, data, chunk_size=1):
        self.data = io.BytesIO(data)
        self.chunk_size = chunk_size

    def recv(self, count):
        return self.data.read(min(count, self.chunk_size))


class BoardTests(unittest.TestCase):
    def test_supplied_rectangular_map_and_coordinates(self):
        board = load_map(ROOT / "maps/testmap2.xml")
        self.assertEqual((board.rows, board.columns), (15, 29))
        self.assertEqual(board.at((28, 14)).vampires, 10)
        self.assertEqual(board.at((0, 0)).werewolves, 10)
        self.assertEqual(sum(c.humans for c in board.cells.values()), 32)

    def test_supplied_trap_map(self):
        board = load_map(ROOT / "maps/thetrap.xml")
        self.assertEqual((board.rows, board.columns), (5, 10))
        self.assertEqual(sum(c.humans for c in board.cells.values()), 9)
        self.assertEqual(board.groups(W), {(4, 1): 4})

    def test_eight_neighbors_interior_three_at_corner(self):
        board = Board(3, 4)
        self.assertEqual(len(board.neighbors((1, 1))), 8)
        self.assertEqual(set(board.neighbors((0, 0))), {(1, 0), (0, 1), (1, 1)})

    def test_rows_and_columns_are_not_transposed(self):
        board = Board(2, 4)
        board.check_position((3, 1))
        with self.assertRaises(ValueError):
            board.check_position((1, 3))

    def test_updates_replace_counts_and_clear_cells(self):
        board = Board(3, 3, {(0, 0): Cell(vampires=10), (2, 2): Cell(humans=2)})
        board.apply_updates(((0, 0, 0, 7, 0), (2, 2, 0, 0, 0)))
        self.assertEqual(board.groups(V), {(0, 0): 7})
        self.assertNotIn((2, 2), board.cells)

    def test_invalid_update_does_not_partially_mutate_board(self):
        board = Board(3, 3, {(0, 0): Cell(vampires=10)})
        with self.assertRaises(ValueError):
            board.apply_updates(((0, 0, 0, 7, 0), (4, 4, 0, 1, 0)))
        self.assertEqual(board.at((0, 0)).vampires, 10)

    def test_invalid_population_or_mixed_cell(self):
        for counts in ({"humans": -1}, {"vampires": 256},
                       {"humans": 1, "vampires": 1}, {"vampires": True}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                Cell(**counts)

    def test_invalid_dimensions(self):
        for rows, columns in [(0, 2), (2, 256), (-1, 2)]:
            with self.subTest(shape=(rows, columns)), self.assertRaises(ValueError):
                Board(rows, columns)


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.board = Board(4, 5, {(1, 1): Cell(vampires=10),
                                  (3, 1): Cell(vampires=3),
                                  (4, 3): Cell(werewolves=20),
                                  (0, 2): Cell(humans=20)})

    def test_all_eight_directions_and_partial_moves(self):
        for target in self.board.neighbors((1, 1)):
            with self.subTest(target=target):
                validate_moves(self.board, V, [Move(1, 1, 4, *target)])

    def test_rule_1_reject_empty_ply(self):
        with self.assertRaises(ValueError):
            validate_moves(self.board, V, [])

    def test_rule_2_reject_opponent_human_and_empty_sources(self):
        for move in [Move(4, 3, 1, 3, 3), Move(0, 2, 1, 0, 1), Move(0, 0, 1, 0, 1)]:
            with self.subTest(move=move), self.assertRaises(ValueError):
                validate_moves(self.board, V, [move])

    def test_rule_3_aggregate_outgoing_population(self):
        with self.assertRaises(ValueError):
            validate_moves(self.board, V, [Move(1, 1, 6, 0, 0), Move(1, 1, 5, 0, 1)])

    def test_rule_4_reject_non_adjacent_stay_and_out_of_bounds(self):
        for target in [(1, 1), (3, 3), (5, 1)]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_moves(self.board, V, [Move(1, 1, 1, *target)])

    def test_rule_5_reject_chaining_in_either_record_order(self):
        board = Board(3, 3, {(0, 0): Cell(vampires=5), (1, 0): Cell(vampires=5)})
        moves = [Move(0, 0, 2, 1, 0), Move(1, 0, 2, 2, 0)]
        for ordered in (moves, list(reversed(moves))):
            with self.assertRaises(ValueError):
                validate_moves(board, V, ordered)

    def test_rule_5_reject_swap(self):
        board = Board(2, 2, {(0, 0): Cell(vampires=5), (1, 0): Cell(vampires=5)})
        with self.assertRaises(ValueError):
            validate_moves(board, V, [Move(0, 0, 5, 1, 0), Move(1, 0, 5, 0, 0)])

    def test_rule_6_reject_zero_and_invalid_move_counts(self):
        for count in (0, -1, 256, 1.5, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                Move(0, 0, count, 1, 1)

    def test_shared_destination_allows_merging(self):
        validate_moves(self.board, V, [Move(1, 1, 10, 2, 1), Move(3, 1, 3, 2, 1)])

    def test_split_budget_and_conservative_record_limit(self):
        moves = [Move(1, 1, 6, 0, 0), Move(1, 1, 4, 0, 1)]
        validate_moves(self.board, V, moves)
        board = Board(3, 3, {(1, 1): Cell(vampires=10)})
        with self.assertRaises(ValueError):
            validate_moves(board, V, moves)
        validate_moves(board, V, moves, strict_group_limit=False)

    def test_risky_attacks_are_legal(self):
        validate_moves(self.board, V, [Move(1, 1, 1, 0, 2)])
        self.board.apply_updates(((4, 2, 0, 0, 20),))
        validate_moves(self.board, V, [Move(3, 1, 1, 4, 2)])

    def test_either_species_can_be_ours(self):
        validate_moves(self.board, W, [Move(4, 3, 20, 3, 2)])


class BattleTests(unittest.TestCase):
    def test_equal_humans_convert_without_random_battle(self):
        odds = battle_odds(4, 4, humans=True)
        self.assertEqual((odds.attacker_win_probability, odds.expected_attackers), (1, 8))
        self.assertEqual(sample_battle(4, 4, None, humans=True), (8, 0))

    def test_monster_guarantee_at_exact_three_to_two_ratio(self):
        self.assertEqual(sample_battle(6, 4, None), (6, 0))
        self.assertEqual(sample_battle(4, 6, None), (0, 6))

    def test_equal_monster_groups_are_random(self):
        odds = battle_odds(10, 10)
        self.assertEqual(odds.attacker_win_probability, 0.5)
        self.assertEqual((odds.expected_attackers, odds.expected_defenders), (2.5, 2.5))

    def test_random_probability_on_either_side_of_equal(self):
        self.assertAlmostEqual(battle_odds(8, 10).attacker_win_probability, 0.4)
        self.assertAlmostEqual(battle_odds(12, 10).attacker_win_probability, 0.7)

    def test_humans_have_no_guaranteed_defender_ratio(self):
        odds = battle_odds(2, 10, humans=True)
        self.assertEqual(odds.attacker_win_probability, 0.1)
        self.assertAlmostEqual(odds.expected_attackers, 0.12)
        self.assertAlmostEqual(odds.expected_defenders, 8.1)

    def test_human_survivors_are_converted_only_when_attackers_win(self):
        class Draws:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        # P = 2 / (2*4) = .25: win, then 3 of 6 potential survivors.
        self.assertEqual(sample_battle(2, 4, Draws([0.1, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9]),
                                       humans=True), (3, 0))
        # Lose, then 3 of 4 humans survive with probability .75.
        self.assertEqual(sample_battle(2, 4, Draws([0.9, 0.1, 0.8, 0.1, 0.1]),
                                       humans=True), (0, 3))

    def test_seeded_sampling_and_mutually_exclusive_survivors(self):
        a, b = random.Random(7), random.Random(7)
        outcomes = [sample_battle(8, 10, a) for _ in range(50)]
        self.assertEqual(outcomes, [sample_battle(8, 10, b) for _ in range(50)])
        self.assertTrue(all(x * y == 0 and 0 <= x <= 8 and 0 <= y <= 10 for x, y in outcomes))

    def test_invalid_battle_inputs(self):
        for a, d in [(0, 1), (1, 0), (-1, 2), (1.5, 2)]:
            with self.subTest(a=a, d=d), self.assertRaises(ValueError):
                battle_odds(a, d)


class ProtocolTests(unittest.TestCase):
    def test_fragmented_and_coalesced_packets(self):
        stream = FragmentedStream(b"SET\x05\x0aHUM\x01\x09\x04HME\x04\x03"
                                  b"MAP\x01\x04\x03\x00\x04\x00UPD\x00ENDBYE")
        expected = [Message("SET", (5, 10)), Message("HUM", ((9, 4),)),
                    Message("HME", (4, 3)), Message("MAP", ((4, 3, 0, 4, 0),)),
                    Message("UPD"), Message("END"), Message("BYE")]
        self.assertEqual([read_message(stream) for _ in expected], expected)

    def test_eof_in_header_and_payload_raises(self):
        for data in (b"", b"SE", b"SET\x01", b"UPD\x01\x00\x00"):
            with self.subTest(data=data), self.assertRaises(ConnectionClosed):
                read_message(FragmentedStream(data))

    def test_unknown_and_non_ascii_commands(self):
        for data in (b"BAD", b"\xffET"):
            with self.assertRaises(ProtocolError):
                read_message(FragmentedStream(data))

    def test_zero_length_read(self):
        self.assertEqual(recv_exact(FragmentedStream(b""), 0), b"")

    def test_name_ascii_and_one_byte_length(self):
        self.assertEqual(encode_name("AI"), b"NME\x02AI")
        self.assertEqual(encode_name("A" * 255)[:4], b"NME\xff")
        for name in ("", "A" * 256, "\u00e9"):
            with self.subTest(name=name[:10]), self.assertRaises(ProtocolError):
                encode_name(name)

    def test_move_byte_order(self):
        self.assertEqual(encode_moves([Move(1, 2, 3, 4, 5)]), b"MOV\x01\x01\x02\x03\x04\x05")

    def test_empty_or_oversized_move_packet_rejected(self):
        for moves in ([], [Move(0, 0, 1, 1, 1)] * 256):
            with self.assertRaises(ProtocolError):
                encode_moves(moves)

    def test_persistent_socket_handshake_two_games_and_bye(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.settimeout(2)
        right.settimeout(2)
        client, session = Client(left), GameSession()
        client.send_name("Test")
        self.assertEqual(recv_exact(right, 8), b"NME\x04Test")
        for species in (V, W):
            counts = b"\x00\x04\x00" if species == V else b"\x00\x00\x04"
            right.sendall(b"SET\x03\x04HUM\x00HME\x00\x00MAP\x01\x00\x00" + counts + b"UPD\x00")
            for _ in range(4):
                self.assertFalse(session.apply(client.receive()))
            self.assertTrue(session.apply(client.receive()))
            self.assertEqual(session.species, species)
            client.send_moves(session.board, session.species, [Move(0, 0, 4, 1, 1)])
            self.assertEqual(recv_exact(right, 9), b"MOV\x01\x00\x00\x04\x01\x01")
            right.sendall(b"END")
            self.assertFalse(session.apply(client.receive()))
            self.assertIsNone(session.board)
            self.assertIsNone(session.species)
        right.sendall(b"BYE")
        session.apply(client.receive())
        self.assertTrue(session.closed)

    def test_send_validates_before_transmitting(self):
        class Sender:
            def sendall(self, data):
                raise AssertionError("Invalid move must not be sent")

        with self.assertRaises(ValueError):
            Client(Sender()).send_moves(Board(2, 2), V, [Move(0, 0, 1, 1, 1)])


class SessionTests(unittest.TestCase):
    def test_reject_update_before_initialization(self):
        with self.assertRaises(ValueError):
            GameSession().apply(Message("UPD"))

    def test_home_must_identify_our_species(self):
        session = GameSession()
        for message in [Message("SET", (2, 2)), Message("HUM"), Message("HME", (0, 0))]:
            session.apply(message)
        with self.assertRaises(ValueError):
            session.apply(Message("MAP", ((0, 0, 4, 0, 0),)))

    def test_end_discards_home_houses_and_initialization(self):
        session = GameSession()
        session.apply(Message("SET", (2, 2)))
        session.apply(Message("HUM", ((0, 0),)))
        session.apply(Message("HME", (1, 1)))
        session.apply(Message("END"))
        self.assertEqual((session.board, session.home, session.houses, session.expected),
                         (None, None, (), "SET"))

    def test_bye_is_terminal(self):
        session = GameSession()
        session.apply(Message("BYE"))
        with self.assertRaises(ValueError):
            session.apply(Message("SET", (2, 2)))


if __name__ == "__main__":
    unittest.main()
