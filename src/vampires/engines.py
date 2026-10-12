"""Explicit, shared engine selection for the launcher and experiments."""

from .balanced import choose_balanced
from .evaluation import evaluate
from .search import choose_turn
from .strategy import cohesive_turns, evaluate_resources, portfolio_turns
from .turns import candidate_turns

ENGINE_NAMES = ("baseline", "balanced", "resources", "balanced_resources", "portfolio",
                "cohesive", "cohesive_material")
DEFAULT_ENGINE = "cohesive_material"


def choose_engine(board, species, *, engine=DEFAULT_ENGINE, **kwargs):
    """Keep algorithms separately selectable; default promotion is provisional.

    Every live mode searches opponent replies. 'cohesive' modes deliberately
    omit partial group moves for both sides; all other candidate limitations
    are documented by their generators. Resource scores are heuristics.
    """
    if engine not in ENGINE_NAMES:
        raise ValueError(f"Unknown engine: {engine}")
    if engine == "baseline":
        return choose_turn(board, species, **kwargs)
    if engine == "resources":
        return choose_turn(board, species, evaluator=evaluate_resources, **kwargs)
    return choose_balanced(board, species, **kwargs,
                           evaluator=evaluate if engine in ("balanced", "cohesive_material") else evaluate_resources,
                           generator=(cohesive_turns if engine.startswith("cohesive") else
                                      portfolio_turns if engine == "portfolio" else candidate_turns))
