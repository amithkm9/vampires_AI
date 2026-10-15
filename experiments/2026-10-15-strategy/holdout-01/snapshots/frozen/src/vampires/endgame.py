"""Small finite-horizon reference trees with exact win/draw/loss probabilities.

This is an OFFLINE oracle, not a live full-game solver. Complete legal coverage
uses the conservative move-record limit and requires explicit combat semantics.
Any generation, state, chance, ambiguity, overflow, or deadline limit raises;
an unfinished calculation must never be reported as an exact solved position.
"""

from dataclasses import dataclass
from fractions import Fraction

from .budget import checkpoint
from .model import Species
from .simulation import turn_outcomes
from .turns import NoLegalMove, exhaustive_turns


class SolverLimit(ValueError):
    pass


@dataclass(frozen=True)
class MatchOutcome:
    win: Fraction
    draw: Fraction
    loss: Fraction

    @property
    def utility(self):
        return self.win - self.loss

    @property
    def score(self):
        return self.win + self.draw / 2


@dataclass(frozen=True)
class SolvedPosition:
    outcome: MatchOutcome
    moves: tuple = ()


class ExactSolver:
    """Finite-horizon expectiminimax, independently of the live search.

    Maximize expected match score. Among exact score ties the acting side
    minimizes its own loss probability. Returned W/D/L describes that policy
    and adversarial reply policy, not every score-equivalent policy.

    ``shared_target`` must be chosen explicitly: 'aggregate' is an unverified
    offline model; 'reject' fails if any encountered legal attack is ambiguous.
    A supplied turn_factory solves only that restricted candidate tree.
    """

    def __init__(self, perspective, *, shared_target, max_states=20000,
                 max_generation_nodes=100000, max_outcomes=4096,
                 turn_factory=None, check=None):
        if shared_target not in {"reject", "aggregate"}:
            raise ValueError("Choose explicit shared-target semantics")
        for value in (max_states, max_generation_nodes, max_outcomes):
            if type(value) is not int or value < 1:
                raise ValueError("Oracle limits must be positive integers")
        self.perspective = Species(perspective)
        self.shared_target = shared_target
        self.max_states = max_states
        self.max_generation_nodes = max_generation_nodes
        self.max_outcomes = max_outcomes
        self.turn_factory = turn_factory
        self.check = check
        self.cache = {}
        self.nodes = 0

    def _terminal(self, board, remaining_plies):
        own = sum(board.groups(self.perspective).values())
        enemy = sum(board.groups(self.perspective.opponent).values())
        if remaining_plies == 0 or not own or not enemy:
            # Equal populations, including simultaneous extinction, are a
            # declared local draw convention pending official-server checks.
            return MatchOutcome(Fraction(own > enemy), Fraction(own == enemy),
                                Fraction(own < enemy))
        return None

    def _rank(self, outcome, side):
        return ((outcome.utility, -outcome.loss) if side == self.perspective
                else (-outcome.utility, -outcome.win))

    def action_values(self, board, side, remaining_plies):
        """Return exact outcomes for EVERY supplied root action, or raise."""
        checkpoint(self.check)
        if type(remaining_plies) is not int or remaining_plies < 0:
            raise ValueError("remaining_plies must be a nonnegative integer")
        side = Species(side)
        if self._terminal(board, remaining_plies) is not None:
            return {}
        turns = (self.turn_factory(board, side) if self.turn_factory is not None
                 else exhaustive_turns(board, side, max_nodes=self.max_generation_nodes,
                                       check=self.check))
        values = {}
        for turn in turns:
            checkpoint(self.check)
            win = draw = loss = Fraction(0)
            for branch in turn_outcomes(board, side, turn, shared_target=self.shared_target,
                                        max_outcomes=self.max_outcomes, check=self.check):
                child = self.solve(branch.board, side.opponent, remaining_plies - 1).outcome
                win += branch.probability * child.win
                draw += branch.probability * child.draw
                loss += branch.probability * child.loss
            values[turn] = MatchOutcome(win, draw, loss)
        if not values:
            raise NoLegalMove("Nonterminal oracle position has no candidate turn")
        return values

    def solve(self, board, side, remaining_plies):
        checkpoint(self.check)
        if type(remaining_plies) is not int or remaining_plies < 0:
            raise ValueError("remaining_plies must be a nonnegative integer")
        side = Species(side)
        cells = tuple(sorted((p, c.humans, c.vampires, c.werewolves)
                             for p, c in board.cells.items()))
        key = board.rows, board.columns, cells, side, remaining_plies
        if key in self.cache:
            return self.cache[key]
        if self.nodes >= self.max_states:
            raise SolverLimit("Exact reference state budget exhausted")
        self.nodes += 1
        outcome = self._terminal(board, remaining_plies)
        if outcome is not None:
            result = SolvedPosition(outcome)
        else:
            values = self.action_values(board, side, remaining_plies)
            turn = max(values, key=lambda t: self._rank(values[t], side))
            result = SolvedPosition(values[turn], turn)
        self.cache[key] = result
        return result
