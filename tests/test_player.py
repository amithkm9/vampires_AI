import io
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

from vampires.model import Board, Cell, Species
from vampires.player import play
from vampires.protocol import (Client, ConnectionClosed, Message, ProtocolError,
                               read_message, recv_exact)
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig
from vampires.turns import NoLegalMove
from tools.check_player import cell_packet, initial_packet

ROOT = Path(__file__).resolve().parents[1]
V, W = Species.VAMPIRES, Species.WEREWOLVES


class FakeClient:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.names, self.sent = [], []

    def send_name(self, name):
        self.names.append(name)

    def receive(self):
        return next(self.messages)

    def send_moves(self, board, species, moves, *, deadline=None, clock=None):
        validate_moves(board, species, moves)
        self.sent.append((board.groups(species), species, moves, deadline))


def initialization(*, species=V, rows=2, columns=3):
    counts = (0, 2, 0) if species == V else (0, 0, 2)
    enemy = (0, 0, 2) if species == V else (0, 2, 0)
    return [Message("SET", (rows, columns)), Message("HUM"), Message("HME", (0, 0)),
            Message("MAP", ((0, 0, *counts), (columns - 1, rows - 1, *enemy)))]


class PlayerLifecycleTests(unittest.TestCase):
    def test_only_upd_triggers_move_including_empty_updates(self):
        client = FakeClient(initialization() + [Message("UPD"), Message("END"), Message("BYE")])
        result = play(client, budget=.01, config=SearchConfig(max_depth=2))
        self.assertEqual((result.turns, result.games), (1, 1))
        self.assertEqual(client.names, ["vampires_AI"])
        self.assertEqual(len(client.sent), 1)

    def test_map_without_upd_sends_no_move(self):
        client = FakeClient(initialization() + [Message("BYE")])
        self.assertEqual(play(client).turns, 0)
        self.assertFalse(client.sent)

    def test_end_resets_species_and_name_is_sent_once(self):
        client = FakeClient(initialization(species=V) + [Message("UPD"), Message("END")] +
                            initialization(species=W) + [Message("UPD"), Message("END"), Message("BYE")])
        result = play(client, budget=.01, config=SearchConfig(max_depth=2))
        self.assertEqual((result.turns, result.games), (2, 2))
        self.assertEqual([s[1] for s in client.sent], [V, W])
        self.assertEqual(len(client.names), 1)

    def test_server_update_replaces_state_without_applying_predicted_move(self):
        client = FakeClient(initialization() + [Message("UPD"),
                            Message("UPD", ((0, 0, 0, 0, 0), (1, 0, 0, 5, 0))), Message("BYE")])
        play(client, budget=.01, config=SearchConfig(max_depth=2))
        self.assertEqual(client.sent[1][0], {(1, 0): 5})

    def test_invalid_initialization_and_updates_do_not_send_moves(self):
        for messages in ([Message("UPD")], initialization() + [Message("UPD", ((8, 8, 0, 1, 0),))]):
            client = FakeClient(messages)
            with self.assertRaises(ValueError):
                play(client)
            self.assertFalse(client.sent)

    def test_extinct_player_does_not_fabricate_pass(self):
        client = FakeClient(initialization() + [Message("UPD", ((0, 0, 0, 0, 0),))])
        with self.assertRaises(NoLegalMove):
            play(client)
        self.assertFalse(client.sent)

    def test_upd_timestamp_includes_prior_parsing_time_in_search_budget(self):
        client = FakeClient(initialization() + [Message("UPD", received_at=10), Message("BYE")])
        play(client, budget=1, clock=lambda: 11.1)
        self.assertEqual(client.sent[0][3], 12)

    def test_budget_validation_happens_before_connection_messages(self):
        for value in (0, -1, 2, float("inf"), float("nan")):
            client = FakeClient([])
            with self.assertRaises(ValueError):
                play(client, budget=value)
            self.assertFalse(client.names)

    def test_repetition_observes_authoritative_updates_and_resets_between_games(self):
        client = FakeClient(initialization() + [Message("UPD", ((2, 1, 0, 0, 3),)),
                            Message("UPD"), Message("END")] + initialization() +
                            [Message("UPD", ((2, 1, 0, 0, 3),)), Message("BYE")])
        with self.assertLogs("vampires.player", level="INFO") as logs:
            result = play(client, budget=.01, config=SearchConfig(max_depth=2))
        self.assertEqual((result.turns, result.repeated_turns, result.trailing_repeated_turns), (3, 1, 1))
        self.assertTrue(any("visits=2 cycle_updates=1 standing=trailing" in line for line in logs.output))
        self.assertTrue(any("horizon=unknown" in line for line in logs.output))


class TimedProtocolTests(unittest.TestCase):
    def sockets(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.settimeout(1)
        right.settimeout(1)
        return left, right

    def test_upd_header_timestamp_is_recorded_without_changing_message_equality(self):
        class Stream:
            def __init__(self):
                self.data = io.BytesIO(b"UPD\x00")
            def recv(self, n):
                return self.data.read(n)
        message = read_message(Stream(), clock=lambda: 123)
        self.assertEqual(message, Message("UPD"))
        self.assertEqual(message.received_at, 123)

    def test_slow_upd_payload_times_out_and_restores_socket_timeout(self):
        left, right = self.sockets()
        right.sendall(b"UPD\x01\x00")  # deliberately incomplete cell record
        with self.assertRaises(TimeoutError):
            read_message(left, turn_timeout=.01)
        self.assertEqual(left.gettimeout(), 1)

    def test_upd_fragments_share_one_absolute_deadline(self):
        class Socket:
            def __init__(self):
                self.data = io.BytesIO(b"UPD\x01\x00\x00\x00\x01\x00")
                self.timeout = None
            def recv(self, n):
                return self.data.read(min(n, 1))
            def gettimeout(self):
                return self.timeout
            def settimeout(self, value):
                self.timeout = value
        values = iter((0., .3, .6, .9, 1.2))
        connection = Socket()
        with self.assertRaises(TimeoutError):
            read_message(connection, turn_timeout=1., clock=lambda: next(values))
        self.assertIsNone(connection.timeout)

    def test_late_move_is_not_transmitted(self):
        left, right = self.sockets()
        client = Client(left)
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        with self.assertRaises(TimeoutError):
            client.send_moves(board, V, (Move(0, 0, 1, 1, 0),), deadline=1, clock=lambda: 1)
        right.settimeout(.01)
        with self.assertRaises(TimeoutError):
            right.recv(1)

    def test_send_timeout_restored_and_bytes_are_valid(self):
        left, right = self.sockets()
        board = Board(1, 2, {(0, 0): Cell(vampires=1)})
        Client(left).send_moves(board, V, (Move(0, 0, 1, 1, 0),), deadline=2, clock=lambda: 1)
        self.assertEqual(recv_exact(right, 9), b"MOV\x01\x00\x00\x01\x01\x00")
        self.assertEqual(left.gettimeout(), 1)

    def test_player_handles_real_socket_restart_and_clean_bye(self):
        left, right = self.sockets()
        errors, results = [], []
        def worker():
            try:
                results.append(play(Client(left), budget=.01, config=SearchConfig(max_depth=2)))
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        self.assertEqual(recv_exact(right, 3), b"NME")
        recv_exact(right, recv_exact(right, 1)[0])
        for species in Species:
            board = Board(1, 2, {(0, 0): Cell(**{species.value: 1}),
                                  (1, 0): Cell(**{species.opponent.value: 1})})
            for chunk in (initial_packet(board, species), b"UP", b"D\x00"):
                right.sendall(chunk)
            self.assertEqual(recv_exact(right, 9), b"MOV\x01\x00\x00\x01\x01\x00")
            right.sendall(b"END")
        right.sendall(b"BYE")
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)
        self.assertEqual((results[0].turns, results[0].games), (2, 2))

    def test_disconnect_and_unknown_packets_are_explicit_failures(self):
        for packet, error in ((b"BAD", ProtocolError), (b"SE", ConnectionClosed)):
            left, right = self.sockets()
            right.sendall(packet)
            right.shutdown(socket.SHUT_WR)
            with self.assertRaises(error):
                play(Client(left))


class LauncherTests(unittest.TestCase):
    def test_launch_help_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "run.py"), "--help"], cwd=directory,
                                    capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("host port", result.stdout)

    def test_cli_rejects_bad_values_before_network_access(self):
        for extra in (("--budget", "nan"), ("--budget", "2"), ("--depth", "1"),
                      ("--candidates", "0"), ("--name", "é")):
            result = subprocess.run([sys.executable, str(ROOT / "run.py"), *extra, "localhost", "1234"],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("error:", result.stderr)
        for port in ("0", "65536", "bad"):
            result = subprocess.run([sys.executable, str(ROOT / "run.py"), "localhost", port],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
