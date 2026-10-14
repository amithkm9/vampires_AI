"""Short deterministic checks of league probes, provenance, and resume safety."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import league
from tools.league_support import (MAP_FAMILIES, SCRIPTED, EngineSpec, Runtime,
                                  digest, distance, generated_board, packed,
                                  parse_spec, run_match, scripted_turn, summarize)


class LeagueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="vampires-league-tests-")
        cls.root = Path(cls.temporary.name)
        cls.fixture = cls.root / "fixture"
        cls.metadata = league.create_run(cls.fixture, engines=["baseline:2"], opponents=["collector"],
                                         maps=["contact"], map_seeds=[11], combat_seeds=[22], policy_seeds=[33],
                                         budget=.001, max_plies=2, command="unit-test fixture; not strength evidence")
        cls.runtime = Runtime.load(cls.fixture / cls.metadata["snapshots"]["current_package"], "test")
        cls.frozen = Runtime.load(cls.fixture / cls.metadata["snapshots"]["frozen_package"], "test_frozen")

    @classmethod
    def tearDownClass(cls):
        cls.runtime.close()
        cls.frozen.close()
        cls.temporary.cleanup()

    def fresh_copy(self):
        destination = self.root / self.id().split(".")[-1]
        shutil.copytree(self.fixture, destination)
        return destination

    def test_generated_families_are_reproducible_valid_and_distinct(self):
        fingerprints = set()
        for family in MAP_FAMILIES:
            for seed in (101, 202, 303):
                board = generated_board(family, seed, self.runtime.model)
                self.assertEqual(packed(board), packed(generated_board(family, seed, self.runtime.model)))
                self.assertTrue(all(board.groups(side) for side in self.runtime.model.Species))
                self.assertLessEqual(sum(c.humans + c.vampires + c.werewolves for c in board.cells.values()), 255)
                if family == "chokepoint":
                    self.assertEqual(min(board.rows, board.columns), 1)
                if family == "endgame":
                    self.assertFalse(any(c.humans for c in board.cells.values()))
                fingerprints.add(digest(packed(board)))
        self.assertGreater(len(fingerprints), len(MAP_FAMILIES))

    def test_all_scripted_policies_are_seeded_legal_live_model_probes(self):
        checked = 0
        for family in MAP_FAMILIES:
            board = generated_board(family, 101, self.runtime.model)
            original = packed(board)
            for side in self.runtime.model.Species:
                for policy in SCRIPTED:
                    moves, diagnostics = scripted_turn(self.runtime, board, side, policy, 202)
                    repeated, _ = scripted_turn(self.runtime, board, side, policy, 202)
                    self.assertEqual(moves, repeated)
                    self.runtime.rules.validate_moves(board, side, moves)
                    self.runtime.simulation.sample_turn(board, side, moves, random.Random(303))
                    self.assertFalse(diagnostics["opponent_lookahead"])
                    self.assertEqual(packed(board), original)
                    checked += 1
        self.assertEqual(checked, 40)

    def test_collector_raider_escape_and_partial_probe_behaviors_are_distinct(self):
        m = self.runtime.model
        side = m.Species.VAMPIRES
        board = m.Board(3, 4, {(1, 1): m.Cell(vampires=5), (2, 1): m.Cell(werewolves=2),
                               (0, 0): m.Cell(humans=4)})
        collect, _ = scripted_turn(self.runtime, board, side, "collector", 1)
        raid, _ = scripted_turn(self.runtime, board, side, "raider", 1)
        self.assertEqual(collect[0].target, (0, 0))
        self.assertEqual(raid[0].target, (2, 1))
        board = m.Board(3, 5, {(1, 1): m.Cell(vampires=6), (3, 1): m.Cell(werewolves=5)})
        flee, _ = scripted_turn(self.runtime, board, side, "escape", 1)
        raid, _ = scripted_turn(self.runtime, board, side, "raider", 1)
        self.assertGreater(distance(flee[0].target, (3, 1)), distance(raid[0].target, (3, 1)))
        board = m.Board(2, 6, {(0, 0): m.Cell(vampires=4), (2, 0): m.Cell(vampires=1),
                               (1, 1): m.Cell(humans=2), (5, 1): m.Cell(werewolves=4)})
        partial, _ = scripted_turn(self.runtime, board, side, "split_merge", 1)
        self.assertTrue(any(move.source == (0, 0) and move.target == (1, 1) and move.count < 4 for move in partial))

    def test_schedule_pairs_every_role_and_uses_explicit_depths(self):
        candidates = [parse_spec("baseline:2"), parse_spec("cohesive_material:4")]
        opponents = [parse_spec("frozen:3", opponent=True), parse_spec("collector", opponent=True)]
        schedule = league.make_schedule(candidates, opponents, {"one": {}, "two": {}}, [11, 12], [21])
        self.assertEqual(len(schedule), 32)
        for first, second in zip(schedule[::2], schedule[1::2]):
            self.assertEqual((first["species"], second["species"]), ("vampires", "werewolves"))
            self.assertEqual(first["candidate"], second["candidate"])
            self.assertEqual(first["combat_seed"], second["combat_seed"])
            self.assertEqual(first["policy_seed"], second["policy_seed"])
        with self.assertRaises(ValueError):
            league.make_schedule(candidates, opponents, {"one": {}}, [11, 11], [21])
        with self.assertRaises(ValueError):
            parse_spec("collector:3", opponent=True)

    def test_exact_current_and_frozen_snapshots_are_loadable(self):
        league.verify_snapshots(self.fixture, self.metadata["snapshots"])
        for module in ("__init__", "growth", "hybrid", "mcts"):
            self.assertIn(f"snapshots/current/src/vampires/experimental/{module}.py",
                          self.metadata["snapshots"]["sha256"])
        board = generated_board("contact", 11, self.runtime.model)
        side = self.runtime.model.Species.WEREWOLVES
        moves, diagnostic = self.runtime.engine_decision(board, side, EngineSpec("frozen", 2), .001,
                                                        target_runtime=self.frozen)
        self.runtime.rules.validate_moves(board, side, moves)
        self.assertLessEqual(diagnostic["selected_depth"], 2)
        moves, _ = self.runtime.engine_decision(board, side, EngineSpec("hybrid", 2), 0)
        self.runtime.rules.validate_moves(board, side, moves)
        self.assertEqual(self.metadata["frozen_revision"], "04a1e855cc78fbab6f0ddef63fbaf085ea46b520")
        self.assertFalse(self.metadata["live_cutoff_supplied"])

    def test_failure_is_unknown_score_and_deadline_failure_is_visible_in_summary(self):
        board = generated_board("contact", 11, self.runtime.model)
        side = self.runtime.model.Species.VAMPIRES
        moves = self.runtime.turns.fallback_turn(board, side)
        times = iter((0.0, 2.1))
        with patch.object(self.runtime, "engine_decision", return_value=(moves, {"completed_depth": 2})):
            result = run_match(self.runtime, self.frozen, board, EngineSpec("baseline", 2),
                               EngineSpec("collector", 3), side, budget=.001, max_plies=2,
                               combat_seed=1, policy_seed=2, clock=lambda: next(times))
        self.assertIsNone(result["score"])
        self.assertIsNone(result["winner"])
        self.assertEqual(result["failure"]["type"], "TimeoutError")
        result.update(map="one", map_family="contact")
        summary = summarize([result])["baseline:d2"]["overall"]
        self.assertEqual(summary["candidate_failures"], 1)
        self.assertEqual(summary["max_candidate_response_seconds"], 2.1)
        self.assertEqual(summary["complete_valid_pairs"], 0)
        self.assertIsNone(summary["paired_score"])

    def test_unsupported_transition_does_not_turn_into_a_victory(self):
        m = self.runtime.model
        board = m.Board(1, 3, {(0, 0): m.Cell(vampires=255), (1, 0): m.Cell(humans=1),
                               (2, 0): m.Cell(werewolves=1)})
        move = self.runtime.rules.Move(0, 0, 255, 1, 0)
        with patch.object(self.runtime, "engine_decision", return_value=((move,), {})):
            result = run_match(self.runtime, self.frozen, board, EngineSpec("baseline", 2),
                               EngineSpec("collector", 3), m.Species.VAMPIRES, budget=.001,
                               max_plies=2, combat_seed=1, policy_seed=2)
        self.assertIsNone(result["score"])
        self.assertEqual(result["failure"]["type"], "UnsupportedPopulation")
        self.assertEqual(result["failure"]["stage"], "simulation")
        self.assertEqual(result["final_board"], packed(board))

    def test_incremental_run_resume_replays_exactly_and_skips_completed_ids(self):
        output = self.fresh_copy()
        with redirect_stdout(io.StringIO()):
            first = league.run_saved(output, max_matches=1)
            first_bytes = (output / "matches.jsonl").read_bytes()
            final = league.run_saved(output)
            final_bytes = (output / "matches.jsonl").read_bytes()
            repeated = league.run_saved(output)
        self.assertFalse(first["complete"])
        self.assertTrue(final["complete"])
        self.assertEqual(repeated["latest_invocation_added_games"], 0)
        self.assertTrue(final_bytes.startswith(first_bytes))
        self.assertEqual(final_bytes, (output / "matches.jsonl").read_bytes())
        for record in league.read_records(output / "matches.jsonl"):
            self.assertIsNone(record["failure"])
            boards = json.loads((output / "boards.json").read_text())
            board = league.unpacked(boards[record["map"]]["board"], self.runtime.model)
            for turn in record["turns"]:
                self.assertEqual(digest(packed(board)), turn["before_sha256"])
                moves = tuple(self.runtime.rules.Move(*move) for move in turn["moves"])
                board = self.runtime.simulation.sample_turn(board, self.runtime.model.Species(turn["species"]),
                                                            moves, random.Random(turn["combat_seed"]))
                self.assertEqual(packed(board), turn["after"])
                self.assertEqual(digest(packed(board)), turn["after_sha256"])
            self.assertEqual(packed(board), record["final_board"])
            self.assertEqual(record["candidate_depth"], 2)

    def test_resume_rejects_snapshot_configuration_and_record_corruption(self):
        output = self.fresh_copy()
        metadata_path = output / "metadata.json"
        original = metadata_path.read_text()
        metadata = json.loads(original)
        metadata["budget_seconds"] = .1
        metadata_path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "configuration changed"):
            league.run_saved(output)
        metadata_path.write_text(original)
        snapshot = output / metadata["snapshots"]["current_package"] / "model.py"
        source = snapshot.read_bytes()
        snapshot.write_bytes(source + b"\n# altered snapshot\n")
        with self.assertRaisesRegex(ValueError, "snapshot"):
            league.run_saved(output)
        snapshot.write_bytes(source)
        with redirect_stdout(io.StringIO()):
            league.run_saved(output, max_matches=1)
        path = output / "matches.jsonl"
        record = json.loads(path.read_text())
        record["score"] = 1 if record["score"] != 1 else 0
        path.write_text(json.dumps(record) + "\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            league.run_saved(output)

    def test_truncated_tail_is_archived_but_interior_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matches.jsonl"
            complete = b'{"match_id":"one"}\n'
            fragment = b'{"match_id":"two"'
            path.write_bytes(complete + fragment)
            records = league.read_records(path, recover=True)
            self.assertEqual(records, [{"match_id": "one"}])
            self.assertEqual(path.read_bytes(), complete)
            archived, = (Path(directory) / "recovery").iterdir()
            self.assertEqual(archived.read_bytes(), fragment)
            path.write_bytes(complete + b"broken\n" + complete)
            with self.assertRaises(ValueError):
                league.read_records(path, recover=True)

    def test_writer_lock_rejects_concurrent_invocations(self):
        output = self.fresh_copy()
        with league.writer_lock(output):
            with self.assertRaisesRegex(RuntimeError, "Another league writer"):
                league.run_saved(output)
        with league.writer_lock(output):
            pass

    def test_invalid_budget_is_rejected_before_creating_artifacts(self):
        for number, budget in enumerate((0, -1, 2, float("inf"), float("nan"))):
            output = self.root / ("invalid-budget-" + str(number))
            with self.assertRaises(ValueError):
                league.create_run(output, engines=["baseline:2"], opponents=["collector"],
                                  maps=["contact"], map_seeds=[11], combat_seeds=[22], policy_seeds=[33],
                                  budget=budget, max_plies=2)
            self.assertFalse(output.exists())
        with self.assertRaises(FileExistsError):
            league.create_run(self.fixture, engines=["baseline:2"], opponents=["collector"], maps=["contact"],
                              map_seeds=[11], combat_seeds=[22], policy_seeds=[33], budget=.001, max_plies=2)


if __name__ == "__main__":
    unittest.main()
