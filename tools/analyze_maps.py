"""Reproduce map facts and exact local risks; does not solve either full game."""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vampires.model import Species, load_map
from vampires.rules import Move
from vampires.simulation import battle_distribution, single_move_outcomes, single_moves


def distance(a, b):
    """Chebyshev distance: empty-board travel lower bound, measured in own turns."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def packed_probability(value):
    value = Fraction(value)
    return {"exact": str(value), "decimal": float(value)}


def optimistic_capture_routes(board, species, goal):
    """Exhaust all house orders for one unsplit stack, ignoring the opponent.

    Travel ignores incidental occupied squares. Therefore durations are lower
    bounds, not demonstrated safe/legal paths or multiplayer optimal routes.
    """
    groups = board.groups(species)
    if len(groups) != 1:
        raise ValueError("Route analysis requires one starting group")
    houses = {p: c.humans for p, c in board.cells.items() if c.humans}
    if len(houses) > 8:
        raise ValueError("Exhaustive house-order analysis is restricted to at most 8 houses")
    start, initial = next(iter(groups.items()))
    routes = []

    def visit(position, population, remaining, turns, route):
        for target, humans in sorted(remaining.items()):
            if population < humans:
                continue
            arrival = turns + distance(position, target)
            step = {"position": target, "humans": humans,
                    "arrival_own_turn_lower_bound": arrival, "population_after": population + humans}
            path = route + [step]
            if target == goal:
                routes.append({"arrival_own_turn_lower_bound": arrival, "captures": path})
            else:
                visit(target, population + humans,
                      {p: h for p, h in remaining.items() if p != target}, arrival, path)

    visit(start, initial, houses, 0, [])
    return sorted(routes, key=lambda item: item["arrival_own_turn_lower_bound"])


def trap_openings(board):
    """Inspect every whole-group opening and every legal one-record reply.

    On this map no opening can capture anything; the opponent initially has one
    group, so under the conservative record limit these replies are exhaustive.
    The statistic is own-species extinction in the next reply, not match loss.
    """
    report = {}
    for species in Species:
        entries = []
        for move in single_moves(board, species, whole_groups_only=True):
            opening = single_move_outcomes(board, species, move)
            assert len(opening) == 1 and opening[0].probability == 1
            after = opening[0].board
            worst_risk, replies = Fraction(0), []
            for reply in single_moves(after, species.opponent):
                outcomes = single_move_outcomes(after, species.opponent, reply)
                risk = sum((outcome.probability for outcome in outcomes
                            if not outcome.board.groups(species)), Fraction(0))
                if risk > worst_risk:
                    worst_risk, replies = risk, [reply.as_tuple()]
                elif risk and risk == worst_risk:
                    replies.append(reply.as_tuple())
            entries.append({"move": move.as_tuple(), "distance_to_four_humans": distance(move.target, (2, 2)),
                            "max_next_reply_extinction_probability": packed_probability(worst_risk),
                            "replies_attaining_max": replies})
        report[species.value] = entries
    return report


def analyze():
    started = perf_counter()
    maps = {}
    for name in ("thetrap", "testmap2"):
        path = ROOT / "maps" / f"{name}.xml"
        board = load_map(path)
        humans = {p: c.humans for p, c in board.cells.items() if c.humans}
        maps[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "rows": board.rows, "columns": board.columns,
                      "total_population_including_humans": sum(c.humans+c.vampires+c.werewolves for c in board.cells.values()),
                      "houses": [{"position": p, "humans": count} for p, count in sorted(humans.items())],
                      "distances": {species.value: [
                          {"house": position, "humans": count,
                           "own_turn_lower_bound": distance(next(iter(board.groups(species))), position)}
                          for position, count in sorted(humans.items())] for species in Species}}
        if name == "thetrap":
            maps[name]["whole_group_opening_audit"] = trap_openings(board)
        else:
            maps[name]["outside_center_humans"] = sum(count for p, count in humans.items() if p != (14, 7))
            maps[name]["optimistic_unsplit_center_routes"] = {}
            for species in Species:
                routes = optimistic_capture_routes(board, species, (14, 7))
                maps[name]["optimistic_unsplit_center_routes"][species.value] = {
                    "total_feasible_house_orders": len(routes), "best": routes[:3]}
    battles = []
    for attackers, defenders, humans in [(1, 1, False), (4, 4, False), (10, 20, True), (14, 20, True),
                                         (18, 20, True), (19, 20, True), (20, 20, True),
                                         (10, 8, False), (8, 10, False)]:
        distribution = battle_distribution(attackers, defenders, humans=humans)
        assert sum(distribution.values()) == 1
        battles.append({"attackers": attackers, "defenders": defenders, "humans": humans,
                        "successor_count": len(distribution),
                        "expected_attacking_survivors": packed_probability(sum(a*p for (a, d), p in distribution.items())),
                        "attacker_extinction_probability": packed_probability(sum(p for (a, d), p in distribution.items() if a == 0)),
                        "both_extinct_probability": packed_probability(distribution.get((0, 0), 0)),
                        "attacker_at_least_20_probability": packed_probability(sum(p for (a, d), p in distribution.items() if a >= 20))})
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in [Path(__file__), ROOT / "src/vampires/simulation.py",
                               ROOT / "src/vampires/rules.py", ROOT / "src/vampires/model.py"]}
    return {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "platform": platform.platform(), "seed": None,
            "method": "Exact rational battle enumeration; exhaustive local reply audit; optimistic house-order enumeration.",
            "limits": "Not full-game search; no opponent in route estimates; no server parity or CTI timing claim; draws unresolved.",
            "configuration": {"strict_move_record_limit": True, "trap_openings": "whole group only",
                              "trap_replies": "all legal one-record moves, including every partial amount"},
            "source_sha256": source_hashes, "maps": maps, "battles": battles,
            "elapsed_seconds": perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze()
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"Saved exact map analysis to {args.output}; {result['elapsed_seconds']:.3f}s")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
