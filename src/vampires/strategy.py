"""Experimental resource projection and diverse, legal movement portfolios.

Straight-line resource races are heuristic estimates, not interception proofs.
Policy turns propose moves; the search still examines adversarial replies.
"""

from math import tanh

from .budget import SearchTimeout, checkpoint
from .evaluation import distance, evaluate, terminal_value
from .model import Species
from .rules import Move, validate_moves
from .turns import Candidates, candidate_turns, canonical, move_priority


def resource_projection(board, to_move, *, check=None):
    """Allocate currently affordable houses exclusively by arrival ply.

    Captures are discounted slowly with distance. No house is credited twice,
    no future converted population is borrowed to cross an affordability threshold,
    and overflow is excluded. Routes can still interfere or be intercepted.
    """
    to_move = Species(to_move)
    groups = {side: board.groups(side) for side in Species}
    projected = {side: float(sum(group.values())) for side, group in groups.items()}
    for target, cell in board.cells.items():
        checkpoint(check)
        if not cell.humans:
            continue
        arrivals = []
        for side in Species:
            for source, count in groups[side].items():
                checkpoint(check)
                if cell.humans <= count and count + cell.humans <= 255:
                    turns = distance(source, target)
                    arrivals.append((2 * turns - (side == to_move), side.value, side, turns))
        if arrivals:
            _, _, side, turns = min(arrivals)
            projected[side] += cell.humans / (1 + .03 * turns)
    return projected


def evaluate_resources(board, perspective, to_move, *, check=None):
    """Value projected population advantage, with a small tactical baseline.

    This nonlinear heuristic values eventual resources more strongly than the
    baseline's small positional bonus. It is not a calibrated win probability or
    a claim about the unknown daylight horizon. It intentionally remains opt-in.
    """
    perspective = Species(perspective)
    terminal = terminal_value(board, perspective)
    if terminal is not None:
        return terminal
    projected = resource_projection(board, to_move, check=check)
    a, b = projected[perspective], projected[perspective.opponent]
    value = .8 * tanh(3 * (a - b) / (a + b)) + .15 * evaluate(board, perspective, to_move, check=check)
    return max(-.95, min(.95, value))


def portfolio_turns(board, species, *, limit=64, per_group=12, check=None,
                    allow_partial=False, max_expansions=2048, protect_tactics=False):
    """Mix baseline turns with whole-stack collect/attack/merge/escape policies.

    Keep complete baseline sets complete; otherwise reserve at most half of the
    slots for a round-robin mix of policy families. Validate after each added
    record, and exclude shared contested targets under the live model. This does
    not supply all legal splitting patterns or guarantee tactical completeness.
    """
    base = candidate_turns(board, species, limit=limit, per_group=per_group, check=check,
                           allow_partial=allow_partial, max_expansions=max_expansions,
                           protect_tactics=protect_tactics)
    if not base.selective or base.truncated:
        return base
    species = Species(species)
    groups, opponents = board.groups(species), board.groups(species.opponent)
    houses = [(p, c.humans) for p, c in board.cells.items() if c.humans]
    families = {name: [] for name in ("collect", "attack", "merge", "escape")}
    truncated = False
    try:
        for policy, family in families.items():
            joint = ()
            for source, count in sorted(groups.items(), key=lambda item: (-item[1], item[0])):
                checkpoint(check)
                choices = []
                for target in board.neighbors(source):
                    checkpoint(check)
                    move = Move(*source, count, *target)
                    gain = move_priority(board, species, move)
                    targets = ([p for p, h in houses if h <= count] if policy == "collect" else
                               [p for p, n in opponents.items() if 2 * count >= 3 * n] if policy == "attack" else
                               [p for p in groups if p != source] if policy == "merge" else [])
                    approach = -min((distance(target, p) for p in targets), default=0)
                    danger = sum(n for p, n in opponents.items() if distance(target, p) <= 1)
                    escape = min((distance(target, p) for p, n in opponents.items()
                                  if 2 * n >= 3 * count), default=0)
                    # A local warning, not a guarantee of survival under joint replies.
                    risk = count if danger and 2 * danger >= 3 * count else 0
                    score = gain + .2 * approach - 2 * risk + (.5 * escape if policy == "escape" else 0)
                    choices.append((score, move))
                choices.sort(key=lambda item: (-item[0], item[1].as_tuple()))
                family.extend((move,) for _, move in choices[:2])
                for _, move in choices:
                    proposed = canonical(joint + (move,))
                    contested = board.at(move.target).humans or board.at(move.target).count(species.opponent)
                    if contested and any(old.target == move.target for old in joint):
                        continue
                    try:
                        validate_moves(board, species, proposed)
                    except ValueError:
                        continue
                    joint = proposed
                    break
            if joint:
                family.insert(0, joint)
    except SearchTimeout:
        if not allow_partial:
            raise
        truncated = True
    reserved = []
    # Distinct policy proposals share the reserved capacity, including merges and retreats.
    for index in range(max((len(f) for f in families.values()), default=0)):
        for family in families.values():
            if index < len(family) and family[index] not in reserved:
                reserved.append(family[index])
        if len(reserved) >= limit // 2:
            break
    merged = list(dict.fromkeys(reserved[:limit // 2] + list(base.turns)))[:limit]
    for turn in merged:
        validate_moves(board, species, turn)
    return Candidates(tuple(merged), True, truncated)
