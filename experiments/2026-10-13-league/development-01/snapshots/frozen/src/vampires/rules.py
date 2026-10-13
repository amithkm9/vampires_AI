"""Validate the six move rules and model one battle (brief, pages 3-4)."""

from dataclasses import dataclass
from .model import Species, byte_value


@dataclass(frozen=True)
class Move:
    x: int
    y: int
    count: int
    target_x: int
    target_y: int

    def __post_init__(self):
        for label in ("x", "y", "target_x", "target_y"):
            byte_value(getattr(self, label), label)
        byte_value(self.count, "move count", minimum=1)

    @property
    def source(self):
        return self.x, self.y

    @property
    def target(self):
        return self.target_x, self.target_y

    def as_tuple(self):
        return self.x, self.y, self.count, self.target_x, self.target_y


def validate_moves(board, species, moves, *, strict_group_limit=True):
    """Check a complete ply against its pre-move board.

    The default conservatively enforces page 6's move-record/group limit.
    Disable it only for offline experiments on page 3's splitting interpretation.
    Combat odds do not make an otherwise valid attack illegal.
    """
    species = Species(species)
    moves = tuple(moves)
    if not 1 <= len(moves) <= 255:
        raise ValueError("A ply must contain 1..255 moves")
    groups = board.groups(species)
    if strict_group_limit and len(moves) > len(groups):
        raise ValueError("Move records exceed our group count (brief page 6)")
    sources, targets, outgoing = set(), set(), {}
    for move in moves:
        if not isinstance(move, Move):
            raise ValueError("Expected Move values")
        board.check_position(move.source)
        board.check_position(move.target)
        if move.source not in groups:
            raise ValueError("Only our species can move")
        if max(abs(move.x - move.target_x), abs(move.y - move.target_y)) != 1:
            raise ValueError("Moves must reach an adjacent cell in 8 directions")
        outgoing[move.source] = outgoing.get(move.source, 0) + move.count
        if outgoing[move.source] > groups[move.source]:
            raise ValueError("Moves overspend the source population")
        sources.add(move.source)
        targets.add(move.target)
    if sources & targets:
        raise ValueError("A cell cannot be both a source and target in one ply")
    return moves


@dataclass(frozen=True)
class BattleOdds:
    attacker_win_probability: float
    expected_attackers: float
    expected_defenders: float


def battle_odds(attackers, defenders, *, humans=False):
    """Unconditional expected survivors; never round these into a game state."""
    for label, value in (("attackers", attackers), ("defenders", defenders)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{label} must be a positive integer")
    if humans and attackers >= defenders:
        return BattleOdds(1.0, float(attackers + defenders), 0.0)
    if not humans:
        if 2 * attackers >= 3 * defenders:
            return BattleOdds(1.0, float(attackers), 0.0)
        if 2 * defenders >= 3 * attackers:
            return BattleOdds(0.0, 0.0, float(defenders))
    p = attackers / (2 * defenders) if attackers <= defenders else attackers / defenders - 0.5
    convertible = defenders if humans else 0
    return BattleOdds(p, p * p * (attackers + convertible), (1 - p) ** 2 * defenders)


def sample_battle(attackers, defenders, rng, *, humans=False):
    """Return (attacking survivors including conversions, defending survivors).

    Inject a random.Random instance to make experiments reproducible. One draw
    chooses the winner; subsequent independent draws decide individual survival.
    """
    odds = battle_odds(attackers, defenders, humans=humans)
    p = odds.attacker_win_probability
    if p == 1:
        return attackers + (defenders if humans else 0), 0
    if p == 0:
        return 0, defenders
    if rng.random() < p:
        population = attackers + (defenders if humans else 0)
        return sum(rng.random() < p for _ in range(population)), 0
    return 0, sum(rng.random() < 1 - p for _ in range(defenders))
