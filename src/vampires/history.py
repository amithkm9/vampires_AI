"""Bounded repetition diagnostics from authoritative updates, not draw rules."""

from collections import OrderedDict
from dataclasses import dataclass

from .model import Species


@dataclass(frozen=True)
class Repetition:
    visits: int
    cycle_updates: int | None
    population_margin: int

    @property
    def standing(self):
        return "leading" if self.population_margin > 0 else "trailing" if self.population_margin < 0 else "tied"

    @property
    def review_trailing_cycle(self):
        return self.visits > 1 and self.population_margin < 0


class PositionHistory:
    """Track recent board/side identities within ONE game.

    Periods count observations (our UPDs in live play), never inferred global
    plies. Evicted positions lose their visit history. Repetition does not imply
    a draw, an imminent cutoff, or a reason to sacrifice a lead or safe draw.
    Both the number of positions and their combined cell records are bounded.
    An individually oversized snapshot is observed but not retained.
    """

    def __init__(self, max_positions=512, *, max_cell_records=131072):
        if type(max_positions) is not int or max_positions < 1:
            raise ValueError("max_positions must be a positive integer")
        if type(max_cell_records) is not int or max_cell_records < 1:
            raise ValueError("max_cell_records must be a positive integer")
        self.max_positions = max_positions
        self.max_cell_records = max_cell_records
        self.clear()

    def clear(self):
        self.positions = OrderedDict()
        self.observations = 0
        self.cell_records = 0

    def observe(self, board, to_move, perspective=None):
        side = Species(to_move)
        perspective = side if perspective is None else Species(perspective)
        cells = tuple(sorted((p, c.humans, c.vampires, c.werewolves)
                             for p, c in board.cells.items()))
        key = board.rows, board.columns, cells, side
        previous = self.positions.pop(key, None)
        if previous is not None:
            self.cell_records -= len(cells)
        visits = 1 if previous is None else previous[0] + 1
        period = None if previous is None else self.observations - previous[1]
        if len(cells) <= self.max_cell_records:
            self.positions[key] = visits, self.observations
            self.cell_records += len(cells)
        self.observations += 1
        while (len(self.positions) > self.max_positions
               or self.cell_records > self.max_cell_records):
            discarded, _ = self.positions.popitem(last=False)
            self.cell_records -= len(discarded[2])
        margin = sum(board.groups(perspective).values()) - sum(board.groups(perspective.opponent).values())
        return Repetition(visits, period, margin)
