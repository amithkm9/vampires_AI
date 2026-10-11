"""Replay saved engine matches to diagnose outcomes without rerunning search."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vampires.model import Board, Cell, Species
from vampires.rules import Move, battle_odds
from vampires.simulation import sample_turn


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed(board):
    return {"rows": board.rows, "columns": board.columns,
            "cells": [(x, y, c.humans, c.vampires, c.werewolves)
                      for (x, y), c in sorted(board.cells.items())]}


def replay(initial, game):
    if game["failure"] is not None:
        raise ValueError("Failed-match replay needs separate handling")
    board = Board(initial["rows"], initial["columns"],
                  {(x, y): Cell(h, v, w) for x, y, h, v, w in initial["cells"]})
    rng = random.Random(game["seed"])
    candidate = Species(game["species"])
    current = Species(game["starting_species"])
    seen, repeats, events = {}, [], []
    chance_battles = monster_battles = candidate_turns = unfinished = 0
    first_deficit = first_unfinished = None
    for index, turn in enumerate(game["turns"]):
        if turn["ply"] != index or Species(turn["species"]) != current:
            raise ValueError("Recorded turn order is inconsistent")
        expected_engine = game["candidate"] if current == candidate else "baseline"
        if turn["engine"] != expected_engine:
            raise ValueError("Recorded engine and species are inconsistent")
        state = (current.value, tuple(tuple(c) for c in packed(board)["cells"]))
        if state in seen:
            repeats.append({"ply": index, "previous_ply": seen[state]})
        seen[state] = index
        decision = turn["decision"]
        if current == candidate:
            candidate_turns += 1
            if decision.get("completed_depth") == 0 and not decision.get("preserved_dominance", False):
                unfinished += 1
                if first_unfinished is None:
                    first_unfinished = {"ply": index, "to_move": current.value,
                                        "board": packed(board), "decision": decision}
        moves = tuple(Move(**move) for move in decision["moves"])
        arrivals = {}
        for move in moves:
            arrivals[move.target] = arrivals.get(move.target, 0) + move.count
        for target, attackers in arrivals.items():
            cell = board.at(target)
            defenders = cell.humans or cell.count(current.opponent)
            if defenders:
                probability = battle_odds(attackers, defenders, humans=bool(cell.humans)).attacker_win_probability
                chance_battles += 0 < probability < 1
                monster_battles += not bool(cell.humans)
                events.append({"ply": index, "species": current.value, "target": target,
                               "defender": "humans" if cell.humans else current.opponent.value,
                               "attackers": attackers, "defenders": defenders,
                               "random_combat": 0 < probability < 1})
        board = sample_turn(board, current, moves, rng)
        current = current.opponent
        if first_deficit is None and sum(board.groups(candidate).values()) < sum(board.groups(candidate.opponent).values()):
            first_deficit = {"after_ply": index, "to_move": current.value, "board": packed(board)}
        if index + 1 < len(game["turns"]) and not all(board.groups(s) for s in Species):
            raise ValueError("Recorded moves continue after extinction")
    populations = {s.value: sum(board.groups(s).values()) for s in Species}
    if populations != game["populations"]:
        raise ValueError("Replay population mismatch")
    winner = None if len(set(populations.values())) == 1 else max(populations, key=populations.get)
    score = .5 if winner is None else float(winner == candidate.value)
    if score != game["score"] or winner != game["winner"]:
        raise ValueError("Replay result mismatch")
    termination = "extinction" if not all(populations.values()) else "pilot_ply_cap"
    if termination != game["termination"]:
        raise ValueError("Replay termination mismatch")
    return {"candidate": game["candidate"], "map": game["map"], "species": candidate.value,
            "seed": game["seed"], "score": score, "termination": termination,
            "plies": len(game["turns"]), "candidate_turns": candidate_turns,
            "unfinished_root_turns": None if game["candidate"] == "uct" else unfinished,
            "repeated_state_visits": len(repeats), "first_repeat": repeats[0] if repeats else None,
            "monster_battles": monster_battles, "random_battles": chance_battles,
            "populations": populations, "remaining_humans": sum(c.humans for c in board.cells.values()),
            "combat_events": events, "first_trailing_state": first_deficit,
            "first_unfinished_root": first_unfinished}


def analyze(runs):
    hashes, games, summaries = {}, [], {}
    for directory in runs:
        metadata = json.loads((directory / "metadata.json").read_text())
        for path, expected in metadata["source_sha256"].items():
            if digest(ROOT / path) != expected:
                raise ValueError(f"Recorded source changed: {path}; replay the recorded revision")
        boards = json.loads((directory / "boards.json").read_text())
        for name, board in boards.items():
            if hashlib.sha256(json.dumps(board, sort_keys=True).encode()).hexdigest() != metadata["map_sha256"][name]:
                raise ValueError(f"Recorded board changed: {name}")
        for name in ("metadata.json", "boards.json", "matches.jsonl"):
            path = directory / name
            hashes[str(path.relative_to(ROOT))] = digest(path)
        for line in (directory / "matches.jsonl").read_text().splitlines():
            game = json.loads(line)
            if game["termination"] == "pilot_ply_cap" and len(game["turns"]) != metadata["max_plies"]:
                raise ValueError("Recorded ply cap mismatch")
            result = replay(boards[game["map"]], game)
            result["run"] = directory.name
            games.append(result)
        for engine in ("bounded", "growth", "uct"):
            selected = [g for g in games if g["run"] == directory.name and g["candidate"] == engine]
            losses = [g for g in selected if g["score"] == 0]
            summaries[f"{directory.name}/{engine}"] = {
                "games": len(selected), "losses": len(losses),
                "losses_without_random_combat": sum(g["random_battles"] == 0 for g in losses),
                "losses_without_monster_combat": sum(g["monster_battles"] == 0 for g in losses),
                "terminations": dict(Counter(g["termination"] for g in selected)),
                "games_with_repeated_states": sum(g["repeated_state_visits"] > 0 for g in selected),
                "repeated_state_visits": sum(g["repeated_state_visits"] for g in selected),
            }
    return {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
            "command": shlex.join([sys.executable, *sys.argv]),
            "tool_sha256": digest(Path(__file__)), "input_sha256": hashes,
            "verified_games": len(games), "verified_plies": sum(g["plies"] for g in games),
            "limits": "Replay of recorded moves with recorded combat seeds; no search rerun, counterfactual improvement, "
                      "or official-server validation. A repeat is the same board and side to move, ignoring elapsed horizon; "
                      "it is not an official draw rule. Correlated games and shared-model errors limit conclusions.",
            "summary": summaries, "games": games}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh output path to preserve prior evidence")
    base = ROOT / "experiments/2026-10-11-strength"
    result = analyze([base / run for run in ("pilot-01", "pilot-02", "long-01")])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {result['verified_games']} match replays and {result['verified_plies']} plies; saved {args.output}")
    for name, record in result["summary"].items():
        print(name, record)


if __name__ == "__main__":
    main()
