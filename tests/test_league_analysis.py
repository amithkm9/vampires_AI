import copy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
from tools.analyze_league import replay
from tools.league_support import EngineSpec, Runtime, packed, run_match


class LeagueReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = Runtime.load(ROOT / "src/vampires", "analysis_test")

    @classmethod
    def tearDownClass(cls):
        cls.runtime.close()

    def fixture(self):
        model = self.runtime.model
        board = model.Board(2, 4, {(0, 0): model.Cell(vampires=4),
                                   (3, 1): model.Cell(werewolves=4),
                                   (1, 0): model.Cell(humans=2)})
        game = run_match(self.runtime, self.runtime, board, EngineSpec("cohesive_material", 3),
                         EngineSpec("split_merge", 3), model.Species.VAMPIRES,
                         budget=0, max_plies=8, combat_seed=13, policy_seed=17)
        game.update(match_id="fixture", map="fixture")
        return packed(board), game

    def test_seeded_reconstruction_and_terminal_result(self):
        board, game = self.fixture()
        result = replay(self.runtime, board, game, 8)
        self.assertEqual(result["plies_verified"], len(game["turns"]))

    def test_tampered_move_successor_result_or_sequence_fails(self):
        board, game = self.fixture()
        for field in ("successor", "score", "species", "move", "cap", "seed", "engine", "elapsed"):
            changed = copy.deepcopy(game)
            if field == "successor":
                changed["turns"][0]["after"]["cells"] = []
            elif field == "score":
                changed["score"] = 42
            elif field == "species":
                changed["turns"][0]["species"] = "werewolves"
            elif field == "move":
                changed["turns"][0]["moves"][0][2] = 255
            elif field == "seed":
                changed["turns"][0]["combat_seed"] += 1
            elif field == "engine":
                changed["turns"][0]["engine"] = "incorrect"
            elif field == "elapsed":
                changed["turns"][0]["elapsed_seconds"] = float("nan")
            with self.subTest(field=field), self.assertRaises(ValueError):
                replay(self.runtime, board, changed, 0 if field == "cap" else 8)


if __name__ == "__main__":
    unittest.main()
