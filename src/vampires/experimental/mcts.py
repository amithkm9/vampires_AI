"""Experimental adversarial UCT with sampled chance; not the default player.

Uses the same legal generator, integer transition rules, and bounded evaluator as
expectiminimax. This is a finite-depth pilot challenger, without progressive
widening or a claim to reproduce every enhancement in the research literature.
"""

from dataclasses import dataclass
from math import isfinite, log, sqrt
import random
from time import monotonic

from ..budget import Deadline, SearchTimeout
from ..certificates import preserving_turn
from ..evaluation import evaluate, terminal_value
from ..model import Species
from ..rules import validate_moves
from ..search import SearchConfig, state_key
from ..simulation import AmbiguousBattle, UnsupportedPopulation, sample_turn
from ..turns import candidate_turns, fallback_turn


@dataclass(frozen=True)
class SampledDecision:
    moves: tuple
    simulations: int
    elapsed_seconds: float
    timed_out: bool
    unsupported_actions: int
    preserved_dominance: bool


def choose_mcts(board, species, *, time_budget=1.25, seed=0, config=None,
                max_simulations=100000, evaluator=evaluate, clock=monotonic):
    if not isfinite(time_budget) or time_budget < 0 or type(max_simulations) is not int or max_simulations < 1:
        raise ValueError("Invalid MCTS budget or simulation limit")
    config, species = config or SearchConfig(), Species(species)
    started = clock()
    deadline = Deadline(started + time_budget, clock)
    rng = random.Random(seed)
    fallback = fallback_turn(board, species)
    tree = {}
    simulations = unsupported = 0
    timed_out = preserved = False
    root_key = (state_key(board), species, config.max_depth)

    def visit(position, side, depth):
        nonlocal unsupported
        deadline.check()
        terminal = terminal_value(position, species)
        if terminal is not None:
            return terminal
        if depth == 0:
            return evaluator(position, species, side, check=deadline.check)
        key = (state_key(position), side, depth)
        if key not in tree:
            local = Deadline(min(deadline.expires_at, clock() + max(.0002, .03 * time_budget)), clock)
            choices = candidate_turns(position, side, limit=config.candidates, per_group=config.per_group,
                                      check=local.check, allow_partial=True,
                                      protect_tactics=config.protect_tactics).turns
            if not choices:
                return evaluator(position, species, side, check=deadline.check)
            if len(tree) >= config.cache_entries:
                return evaluator(position, species, side, check=deadline.check)
            tree[key] = [[turn, 0, 0.] for turn in choices]
        edges = tree[key]
        visits = sum(edge[1] for edge in edges)
        untried = next((edge for edge in edges if edge[1] == 0), None)
        sign = 1 if side == species else -1
        edge = untried if untried is not None else max(
            edges, key=lambda e: sign * e[2] / e[1] + 1.4 * sqrt(log(max(1, visits)) / e[1]))
        try:
            successor = sample_turn(position, side, edge[0], rng, check=deadline.check)
        except (AmbiguousBattle, UnsupportedPopulation):
            # Experimental conservative penalty to the acting side, not a sampled
            # physical outcome. Count explicitly; supplied-map totals avoid overflow.
            unsupported += 1
            value = -float(sign)
        else:
            value = visit(successor, side.opponent, depth - 1)
        if not isfinite(value) or not -1 <= value <= 1:
            raise ValueError("MCTS evaluator must be finite and in [-1,1]")
        edge[1] += 1
        edge[2] += value
        return value

    try:
        deadline.check()
        certified = preserving_turn(board, species, check=deadline.check) if config.preserve_dominance else None
        if certified:
            fallback, preserved = certified, True
        else:
            for _ in range(max_simulations):
                visit(board, species, config.max_depth)
                simulations += 1
    except SearchTimeout:
        timed_out = True
    finally:
        visit = None  # Release the self-referential closure after every exit.
    edges = tree.get(root_key, [])
    visited = [edge for edge in edges if edge[1]]
    if visited:
        fallback = max(visited, key=lambda e: (e[1], e[2] / e[1]))[0]
    validate_moves(board, species, fallback)
    return SampledDecision(fallback, simulations, clock() - started, timed_out, unsupported, preserved)
