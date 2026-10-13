"""Preserve a dominant intact stack under the written population/combat rules."""

from .budget import checkpoint
from .model import Species
from .rules import Move, validate_moves


def dominant_stack(board, species, *, check=None):
    species = Species(species)
    ceiling = 0
    for cell in board.cells.values():
        checkpoint(check)
        ceiling += cell.humans + cell.count(species.opponent)
    for position, cell in board.cells.items():
        checkpoint(check)
        count = cell.count(species)
        if count > ceiling and 2 * count >= 3 * ceiling:
            return position, count, ceiling
    return None


def preserving_turn(board, species, *, check=None):
    """Choose a legal deterministic move of the certified stack, keeping it whole.

    Every enemy can grow to at most enemy_total + remaining_humans. A stack
    satisfying the certificate cannot lose combat under that worst-case bound.
    This is conditional on the written rules, not an official-server guarantee.
    """
    checkpoint(check)
    species = Species(species)
    certificate = dominant_stack(board, species, check=check)
    if certificate is None:
        return None
    source, count, ceiling = certificate
    enemies = board.groups(species.opponent)
    choices = []
    for target in board.neighbors(source):
        checkpoint(check)
        cell = board.at(target)
        if count + cell.humans + cell.count(species) > 255:
            continue
        # Prefer immediate elimination/conversion, then approach the nearest enemy.
        gap = None
        for position in enemies:
            checkpoint(check)
            steps = max(abs(target[0] - position[0]), abs(target[1] - position[1]))
            gap = steps if gap is None else min(gap, steps)
        priority = (cell.count(species.opponent), cell.humans, -(gap or 0))
        choices.append((priority, Move(*source, count, *target)))
    if not choices:
        return None
    move = max(choices, key=lambda item: item[0])[1]
    return validate_moves(board, species, (move,))
