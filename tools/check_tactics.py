"""Exact development-position audit of candidate and opponent-reply omissions.

All legal trees use the explicit OFFLINE aggregate shared-target assumption.
This measures move-generation loss separately from live time/chance truncation.
It is not official-server parity, a map solution, or a match-strength benchmark.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import shlex
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vampires.budget import Deadline, SearchTimeout
from vampires.endgame import ExactSolver, SolverLimit
from vampires.model import Board, Cell, Species
from vampires.simulation import OutcomeLimit, UnsupportedPopulation, turn_outcomes
from vampires.turns import GenerationLimit, candidate_turns, significant_amounts

V = Species.VAMPIRES


def packed(board):
    return {"rows": board.rows, "columns": board.columns,
            "cells": [(x, y, c.humans, c.vampires, c.werewolves)
                      for (x, y), c in sorted(board.cells.items())]}


def fraction(value):
    return {"exact": str(value), "decimal": float(value)}


def outcome(value):
    return {key: fraction(getattr(value, key)) for key in ("win", "draw", "loss", "score")}


def positions():
    # Development fixtures selected before measuring generator regret.
    fixtures = {
        "trailing_gamble": (Board(2, 3, {(1, 0): Cell(vampires=2), (0, 0): Cell(humans=3),
                                          (2, 1): Cell(werewolves=3)}), 1),
        "preserve_lead": (Board(2, 3, {(1, 0): Cell(vampires=3), (0, 0): Cell(humans=4),
                                        (2, 1): Cell(werewolves=2)}), 1),
        "preserve_draw": (Board(1, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(werewolves=1)}), 2),
        "shared_capture": (Board(2, 3, {(0, 0): Cell(vampires=1), (2, 0): Cell(vampires=2),
                                         (2, 1): Cell(werewolves=3), (1, 1): Cell(humans=3)}), 1),
        "shared_attack": (Board(2, 3, {(0, 0): Cell(vampires=2), (2, 0): Cell(vampires=2),
                                        (1, 1): Cell(werewolves=3)}), 2),
        "escape_and_reinforce": (Board(2, 3, {(1, 0): Cell(vampires=2), (0, 1): Cell(werewolves=3),
                                               (2, 1): Cell(werewolves=1), (0, 0): Cell(humans=3)}), 2),
        "joint_resource_race": (Board(2, 4, {(0, 0): Cell(vampires=2), (3, 0): Cell(vampires=3),
                                              (1, 1): Cell(werewolves=4), (2, 1): Cell(humans=3)}), 2),
    }
    # Fixed development seeds; these are not a held-out promotion set.
    for seed in range(1201, 1209):
        rng = random.Random(seed)
        cells = rng.sample([(x, y) for y in range(2) for x in range(3)], 4)
        board = Board(2, 3, {cells[0]: Cell(vampires=rng.randint(1, 2)),
                             cells[1]: Cell(vampires=rng.randint(1, 2)),
                             cells[2]: Cell(werewolves=rng.randint(1, 3)),
                             cells[3]: Cell(humans=rng.randint(1, 3))})
        fixtures[f"generated_{seed}"] = board, 2
    return fixtures


def omission_kind(board, side, turn):
    for move in turn:
        cell = board.at(move.target)
        if (cell.humans or cell.count(side.opponent)) and sum(m.target == move.target for m in turn) > 1:
            return "unverified_shared_target"
    if len({m.source for m in turn}) < len(turn):
        return "wider_source_split"
    for move in turn:
        if move.count not in significant_amounts(board.at(move.source).count(side), board.at(move.target), side):
            return "population_amount_pruning"
    return "ranking_or_combination_cap"


def audit(board, horizon, *, perspective=V, limit=64, seconds=5, max_states=20000, protect_tactics=False):
    perspective = Species(perspective)
    deadline = Deadline(monotonic() + seconds)
    reference = ExactSolver(perspective, shared_target="aggregate", max_states=max_states, check=deadline.check)
    full = reference.action_values(board, perspective, horizon)
    def retained(position, side):
        generated = candidate_turns(position, side, limit=limit, check=deadline.check,
                                    protect_tactics=protect_tactics)
        return generated.turns
    restricted = ExactSolver(perspective, shared_target="aggregate", max_states=max_states,
                             turn_factory=retained, check=deadline.check)
    partial = restricted.action_values(board, perspective, horizon)
    best = max(full, key=lambda t: (full[t].score, -full[t].loss))
    selected = max(partial, key=lambda t: (partial[t].score, -partial[t].loss))
    best_retained = max(full[t].score for t in partial)
    optimistic = max(partial, key=lambda t: partial[t].score - full[t].score)
    reply_example = None
    biggest_gap = 0
    for branch in turn_outcomes(board, perspective, optimistic, shared_target="aggregate", check=deadline.check):
        reply = reference.solve(branch.board, perspective.opponent, horizon - 1)
        pruned = restricted.solve(branch.board, perspective.opponent, horizon - 1)
        gap = branch.probability * (pruned.outcome.score - reply.outcome.score)
        if gap > biggest_gap and reply.moves not in retained(branch.board, perspective.opponent):
            biggest_gap = gap
            reply_example = {"board": packed(branch.board), "to_move": perspective.opponent.value,
                             "moves": [m.as_tuple() for m in reply.moves],
                             "reason": omission_kind(branch.board, perspective.opponent, reply.moves),
                             "branch_probability": fraction(branch.probability),
                             "weighted_score_gap": fraction(gap)}
    return {"complete": True, "legal_root_turns": len(full), "retained_root_turns": len(partial),
            "reference_states": reference.nodes, "restricted_states": restricted.nodes,
            "optimal": {"moves": [m.as_tuple() for m in best], "outcome": outcome(full[best])},
            "selected": {"moves": [m.as_tuple() for m in selected],
                         "predicted": outcome(partial[selected]), "actual": outcome(full[selected])},
            "root_omission_regret": fraction(full[best].score - best_retained),
            "decision_regret": fraction(full[best].score - full[selected].score),
            "largest_reply_optimism": fraction(partial[optimistic].score - full[optimistic].score),
            "most_optimistic_action": [m.as_tuple() for m in optimistic],
            "missing_optimal_root_reason": omission_kind(board, perspective, best) if best not in partial else None,
            "missing_reply_example": reply_example}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds-per-case", type=float, default=5)
    parser.add_argument("--limits", type=int, nargs="+", default=[64, 8])
    parser.add_argument("--protect-tactics", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path; preserve original records")
    if not 0 < args.seconds_per_case < float("inf") or any(n < 1 for n in args.limits):
        parser.error("Positive finite budgets and candidate limits required")
    started = monotonic()
    records = []
    for name, (board, horizon) in positions().items():
        for perspective in Species:
            for limit in args.limits:
                record = {"position": name, "board": packed(board), "remaining_plies": horizon,
                          "species": perspective.value, "candidate_limit": limit, "max_states_per_solver": 20000}
                begin = monotonic()
                try:
                    record.update(audit(board, horizon, perspective=perspective, limit=limit,
                                        seconds=args.seconds_per_case, protect_tactics=args.protect_tactics))
                except (SolverLimit, SearchTimeout, GenerationLimit, OutcomeLimit, UnsupportedPopulation) as exc:
                    record.update(complete=False, error=type(exc).__name__, message=str(exc))
                record["elapsed_seconds"] = monotonic() - begin
                records.append(record)
                print(name, perspective.value, limit, "regret=" + record.get("decision_regret", {}).get("exact", "incomplete"), flush=True)
    paths = sorted((ROOT / "src/vampires").rglob("*.py")) + [Path(__file__)]
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "platform": platform.platform(), "revision": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "command": shlex.join([sys.executable, *sys.argv]),
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "seed_range": [1201, 1208], "seconds_per_case": args.seconds_per_case,
              "protect_tactics": args.protect_tactics,
              "elapsed_seconds": monotonic() - started,
              "limits": "Exact finite-horizon DEVELOPMENT positions under offline shared-target aggregation and independent combat. "
                        "Equal populations are a draw convention. Selective tree uses live generation without wall-clock truncation. "
                        "Regret is expected match-score loss, not a tournament win rate. Incomplete cases are unsolved.",
              "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
