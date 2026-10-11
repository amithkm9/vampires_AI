"""Hand-written iterative expectiminimax with exact chance probabilities.

Candidate pruning is explicit. A completed search is exact only for its retained
actions, finite depth, evaluation, and stated transition assumptions. It does not
prove full-game optimality. No AI/search/tree/graph library is used.
"""

from dataclasses import dataclass
from math import isfinite
from time import monotonic

from .budget import Deadline, SearchTimeout
from .evaluation import evaluate, terminal_value
from .model import Species
from .rules import validate_moves
from .simulation import AmbiguousBattle, OutcomeLimit, UnsupportedPopulation, turn_outcomes
from .turns import candidate_turns, fallback_turn


@dataclass(frozen=True)
class SearchConfig:
    max_depth: int = 3
    candidates: int = 64
    per_group: int = 12
    max_outcomes: int = 512
    cache_entries: int = 10000

    def __post_init__(self):
        for field in ("max_depth", "candidates", "per_group", "max_outcomes", "cache_entries"):
            value = getattr(self, field)
            if type(value) is not int or value < 1:
                raise ValueError(f"{field} must be a positive integer")
        if self.max_depth > 8:
            raise ValueError("Baseline search depth is limited to 8")


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


def state_key(board):
    return (board.rows, board.columns,
            tuple(sorted((p, c.humans, c.vampires, c.werewolves) for p, c in board.cells.items())))


def choose_turn(board, species, *, time_budget=1.25, expires_at=None,
                config=None, clock=monotonic, evaluator=evaluate):
    """Return a validated legal turn; start at two plies unless depth=1 is explicit.

    A partial root iteration never replaces a completed shallower iteration.
    If no iteration completes, retain the best FULLY evaluated root action from
    the initial two-ply attempt, or the legality fallback if none completes.
    No partially expanded chance node is ever assigned a finished score.
    """
    if not isfinite(time_budget) or time_budget < 0:
        raise ValueError("time_budget must be finite and nonnegative")
    if expires_at is not None and not isfinite(expires_at):
        raise ValueError("expires_at must be finite")
    config = config or SearchConfig()
    species = Species(species)
    started = clock()
    deadline = Deadline(started + time_budget if expires_at is None else expires_at, clock)
    fallback = fallback_turn(board, species)
    best, best_value = fallback, None
    completed_depth = selected_depth = evaluated_roots = 0
    nodes = chance_count = selective_nodes = unsupported_actions = 0
    timed_out = False
    cache = {}

    def leaf(position, side):
        value = evaluator(position, species, side, check=deadline.check)
        if not isfinite(value) or not -1 <= value <= 1:
            raise ValueError("Evaluation must be finite and in [-1, 1]")
        return value

    def action_value(position, side, turn, depth):
        nonlocal chance_count
        outcomes = turn_outcomes(position, side, turn, max_outcomes=config.max_outcomes,
                                 check=deadline.check)
        value = 0.0
        for outcome in outcomes:
            deadline.check()
            chance_count += 1
            value += float(outcome.probability) * visit(outcome.board, side.opponent, depth - 1)
        return value

    def candidates(position, side):
        nonlocal selective_nodes
        result = candidate_turns(position, side, limit=config.candidates,
                                 per_group=config.per_group, check=deadline.check)
        selective_nodes += int(result.selective)
        return result.turns

    def visit(position, side, depth):
        nonlocal nodes, unsupported_actions
        deadline.check()
        nodes += 1
        terminal = terminal_value(position, species)
        if terminal is not None:
            return terminal
        if depth == 0:
            return leaf(position, side)
        key = (state_key(position), side, depth)
        if key in cache:
            return cache[key]
        maximizing = side == species
        value = None
        for turn in candidates(position, side):
            try:
                score = action_value(position, side, turn, depth)
            except (AmbiguousBattle, OutcomeLimit, UnsupportedPopulation):
                unsupported_actions += 1
                continue
            if value is None or (score > value if maximizing else score < value):
                value = score
        # No fabricated pass or terminal result: the unsupported/no-action state
        # receives a heuristic leaf value, and limitations remain in diagnostics.
        if value is None:
            value = leaf(position, side)
        if len(cache) < config.cache_entries:
            cache[key] = value
        return value

    try:
        deadline.check()
        roots = candidates(board, species)
        for depth in range(min(2, config.max_depth), config.max_depth + 1):
            iteration_best, iteration_value = None, None
            count = 0
            for turn in roots:
                deadline.check()
                try:
                    value = action_value(board, species, turn, depth)
                except (AmbiguousBattle, OutcomeLimit, UnsupportedPopulation):
                    unsupported_actions += 1
                    continue
                count += 1
                if iteration_value is None or value > iteration_value:
                    iteration_best, iteration_value = turn, value
                if completed_depth == 0:
                    best, best_value = iteration_best, iteration_value
                    selected_depth, evaluated_roots = depth, count
            if iteration_best is None:
                break
            best, best_value = iteration_best, iteration_value
            completed_depth = selected_depth = depth
            evaluated_roots = count
            roots = (best,) + tuple(turn for turn in roots if turn != best)
    except SearchTimeout:
        timed_out = True
    validate_moves(board, species, best)
    return Decision(best, best_value, completed_depth, selected_depth, evaluated_roots,
                    nodes, chance_count, selective_nodes, unsupported_actions, timed_out,
                    clock() - started)
