"""Board coordinates and authoritative server state (brief, pages 3 and 5-8)."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import xml.etree.ElementTree as ET


class Species(str, Enum):
    VAMPIRES = "vampires"
    WEREWOLVES = "werewolves"

    @property
    def opponent(self):
        return (Species.WEREWOLVES if self == Species.VAMPIRES
                else Species.VAMPIRES)


def byte_value(value, label, minimum=0):
    if type(value) is not int or not minimum <= value <= 255:
        raise ValueError(f"{label} must be an integer in {minimum}..255")


@dataclass(frozen=True)
class Cell:
    humans: int = 0
    vampires: int = 0
    werewolves: int = 0

    def __post_init__(self):
        for label in ("humans", "vampires", "werewolves"):
            byte_value(getattr(self, label), label)
        if sum(n > 0 for n in (self.humans, self.vampires, self.werewolves)) > 1:
            raise ValueError("A resolved cell cannot contain multiple species")

    def count(self, species):
        return getattr(self, Species(species).value)

    @property
    def empty(self):
        return not (self.humans or self.vampires or self.werewolves)


@dataclass
class Board:
    rows: int
    columns: int
    cells: dict = field(default_factory=dict)

    def __post_init__(self):
        byte_value(self.rows, "rows", minimum=1)
        byte_value(self.columns, "columns", minimum=1)
        self.cells = dict(self.cells)
        for position, cell in self.cells.items():
            self.check_position(position)
            if not isinstance(cell, Cell):
                raise ValueError("Board contents must be Cell values")
        self.cells = {p: c for p, c in self.cells.items() if not c.empty}

    def check_position(self, position):
        x, y = position
        byte_value(x, "x")
        byte_value(y, "y")
        if not (x < self.columns and y < self.rows):
            raise ValueError(f"Position {position} is outside the board")

    def at(self, position):
        self.check_position(position)
        return self.cells.get(position, Cell())

    def groups(self, species):
        return {p: c.count(species) for p, c in self.cells.items()
                if c.count(species)}

    def neighbors(self, position):
        self.check_position(position)
        x, y = position
        return [(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dx or dy) and 0 <= x + dx < self.columns
                and 0 <= y + dy < self.rows]

    def apply_updates(self, updates):
        """Replace cell contents, including deletions, atomically. UPD is not a delta."""
        changed = dict(self.cells)
        for x, y, humans, vampires, werewolves in updates:
            self.check_position((x, y))
            cell = Cell(humans, vampires, werewolves)
            if cell.empty:
                changed.pop((x, y), None)
            else:
                changed[(x, y)] = cell
        self.cells = changed


def load_map(path):
    """Read the supplied XML map format without executing the map generator."""
    root = ET.parse(Path(path)).getroot()
    if root.tag != "Map":
        raise ValueError("Map XML must have a Map root")
    board = Board(int(root.attrib["Rows"]), int(root.attrib["Columns"]))
    fields = {"Humans": "humans", "Vampires": "vampires", "Werewolves": "werewolves"}
    for element in root:
        if element.tag not in fields:
            raise ValueError(f"Unknown map element: {element.tag}")
        position = int(element.attrib["X"]), int(element.attrib["Y"])
        board.check_position(position)
        if position in board.cells:
            raise ValueError(f"Repeated map cell: {position}")
        count = int(element.attrib["Count"])
        byte_value(count, "map count", minimum=1)
        board.cells[position] = Cell(**{fields[element.tag]: count})
    return board


@dataclass
class GameSession:
    board: Board | None = None
    houses: tuple = ()
    home: tuple | None = None
    species: Species | None = None
    expected: str = "SET"
    closed: bool = False

    def reset(self):
        self.board = None
        self.houses = ()
        self.home = None
        self.species = None
        self.expected = "SET"

    def apply(self, message):
        """Return True only for a valid UPD, which is the signal to play."""
        if self.closed:
            raise ValueError("Session already received BYE")
        command, payload = message.command, message.payload
        if command in ("END", "BYE"):
            self.reset()
            self.closed = command == "BYE"
            return False
        if command != self.expected:
            raise ValueError(f"Expected {self.expected}, received {command}")
        if command == "SET":
            self.board = Board(*payload)
            self.expected = "HUM"
        elif command == "HUM":
            for position in payload:
                self.board.check_position(position)
            self.houses = tuple(payload)
            self.expected = "HME"
        elif command == "HME":
            self.board.check_position(payload)
            self.home = tuple(payload)
            self.expected = "MAP"
        elif command == "MAP":
            board = Board(self.board.rows, self.board.columns)
            board.apply_updates(payload)
            home = board.at(self.home)
            if not (home.vampires or home.werewolves):
                raise ValueError("Home does not identify our species")
            self.species = Species.VAMPIRES if home.vampires else Species.WEREWOLVES
            self.board = board
            self.expected = "UPD"
        elif command == "UPD":
            self.board.apply_updates(payload)
            return True
        return False
