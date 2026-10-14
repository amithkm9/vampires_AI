"""Reproducible maximum-area board probes; local timing, not a CTI guarantee."""

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
from vampires.engines import ENGINE_NAMES, choose_engine
from vampires.model import Board, Cell, Species
from vampires.rules import validate_moves
from vampires.search import SearchConfig


def positions():
    # Each board is possible only after many UPDs; one MAP packet cannot carry
    # 65025 records. Generation code/source hash records every cell reproducibly.
    yield "checker_dense", Board(255, 255, {
        (x, y): Cell(**{"vampires" if (x + y) % 2 else "werewolves": 1})
        for y in range(255) for x in range(255)})
    cells = {(x, y): Cell(humans=1) for y in range(255) for x in range(255)}
    cells[254, 254], cells[254, 253] = Cell(vampires=1), Cell(werewolves=1)
    yield "houses_dense_last_sources", Board(255, 255, cells)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--engines", nargs="+", choices=ENGINE_NAMES,
                        default=["baseline", "cohesive_material"])
    parser.add_argument("--depth", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path")
    config = SearchConfig(max_depth=args.depth)
    results = []
    for name, board in positions():
        for engine in args.engines:
            for species in Species:
                for budget in (0., .05, 1.25):
                    decision = choose_engine(board, species, engine=engine, time_budget=budget, config=config)
                    validate_moves(board, species, decision.moves)
                    if decision.elapsed_seconds >= 2:
                        raise AssertionError((name, engine, species, budget, decision.elapsed_seconds))
                    results.append({"position": name, "rows": 255, "columns": 255, "occupied_cells": len(board.cells),
                                    "engine": engine, "species": species.value, "budget_seconds": budget,
                                    "decision": asdict(decision), "legal": True})
    paths = sorted((ROOT / "src/vampires").rglob("*.py")) + [Path(__file__)]
    record = {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "platform": platform.platform(), "search_config": asdict(config), "seed": None,
              "board_reproduction": "Exact deterministic positions() in the hashed tool; no random inputs",
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "limitations": "Synthetic local cooperative search timing. No proof of worst-case timing or official-server/CTI parity.",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Passed {len(results)} maximum-area probes; max {max(r['decision']['elapsed_seconds'] for r in results):.6f}s")


if __name__ == "__main__":
    main()
