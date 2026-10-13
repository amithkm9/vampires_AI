"""Experimental optimistic multi-house reachability, not safe-path planning."""

from dataclasses import dataclass

from .budget import checkpoint
from .evaluation import distance, evaluate, terminal_value
from .model import Species


@dataclass(frozen=True)
class Reachability:
    arrivals: dict
    complete: bool


def human_arrivals(board, species, *, allowed=None, max_states=4096, check=None):
    """Own-turn travel lower bounds through affordable conversion sequences.

    A state is (captured-house bit mask, last house), with its best travel time.
    Population depends only on the mask. Paths ignore opponents and incidental
    occupied cells; different target bounds need not share one feasible itinerary.
    """
    species = Species(species)
    houses = [(p, c.humans) for p, c in sorted(board.cells.items())
              if c.humans and (allowed is None or p in allowed)]
    groups = board.groups(species)
    if len(houses) > 8 or len(groups) > 4:
        return Reachability({}, False)
    arrivals, visited = {}, 0
    for start, count in sorted(groups.items()):
        frontier = {(0, -1): 0}
        for _ in range(len(houses)):
            next_frontier = {}
            for (mask, last), elapsed in frontier.items():
                checkpoint(check)
                visited += 1
                if visited > max_states:
                    return Reachability(arrivals, False)
                population = count + sum(h for i, (_, h) in enumerate(houses) if mask & (1 << i))
                position = start if last == -1 else houses[last][0]
                for i, (target, humans) in enumerate(houses):
                    checkpoint(check)
                    if mask & (1 << i) or humans > population or population + humans > 255:
                        continue
                    time = elapsed + distance(position, target)
                    key = mask | (1 << i), i
                    next_frontier[key] = min(next_frontier.get(key, time), time)
                    arrivals[target] = min(arrivals.get(target, time), time)
            frontier = next_frontier
    return Reachability(arrivals, True)


def evaluate_growth(board, perspective, to_move, *, check=None):
    """Experimental feature with exclusive house ownership and rechecked resources.

    Independently optimistic routes first assign each house to one side. Recompute
    using only that side's assigned houses, so a route cannot borrow humans already
    credited to the opponent. This is still a relaxation, not a joint safe plan.
    """
    perspective, to_move = Species(perspective), Species(to_move)
    base = evaluate(board, perspective, to_move, check=check)
    if terminal_value(board, perspective) is not None:
        return base
    plans = {s: human_arrivals(board, s, check=check) for s in Species}
    if not all(p.complete for p in plans.values()):
        return base
    assigned = {s: set() for s in Species}
    for position, cell in board.cells.items():
        checkpoint(check)
        if not cell.humans:
            continue
        arrivals = [(2 * plans[s].arrivals[position] - (s == to_move), s.value, s)
                    for s in Species if position in plans[s].arrivals]
        if arrivals:
            assigned[min(arrivals)[2]].add(position)
    bonus = 0.
    for s in Species:
        plan = human_arrivals(board, s, allowed=assigned[s], check=check)
        for position, turns in plan.arrivals.items():
            bonus += (1 if s == perspective else -1) * board.at(position).humans / (1 + .25 * turns)
    population = sum(c.humans + c.vampires + c.werewolves for c in board.cells.values())
    return max(-.95, min(.95, base + .12 * bonus / max(1, population)))
