"""Explicit, shared engine selection for the launcher and experiments."""

from .balanced import choose_balanced
from .evaluation import evaluate
from .experimental.hybrid import hybrid_turns
from .planning import evaluate_outcome, evaluate_strategic
from .search import SearchConfig, choose_turn
from .strategy import cohesive_turns, evaluate_resources, portfolio_turns
from .turns import candidate_turns

ENGINE_NAMES = ("baseline", "balanced", "resources", "balanced_resources", "portfolio",
                "cohesive", "cohesive_material", "adaptive", "hybrid", "hybrid_adaptive",
                "outcome", "strategic", "tactical")
DEFAULT_ENGINE = "strategic"


def default_depth(engine=DEFAULT_ENGINE):
    """Keep the measured normal-budget depth with each selectable mode."""
    return 5 if engine in ("adaptive", "hybrid_adaptive", "outcome", "strategic", "tactical") else 3


def choose_engine(board, species, *, engine=DEFAULT_ENGINE, **kwargs):
    """Keep algorithms separately selectable; default promotion is provisional.

    Every live mode searches opponent replies. 'cohesive' modes deliberately
    omit partial group moves for both sides; all other candidate limitations
    are documented by their generators. Resource scores are heuristics.
    """
    if engine not in ENGINE_NAMES:
        raise ValueError(f"Unknown engine: {engine}")
    if kwargs.get("config") is None:
        kwargs["config"] = SearchConfig(max_depth=default_depth(engine))
    if engine == "baseline":
        return choose_turn(board, species, **kwargs)
    if engine == "resources":
        return choose_turn(board, species, evaluator=evaluate_resources, **kwargs)
    if engine in ("outcome", "strategic", "tactical"):
        return choose_balanced(board, species, **kwargs,
                               evaluator=evaluate_outcome if engine == "outcome" else evaluate_strategic,
                               generator=hybrid_turns if engine == "tactical" else cohesive_turns,
                               reuse_work=True, collect_iterations=True)
    if engine in ("adaptive", "hybrid", "hybrid_adaptive"):
        return choose_balanced(board, species, **kwargs, evaluator=evaluate,
                               generator=cohesive_turns if engine == "adaptive" else hybrid_turns,
                               reuse_work=engine != "hybrid", collect_iterations=True)
    return choose_balanced(board, species, **kwargs,
                           evaluator=evaluate if engine in ("balanced", "cohesive_material") else evaluate_resources,
                           generator=(cohesive_turns if engine.startswith("cohesive") else
                                      portfolio_turns if engine == "portfolio" else candidate_turns))
