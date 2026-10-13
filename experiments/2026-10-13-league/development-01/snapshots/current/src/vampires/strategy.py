"""Experimental resource projection and diverse, legal movement portfolios.

Straight-line resource races are heuristic estimates, not interception proofs.
Policy turns propose moves; the search still examines adversarial replies.
"""

from math import tanh

from .budget import SearchTimeout, checkpoint
from .evaluation import distance, evaluate, terminal_value
from .model import Species
from .rules import Move
from .turns import Candidates, candidate_turns, canonical, compatible_extension, move_priority


def cohesive_turns(board, species, **kwargs):
    """Whole-group action abstraction; omits partial moves including enemy splits.

    Retains whole-group attacks, merges, retreats and joint movement. This trades
    tactical coverage for more complete finite-depth search, not a proof that
    splitting is inferior. Used identically for both players in experiments.
    """
    return candidate_turns(board, species, whole_groups=True, **kwargs)


def resource_projection(board, to_move, *, check=None):
    """Allocate currently affordable houses exclusively by arrival ply.

    Captures are discounted slowly with distance. No house is credited twice,
    no future converted population is borrowed to cross an affordability threshold,
    and overflow is excluded. Routes can still interfere or be intercepted.
    """
    to_move = Species(to_move)
    checkpoint(check)
    groups = {side: board.groups(side) for side in Species}
    checkpoint(check)
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
    families = {name: [] for name in ("collect", "attack", "merge", "escape")}
    truncated = False
    try:
        checkpoint(check)
        groups, opponents = board.groups(species), board.groups(species.opponent)
        houses = []
        for position, cell in board.cells.items():
            checkpoint(check)
            if cell.humans:
                houses.append((position, cell.humans))
        for policy, family in families.items():
            joint = ()
            for source, count in sorted(groups.items(), key=lambda item: (-item[1], item[0])):
                checkpoint(check)
                choices = []
                targets = []
                candidates = (houses if policy == "collect" else
                              opponents.items() if policy == "attack" else
                              groups.items() if policy == "merge" else ())
                for position, population in candidates:
                    checkpoint(check)
                    if ((policy == "collect" and population <= count) or
                            (policy == "attack" and 2 * count >= 3 * population) or
                            (policy == "merge" and position != source)):
                        targets.append(position)
                for target in board.neighbors(source):
                    checkpoint(check)
                    move = Move(*source, count, *target)
                    gain = move_priority(board, species, move)
                    nearest = None
                    for position in targets:
                        checkpoint(check)
                        steps = distance(target, position)
                        nearest = steps if nearest is None else min(nearest, steps)
                    approach = -(nearest or 0)
                    danger, threat_distance = 0, None
                    for position, population in opponents.items():
                        checkpoint(check)
                        steps = distance(target, position)
                        if steps <= 1:
                            danger += population
                        if 2 * population >= 3 * count:
                            threat_distance = steps if threat_distance is None else min(threat_distance, steps)
                    escape = threat_distance or 0
                    # A local warning, not a guarantee of survival under joint replies.
                    risk = count if danger and 2 * danger >= 3 * count else 0
                    score = gain + .2 * approach - 2 * risk + (.5 * escape if policy == "escape" else 0)
                    choices.append((score, move))
                choices.sort(key=lambda item: (-item[0], item[1].as_tuple()))
                family.extend((move,) for _, move in choices[:2])
                for _, move in choices:
                    checkpoint(check)
                    if not compatible_extension(board, species, joint, move):
                        continue
                    joint = canonical(joint + (move,))
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
    # Base turns and whole-source policy atoms were already checked. Re-running
    # the board-wide validator here could overrun an already-expired deadline.
    return Candidates(tuple(merged), True, truncated)
