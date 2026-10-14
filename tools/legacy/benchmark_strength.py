"""Paired local pilot against a pinned baseline; not an official tournament."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import shlex
import subprocess
import sys
import tempfile
from time import monotonic

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vampires.experimental.growth import evaluate_growth
from vampires.experimental.mcts import choose_mcts
from vampires.model import Board, Cell, Species, load_map
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig, choose_turn
from vampires.simulation import sample_turn

BASELINE = "2a08829b1935a80c3c11a37ecea5efb089425268"


def packed(board):
    return {"rows": board.rows, "columns": board.columns,
            "cells": [(x, y, c.humans, c.vampires, c.werewolves) for (x, y), c in sorted(board.cells.items())]}


def generated(seed):
    rng = random.Random(seed)
    cells = {(0, 0): Cell(vampires=4), (6, 5): Cell(werewolves=4)}
    for count in (2, 3, 4):
        available = [(x, y) for x in range(7) for y in range(6)
                     if (x, y) not in cells and (6 - x, 5 - y) not in cells]
        x, y = rng.choice(available)
        cells[x, y] = cells[6 - x, 5 - y] = Cell(humans=count)
    return Board(6, 7, cells)


def load_baseline(directory, revision=BASELINE):
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision, "src/vampires"], cwd=ROOT, text=True).splitlines()
    package = Path(directory) / "baseline_vampires"
    package.mkdir()
    hashes = {}
    for path in paths:
        if not path.endswith(".py"):
            continue
        data = subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)
        target = package / Path(path).relative_to("src/vampires")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[path] = hashlib.sha256(data).hexdigest()
    spec = importlib.util.spec_from_file_location("baseline_vampires", package / "__init__.py",
                                                 submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return importlib.import_module("baseline_vampires.model"), importlib.import_module("baseline_vampires.search"), hashes


def match(initial, candidate, species, seed, budget, max_plies, baseline_model, baseline_search):
    board = Board(initial.rows, initial.columns, initial.cells)
    rng = random.Random(seed)
    current = Species.VAMPIRES
    turns, failure = [], None
    winner = None
    config = SearchConfig()
    for ply in range(max_plies):
        engine = candidate if current == species else "baseline"
        search_seed = seed * 100000 + ply
        started = monotonic()
        try:
            if engine == "baseline":
                # Build the old module's own value types without changing its code.
                old_board = baseline_model.Board(board.rows, board.columns, {
                    p: baseline_model.Cell(c.humans, c.vampires, c.werewolves) for p, c in board.cells.items()})
                decision = baseline_search.choose_turn(old_board, baseline_model.Species(current.value), time_budget=budget)
                moves = tuple(Move(*m.as_tuple()) for m in decision.moves)
            elif engine == "uct":
                decision = choose_mcts(board, current, time_budget=budget, seed=search_seed, config=config)
                moves = decision.moves
            else:
                kwargs = {"evaluator": evaluate_growth} if engine == "growth" else {}
                decision = choose_turn(board, current, time_budget=budget, config=config, **kwargs)
                moves = decision.moves
            elapsed = monotonic() - started
            validate_moves(board, current, moves)
            if elapsed >= 2:
                raise TimeoutError(f"Two-second deadline missed: {elapsed}")
            turns.append({"ply": ply, "engine": engine, "species": current.value, "search_seed": search_seed,
                          "elapsed_seconds": elapsed, "decision": asdict(decision)})
            board = sample_turn(board, current, moves, rng)
        except Exception as exc:
            failure = {"ply": ply, "engine": engine, "error": repr(exc)}
            winner = current.opponent
            break
        if not all(board.groups(s) for s in Species):
            break
        current = current.opponent
    totals = {s.value: sum(board.groups(s).values()) for s in Species}
    if winner is None and totals["vampires"] != totals["werewolves"]:
        winner = Species.VAMPIRES if totals["vampires"] > totals["werewolves"] else Species.WEREWOLVES
    score = .5 if winner is None else float(winner == species)
    return {"candidate": candidate, "species": species.value, "starting_species": "vampires", "seed": seed,
            "score": score, "winner": None if winner is None else winner.value, "populations": totals,
            "termination": "failure" if failure else "extinction" if not all(totals.values()) else "pilot_ply_cap",
            "failure": failure, "turns": turns}


def summarize(matches):
    summary = {}
    for engine in sorted({m["candidate"] for m in matches}):
        games = [m for m in matches if m["candidate"] == engine]
        paired = {}
        for game in games:
            paired.setdefault((game["map"], game["seed"]), []).append(game["score"])
        values = [sum(scores) / len(scores) for scores in paired.values()]
        rng = random.Random(20261011)
        boot = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(2000))
        elapsed = sorted(t["elapsed_seconds"] for m in games for t in m["turns"] if t["engine"] == engine)
        summary[engine] = {"games": len(games), "pairs": len(values), "wins": sum(m["score"] == 1 for m in games),
                           "draws": sum(m["score"] == .5 for m in games), "losses": sum(m["score"] == 0 for m in games),
                           "paired_score": sum(values) / len(values), "paired_score_bootstrap_95": [boot[49], boot[1949]],
                           "pair_scores": values, "failures": sum(m["failure"] is not None for m in games),
                           "max_response_seconds": max(elapsed, default=0),
                           "completed_depth_zero": sum(t["decision"].get("completed_depth") == 0 for m in games
                                                       for t in m["turns"] if t["engine"] == engine),
                           "certificate_turns": sum(t["decision"].get("preserved_dominance", False) for m in games
                                                    for t in m["turns"] if t["engine"] == engine)}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=.03)
    parser.add_argument("--max-plies", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh output directory; raw experiment records are preserved")
    args.output.mkdir(parents=True)
    maps = {name: load_map(ROOT / "maps" / (name + ".xml")) for name in ("thetrap", "testmap2")}
    maps.update({f"generated_{seed}": generated(seed) for seed in (71, 83)})
    inputs = {name: packed(board) for name, board in maps.items()}
    (args.output / "boards.json").write_text(json.dumps(inputs, indent=2) + "\n")
    source_paths = sorted((ROOT / "src/vampires").rglob("*.py")) + [Path(__file__)]
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "baseline_revision": BASELINE,
                "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                "cpu_count": os.cpu_count(), "command": shlex.join([sys.executable, *sys.argv]),
                "budget_seconds": args.budget, "max_plies": args.max_plies, "search_config": asdict(SearchConfig()),
                "source_sha256": source_hashes, "map_sha256": {name: hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
                                                               for name, data in inputs.items()},
                "limits": "Local shared model, finite-ply proxy, low time budget, small map set; no official-server/CTI or tournament claim. "
                          "Pair bootstrap is conditional on the observed map/seed clusters; correlated maps and timing variation limit inference."}
    matches = []
    started = monotonic()
    with tempfile.TemporaryDirectory(prefix="vampires-baseline-") as directory:
        baseline_model, baseline_search, hashes = load_baseline(directory)
        metadata["baseline_source_sha256"] = hashes
        (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        with (args.output / "matches.jsonl").open("w") as stream:
            for engine in ("bounded", "growth", "uct"):
                for map_name, board in maps.items():
                    for seed in (20261011, 20261012):
                        for species in Species:
                            result = match(board, engine, species, seed, args.budget, args.max_plies,
                                           baseline_model, baseline_search)
                            result["map"] = map_name
                            matches.append(result)
                            stream.write(json.dumps(result) + "\n")
                            stream.flush()
                print(engine, summarize(matches)[engine], flush=True)
    for path, digest in source_hashes.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Source changed during experiment: " + path)
    result = {"elapsed_seconds": monotonic() - started, "engines": summarize(matches)}
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {len(matches)} matches to {args.output}", flush=True)


if __name__ == "__main__":
    main()
