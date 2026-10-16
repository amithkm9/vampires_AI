"""Per-call working data must release without waiting for cyclic collection."""

from contextlib import contextmanager
import gc
import unittest
import weakref

from vampires.balanced import choose_balanced
from vampires.budget import SearchTimeout
from vampires.evaluation import evaluate
from vampires.experimental.mcts import choose_mcts
from vampires.model import Board, Cell, Species
from vampires.rules import Move
from vampires.search import SearchConfig, choose_turn
from vampires.simulation import iter_turn_outcome_steps
from vampires.turns import exhaustive_turns


@contextmanager
def without_collection():
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()
        gc.collect()


def board():
    return Board(2, 4, {(0, 0): Cell(vampires=2), (3, 1): Cell(werewolves=2)})


class LifecycleTests(unittest.TestCase):
    def test_transition_stream_releases_input_on_exhaustion_close_and_failure(self):
        for ending in ("exhaust", "close", "failure"):
            with self.subTest(ending=ending), without_collection():
                position = board()
                position.cells[1, 0] = Cell(humans=3)
                reference = weakref.ref(position)
                fail = False

                def check():
                    if fail:
                        raise SearchTimeout

                stream = iter_turn_outcome_steps(
                    position, Species.VAMPIRES, (Move(0, 0, 2, 1, 0),), check=check)
                self.assertIsNone(next(stream))
                next(stream)  # Suspend inside the recursive product walker.
                if ending == "exhaust":
                    list(stream)
                elif ending == "close":
                    stream.close()
                else:
                    fail = True
                    with self.assertRaises(SearchTimeout):
                        next(stream)
                del position, stream
                self.assertIsNone(reference())

    def test_exhaustive_generator_releases_input_after_close_and_exhaustion(self):
        for exhausted in (False, True):
            with self.subTest(exhausted=exhausted), without_collection():
                position = board()
                reference = weakref.ref(position)
                stream = exhaustive_turns(position, Species.VAMPIRES)
                if exhausted:
                    list(stream)
                else:
                    next(stream)
                    stream.close()
                del position, stream
                self.assertIsNone(reference())

    def test_search_releases_evaluator_and_leaf_boards_on_every_exit(self):
        # The evaluator is also a sentinel for the entire mutually recursive
        # search closure, including its transposition and candidate caches.
        for engine in ("sequential", "balanced", "adaptive", "mcts"):
            for ending in ("complete", "timeout", "error"):
                with self.subTest(engine=engine, ending=ending), without_collection():
                    leaves = []

                    class Evaluator:
                        def __call__(self, position, perspective, side, *, check=None):
                            leaves.append(weakref.ref(position))
                            if ending == "timeout":
                                raise SearchTimeout
                            if ending == "error":
                                raise ValueError("evaluation failure")
                            return evaluate(position, perspective, side, check=check)

                    evaluator = Evaluator()
                    reference = weakref.ref(evaluator)
                    kwargs = dict(time_budget=10, clock=lambda: 0., evaluator=evaluator,
                                  config=SearchConfig(max_depth=2, preserve_dominance=False))
                    if engine == "mcts":
                        operation = choose_mcts
                        kwargs["max_simulations"] = 5
                    elif engine == "sequential":
                        operation = choose_turn
                    else:
                        operation = choose_balanced
                        kwargs["reuse_work"] = engine == "adaptive"
                    if ending == "error":
                        with self.assertRaisesRegex(ValueError, "evaluation failure"):
                            operation(board(), Species.VAMPIRES, **kwargs)
                    else:
                        decision = operation(board(), Species.VAMPIRES, **kwargs)
                        self.assertEqual(decision.timed_out, ending == "timeout")
                    del evaluator, kwargs
                    self.assertTrue(leaves)
                    self.assertIsNone(reference())
                    self.assertTrue(all(leaf() is None for leaf in leaves))


if __name__ == "__main__":
    unittest.main()
