"""Hand-written iterative expectiminimax with exact chance probabilities.

Candidate pruning is explicit. A completed search is exact only for its retained
actions, finite depth, evaluation, and stated transition assumptions. It does not
prove full-game optimality. No AI/search/tree/graph library is used.
"""

from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
from math import isfinite
from time import monotonic

from .budget import Deadline, SearchTimeout
from .certificates import preserving_turn
from .evaluation import evaluate, terminal_value
from .model import Species
from .rules import validate_moves
from .simulation import AmbiguousBattle, UnsupportedPopulation, iter_turn_outcomes
from .turns import candidate_turns, fallback_turn


@dataclass(frozen=True)
class SearchConfig:
    max_depth: int = 3
    candidates: int = 64
    per_group: int = 12
    max_outcomes: int = 512
    cache_entries: int = 10000
    preserve_dominance: bool = True
    protect_tactics: bool = False

    def __post_init__(self):
        for field in ("max_depth", "candidates", "per_group", "max_outcomes", "cache_entries"):
            value = getattr(self, field)
            if type(value) is not int or value < 1:
                raise ValueError(f"{field} must be a positive integer")
        if self.max_depth > 8:
            raise ValueError("Baseline search depth is limited to 8")
        for field in ("preserve_dominance", "protect_tactics"):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f"{field} must be a boolean")


@dataclass(frozen=True)
class Decision:
    moves: tuple
    value: float | None
    completed_depth: int
    selected_depth: int
    evaluated_root_actions: int
    nodes: int
    chance_outcomes: int
    selective_nodes: int
    unsupported_actions: int
    timed_out: bool
    elapsed_seconds: float
    value_lower: float = -1.0
    value_upper: float = 1.0
    bounded_actions: int = 0
    truncated_generations: int = 0
    preserved_dominance: bool = False
    remaining_plies: int | None = None


@dataclass(frozen=True)
class Bounds:
    lower: float
    upper: float

    @property
    def point(self):
        return (self.lower + self.upper) / 2 if self.upper - self.lower < 1e-9 else None


def chance_bounds(lower_sum, upper_sum, visited_mass):
    """Unvisited mass retains [-1,1]; never renormalize a probability prefix."""
    remaining = float(1 - visited_mass)
    # Small outward padding covers accumulated binary-float expectation rounding.
    return Bounds(max(-1., lower_sum - remaining - 1e-12),
                  min(1., upper_sum + remaining + 1e-12))


def state_key(board):
    return (board.rows, board.columns,
            tuple(sorted((p, c.humans, c.vampires, c.werewolves) for p, c in board.cells.items())))


def choose_turn(board, species, *, time_budget=1.25, expires_at=None,
                config=None, clock=monotonic, evaluator=evaluate, remaining_plies=None):
    """Iterative expectiminimax with conservative bounds for unexpanded chance.

    Root selection maximizes the lower bound, breaking ties by upper bound.
    Bounds apply to the retained candidate tree and finite-depth evaluator, not
    all legal actions or full-game win probability. Unknown model actions remain
    [-1,1]. Interrupted deeper iterations cannot replace a finished iteration.
    A supplied remaining_plies counts ALL player moves, including this move.
    At zero, use population-based win/draw/loss instead of a heuristic. None
    means unknown (the live protocol default); search depth is not a game cutoff.
    """
    if not isfinite(time_budget) or time_budget < 0:
        raise ValueError("time_budget must be finite and nonnegative")
    if expires_at is not None and not isfinite(expires_at):
        raise ValueError("expires_at must be finite")
    if remaining_plies is not None and (type(remaining_plies) is not int or remaining_plies < 1):
        raise ValueError("A move requires a positive remaining_plies, or None for unknown")
    config = config or SearchConfig()
    species = Species(species)
    started = clock()
    deadline = Deadline(started + time_budget if expires_at is None else expires_at, clock)
    best = fallback_turn(board, species)
    best_bounds = Bounds(-1., 1.)
    completed_depth = selected_depth = evaluated_roots = 0
    nodes = chance_count = selective_nodes = unsupported_actions = 0
    bounded_actions = truncated_generations = 0
    timed_out = preserved = False
    cache = {}

    def leaf(position, side):
        value = evaluator(position, species, side, check=deadline.check)
        if not isfinite(value) or not -1 <= value <= 1:
            raise ValueError("Evaluation must be finite and in [-1, 1]")
        return Bounds(value, value)

    def action_value(position, side, turn, depth, remaining, incumbent=None):
        nonlocal chance_count, bounded_actions, unsupported_actions
        low = high = 0.0
        mass = Fraction(0)
        try:
            stream = iter_turn_outcomes(position, side, turn, check=deadline.check)
            for outcome in islice(stream, config.max_outcomes):
                deadline.check()
                child = visit(outcome.board, side.opponent, depth - 1,
                              None if remaining is None else remaining - 1)
                chance_count += 1
                mass += outcome.probability
                low += float(outcome.probability) * child.lower
                high += float(outcome.probability) * child.upper
                bounds = chance_bounds(low, high, mass)
                if incumbent is not None:
                    if side == species and bounds.upper < incumbent.lower:
                        break
                    if side != species and bounds.lower > incumbent.upper:
                        break
        except (AmbiguousBattle, UnsupportedPopulation):
            unsupported_actions += 1
            return Bounds(-1., 1.)
        result = chance_bounds(low, high, mass)
        if result.point is None:
            bounded_actions += 1
        return result

    def candidates(position, side):
        nonlocal selective_nodes, truncated_generations
        # Spend at most 3% of the original budget on any one generation call.
        local = Deadline(min(deadline.expires_at, clock() + max(.0002, .03 * time_budget)), clock)
        result = candidate_turns(position, side, limit=config.candidates,
                                 per_group=config.per_group, check=local.check, allow_partial=True,
                                 protect_tactics=config.protect_tactics)
        selective_nodes += int(result.selective)
        truncated_generations += int(result.truncated)
        return result.turns

    def visit(position, side, depth, remaining):
        nonlocal nodes
        deadline.check()
        nodes += 1
        terminal = terminal_value(position, species, remaining_plies=remaining)
        if terminal is not None:
            return Bounds(terminal, terminal)
        if depth == 0:
            return leaf(position, side)
        key = (state_key(position), side, depth, remaining)
        if key in cache:
            return cache[key]
        value = None
        for turn in candidates(position, side):
            child = action_value(position, side, turn, depth, remaining, value)
            if value is None:
                value = child
            elif side == species:
                value = Bounds(max(value.lower, child.lower), max(value.upper, child.upper))
            else:
                value = Bounds(min(value.lower, child.lower), min(value.upper, child.upper))
        if value is None:
            value = Bounds(-1., 1.)
        if len(cache) < config.cache_entries:
            cache[key] = value
        return value

    try:
        deadline.check()
        # Known-horizon comparisons evaluate outcomes explicitly. The live
        # unknown-horizon certificate remains the same conditional policy.
        certified = (preserving_turn(board, species, check=deadline.check)
                     if config.preserve_dominance and remaining_plies is None else None)
        if certified:
            best, preserved = certified, True
            # A conditional strategy certificate is not a terminal game result.
            best_bounds = Bounds(.95, .95)
        else:
            roots = candidates(board, species)
            if roots:
                best = roots[0]  # Retain useful generation even if search cannot finish an action.
            max_depth = min(config.max_depth, remaining_plies) if remaining_plies is not None else config.max_depth
            for depth in range(min(2, max_depth), max_depth + 1):
                iteration_best = iteration_bounds = None
                count = 0
                for turn in roots:
                    deadline.check()
                    bounds = action_value(board, species, turn, depth, remaining_plies, iteration_bounds)
                    count += 1
                    if (iteration_bounds is None or
                            (bounds.lower, bounds.upper) > (iteration_bounds.lower, iteration_bounds.upper)):
                        iteration_best, iteration_bounds = turn, bounds
                    if completed_depth == 0:
                        best, best_bounds = iteration_best, iteration_bounds
                        selected_depth, evaluated_roots = depth, count
                if iteration_best is None:
                    break
                best, best_bounds = iteration_best, iteration_bounds
                completed_depth = selected_depth = depth
                evaluated_roots = count
                roots = (best,) + tuple(turn for turn in roots if turn != best)
    except SearchTimeout:
        timed_out = True
    finally:
        # Break mutual recursion so per-turn caches do not wait for cyclic GC.
        action_value = visit = None
    validate_moves(board, species, best)
    return Decision(best, best_bounds.point, completed_depth, selected_depth, evaluated_roots,
                    nodes, chance_count, selective_nodes, unsupported_actions, timed_out,
                    clock() - started, best_bounds.lower, best_bounds.upper, bounded_actions,
                    truncated_generations, preserved, remaining_plies)
