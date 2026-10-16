"""Record bounded-search diagnostics on deterministic edge-case positions."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vampires.model import Board, Cell, Species
from vampires.engines import DEFAULT_ENGINE, ENGINE_NAMES, choose_engine
from vampires.rules import validate_moves
from vampires.search import SearchConfig


def positions():
    return {
        "many_groups": Board(8, 8, {(x, y): Cell(**{"vampires" if (x + y) % 2 else "werewolves": 2})
                                     for y in range(8) for x in range(8)}),
        "max_byte_random_battle": Board(1, 2, {(0, 0): Cell(vampires=255), (1, 0): Cell(werewolves=255)}),
        "long_column": Board(255, 1, {(0, 0): Cell(vampires=10), (0, 254): Cell(werewolves=10),
                                      (0, 127): Cell(humans=20)}),
        "unsupported_conversion_overflow": Board(1, 3, {(0, 0): Cell(vampires=200),
                                                         (1, 0): Cell(humans=200),
                                                         (2, 0): Cell(werewolves=200)}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=.05)
    parser.add_argument("--engine", choices=ENGINE_NAMES, default=DEFAULT_ENGINE)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path; preserve original records")
    config = SearchConfig(max_depth=args.depth)
    results = []
    for name, board in positions().items():
        cells = [(x, y, c.humans, c.vampires, c.werewolves) for (x, y), c in sorted(board.cells.items())]
        for species in Species:
            decision = choose_engine(board, species, engine=args.engine, time_budget=args.budget, config=config)
            validate_moves(board, species, decision.moves)
            if decision.elapsed_seconds >= 2:
                raise AssertionError(f"Local search exceeded two seconds: {name}, {species.value}")
            results.append({"position": name, "rows": board.rows, "columns": board.columns,
                            "cells": cells, "species": species.value, "seed": None,
                            "legal": True, "decision": asdict(decision)})
    paths = sorted((ROOT / "src/vampires").rglob("*.py")) + [Path(__file__)]
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "configuration": {"budget_seconds": args.budget, "engine": args.engine, **asdict(config)},
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "limits": "Synthetic local timing probes, not worst-case guarantees, CTI timings, or match-strength measurements.",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"Passed {len(results)} search edge cases; max response {max(r['decision']['elapsed_seconds'] for r in results):.4f}s")


if __name__ == "__main__":
    main()
