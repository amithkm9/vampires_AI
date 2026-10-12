"""Serial, reproducible ablations against the immutable pre-upgrade engine."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
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

from benchmark_strength import ROOT, generated, load_baseline, packed, summarize
from vampires.engines import choose_engine
from vampires.model import Board, Species, load_map
from vampires.rules import Move, validate_moves
from vampires.search import SearchConfig
from vampires.simulation import sample_turn

BASELINE = "d28c5179a721bb7812c14d277a5cc327c641d47c"
ENGINES = ("balanced", "resources", "balanced_resources", "portfolio", "cohesive", "cohesive_material")


def decide(board, side, engine, budget, config):
    return choose_engine(board, side, engine=engine, time_budget=budget, config=config)


def match(initial, engine, species, seed, budget, max_plies, old_model, old_search, config):
    board = Board(initial.rows, initial.columns, initial.cells)
    rng = random.Random(seed)
    side = Species.VAMPIRES
    turns, failure = [], None
    for ply in range(max_plies):
        participant = engine if side == species else "baseline"
        started = monotonic()
        try:
            if participant == "baseline":
                old_board = old_model.Board(board.rows, board.columns, {
                    p: old_model.Cell(c.humans, c.vampires, c.werewolves) for p, c in board.cells.items()})
                decision = old_search.choose_turn(old_board, old_model.Species(side.value), time_budget=budget,
                                                  config=old_search.SearchConfig(**asdict(config)))
                moves = tuple(Move(*move.as_tuple()) for move in decision.moves)
            else:
                decision = decide(board, side, engine, budget, config)
                moves = decision.moves
            elapsed = monotonic() - started
            validate_moves(board, side, moves)
            if elapsed >= 2:
                raise RuntimeError("Two-second local response limit exceeded")
            following = sample_turn(board, side, moves, rng)
            turns.append({"ply": ply, "engine": participant, "species": side.value,
                          "elapsed_seconds": elapsed, "decision": asdict(decision),
                          "moves": [m.as_tuple() for m in moves], "after": packed(following)})
            board = following
            if not board.groups(Species.VAMPIRES) or not board.groups(Species.WEREWOLVES):
                break
            side = side.opponent
        except Exception as exc:
            failure = {"ply": ply, "engine": participant, "type": type(exc).__name__, "message": str(exc)}
            break
    totals = {s.value: sum(board.groups(s).values()) for s in Species}
    winner = (None if totals["vampires"] == totals["werewolves"] else
              max(Species, key=lambda s: totals[s.value]))
    # A failed candidate loses; an opponent failure is explicitly visible too.
    if failure:
        winner = side.opponent
    return {"candidate": engine, "species": species.value, "starting_species": "vampires", "seed": seed,
            "score": .5 if winner is None else float(winner == species),
            "winner": None if winner is None else winner.value, "populations": totals,
            "termination": "failure" if failure else "extinction" if not all(totals.values()) else "pilot_ply_cap",
            "failure": failure, "turns": turns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engines", nargs="+", choices=ENGINES, default=list(ENGINES))
    parser.add_argument("--budget", type=float, default=.05)
    parser.add_argument("--max-plies", type=int, default=60)
    parser.add_argument("--map-seeds", nargs="+", type=int, default=[271, 383])
    parser.add_argument("--combat-seeds", nargs="+", type=int, default=[20261013])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output directory; preserve existing raw evidence")
    if not 0 < args.budget <= 1.5 or not 1 <= args.max_plies:
        parser.error("budget must be in (0, 1.5] and max-plies must be positive")
    args.output.mkdir(parents=True)
    config = SearchConfig()
    maps = {name: load_map(ROOT / "maps" / (name + ".xml")) for name in ("thetrap", "testmap2")}
    maps.update({f"generated_{seed}": generated(seed) for seed in args.map_seeds})
    inputs = {name: packed(board) for name, board in maps.items()}
    (args.output / "boards.json").write_text(json.dumps(inputs, indent=2) + "\n")
    paths = sorted((ROOT / "src/vampires").glob("*.py")) + [Path(__file__), ROOT / "tools/benchmark_strength.py"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "baseline_revision": BASELINE,
                "candidate_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                "cpu_count": os.cpu_count(), "command": shlex.join([sys.executable, *sys.argv]),
                "budget_seconds": args.budget, "max_plies": args.max_plies, "search_config": asdict(config),
                "engines": args.engines, "map_seeds": args.map_seeds, "combat_seeds": args.combat_seeds,
                "source_sha256": hashes,
                "map_sha256": {name: hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest() for name, b in inputs.items()},
                "limitations": "Local unverified simulator; finite-ply population outcome proxy; unknown horizon to both agents; "
                               "small sample and related maps; timing dependent; conditional cluster bootstrap is not a general guarantee."}
    matches = []
    started = monotonic()
    with tempfile.TemporaryDirectory(prefix="vampires-upgrade-baseline-") as directory:
        old_model, old_search, old_hashes = load_baseline(directory, BASELINE)
        metadata["baseline_source_sha256"] = old_hashes
        (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        with (args.output / "matches.jsonl").open("w") as stream:
            for engine in args.engines:
                for name, board in maps.items():
                    for seed in args.combat_seeds:
                        for species in Species:
                            result = match(board, engine, species, seed, args.budget, args.max_plies,
                                           old_model, old_search, config)
                            result["map"] = name
                            matches.append(result)
                            stream.write(json.dumps(result) + "\n")
                            stream.flush()
                            print(engine, name, species.value, result["score"], result["populations"],
                                  len(result["turns"]), result["failure"], flush=True)
                print(json.dumps(summarize(matches)[engine]), flush=True)
    for path, digest in hashes.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Source changed during timed experiment: " + path)
    summary = {"elapsed_seconds": monotonic() - started, "engines": summarize(matches)}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
