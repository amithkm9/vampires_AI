"""Bounded baseline heuristics, not calibrated win probabilities or safe routes."""

from .budget import checkpoint
from .model import Species


def distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def terminal_value(board, perspective, *, remaining_plies=None):
    if remaining_plies == 0:
        own = sum(board.groups(perspective).values())
        enemy = sum(board.groups(Species(perspective).opponent).values())
        # Known local cutoff only; the live protocol supplies no countdown.
        return float((own > enemy) - (own < enemy))
    own = bool(board.groups(perspective))
    enemy = bool(board.groups(Species(perspective).opponent))
    if own and enemy:
        return None
    # Both extinct is a neutral MODEL convention until the server is checked.
    return float(own) - float(enemy)


def evaluate(board, perspective, to_move, *, check=None):
    """Population, exclusive house races, group exposure, and approach distance.

    House estimates require a sufficient CURRENT stack and use straight-line
    lower bounds. Each house contributes to only one side. This does not model
    future growth sequences, safe travel, merges en route, or capture denial yet.
    """
    checkpoint(check)
    perspective, to_move = Species(perspective), Species(to_move)
    terminal = terminal_value(board, perspective)
    if terminal is not None:
        return terminal
    own, enemy = board.groups(perspective), board.groups(perspective.opponent)
    ours, theirs = sum(own.values()), sum(enemy.values())
    monsters = ours + theirs
    humans = sum(cell.humans for cell in board.cells.values())
    race = 0.0
    for position, cell in board.cells.items():
        checkpoint(check)
        if not cell.humans:
            continue
        arrivals = []
        for species, groups in ((perspective, own), (perspective.opponent, enemy)):
            closest = None
            for source, count in groups.items():
                checkpoint(check)
                if count >= cell.humans:
                    turns = distance(source, position)
                    closest = turns if closest is None else min(closest, turns)
            arrivals.append(None if closest is None else (2 * closest - (species == to_move), closest))
        a, b = arrivals
        if a is not None and (b is None or a[0] < b[0]):
            race += cell.humans / (1 + .25 * a[1])
        elif b is not None and (a is None or b[0] < a[0]):
            race -= cell.humans / (1 + .25 * b[1])
    exposure, approach = 0.0, 0.0
    for side, groups, opponents in ((1, own, enemy), (-1, enemy, own)):
        for position, count in groups.items():
            checkpoint(check)
            adjacent = 0
            nearest_prey = None
            for other, population in opponents.items():
                checkpoint(check)
                gap = distance(position, other)
                if gap == 1:
                    adjacent += population
                if 2 * count >= 3 * population:
                    nearest_prey = gap if nearest_prey is None else min(nearest_prey, gap)
            # Aggregate adjacent enemies are a conservative warning, not a claim
            # that the official server resolves their joint attack in one battle.
            if adjacent and 2 * adjacent >= 3 * count:
                exposure += side * count
            if nearest_prey is not None:
                approach += side * count / (1 + nearest_prey)
    value = (.65 * (ours - theirs) / monsters + .25 * race / (monsters + humans)
             - .08 * exposure / monsters + .02 * approach / monsters)
    return max(-.95, min(.95, value))
