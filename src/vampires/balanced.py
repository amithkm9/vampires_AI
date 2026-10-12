"""Resumable expectiminimax: share work across roots, retain chance intervals.

This is a hand-written deterministic scheduler, not a bandit confidence method.
Bounds cover only the generated tree, evaluator, and transition model. Unsearched
actions inside that tree and chance mass keep their full [-1, 1] interval.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from time import monotonic

from .budget import Deadline, SearchTimeout
from .certificates import preserving_turn
from .evaluation import evaluate, terminal_value
from .model import Species
from .rules import validate_moves
from .search import Bounds, Decision, SearchConfig, chance_bounds, state_key
from .simulation import AmbiguousBattle, UnsupportedPopulation, iter_turn_outcomes
from .turns import candidate_turns, fallback_turn


@dataclass(frozen=True)
class BalancedDecision(Decision):
    root_started: int = 0
    root_finished: int = 0
    root_updates: int = 0
    root_pruned: int = 0


def choose_balanced(board, species, *, time_budget=1.25, expires_at=None,
                    config=None, clock=monotonic, evaluator=evaluate,
                    remaining_plies=None, generator=candidate_turns):
    """Round-robin root continuations, followed by deeper complete iterations.

    A continuation yields after a leaf update or candidate generation. Expensive
    stochastic roots therefore cannot monopolize the entire deadline. Proven
    inferior roots stop for this iteration. Interrupted deeper iterations retain
    the previous completed decision; a partial first iteration selects by lower
    bound, then upper bound. No unknown live game cutoff is inferred.
    """
    if not isfinite(time_budget) or time_budget < 0:
        raise ValueError("time_budget must be finite and nonnegative")
    if expires_at is not None and not isfinite(expires_at):
        raise ValueError("expires_at must be finite")
    if remaining_plies is not None and (type(remaining_plies) is not int or remaining_plies < 1):
        raise ValueError("A move requires a positive remaining_plies, or None")
    config = config or SearchConfig()
    species = Species(species)
    started = clock()
    deadline = Deadline(started + time_budget if expires_at is None else expires_at, clock)
    best, best_bounds = fallback_turn(board, species), Bounds(-1., 1.)
    completed_depth = selected_depth = evaluated_roots = 0
    nodes = chance_count = selective_nodes = unsupported_actions = 0
    bounded_actions = truncated_generations = 0
    root_started = root_finished = root_updates = root_pruned = 0
    timed_out = preserved = False
    cache = {}

    def candidates(position, side):
        nonlocal selective_nodes, truncated_generations
        local = Deadline(min(deadline.expires_at, clock() + max(.0002, .03 * time_budget)), clock)
        result = generator(position, side, limit=config.candidates, per_group=config.per_group,
                           check=local.check, allow_partial=True,
                           protect_tactics=config.protect_tactics)
        selective_nodes += int(result.selective)
        truncated_generations += int(result.truncated)
        return result.turns

    def action(position, side, turn, depth, remaining, incumbent=None):
        nonlocal chance_count, unsupported_actions, bounded_actions
        low = high = 0.
        mass = Fraction(0)
        bounds = Bounds(-1., 1.)
        try:
            for index, outcome in enumerate(iter_turn_outcomes(position, side, turn, check=deadline.check)):
                deadline.check()
                if index >= config.max_outcomes:
                    break
                probability = float(outcome.probability)
                for child in visit(outcome.board, side.opponent, depth - 1,
                                   None if remaining is None else remaining - 1):
                    bounds = chance_bounds(low + probability * child.lower,
                                           high + probability * child.upper,
                                           mass + outcome.probability)
                    yield bounds
                    if incumbent is not None and (
                            (side == species and bounds.upper < incumbent.lower) or
                            (side != species and bounds.lower > incumbent.upper)):
                        bounded_actions += int(bounds.point is None)
                        return
                chance_count += 1
                mass += outcome.probability
                low += probability * child.lower
                high += probability * child.upper
        except (AmbiguousBattle, UnsupportedPopulation):
            unsupported_actions += 1
            bounds = Bounds(-1., 1.)
            yield bounds
        bounded_actions += int(bounds.point is None)

    def combine(a, b, maximizing):
        if a is None:
            return b
        function = max if maximizing else min
        return Bounds(function(a.lower, b.lower), function(a.upper, b.upper))

    def visit(position, side, depth, remaining):
        nonlocal nodes
        deadline.check()
        nodes += 1
        terminal = terminal_value(position, species, remaining_plies=remaining)
        if terminal is not None:
            yield Bounds(terminal, terminal)
            return
        if depth == 0:
            value = evaluator(position, species, side, check=deadline.check)
            if not isfinite(value) or not -1 <= value <= 1:
                raise ValueError("Evaluation must be finite and in [-1, 1]")
            yield Bounds(value, value)
            return
        key = state_key(position), side, depth, remaining
        if key in cache:
            yield cache[key]
            return
        turns = candidates(position, side)
        yield Bounds(-1., 1.)  # Generation itself consumes a scheduling quantum.
        value = None
        for index, turn in enumerate(turns):
            for child in action(position, side, turn, depth, remaining, value):
                partial = combine(value, child, side == species)
                if index < len(turns) - 1:
                    partial = combine(partial, Bounds(-1., 1.), side == species)
                yield partial
            value = combine(value, child, side == species)
        value = value or Bounds(-1., 1.)
        if len(cache) < config.cache_entries:
            cache[key] = value
        yield value

    try:
        deadline.check()
        certified = (preserving_turn(board, species, check=deadline.check)
                     if config.preserve_dominance and remaining_plies is None else None)
        if certified:
            best, preserved, best_bounds = certified, True, Bounds(.95, .95)
        else:
            roots = candidates(board, species)
            if roots:
                best = roots[0]
            max_depth = min(config.max_depth, remaining_plies) if remaining_plies is not None else config.max_depth
            for depth in range(min(2, max_depth), max_depth + 1):
                streams = [action(board, species, turn, depth, remaining_plies) for turn in roots]
                bounds = [Bounds(-1., 1.) for _ in roots]
                active = list(range(len(roots)))
                started_roots, finished = set(), set()
                while active:
                    next_round = []
                    incumbent = max(b.lower for b in bounds)
                    for i in active:
                        deadline.check()
                        if bounds[i].upper < incumbent:
                            root_pruned += 1
                            finished.add(i)
                            streams[i].close()
                            continue
                        if i not in started_roots:
                            started_roots.add(i)
                            root_started += 1
                        try:
                            bounds[i] = next(streams[i])
                            root_updates += 1
                            next_round.append(i)
                        except StopIteration:
                            finished.add(i)
                            root_finished += 1
                        incumbent = max(incumbent, bounds[i].lower)
                        winner = max(range(len(roots)), key=lambda j: (bounds[j].lower, bounds[j].upper))
                        if completed_depth == 0:
                            best, best_bounds = roots[winner], bounds[winner]
                            selected_depth, evaluated_roots = depth, len(finished)
                    active = next_round
                if not roots:
                    break
                winner = max(range(len(roots)), key=lambda j: (bounds[j].lower, bounds[j].upper))
                best, best_bounds = roots[winner], bounds[winner]
                completed_depth = selected_depth = depth
                evaluated_roots = len(roots)
                roots = (best,) + tuple(turn for turn in roots if turn != best)
    except SearchTimeout:
        timed_out = True
    validate_moves(board, species, best)
    return BalancedDecision(best, best_bounds.point, completed_depth, selected_depth, evaluated_roots,
                            nodes, chance_count, selective_nodes, unsupported_actions, timed_out,
                            clock() - started, best_bounds.lower, best_bounds.upper, bounded_actions,
                            truncated_generations, preserved, remaining_plies,
                            root_started, root_finished, root_updates, root_pruned)
