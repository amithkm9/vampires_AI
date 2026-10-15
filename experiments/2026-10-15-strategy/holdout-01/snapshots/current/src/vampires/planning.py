"""Outcome-oriented evaluation and bounded sequential conversion races.

These are leaf heuristics for adversarial search, not solved game values. The
live daylight horizon stays unknown. Projected routes ignore interception and
incidental occupied squares; the tactical tree still examines opponent replies.
"""

from dataclasses import dataclass
from math import tanh

from .budget import checkpoint
from .evaluation import distance, evaluate, terminal_value
from .model import Species


@dataclass(frozen=True)
class Capture:
    species: Species
    source: tuple
    target: tuple
    humans: int
    before: int
    after: int
    arrival_ply: int


@dataclass(frozen=True)
class ConversionRace:
    populations: dict
    captures: tuple
    complete: bool


def conversion_race(board, to_move, *, check=None):
    """Greedily allocate each house once, updating a capturing group's strength.

    A group's travel clock carries forward after each capture. A conversion can
    therefore unlock a later house, but cannot borrow another group's humans.
    Competing arrival times include initiative. At equal own-side arrival times,
    prefer the larger house and then coordinates for reproducibility.

    These events are optimistic travel estimates, not macro moves or a verified
    executable joint plan. No battle or opponent move is skipped in live search.
    Limit the heuristic to twelve houses/eight groups, without a board-area grid.
    """
    checkpoint(check)
    to_move = Species(to_move)
    groups, houses = [], {}
    totals = {side: 0 for side in Species}
    for position, cell in sorted(board.cells.items()):
        checkpoint(check)
        if cell.humans:
            houses[position] = cell.humans
        for side in Species:
            count = cell.count(side)
            if count:
                totals[side] += count
                groups.append([side, position, count, 0])
    if len(houses) > 12 or len(groups) > 8:
        return ConversionRace(totals, (), False)
    captures = []
    while houses:
        selected = None
        for index, (side, source, count, elapsed) in enumerate(groups):
            for target, humans in houses.items():
                checkpoint(check)
                if humans > count or count + humans > 255:
                    continue
                arrival = elapsed + distance(source, target)
                ply = 2 * arrival - int(side == to_move)
                rank = (ply, -humans, source, target, index)
                if selected is None or rank < selected[0]:
                    selected = rank, index, target, arrival
        if selected is None:
            break
        rank, index, target, arrival = selected
        side, source, count, _ = groups[index]
        humans = houses.pop(target)
        captures.append(Capture(side, source, target, humans, count,
                                count + humans, rank[0]))
        totals[side] += humans
        groups[index] = [side, target, count + humans, arrival]
    return ConversionRace(totals, tuple(captures), True)


def evaluate_outcome(board, perspective, to_move, *, check=None):
    """Value no-human population standing strongly enough to consider recovery.

    A small material deficit is a poor proxy for a losing final score. With no
    humans remaining, favor maintaining a lead, consolidation, and approaching
    when behind. A trailing agent can then prefer a meaningful stochastic battle
    over indefinitely retaining its deficit. This is not a cutoff/termination
    claim. Equal population has no sign bonus and is not automatically a draw.
    """
    checkpoint(check)
    perspective = Species(perspective)
    terminal = terminal_value(board, perspective)
    if terminal is not None:
        return terminal
    for cell in board.cells.values():
        checkpoint(check)
        if cell.humans:
            return evaluate(board, perspective, to_move, check=check)
    own, enemy = board.groups(perspective), board.groups(perspective.opponent)
    ours, theirs = sum(own.values()), sum(enemy.values())
    standing = (ours > theirs) - (ours < theirs)
    cohesion = sum(n * n for n in own.values()) / (ours * ours)
    cohesion -= sum(n * n for n in enemy.values()) / (theirs * theirs)
    nearest = None
    for source in own:
        for target in enemy:
            checkpoint(check)
            gap = distance(source, target)
            nearest = gap if nearest is None else min(nearest, gap)
    separation = nearest / (1 + nearest)
    value = (.84 * standing + .04 * (ours - theirs) / (ours + theirs)
             + .06 * cohesion + .04 * standing * separation
             + .02 * evaluate(board, perspective, to_move, check=check))
    return max(-.95, min(.95, value))


def evaluate_strategic(board, perspective, to_move, *, check=None):
    """Project exclusive sequential conversions; search checks local tactics."""
    checkpoint(check)
    perspective = Species(perspective)
    terminal = terminal_value(board, perspective)
    if terminal is not None:
        return terminal
    if not any(cell.humans for cell in board.cells.values()):
        return evaluate_outcome(board, perspective, to_move, check=check)
    base = evaluate(board, perspective, to_move, check=check)
    race = conversion_race(board, to_move, check=check)
    if not race.complete:
        return base
    own, enemy = race.populations[perspective], race.populations[perspective.opponent]
    value = .8 * tanh(4 * (own - enemy) / (own + enemy)) + .15 * base
    return max(-.95, min(.95, value))
