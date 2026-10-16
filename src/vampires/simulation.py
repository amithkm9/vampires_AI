"""Exact rational transitions under the written battle rules.

Shared-target battles require an explicit aggregation assumption. Independent
battles use independent draws. Neither convention has official-server parity yet.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import comb

from .budget import checkpoint
from .model import Board, Cell, Species
from .rules import Move, battle_odds, sample_battle, validate_moves


class UnsupportedPopulation(ValueError):
    """A possible successor exceeds the byte-bounded board model."""


class AmbiguousBattle(ValueError):
    """Multiple arrivals at a contested cell need a server resolution rule."""


class OutcomeLimit(ValueError):
    """Exact enumeration exceeds its explicit limit; no mass was discarded."""


def battle_distribution(attackers, defenders, *, humans=False, check=None):
    """Return {(attacker_survivors, defender_survivors): exact probability}.

    Coalesce the empty-cell outcome reached through either winner branch.
    Binomial coefficients aggregate individual survival events; there is no
    sampling, expected-state rounding, or omitted probability mass.
    """
    checkpoint(check)
    odds = battle_odds(attackers, defenders, humans=humans)
    if odds.attacker_win_probability == 1:
        return {(attackers + (defenders if humans else 0), 0): Fraction(1)}
    if odds.attacker_win_probability == 0:
        return {(0, defenders): Fraction(1)}
    p = (Fraction(attackers, 2 * defenders) if attackers <= defenders
         else Fraction(attackers, defenders) - Fraction(1, 2))
    outcomes = {}
    potential_attackers = attackers + (defenders if humans else 0)
    for k in range(potential_attackers + 1):
        checkpoint(check)
        outcomes[k, 0] = p * comb(potential_attackers, k) * p**k * (1-p)**(potential_attackers-k)
    for k in range(defenders + 1):
        checkpoint(check)
        key = 0, k
        probability = (1-p) * comb(defenders, k) * (1-p)**k * p**(defenders-k)
        outcomes[key] = outcomes.get(key, Fraction(0)) + probability
    return outcomes


@dataclass(frozen=True)
class Outcome:
    probability: Fraction
    board: Board


def single_moves(board, species, *, whole_groups_only=False):
    """Enumerate all legal one-record turns, including partial-group movement."""
    for (x, y), count in sorted(board.groups(species).items()):
        amounts = (count,) if whole_groups_only else range(1, count + 1)
        for target in board.neighbors((x, y)):
            for amount in amounts:
                yield Move(x, y, amount, *target)


def single_move_outcomes(board, species, move):
    """Enumerate a one-record turn without mutating the authoritative board."""
    species = Species(species)
    validate_moves(board, species, (move,))
    source, target = board.at(move.source), board.at(move.target)
    remainder = source.count(species) - move.count
    base = dict(board.cells)
    if remainder:
        base[move.source] = Cell(**{species.value: remainder})
    else:
        base.pop(move.source)
    if target.empty or target.count(species):
        counts = {(move.count + target.count(species), 0): Fraction(1)}
        defender_field = species.opponent.value
    else:
        humans = bool(target.humans)
        defenders = target.humans if humans else target.count(species.opponent)
        counts = battle_distribution(move.count, defenders, humans=humans)
        defender_field = "humans" if humans else species.opponent.value
    if any(max(a, d) > 255 for a, d in counts):
        raise UnsupportedPopulation("Possible population exceeds 255; server behavior is unresolved")
    result = []
    for (attackers, defenders), probability in counts.items():
        cells = dict(base)
        cells.pop(move.target, None)
        if attackers:
            cells[move.target] = Cell(**{species.value: attackers})
        elif defenders:
            cells[move.target] = Cell(**{defender_field: defenders})
        result.append(Outcome(probability, Board(board.rows, board.columns, cells)))
    return tuple(result)


def turn_outcomes(board, species, moves, *, shared_target="reject",
                  max_outcomes=4096, check=None):
    """Apply an entire validated turn, debiting all sources before arrivals.

    Default: allow shared empty/friendly destinations, reject shared contested
    destinations. ``shared_target='aggregate'`` is an OFFLINE assumption: add
    arrivals before a single battle. The live baseline uses the default.

    Check the complete Cartesian product size before allocating successor boards.
    Overflow or a size/deadline limit aborts the entire action, never just a tail.
    Input and returned boards have independent cell dictionaries.
    """
    if shared_target not in {"reject", "aggregate"}:
        raise ValueError("Unknown shared-target policy")
    if type(max_outcomes) is not int or max_outcomes < 1:
        raise ValueError("max_outcomes must be a positive integer")
    checkpoint(check)
    species = Species(species)
    moves = validate_moves(board, species, moves)
    outgoing, arrivals, records = {}, {}, {}
    for move in moves:
        checkpoint(check)
        outgoing[move.source] = outgoing.get(move.source, 0) + move.count
        arrivals[move.target] = arrivals.get(move.target, 0) + move.count
        records[move.target] = records.get(move.target, 0) + 1
    base = dict(board.cells)
    for source, count in outgoing.items():
        remaining = board.at(source).count(species) - count
        if remaining:
            base[source] = Cell(**{species.value: remaining})
        else:
            base.pop(source)
    targets, count = [], 1
    for position, incoming in sorted(arrivals.items()):
        checkpoint(check)
        target = board.at(position)
        contested = target.humans or target.count(species.opponent)
        if contested and records[position] > 1 and shared_target == "reject":
            raise AmbiguousBattle("Shared-target combat requires official-server verification")
        # Even a transient incoming population must fit the supported byte model.
        if incoming > 255:
            raise UnsupportedPopulation("Combined arrivals exceed 255")
        if not contested:
            distribution = {(incoming + target.count(species), 0): Fraction(1)}
            defender_field = species.opponent.value
        else:
            # Reject possible overflow before doing expensive binomial arithmetic.
            if target.humans and incoming + target.humans > 255:
                raise UnsupportedPopulation("Possible converted population exceeds 255")
            distribution = battle_distribution(incoming, contested,
                                               humans=bool(target.humans), check=check)
            defender_field = "humans" if target.humans else species.opponent.value
        choices = []
        for (attackers, defenders), probability in distribution.items():
            checkpoint(check)
            if max(attackers, defenders) > 255:
                raise UnsupportedPopulation("Possible population exceeds 255")
            cell = (Cell(**{species.value: attackers}) if attackers else
                    Cell(**{defender_field: defenders}) if defenders else Cell())
            choices.append((probability, cell))
        count *= len(choices)
        if count > max_outcomes:
            raise OutcomeLimit(f"Turn needs {count} or more outcomes; limit is {max_outcomes}")
        targets.append((position, choices))
        base.pop(position, None)
    branches = [(Fraction(1), base)]
    for position, choices in targets:
        expanded = []
        for probability, cells in branches:
            for chance, cell in choices:
                checkpoint(check)
                successor = dict(cells)
                if not cell.empty:
                    successor[position] = cell
                expanded.append((probability * chance, successor))
        branches = expanded
    result = []
    for probability, cells in branches:
        checkpoint(check)
        result.append(Outcome(probability, Board(board.rows, board.columns, cells)))
    return tuple(result)


def _live_layout(board, species, moves, check):
    """Factor a live turn without allocating its Cartesian product of outcomes."""
    checkpoint(check)
    species = Species(species)
    moves = validate_moves(board, species, moves)
    outgoing, arrivals, records = {}, {}, {}
    for move in moves:
        checkpoint(check)
        outgoing[move.source] = outgoing.get(move.source, 0) + move.count
        arrivals[move.target] = arrivals.get(move.target, 0) + move.count
        records[move.target] = records.get(move.target, 0) + 1
    base = dict(board.cells)
    for source, count in outgoing.items():
        left = board.at(source).count(species) - count
        base.pop(source)
        if left:
            base[source] = Cell(**{species.value: left})
    targets = []
    for position, incoming in sorted(arrivals.items()):
        checkpoint(check)
        defender = board.at(position)
        contested = defender.humans or defender.count(species.opponent)
        if contested and records[position] > 1:
            raise AmbiguousBattle("Shared-target combat is unverified")
        possible = incoming + defender.humans + defender.count(species)
        if possible > 255:
            raise UnsupportedPopulation("Possible live successor exceeds 255")
        base.pop(position, None)
        targets.append((position, incoming, defender))
    return species, base, targets


def iter_turn_outcomes(board, species, moves, *, check=None):
    """Stream exact outcomes. Stopping early leaves explicit unvisited mass.

    Each cell's outcomes are ordered by probability; traversal is a depth-first
    Cartesian product, not a globally probability-sorted joint distribution.
    The separate eager implementation remains a regression reference.
    """
    for step in iter_turn_outcome_steps(board, species, moves, check=check):
        if step is not None:
            yield step


def iter_turn_outcome_steps(board, species, moves, *, check=None):
    """Yield preparation checkpoints (None), then the exact outcome stream.

    A joint action can contain many expensive battles. Yield before preparing
    each target's distribution so resumable callers can share work with other
    actions. None carries no probability mass; ordinary transition consumers
    should keep using iter_turn_outcomes. Individual battle arithmetic still
    checks the caller's deadline cooperatively.
    """
    species, base, targets = _live_layout(board, species, moves, check)
    factors = []
    for position, incoming, target in targets:
        checkpoint(check)
        yield None
        defenders = target.humans or target.count(species.opponent)
        counts = (battle_distribution(incoming, defenders, humans=bool(target.humans), check=check)
                  if defenders else {(incoming + target.count(species), 0): Fraction(1)})
        field = "humans" if target.humans else species.opponent.value
        choices = []
        for (a, d), probability in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            checkpoint(check)
            choices.append((probability, Cell(**{species.value: a}) if a else
                            Cell(**{field: d}) if d else Cell()))
        factors.append((position, choices))

    def visit(index, probability):
        checkpoint(check)
        if index == len(factors):
            yield Outcome(probability, Board(board.rows, board.columns, base))
            return
        position, choices = factors[index]
        for chance, cell in choices:
            checkpoint(check)
            if cell.empty:
                base.pop(position, None)
            else:
                base[position] = cell
            yield from visit(index + 1, probability * chance)
        base.pop(position, None)

    try:
        yield from visit(0, Fraction(1))
    finally:
        # Recursive local functions otherwise keep themselves and their board
        # data alive until cyclic GC, even after exhaustion or explicit close.
        visit = None


def sample_turn(board, species, moves, rng, *, check=None):
    """Sample actual integer successors; never replace chance by expected counts."""
    species, cells, targets = _live_layout(board, species, moves, check)
    for position, incoming, target in targets:
        checkpoint(check)
        defenders = target.humans or target.count(species.opponent)
        if defenders:
            a, d = sample_battle(incoming, defenders, rng, humans=bool(target.humans))
        else:
            a, d = incoming + target.count(species), 0
        if a:
            cells[position] = Cell(**{species.value: a})
        elif d:
            cells[position] = Cell(**{"humans" if target.humans else species.opponent.value: d})
    return Board(board.rows, board.columns, cells)
