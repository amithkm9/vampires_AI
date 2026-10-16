#!/usr/bin/env python3
"""Verify league replays using their exact snapshotted transition implementation."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.league_support import Runtime, derive_seed, digest, packed, unpacked
from tools.league import configuration_hash, read_records, validate_existing_records


def replay(runtime, initial, game, max_plies):
    board = unpacked(initial, runtime.model)
    side = runtime.model.Species(game["starting_species"])
    candidate = runtime.model.Species(game["species"])
    visited = Counter({(side.value, digest(packed(board))): 1})
    repeated = unfinished = 0
    first_repeat = first_deficit = None
    partial_records = battles = stochastic_battles = 0
    if len(game["turns"]) > max_plies:
        raise ValueError("Too many turns for the configured cap")
    for index, turn in enumerate(game["turns"]):
        if not all(board.groups(s) for s in runtime.model.Species):
            raise ValueError("Moves continue after extinction")
        if turn["ply"] != index or turn["species"] != side.value:
            raise ValueError("Turn sequence mismatch")
        role = "candidate" if side == candidate else "opponent"
        if turn["role"] != role or turn["engine"] != game[role]:
            raise ValueError("Participant role mismatch")
        if (turn["combat_seed"] != derive_seed(game["combat_seed"], "combat", index)
                or turn["policy_seed"] != derive_seed(game["policy_seed"], role, index)):
            raise ValueError("Per-turn random seed does not match the declared match seed")
        if digest(packed(board)) != turn["before_sha256"]:
            raise ValueError("Pre-move board checksum mismatch")
        moves = tuple(runtime.rules.Move(*m) for m in turn["moves"])
        runtime.rules.validate_moves(board, side, moves)
        for move in moves:
            partial_records += move.count < board.at(move.source).count(side)
            cell = board.at(move.target)
            defenders = cell.humans or cell.count(side.opponent)
            if defenders:
                battles += 1
                odds = runtime.rules.battle_odds(move.count, defenders, humans=bool(cell.humans))
                stochastic_battles += odds.attacker_win_probability not in (0, 1)
        board = runtime.simulation.sample_turn(board, side, moves, random.Random(turn["combat_seed"]))
        after = packed(board)
        if after != turn["after"] or digest(after) != turn["after_sha256"]:
            raise ValueError("Recorded successor does not match seeded transition")
        elapsed = turn["elapsed_seconds"]
        if not math.isfinite(elapsed) or not 0 <= elapsed < 2:
            raise ValueError("A successful turn exceeded the local deadline")
        decision = turn["decision"]
        if turn["role"] == "candidate" and decision.get("completed_depth", 0) == 0:
            unfinished += 1
        side = side.opponent
        key = side.value, digest(after)
        if visited[key]:
            repeated += 1
            if first_repeat is None:
                first_repeat = {"after_ply": index, "to_move": side.value, "board": after}
        visited[key] += 1
        if first_deficit is None and sum(board.groups(candidate).values()) < sum(board.groups(candidate.opponent).values()):
            first_deficit = {"after_ply": index, "to_move": side.value, "board": after}
    final = packed(board)
    populations = {s.value: sum(board.groups(s).values()) for s in runtime.model.Species}
    if final != game["final_board"] or digest(final) != game["final_sha256"] or populations != game["populations"]:
        raise ValueError("Final board/population mismatch")
    if game["failure"] is not None:
        if game["score"] is not None or game["winner"] is not None or game["termination"] != "failure":
            raise ValueError("Failed match was assigned a strength result")
        if game["failure"]["ply"] != len(game["turns"]) or game["failure"]["before_sha256"] != digest(final):
            raise ValueError("Failure location mismatch")
        role = "candidate" if side == candidate else "opponent"
        if (game["failure"]["role"], game["failure"]["species"], game["failure"]["engine"]) != (role, side.value, game[role]):
            raise ValueError("Failure participant mismatch")
    else:
        termination = "extinction" if not all(populations.values()) else "local_ply_cap"
        if len(game["turns"]) > max_plies or (termination == "local_ply_cap" and len(game["turns"]) != max_plies):
            raise ValueError("Match termination does not match the configured cap")
        winner = None if len(set(populations.values())) == 1 else max(populations, key=populations.get)
        score = .5 if winner is None else float(winner == candidate.value)
        if (termination, winner, score) != (game["termination"], game["winner"], game["score"]):
            raise ValueError("Recorded result mismatch")
    return {key: game[key] for key in ("match_id", "candidate", "opponent", "map", "species", "score", "termination")} | {
        "plies_verified": len(game["turns"]), "repeated_positions": repeated,
        "candidate_turns_without_completed_iteration": unfinished,
        "partial_move_records": partial_records, "battles": battles, "stochastic_battles": stochastic_battles,
        "first_repeated_position": first_repeat, "first_population_deficit": first_deficit,
    }


def analyze(directory):
    directory = Path(directory).resolve()
    metadata = json.loads((directory / "metadata.json").read_text())
    if configuration_hash(metadata) != metadata["configuration_sha256"]:
        raise ValueError("Experiment configuration checksum mismatch")
    if digest(metadata["schedule"]) != metadata["schedule_sha256"]:
        raise ValueError("Schedule checksum mismatch")
    for relative, expected in metadata["snapshots"]["sha256"].items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Snapshot checksum mismatch: {relative}")
    boards_bytes = (directory / "boards.json").read_bytes()
    if hashlib.sha256(boards_bytes).hexdigest() != metadata["boards_sha256"]:
        raise ValueError("Board manifest checksum mismatch")
    boards = json.loads(boards_bytes)
    for name, record in boards.items():
        if digest(record["board"]) != record["sha256"]:
            raise ValueError(f"Board checksum mismatch: {name}")
    # Apply the same complete-append rule as resume: even a valid JSON object
    # without its final newline can be an interrupted write, not a saved match.
    journal = directory / "matches.jsonl"
    if not journal.is_file():
        raise ValueError("Missing match journal")
    games = read_records(journal)
    validate_existing_records(games, metadata["schedule"], boards)
    if any(g["configuration_sha256"] != metadata["configuration_sha256"] for g in games):
        raise ValueError("Match configuration checksum mismatch")
    runtime = Runtime.load(directory / metadata["snapshots"]["current_package"], "replay")
    try:
        records = [replay(runtime, boards[g["map"]]["board"], g, metadata["max_plies"]) for g in games]
    finally:
        runtime.close()
    return {"run": str(directory), "verified_matches": len(records),
            "verified_plies": sum(r["plies_verified"] for r in records),
            "input_sha256": hashlib.sha256((directory / "matches.jsonl").read_bytes()).hexdigest(),
            "matches": records,
            "limitation": "Replay verifies recorded transitions, not optimal play or official-server parity. "
                          "Repeated states and deficits are diagnostic positions, not proofs of avoidable errors."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path; preserve original records")
    result = analyze(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({k: result[k] for k in ("verified_matches", "verified_plies")}))


if __name__ == "__main__":
    main()
