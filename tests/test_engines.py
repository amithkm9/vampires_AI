import subprocess
import sys
import unittest
from unittest.mock import patch

from vampires.engines import DEFAULT_ENGINE, ENGINE_NAMES, choose_engine
from vampires.budget import SearchTimeout
from vampires.certificates import dominant_stack
from vampires.model import Board, Cell, Species
from vampires.player import SessionResult, main, play
from vampires.protocol import Message
from vampires.search import SearchConfig
from test_player import FakeClient, ROOT, initialization


class EngineLifecycleTests(unittest.TestCase):
    def test_api_default_and_explicit_depth_contract(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=2), (1, 0): Cell(werewolves=2)})
        self.assertEqual(DEFAULT_ENGINE, "strategic")
        with patch("vampires.engines.choose_balanced") as search:
            choose_engine(board, Species.VAMPIRES)
            self.assertEqual(search.call_args.kwargs["config"].max_depth, 5)
            choose_engine(board, Species.VAMPIRES, engine="cohesive_material")
            self.assertEqual(search.call_args.kwargs["config"].max_depth, 3)
            choose_engine(board, Species.VAMPIRES, engine="adaptive")
            self.assertEqual(search.call_args.kwargs["config"].max_depth, 5)
            choose_engine(board, Species.VAMPIRES, config=SearchConfig(max_depth=2))
            self.assertEqual(search.call_args.kwargs["config"].max_depth, 2)

    def test_launcher_uses_mode_depth_and_respects_override(self):
        for flags, expected_engine, expected_depth in (([], "strategic", 5),
                (["--engine", "cohesive_material"], "cohesive_material", 3),
                (["--depth", "4"], "strategic", 4)):
            with patch("vampires.player.Client.connect") as connect, patch(
                    "vampires.player.play", return_value=SessionResult(0, 0)) as session:
                self.assertEqual(main(["--quiet", *flags, "127.0.0.1", "5555"]), 0)
                connect.assert_called_once_with("127.0.0.1", 5555)
                self.assertEqual(session.call_args.kwargs["engine"], expected_engine)
                self.assertEqual(session.call_args.kwargs["config"].max_depth, expected_depth)

    def test_dominance_scan_cooperates_with_expired_deadline(self):
        board = Board(1, 2, {(0, 0): Cell(vampires=10), (1, 0): Cell(werewolves=1)})
        def expired():
            raise SearchTimeout
        with self.assertRaises(SearchTimeout):
            dominant_stack(board, Species.VAMPIRES, check=expired)

    def test_strategy_flags_cannot_silently_accept_truthy_strings(self):
        for field in ("preserve_dominance", "protect_tactics"):
            for value in ("false", 1, None):
                with self.assertRaises(ValueError):
                    SearchConfig(**{field: value})

    def test_every_engine_handles_species_switch_and_persistent_session(self):
        for engine in ENGINE_NAMES:
            with self.subTest(engine=engine):
                messages = []
                for species in Species:
                    messages += initialization(species=species)
                    messages += [Message("UPD"), Message("END")]
                client = FakeClient(messages + [Message("BYE")])
                result = play(client, engine=engine, budget=.01, config=SearchConfig(max_depth=2))
                self.assertEqual((result.turns, result.games), (2, 2))
                self.assertEqual(len(client.names), 1)
                self.assertEqual([s[1] for s in client.sent], list(Species))

    def test_unknown_engine_and_reflex_live_config_fail_before_network_write(self):
        for kwargs in ({"engine": "unknown"}, {"config": SearchConfig(max_depth=1)}):
            client = FakeClient([])
            with self.assertRaises(ValueError):
                play(client, **kwargs)
            self.assertFalse(client.names)
            self.assertFalse(client.sent)

    def test_stray_and_duplicate_end_do_not_inflate_completed_game_count(self):
        client = FakeClient([Message("END")] + initialization() +
                            [Message("END"), Message("END"), Message("BYE")])
        self.assertEqual(play(client).games, 1)

    def test_invalid_cli_engine_fails_before_connecting(self):
        result = subprocess.run([sys.executable, str(ROOT / "run.py"), "--engine", "unknown", "localhost", "1234"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
