"""Exact single-move reference model for analysis, not a complete turn simulator.

Uses rational probabilities as a correctness oracle. Multiple move records,
simultaneous arrivals, live search timing, and server parity remain separate work.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import comb

from .model import Board, Cell, Species
from .rules import Move, battle_odds, validate_moves


class UnsupportedPopulation(ValueError):
    """A possible successor exceeds the byte-bounded board model."""


def battle_distribution(attackers, defenders, *, humans=False):
    """Return {(attacker_survivors, defender_survivors): exact probability}.

    Coalesce the empty-cell outcome reached through either winner branch.
    Binomial coefficients aggregate individual survival events; there is no
    sampling, expected-state rounding, or omitted probability mass.
    """
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
        outcomes[k, 0] = p * comb(potential_attackers, k) * p**k * (1-p)**(potential_attackers-k)
    for k in range(defenders + 1):
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
