import unittest

from vampires.history import PositionHistory
from vampires.model import Board, Cell, Species

V, W = Species.VAMPIRES, Species.WEREWOLVES


class HistoryTests(unittest.TestCase):
    def test_only_trailing_repetition_requests_risk_review(self):
        for count, standing in ((1, "trailing"), (2, "tied"), (3, "leading")):
            board = Board(1, 3, {(0, 0): Cell(vampires=count), (2, 0): Cell(werewolves=2)})
            history = PositionHistory()
            first = history.observe(board, V)
            self.assertFalse(first.review_trailing_cycle)
            repeat = history.observe(board, V)
            self.assertEqual((repeat.visits, repeat.cycle_updates, repeat.standing), (2, 1, standing))
            self.assertEqual(repeat.review_trailing_cycle, count == 1)

    def test_identity_includes_contents_dimensions_and_side(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=2)})
        history = PositionHistory()
        history.observe(board, V)
        self.assertEqual(history.observe(board, W).visits, 1)
        self.assertEqual(history.observe(Board(2, 3, board.cells), V).visits, 1)
        board.apply_updates(((0, 0, 0, 2, 0),))
        self.assertEqual(history.observe(board, V).visits, 1)
        board.apply_updates(((0, 0, 0, 1, 0),))
        repeat = history.observe(board, V)
        self.assertEqual((repeat.visits, repeat.cycle_updates), (2, 4))

    def test_history_is_bounded_and_reset_drops_previous_game(self):
        history = PositionHistory(max_positions=2)
        boards = [Board(1, 4, {(x, 0): Cell(vampires=1)}) for x in range(3)]
        for board in boards:
            history.observe(board, V)
        self.assertEqual(len(history.positions), 2)
        self.assertEqual(history.observe(boards[0], V).visits, 1)
        history.clear()
        self.assertEqual(history.observations, 0)
        self.assertEqual(history.observe(boards[0], V).visits, 1)

    def test_perspective_changes_standing_without_changing_state_identity(self):
        board = Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=2)})
        history = PositionHistory()
        history.observe(board, V, V)
        result = history.observe(board, V, W)
        self.assertEqual((result.visits, result.standing), (2, "leading"))


if __name__ == "__main__":
    unittest.main()
