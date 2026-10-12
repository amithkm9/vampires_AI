"""Adversarial wire, state, and history cases independent of the live server."""

import io
import random
import unittest

from vampires.history import PositionHistory
from vampires.model import Board, Cell, GameSession, Species
from vampires.protocol import (Client, ConnectionClosed, Message, ProtocolError,
                               encode_name, read_message, recv_exact)
from vampires.rules import Move

V, W = Species.VAMPIRES, Species.WEREWOLVES


class VirtualSocket:
    """A deterministic socket with a controllable receive clock and fragmentation."""

    def __init__(self, data=b"", *, fragment=255, delays=(), timeout=None,
                 enforce_timeout=True):
        self.data = io.BytesIO(data)
        self.fragment = fragment
        self.delays = iter(delays)
        self.timeout = timeout
        self.enforce_timeout = enforce_timeout
        self.now = 0.0
        self.timeouts_at_receive = []
        self.sent = []

    def clock(self):
        return self.now

    def gettimeout(self):
        return self.timeout

    def settimeout(self, value):
        self.timeout = value

    def recv(self, size):
        self.timeouts_at_receive.append(self.timeout)
        delay = next(self.delays, 0.0)
        self.now += delay
        if self.enforce_timeout and self.timeout is not None and delay > self.timeout:
            raise TimeoutError("simulated network stall")
        return self.data.read(min(size, self.fragment))

    def sendall(self, data):
        self.sent.append(data)


class WireEdgeTests(unittest.TestCase):
    def test_first_upd_byte_starts_deadline_even_with_fragmented_header(self):
        stream = VirtualSocket(b"UPD\x00", fragment=1, delays=(10.0, .8, .8), timeout=None)
        with self.assertRaises(TimeoutError):
            read_message(stream, turn_timeout=1, clock=stream.clock)
        self.assertEqual(stream.timeouts_at_receive[0], None)
        self.assertAlmostEqual(stream.timeouts_at_receive[1], 1.0)
        self.assertAlmostEqual(stream.timeouts_at_receive[2], .2)
        self.assertIsNone(stream.timeout)

    def test_first_byte_timestamp_includes_header_time_but_not_opponent_wait(self):
        stream = VirtualSocket(b"UPD\x00", fragment=1, delays=(20, .1, .2, .3))
        message = read_message(stream, turn_timeout=1, clock=stream.clock)
        self.assertEqual(message.received_at, 20)
        self.assertAlmostEqual(stream.now, 20.6)
        self.assertIsNone(stream.timeout)

    def test_non_upd_commands_do_not_inherit_a_turn_deadline(self):
        for data in (b"SET\x01\x02", b"HUM\x00", b"MAP\x00", b"HME\x00\x00", b"END", b"BYE"):
            stream = VirtualSocket(data, fragment=1, delays=(5,) * len(data))
            read_message(stream, turn_timeout=1, clock=stream.clock)
            self.assertTrue(all(t is None for t in stream.timeouts_at_receive))

    def test_receive_finishing_after_deadline_is_not_accepted(self):
        # Simulates scheduling delay around a successful final recv, which the
        # OS socket timeout alone cannot account for after it returns.
        stream = VirtualSocket(b"x", delays=(2,), enforce_timeout=False)
        with self.assertRaises(TimeoutError):
            recv_exact(stream, 1, deadline=1, clock=stream.clock)
        self.assertIsNone(stream.timeout)

    def test_receive_keeps_shorter_existing_timeout_and_restores_it(self):
        stream = VirtualSocket(b"UPD\x00", fragment=1, timeout=.25)
        read_message(stream, turn_timeout=1, clock=stream.clock)
        self.assertEqual(stream.timeout, .25)
        self.assertTrue(all(t == .25 for t in stream.timeouts_at_receive))

    def test_all_truncated_packet_offsets_raise_without_spinning(self):
        packets = (b"SET\xff\xff", b"HME\xfe\xfe", b"HUM\x02\x00\x01\xfe\xfe",
                   b"MAP\x02\x00\x00\x00\xff\x00\xfe\xfe\x00\x00\xff",
                   b"UPD\x02\x00\x00\x00\x00\x00\xfe\xfe\xff\x00\x00",
                   b"END", b"BYE")
        for packet in packets:
            for cut in range(len(packet)):
                stream = VirtualSocket(packet[:cut], fragment=1, timeout=3)
                with self.subTest(packet=packet[:3], cut=cut), self.assertRaises(ConnectionClosed):
                    read_message(stream, turn_timeout=1, clock=stream.clock)
                self.assertEqual(stream.timeout, 3)

    def test_maximum_count_and_random_fragment_sizes_preserve_following_packet(self):
        rng = random.Random(20261012)
        records = tuple((x, 0, 0, x, 0) for x in range(255))
        body = bytes(value for record in records for value in record)
        for command in (b"MAP", b"UPD"):
            for _ in range(12):
                stream = VirtualSocket(command + b"\xff" + body + b"BYE",
                                       fragment=rng.randint(1, 128))
                message = read_message(stream, turn_timeout=1, clock=stream.clock)
                self.assertEqual(message.payload, records)
                self.assertEqual(read_message(stream), Message("BYE"))

    def test_zero_count_variable_packets_leave_stream_aligned(self):
        stream = VirtualSocket(b"HUM\x00MAP\x00UPD\x00ENDBYE", fragment=1)
        self.assertEqual([read_message(stream) for _ in range(5)],
                         [Message(c) for c in ("HUM", "MAP", "UPD", "END", "BYE")])

    def test_invalid_timeout_values_fail_before_any_network_read(self):
        for value in (0, -1, float("nan"), float("inf"), True, "2", 10 ** 1000):
            stream = VirtualSocket(b"UPD\x00")
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_message(stream, turn_timeout=value)
            self.assertFalse(stream.timeouts_at_receive)

    def test_invalid_deadlines_fail_before_receive_or_send(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        for value in (float("nan"), float("inf"), False, "2", 10 ** 1000):
            stream = VirtualSocket(b"x")
            with self.subTest(value=value), self.assertRaises(ValueError):
                recv_exact(stream, 1, deadline=value)
            with self.assertRaises(ValueError):
                Client(stream).send_moves(board, V, (Move(0, 0, 1, 1, 0),), deadline=value)
            self.assertFalse(stream.timeouts_at_receive)
            self.assertFalse(stream.sent)

    def test_connection_reset_and_send_failure_restore_original_timeout(self):
        class ResetSocket(VirtualSocket):
            def recv(self, size):
                raise ConnectionResetError("reset")

            def sendall(self, data):
                raise BrokenPipeError("closed")

        stream = ResetSocket(timeout=5)
        with self.assertRaises(ConnectionResetError):
            recv_exact(stream, 1, deadline=1, clock=stream.clock)
        self.assertEqual(stream.timeout, 5)
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        with self.assertRaises(BrokenPipeError):
            Client(stream).send_moves(board, V, (Move(0, 0, 1, 1, 0),), deadline=1, clock=stream.clock)
        self.assertEqual(stream.timeout, 5)

    def test_non_string_names_are_explicit_protocol_errors(self):
        for name in (None, b"AI", 123, True):
            with self.subTest(name=name), self.assertRaises(ProtocolError):
                encode_name(name)


class SessionEdgeTests(unittest.TestCase):
    def initialized(self):
        session = GameSession()
        for message in (Message("SET", (2, 3)), Message("HUM"), Message("HME", (0, 0)),
                        Message("MAP", ((0, 0, 0, 2, 0), (2, 1, 0, 0, 3)))):
            session.apply(message)
        return session

    def test_invalid_update_is_atomic_even_after_valid_prior_records(self):
        for invalid in ((3, 0, 0, 1, 0), (1, 1, 1, 1, 0), (1, 1, 0, 256, 0)):
            session = self.initialized()
            before = dict(session.board.cells)
            with self.assertRaises(ValueError):
                session.apply(Message("UPD", ((0, 0, 0, 0, 0), invalid)))
            self.assertEqual(session.board.cells, before)
            self.assertEqual(session.expected, "UPD")

    def test_failed_map_does_not_publish_partial_state_or_species(self):
        session = GameSession()
        for message in (Message("SET", (2, 2)), Message("HUM"), Message("HME", (0, 0))):
            session.apply(message)
        with self.assertRaises(ValueError):
            session.apply(Message("MAP", ((0, 0, 0, 4, 0), (1, 1, 2, 0, 3))))
        self.assertFalse(session.board.cells)
        self.assertIsNone(session.species)
        self.assertEqual(session.expected, "MAP")

    def test_bye_terminates_every_initialization_stage(self):
        messages = (Message("SET", (1, 2)), Message("HUM"), Message("HME", (0, 0)),
                    Message("MAP", ((0, 0, 0, 2, 0), (1, 0, 0, 0, 2))))
        for count in range(len(messages) + 1):
            session = GameSession()
            for message in messages[:count]:
                session.apply(message)
            session.apply(Message("BYE"))
            self.assertTrue(session.closed)
            self.assertIsNone(session.board)
            with self.assertRaises(ValueError):
                session.apply(Message("SET", (1, 2)))


class HistoryCapacityEdgeTests(unittest.TestCase):
    def test_cell_record_budget_evicts_oldest_snapshots(self):
        history = PositionHistory(max_positions=10, max_cell_records=4)
        boards = [Board(1, 4, {(x, 0): Cell(vampires=1), (3, 0): Cell(werewolves=2)})
                  for x in range(3)]
        history.observe(boards[0], V)
        history.observe(boards[1], V)
        history.observe(boards[0], V)  # Refresh the LRU entry without double-counting its cells.
        self.assertEqual(history.cell_records, 4)
        history.observe(boards[2], V)
        self.assertEqual(history.cell_records, 4)
        self.assertEqual(history.observe(boards[0], V).visits, 3)
        self.assertEqual(history.observe(boards[1], V).visits, 1)

    def test_oversized_snapshot_is_observed_without_exceeding_retention_budget(self):
        history = PositionHistory(max_cell_records=1)
        board = Board(1, 2, {(0, 0): Cell(vampires=1), (1, 0): Cell(werewolves=2)})
        for _ in range(3):
            result = history.observe(board, V)
            self.assertEqual((result.visits, result.cycle_updates, result.standing), (1, None, "trailing"))
        self.assertEqual((len(history.positions), history.cell_records, history.observations), (0, 0, 3))

    def test_empty_boards_remain_bounded_by_position_count(self):
        history = PositionHistory(max_positions=2, max_cell_records=1)
        for rows in range(1, 10):
            history.observe(Board(rows, 2), V)
        self.assertEqual((len(history.positions), history.cell_records), (2, 0))

    def test_invalid_capacity_and_reset(self):
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                PositionHistory(max_cell_records=value)
        history = PositionHistory(max_cell_records=2)
        history.observe(Board(1, 1, {(0, 0): Cell(vampires=255)}), V)
        history.clear()
        self.assertEqual((history.observations, history.cell_records, len(history.positions)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
