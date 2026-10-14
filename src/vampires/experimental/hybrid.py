"""Experimental intact-group actions with selective tactical partial refinements.

Both players receive the same abstraction. Partial moves leave creatures at their
origin; wider source splitting and shared contested arrivals are still excluded.
This is a bounded heuristic candidate set, not complete tactical coverage.
"""

from ..budget import SearchTimeout, checkpoint
from ..evaluation import distance
from ..model import Species
from ..rules import Move
from ..strategy import cohesive_turns
from ..turns import (Candidates, GenerationLimit, canonical, compatible_extension,
                    move_priority)


def _local_cells(board, source, work):
    """Only radius-two cells can border a source's possible destinations."""
    x, y = source
    result = []
    for ty in range(max(0, y - 2), min(board.rows, y + 3)):
        for tx in range(max(0, x - 2), min(board.columns, x + 3)):
            work()
            position = tx, ty
            cell = board.at(position)
            if not cell.empty:
                result.append((position, cell))
    return result


def _partials(source, count, target, cell, species, local, work):
    """Propose amounts at capture, defense, reinforcement and capacity boundaries.

    Threat thresholds order/propose moves; they never certify a safe route.
    Especially, a move can leave a vulnerable remainder or expose its arrival.
    Search must assess the enemy's response rather than treating these as safe.
    """
    enemy = cell.count(species.opponent)
    friendly = cell.count(species)
    amounts = set()
    family = "capture" if cell.humans else "attack" if enemy else "reinforce" if friendly else "separate"
    source_threats, target_threats, houses = [], [], []
    for position, population in local:
        work()
        hostile = population.count(species.opponent)
        if hostile:
            if distance(position, source) <= 1:
                source_threats.append(hostile)
            if distance(position, target) <= 1:
                target_threats.append(hostile)
        if population.humans:
            houses.append((position, population.humans))

    if cell.humans or enemy:
        # Small actual combats are where fine amount changes most often matter.
        # Keep risky partial attacks, including sub-threshold human gambles.
        if count <= 8:
            amounts.update(range(1, count))
        else:
            amounts.add(count - 1)
            thresholds = (cell.humans,) if cell.humans else (
                (3 * enemy + 1) // 2, 2 * enemy // 3 + 1, enemy)
            for needed in thresholds:
                amounts.update((needed, needed - 1))
    elif friendly:
        amounts.update((1, count - 1))
        for position, population in local:
            work()
            if distance(position, target) <= 1:
                hostile = population.count(species.opponent)
                if hostile:
                    amounts.update(((3 * hostile + 1) // 2 - friendly,
                                    2 * hostile // 3 + 1 - friendly))
                if population.humans:
                    amounts.add(population.humans - friendly)
    else:
        # A one-creature movement can retain a useful position when passing is
        # forbidden. Limit this refinement to nearby combat or adjacent houses.
        if any(c.count(species.opponent) for _, c in local) or any(
                distance(source, position) <= 1 for position, _ in houses):
            amounts.add(1)
        # Divide a local resource race only when the remainder can afford a
        # different house which the proposed step does not approach.
        for position, humans in houses:
            work()
            if humans < count and distance(target, position) < distance(source, position):
                for other, population in houses:
                    work()
                    if (other != position and population <= count - humans and
                            distance(source, other) <= distance(target, other)):
                        amounts.add(humans)
        # A threatened source may separate toward a less exposed empty neighbor;
        # retaining a small group can matter under stochastic extinction/cutoffs.
        if source_threats and (not target_threats or max(target_threats) < max(source_threats)):
            amounts.add(count - 1)

    for hostile in source_threats:
        work()
        amounts.update((count - (3 * hostile + 1) // 2,
                        count - (2 * hostile // 3 + 1)))
    for hostile in target_threats:
        work()
        # Existing friendly population and guaranteed converted humans augment
        # arrivals, but the latter only applies when the attack amount >= humans.
        credit = friendly or cell.humans
        for required in ((3 * hostile + 1) // 2, 2 * hostile // 3 + 1):
            amount = required - credit
            if not cell.humans or amount >= cell.humans:
                amounts.add(amount)
    # Keep a supported partial at the exact byte boundary; larger legal whole
    # moves remain in the backbone and retain explicit simulator diagnostics.
    amounts.add(255 - friendly - cell.humans)
    return family, tuple(sorted(n for n in amounts if 1 <= n < count))


def hybrid_turns(board, species, *, limit=64, per_group=12, check=None,
                 allow_partial=False, max_expansions=2048, protect_tactics=False):
    """Keep a cohesive backbone and refine selected moves with partial amounts.

    Under a full cap, retain at least three quarters of the ranked whole-group
    turns (at least one for tiny caps), reserving the remaining slots for a mix
    of capture, attack, reinforcement and separation proposals. Spare slots can
    hold additional partials. Thus a full backbone can lose its lowest-ranked
    turns; the hybrid has no monotonic-strength guarantee under the same cap.

    Refinements are single partial records and replacements/additions around up
    to four cohesive turns. Their source is never also a destination. The base
    generator's own work cap is followed by at most max_expansions refinement
    checkpoints; all work shares the supplied deadline. Partial interrupted work
    returns legal completed candidates and is explicitly marked truncated.
    """
    base = cohesive_turns(board, species, limit=limit, per_group=per_group, check=check,
                          allow_partial=allow_partial, max_expansions=max_expansions,
                          protect_tactics=protect_tactics)
    if not base.turns or base.truncated or limit == 1:
        return base
    species = Species(species)
    reserve = min(limit - 1, max(1, limit // 4))
    capacity = max(reserve, limit - len(base.turns))
    family_names = ("capture", "attack", "reinforce", "separate")
    families = {name: {} for name in family_names}
    steps, truncated = 0, False

    def work():
        nonlocal steps
        checkpoint(check)
        steps += 1
        if steps > max_expansions:
            raise GenerationLimit("Hybrid refinement work cap reached")

    def order(items):
        return sorted(items, key=lambda item: (-item[1], tuple(m.as_tuple() for m in item[0])))

    def retain(family, turn, score):
        pool = families[family]
        pool[turn] = score
        if len(pool) > 2 * capacity:
            families[family] = dict(order(pool.items())[:capacity])

    try:
        work()
        groups = board.groups(species)
        for source, count in sorted(groups.items()):
            work()
            if count < 2:
                continue
            local = _local_cells(board, source, work)
            for target in board.neighbors(source):
                work()
                cell = board.at(target)
                family, amounts = _partials(source, count, target, cell, species, local, work)
                for amount in amounts:
                    work()
                    move = Move(*source, amount, *target)
                    priority = move_priority(board, species, move)
                    # A successful minimum human capture leaves useful reserves.
                    # This is ordering only; gambling moves remain candidates.
                    bonus = .01 * (count - amount) if cell.humans and amount >= cell.humans else 0
                    retain(family, (move,), priority + bonus)
                    for backbone in base.turns[:4]:
                        work()
                        other_moves = tuple(old for old in backbone if old.source != source)
                        if compatible_extension(board, species, other_moves, move):
                            combined = canonical(other_moves + (move,))
                            combined_priority = priority + bonus
                            for old in other_moves:
                                work()
                                combined_priority += move_priority(board, species, old)
                            retain(family, combined, combined_priority)
    except SearchTimeout:
        if not allow_partial:
            raise
        truncated = True
    except GenerationLimit:
        truncated = True

    ordered = {name: [turn for turn, _ in order(families[name].items())] for name in family_names}
    partials, seen = [], set()
    for index in range(max(map(len, ordered.values()), default=0)):
        for name in family_names:
            if index < len(ordered[name]):
                turn = ordered[name][index]
                if turn not in seen:
                    seen.add(turn)
                    partials.append(turn)
                    if len(partials) == capacity:
                        break
        if len(partials) == capacity:
            break
    backbone_count = max(1, limit - len(partials))
    merged = tuple(dict.fromkeys(base.turns[:backbone_count] + tuple(partials) +
                                base.turns[backbone_count:]))[:limit]
    return Candidates(merged, True, truncated)
