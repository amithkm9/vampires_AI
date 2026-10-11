"""Our own bounded joint-turn generator plus a small-position exhaustive oracle.

The live candidate set is deliberately selective, not a proof of optimal play.
It keeps at most one outgoing record per source. The reference enumerator also
covers wider splitting within the brief's conservative record limit.
"""

from dataclasses import dataclass

from .budget import checkpoint
from .model import Species
from .rules import Move, battle_odds, validate_moves
from .simulation import single_moves


class NoLegalMove(ValueError):
    pass


class GenerationLimit(ValueError):
    pass


def canonical(moves):
    return tuple(sorted(moves, key=lambda move: move.as_tuple()))


def fallback_turn(board, species):
    """Find one legal record without building the action space or evaluating it.

    This is a legality fallback, not a safety/strength guarantee. A 1x1 board or
    an extinct species has no valid turn; never invent a pass or an empty MOV.
    """
    species = Species(species)
    for (x, y), cell in board.cells.items():
        count = cell.count(species)
        if count:
            neighbors = board.neighbors((x, y))
            if neighbors:
                return (Move(x, y, count, *neighbors[0]),)
    raise NoLegalMove("No legal movement exists for this species")


def exhaustive_turns(board, species, *, max_nodes=100000, check=None):
    """Enumerate canonical legal turns on SMALL boards, including split sources.

    Repeated records on the same directed edge are represented by their summed
    count. This is movement equivalence only, not a claim about repeated battles.
    Hitting max_nodes raises; consumers must not label an interrupted set complete.
    """
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    species = Species(species)
    atoms = []
    nodes = 0
    for move in single_moves(board, species):
        checkpoint(check)
        nodes += 1
        if nodes > max_nodes:
            raise GenerationLimit("Primitive move limit reached")
        atoms.append(move)
    atoms.sort(key=lambda move: move.as_tuple())
    maximum = min(255, len(board.groups(species)))

    def visit(start, selected, edges):
        nonlocal nodes
        for index in range(start, len(atoms)):
            checkpoint(check)
            nodes += 1
            if nodes > max_nodes:
                raise GenerationLimit("Exhaustive turn limit reached")
            move = atoms[index]
            edge = move.source, move.target
            if edge in edges:
                continue
            turn = selected + (move,)
            try:
                validate_moves(board, species, turn)
            except ValueError:
                continue
            yield turn
            if len(turn) < maximum:
                yield from visit(index + 1, turn, edges | {edge})

    yield from visit(0, (), set())


def significant_amounts(count, target, species):
    if count <= 8:
        return tuple(range(1, count + 1))
    amounts = {1, count, count // 2}
    enemy = target.count(species.opponent)
    thresholds = ([target.humans] if target.humans else
                  [(3 * enemy + 1) // 2, 2 * enemy // 3 + 1] if enemy else [])
    for needed in thresholds:
        amounts.update((needed, needed - 1, count - needed))
    return tuple(sorted(n for n in amounts if 1 <= n <= count))


def move_priority(board, species, move):
    """Cheap ordering only; the search evaluates actual stochastic successors."""
    target = board.at(move.target)
    if target.humans or target.count(species.opponent):
        enemy = target.humans or target.count(species.opponent)
        odds = battle_odds(move.count, enemy, humans=bool(target.humans))
        return (odds.expected_attackers - move.count +
                (0 if target.humans else enemy - odds.expected_defenders))
    return .001 * move.count


@dataclass(frozen=True)
class Candidates:
    turns: tuple
    selective: bool


def candidate_turns(board, species, *, limit=64, per_group=12, check=None):
    """Combine ranked per-source choices with whole-turn rule validation.

    All one-record amounts are retained on a one-group count<=8 position when
    limit>=64. Larger positions use thresholds and a bounded beam. Friendly
    merges are allowed; shared contested destinations are withheld until verified.
    """
    if type(limit) is not int or limit < 1 or type(per_group) is not int or per_group < 1:
        raise ValueError("Candidate limits must be positive integers")
    checkpoint(check)
    species = Species(species)
    groups = board.groups(species)
    if not groups or board.rows * board.columns == 1:
        return Candidates((), False)
    pool = {}
    beam = [(0.0, ())]
    selective = len(groups) > 1
    for source, count in sorted(groups.items()):
        checkpoint(check)
        options = []
        for target in board.neighbors(source):
            cell = board.at(target)
            amounts = significant_amounts(count, cell, species)
            selective |= len(amounts) < count
            for amount in amounts:
                checkpoint(check)
                move = Move(*source, amount, *target)
                priority = move_priority(board, species, move)
                options.append((priority, move))
                pool[(move,)] = priority
        options.sort(key=lambda item: (-item[0], item[1].as_tuple()))
        expanded = dict((turn, score) for score, turn in beam)
        for score, previous in beam:
            for priority, move in options[:per_group]:
                checkpoint(check)
                turn = canonical(previous + (move,))
                contested = board.at(move.target).humans or board.at(move.target).count(species.opponent)
                if contested and any(old.target == move.target for old in previous):
                    continue
                try:
                    validate_moves(board, species, turn)
                except ValueError:
                    continue
                expanded[turn] = score + priority
                pool[turn] = score + priority
        beam = sorted(((score, turn) for turn, score in expanded.items()),
                      key=lambda item: (-item[0], tuple(m.as_tuple() for m in item[1])))[:limit]
        # Bound storage between groups, not only at the end.
        if len(pool) > limit * 4:
            selective = True
            pool = dict(sorted(pool.items(), key=lambda item: (-item[1], tuple(m.as_tuple() for m in item[0])))[:limit * 2])
    ordered = sorted(pool, key=lambda turn: (-pool[turn], tuple(m.as_tuple() for m in turn)))
    selective |= len(ordered) > limit
    checkpoint(check)
    return Candidates(tuple(ordered[:limit]), selective)
