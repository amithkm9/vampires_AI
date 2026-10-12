"""Our own bounded joint-turn generator plus a small-position exhaustive oracle.

The live candidate set is deliberately selective, not a proof of optimal play.
It keeps at most one outgoing record per source. The reference enumerator also
covers wider splitting within the brief's conservative record limit.
"""

from dataclasses import dataclass

from .budget import SearchTimeout, checkpoint
from .model import Cell, Species, byte_value
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

    Prefer a representable full move, then a representable partial move, among
    the first movable source's neighbors. This bounded check does not search all
    groups or establish combat safety. If none is representable, retain a legal
    move with unresolved overflow semantics. A 1x1 board or an extinct species
    has no valid turn; never invent a pass or an empty MOV.
    """
    species = Species(species)
    for (x, y), cell in board.cells.items():
        count = cell.count(species)
        if count:
            neighbors = board.neighbors((x, y))
            if neighbors:
                partial = None
                for target in neighbors:
                    destination = board.at(target)
                    capacity = 255 - destination.humans - destination.count(species)
                    if count <= capacity:
                        return (Move(x, y, count, *target),)
                    if capacity > 0 and (partial is None or capacity > partial.count):
                        partial = Move(x, y, capacity, *target)
                return (partial or Move(x, y, count, *neighbors[0]),)
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
    byte_value(count, "source count", minimum=1)
    if not isinstance(target, Cell):
        raise ValueError("Expected a Cell target")
    species = Species(species)
    if count <= 8:
        return tuple(range(1, count + 1))
    amounts = {1, count, count // 2}
    enemy = target.count(species.opponent)
    thresholds = ([target.humans] if target.humans else
                  [(3 * enemy + 1) // 2, 2 * enemy // 3 + 1] if enemy else [])
    for needed in thresholds:
        amounts.update((needed, needed - 1, count - needed))
    # Retain the largest partial arrival supported by the byte-bounded model.
    # Larger legal movements stay visible: their server semantics are unresolved.
    capacity = 255 - target.humans - target.count(species)
    amounts.update((capacity, count - capacity))
    return tuple(sorted(n for n in amounts if 1 <= n <= count))


def compatible_extension(board, species, previous, move):
    """Check a new one-source atom against an already legal live turn.

    Internal construction contract: each atom is an owned, affordable adjacent
    movement. Enforce distinct sources, the packet cap, source/destination
    disjointness and the live shared-combat restriction without rescanning the
    entire board for each proposed combination. Independent tests also run the
    complete six-rule validator on generated turns.
    """
    if len(previous) >= 255:
        return False
    target = board.at(move.target)
    contested = target.humans or target.count(species.opponent)
    for old in previous:
        if (old.source == move.source or old.source == move.target or
                old.target == move.source or (contested and old.target == move.target)):
            return False
    return True


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
    truncated: bool = False


def candidate_turns(board, species, *, limit=64, per_group=12, check=None,
                    allow_partial=False, max_expansions=2048, protect_tactics=False,
                    whole_groups=False):
    """Combine ranked per-source choices with whole-turn rule validation.

    All one-record amounts are retained on a one-group count<=8 position when
    limit>=64. Larger positions use thresholds and a bounded beam. Friendly
    merges are allowed; shared contested destinations are withheld until verified.
    Experimental protect_tactics reserves whole-group attacks with a nonzero
    chance of success before filling the remaining budget by ordinary priority.
    It does not protect every decisive split, escape, merge, or joint attack.
    whole_groups is an experimental action abstraction that excludes all partial
    movements for BOTH sides when used by a search; it is always labeled selective.
    """
    if (type(limit) is not int or limit < 1 or type(per_group) is not int or per_group < 1
            or type(max_expansions) is not int or max_expansions < 1):
        raise ValueError("Candidate limits must be positive integers")
    if any(type(flag) is not bool for flag in (allow_partial, protect_tactics, whole_groups)):
        raise ValueError("Candidate flags must be booleans")
    checkpoint(check)
    species = Species(species)
    groups = board.groups(species)
    if not groups or board.rows * board.columns == 1:
        return Candidates((), False)
    pool = {}
    protected = {}
    beam = [(0.0, ())]
    selective = whole_groups or len(groups) > 1
    truncated = False
    by_source = []
    expansions = 0

    def ranked(items):
        return sorted(items, key=lambda item: (-item[1], tuple(m.as_tuple() for m in item[0])))

    try:
        # Collect singles across sources before spending the budget on combinations.
        for source, count in sorted(groups.items()):
            checkpoint(check)
            options = []
            for target in board.neighbors(source):
                cell = board.at(target)
                amounts = (count,) if whole_groups else significant_amounts(count, cell, species)
                selective |= len(amounts) < count
                for amount in amounts:
                    checkpoint(check)
                    move = Move(*source, amount, *target)
                    priority = move_priority(board, species, move)
                    options.append((priority, move))
                    pool[(move,)] = priority
                    enemy = cell.count(species.opponent)
                    if (protect_tactics and amount == count and
                            (cell.humans or (enemy and 2 * enemy < 3 * count))):
                        protected[(move,)] = priority
            options.sort(key=lambda item: (-item[0], item[1].as_tuple()))
            by_source.append(options[:per_group])
            if len(pool) > limit * 4:
                selective = True
                pool = dict(ranked(pool.items())[:limit * 2])
            if len(protected) > limit * 4:
                protected = dict(ranked(protected.items())[:limit * 2])
        for options in by_source:
            expanded = dict((turn, score) for score, turn in beam)
            for score, previous in beam:
                for priority, move in options:
                    checkpoint(check)
                    expansions += 1
                    if expansions > max_expansions:
                        raise GenerationLimit("Joint candidate work cap reached")
                    if not compatible_extension(board, species, previous, move):
                        continue
                    turn = canonical(previous + (move,))
                    expanded[turn] = score + priority
                    pool[turn] = score + priority
            beam = [(score, turn) for turn, score in ranked(expanded.items())[:limit]]
            if len(pool) > limit * 4:
                selective = True
                pool = dict(ranked(pool.items())[:limit * 2])
    except SearchTimeout:
        if not allow_partial:
            raise
        truncated = True
    except GenerationLimit:
        truncated = True
    # Preserve reserved moves even if intermediate pool trimming removed them.
    pool.update(protected)
    ordered = [turn for turn, _ in ranked(pool.items())]
    selective |= truncated or len(ordered) > limit
    if protected:
        reserved = {turn for turn, _ in ranked(protected.items())[:limit]}
        for turn in ordered:
            if len(reserved) >= limit:
                break
            reserved.add(turn)
        ordered = [turn for turn in ordered if turn in reserved]
    if not truncated:
        try:
            checkpoint(check)
        except SearchTimeout:
            if not allow_partial:
                raise
            truncated = selective = True
    return Candidates(tuple(ordered[:limit]), selective, truncated)
