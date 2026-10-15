"""Stdlib-only local league probes, map families, and paired summaries.

The four scripted policies are deliberately distinct benchmark probes. They
are not opponent-aware submitted agents and do not establish tournament skill.
All transitions use the project's still-unverified live simulation conventions.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import random
import sys
from time import monotonic
from uuid import uuid4


FROZEN_REVISION = "04a1e855cc78fbab6f0ddef63fbaf085ea46b520"
MAP_FAMILIES = ("resource_race", "chokepoint", "dispersed", "contact", "endgame")
SCRIPTED = ("collector", "raider", "escape", "split_merge")
POLICY_DESCRIPTIONS = {
    "collector": "Whole-group moves favor immediate human conversion and distance to affordable houses; penalize battle losses.",
    "raider": "Whole-group moves favor expected enemy casualties and closing distance, accepting risky combat.",
    "escape": "With a population lead, whole-group moves favor separation and low adjacent danger; otherwise pursue resources and combat.",
    "split_merge": "Bounded legal joint/partial moves favor conversions, useful retained remainders, and friendly merges; no shared contested attacks.",
    "baseline": "Current snapshotted sequential expectiminimax, with its explicitly recorded depth.",
    "adaptive": "Current snapshotted adaptive expectiminimax control, with its explicitly recorded depth.",
    "frozen": "Frozen cohesive_material expectiminimax at revision " + FROZEN_REVISION + ", with explicitly recorded depth.",
}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def derive_seed(seed, *labels):
    return int(digest([seed, *labels])[:16], 16)


def packed(board):
    return {"rows": board.rows, "columns": board.columns,
            "cells": [[x, y, cell.humans, cell.vampires, cell.werewolves]
                      for (x, y), cell in sorted(board.cells.items())]}


def unpacked(value, model):
    return model.Board(value["rows"], value["columns"],
                       {(x, y): model.Cell(h, v, w) for x, y, h, v, w in value["cells"]})


@dataclass(frozen=True)
class EngineSpec:
    name: str
    depth: int

    @property
    def label(self):
        return self.name if self.name in SCRIPTED else f"{self.name}:d{self.depth}"


def parse_spec(value, *, default_depth=3, opponent=False):
    pieces = value.split(":")
    if len(pieces) not in (1, 2) or not pieces[0]:
        raise ValueError("Use NAME or NAME:DEPTH")
    name = pieces[0]
    depth = default_depth if len(pieces) == 1 else int(pieces[1])
    if not 2 <= depth <= 8:
        raise ValueError("Search depths must be in 2..8")
    if opponent and name not in ("frozen", "baseline", "adaptive", *SCRIPTED):
        raise ValueError(f"Unknown league opponent: {name}")
    if name in SCRIPTED and len(pieces) == 2:
        raise ValueError("Scripted probes have no search depth")
    return EngineSpec(name, depth)


@dataclass
class Runtime:
    package: str
    model: object
    rules: object
    simulation: object
    search: object
    engines: object
    turns: object

    @classmethod
    def load(cls, directory, label):
        directory = Path(directory)
        package = "_league_" + label + "_" + uuid4().hex
        spec = importlib.util.spec_from_file_location(package, directory / "__init__.py",
                                                     submodule_search_locations=[str(directory)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        try:
            spec.loader.exec_module(module)
            modules = [importlib.import_module(package + "." + name)
                       for name in ("model", "rules", "simulation", "search", "engines", "turns")]
            return cls(package, *modules)
        except BaseException:
            for name in tuple(sys.modules):
                if name == package or name.startswith(package + "."):
                    del sys.modules[name]
            raise

    def close(self):
        for name in tuple(sys.modules):
            if name == self.package or name.startswith(self.package + "."):
                del sys.modules[name]

    def engine_decision(self, board, side, spec, budget, *, target_runtime=None):
        target = self if target_runtime is None else target_runtime
        converted = unpacked(packed(board), target.model) if target is not self else board
        species = target.model.Species(side.value)
        name = "cohesive_material" if spec.name == "frozen" else spec.name
        # No local cutoff is supplied to either engine. The harness cap is an
        # outcome proxy, not information available in the live protocol.
        decision = target.engines.choose_engine(converted, species, engine=name, time_budget=budget,
                                                 config=target.search.SearchConfig(max_depth=spec.depth))
        moves = tuple(self.rules.Move(*move.as_tuple()) for move in decision.moves)
        return moves, asdict(decision)


def generated_board(family, seed, model):
    """Small reproducible families; there are no terrain obstacles in this game."""
    if family not in MAP_FAMILIES:
        raise ValueError(f"Unknown map family: {family}")
    rng = random.Random(seed)
    Cell, Board = model.Cell, model.Board
    if family == "chokepoint":
        # A one-cell-wide board creates contact constraints without inventing
        # impassable terrain. Rotate the same structural family by seed.
        cells = {(0, 0): Cell(vampires=3), (10, 0): Cell(werewolves=3),
                 (2, 0): Cell(humans=2), (8, 0): Cell(humans=2),
                 (4, 0): Cell(humans=1), (6, 0): Cell(humans=1),
                 (5, 0): Cell(humans=rng.choice((5, 6, 7)))}
        if rng.randrange(2):
            return Board(11, 1, {(y, x): cell for (x, y), cell in cells.items()})
        return Board(1, 11, cells)
    if family == "resource_race":
        cells = {(0, 0): Cell(vampires=4), (6, 6): Cell(werewolves=4),
                 (3, 3): Cell(humans=rng.choice((6, 7, 8)))}
        for count in (2, 3):
            positions = [(x, y) for x in range(7) for y in range(7)
                         if (x, y) not in cells and (6 - x, 6 - y) not in cells]
            x, y = rng.choice(positions)
            cells[x, y] = cells[6 - x, 6 - y] = Cell(humans=count)
        return Board(7, 7, cells)
    if family == "dispersed":
        cells = {(0, 0): Cell(vampires=3), (0, 5): Cell(vampires=2),
                 (5, 0): Cell(werewolves=2), (5, 5): Cell(werewolves=3)}
        for count in (2, 3, 4, 5):
            position = rng.choice([(x, y) for x in range(6) for y in range(6) if (x, y) not in cells])
            cells[position] = Cell(humans=count)
        return Board(6, 6, cells)
    if family == "contact":
        count = rng.choice((3, 4, 5))
        cells = {(1, 1): Cell(vampires=count), (3, 1): Cell(werewolves=count)}
        for population in (1, 2, count):
            position = rng.choice([(x, y) for x in range(5) for y in range(4) if (x, y) not in cells])
            cells[position] = Cell(humans=population)
        return Board(4, 5, cells)
    own, other = rng.choice(((7, 6), (6, 7), (6, 6), (9, 6)))
    cells = {(0, 1): Cell(vampires=own), (6, 1): Cell(werewolves=other)}
    if rng.randrange(2):
        cells[0, 1] = Cell(vampires=own - 2)
        cells[0, 2] = Cell(vampires=2)
        cells[6, 1] = Cell(werewolves=other - 2)
        cells[6, 0] = Cell(werewolves=2)
    return Board(3, 7, cells)


def distance(left, right):
    return max(abs(left[0] - right[0]), abs(left[1] - right[1]))


def _script_score(runtime, board, side, turn, policy):
    enemies = board.groups(side.opponent)
    houses = [(p, c.humans) for p, c in board.cells.items() if c.humans]
    own_total = sum(board.groups(side).values())
    enemy_total = sum(enemies.values())
    human_gain = enemy_loss = own_loss = resources = approach = danger = escape = merge = split = 0.0
    for move in turn:
        target = board.at(move.target)
        count = move.count
        defenders = target.humans or target.count(side.opponent)
        if defenders:
            odds = runtime.rules.battle_odds(count, defenders, humans=bool(target.humans))
            own_loss += max(0, count - odds.expected_attackers)
            if target.humans:
                human_gain += odds.expected_attackers - count
            else:
                enemy_loss += defenders - odds.expected_defenders
        affordable = [distance(move.target, p) for p, number in houses if number <= count]
        resources += count / (1 + min(affordable, default=board.rows + board.columns))
        nearest = min((distance(move.target, p) for p in enemies), default=0)
        approach += count / (1 + nearest)
        escape += count * min(nearest, 6)
        adjacent = sum(number for p, number in enemies.items() if distance(move.target, p) <= 1)
        danger += count if 2 * adjacent >= 3 * (count + target.count(side)) else 0
        merge += min(count, target.count(side))
        remainder = board.at(move.source).count(side) - count
        if target.humans and count >= target.humans and remainder > 0:
            split += min(remainder, target.humans)
    if policy == "collector":
        return 12 * human_gain + 2 * resources - 6 * own_loss - 3 * danger
    if policy == "raider":
        return 10 * enemy_loss + 3 * approach + human_gain - 2 * own_loss
    if policy == "escape" and own_total > enemy_total:
        return 3 * escape + 4 * human_gain - 12 * own_loss - 12 * danger
    if policy == "escape":
        return 8 * human_gain + 4 * enemy_loss + resources + approach - 3 * own_loss
    return 12 * human_gain + 2 * resources + 2 * merge + 3 * split - 6 * own_loss - 4 * danger


def scripted_turn(runtime, board, side, policy, policy_seed):
    if policy not in SCRIPTED:
        raise ValueError(f"Unknown scripted policy: {policy}")
    if policy == "split_merge":
        turns = runtime.turns.candidate_turns(board, side, limit=96, per_group=16).turns
    else:
        turns = []
        for (x, y), count in sorted(board.groups(side).items()):
            for target in board.neighbors((x, y)):
                cell = board.at(target)
                if count + cell.humans + cell.count(side) <= 255:
                    turns.append((runtime.rules.Move(x, y, count, *target),))
    if not turns:
        # Let the existing legal fallback expose unresolved population overflow
        # to the harness rather than pretending that the probe lost normally.
        turns = (runtime.turns.fallback_turn(board, side),)
    rng = random.Random(policy_seed)
    scores = [(_script_score(runtime, board, side, turn, policy), rng.random(), turn) for turn in turns]
    score, _, chosen = max(scores, key=lambda item: item[:2])
    runtime.rules.validate_moves(board, side, chosen)
    return chosen, {"policy": policy, "heuristic_score": score, "considered_turns": len(turns),
                    "policy_seed": policy_seed, "opponent_lookahead": False}


def run_match(runtime, frozen, initial, candidate, opponent, species, *, budget,
              max_plies, combat_seed, policy_seed, clock=monotonic):
    """Run serially. Any failure makes the score unknown, never an implicit win."""
    board = unpacked(packed(initial), runtime.model)
    side = runtime.model.Species.VAMPIRES
    species = runtime.model.Species(species)
    turns, failure = [], None
    before_hash = digest(packed(board))
    for ply in range(max_plies):
        if not all(board.groups(s) for s in runtime.model.Species):
            break
        role = "candidate" if side == species else "opponent"
        spec = candidate if role == "candidate" else opponent
        chosen_seed = derive_seed(policy_seed, role, ply)
        chance_seed = derive_seed(combat_seed, "combat", ply)
        started = clock()
        moves, diagnostics, stage = (), None, "decision"
        elapsed = None
        try:
            if role == "opponent" and spec.name in SCRIPTED:
                moves, diagnostics = scripted_turn(runtime, board, side, spec.name, chosen_seed)
            else:
                moves, diagnostics = runtime.engine_decision(board, side, spec, budget,
                                                             target_runtime=frozen if spec.name == "frozen" else None)
            stage = "validation"
            runtime.rules.validate_moves(board, side, moves)
            elapsed = clock() - started
            if elapsed >= 2:
                raise TimeoutError(f"Two-second local response limit exceeded: {elapsed:.6f}s")
            stage = "simulation"
            following = runtime.simulation.sample_turn(board, side, moves, random.Random(chance_seed))
            after = packed(following)
            after_hash = digest(after)
            turns.append({"ply": ply, "role": role, "engine": spec.label, "species": side.value,
                          "policy_seed": chosen_seed, "combat_seed": chance_seed,
                          "elapsed_seconds": elapsed, "decision": diagnostics,
                          "moves": [list(move.as_tuple()) for move in moves],
                          "before_sha256": before_hash, "after_sha256": after_hash, "after": after})
            board, before_hash = following, after_hash
            side = side.opponent
        except Exception as exc:
            failure = {"ply": ply, "role": role, "engine": spec.label, "species": side.value,
                       "stage": stage, "type": type(exc).__name__, "message": str(exc),
                       "elapsed_seconds": elapsed if elapsed is not None else clock() - started,
                       "attempted_moves": [list(move.as_tuple()) for move in moves],
                       "decision": diagnostics, "before_sha256": before_hash}
            break
    populations = {s.value: sum(board.groups(s).values()) for s in runtime.model.Species}
    winner = None
    score = None
    if failure is None:
        if populations[species.value] != populations[species.opponent.value]:
            winner = species if populations[species.value] > populations[species.opponent.value] else species.opponent
        score = .5 if winner is None else float(winner == species)
    return {"candidate": candidate.label, "opponent": opponent.label, "species": species.value,
            "starting_species": "vampires", "combat_seed": combat_seed, "policy_seed": policy_seed,
            "score": score, "winner": winner.value if winner is not None else None,
            "termination": "failure" if failure else "extinction" if not all(populations.values()) else "local_ply_cap",
            "populations": populations, "failure": failure, "turns": turns,
            "final_board": packed(board), "final_sha256": before_hash}


def _summary(games):
    valid = [game for game in games if game["failure"] is None]
    grouped = defaultdict(list)
    for game in games:
        key = game["opponent"], game["map"], game["combat_seed"], game["policy_seed"]
        grouped[key].append(game)
    pairs, map_scores = [], defaultdict(list)
    for key, pair in grouped.items():
        if (len(pair) == 2 and {g["species"] for g in pair} == {"vampires", "werewolves"}
                and all(g["failure"] is None for g in pair)):
            score = sum(game["score"] for game in pair) / 2
            pairs.append(score)
            map_scores[key[1]].append(score)
    clusters = [sum(values) / len(values) for values in map_scores.values()]
    interval = None
    if len(clusters) >= 2:
        rng = random.Random(20261013)
        bootstrap = sorted(sum(rng.choice(clusters) for _ in clusters) / len(clusters) for _ in range(1000))
        interval = [bootstrap[24], bootstrap[974]]
    elapsed = [turn["elapsed_seconds"] for game in games for turn in game["turns"] if turn["role"] == "candidate"]
    elapsed.extend(game["failure"]["elapsed_seconds"] for game in games
                   if game["failure"] is not None and game["failure"]["role"] == "candidate")
    completed_depths = [turn["decision"]["completed_depth"] for game in games for turn in game["turns"]
                        if turn["role"] == "candidate" and "completed_depth" in turn["decision"]]
    return {"games": len(games), "valid_games": len(valid), "failed_games": len(games) - len(valid),
            "candidate_failures": sum(g["failure"] is not None and g["failure"]["role"] == "candidate" for g in games),
            "opponent_failures": sum(g["failure"] is not None and g["failure"]["role"] == "opponent" for g in games),
            "wins": sum(g["score"] == 1 for g in valid), "draws": sum(g["score"] == .5 for g in valid),
            "losses": sum(g["score"] == 0 for g in valid), "complete_valid_pairs": len(pairs),
            "incomplete_or_failed_pairs": len(grouped) - len(pairs),
            "paired_score": sum(pairs) / len(pairs) if pairs else None,
            "map_balanced_score": sum(clusters) / len(clusters) if clusters else None,
            "map_clusters": len(clusters), "map_cluster_bootstrap_95": interval,
            "max_candidate_response_seconds": max(elapsed, default=0),
            "candidate_completed_depth_histogram": {str(depth): completed_depths.count(depth)
                                                     for depth in sorted(set(completed_depths))},
            "local_ply_cap_games": sum(g["termination"] == "local_ply_cap" for g in games),
            "limitation": "Descriptive local evidence. Failed games have no score; incomplete pairs are excluded explicitly. "
                          "Intervals resample observed map clusters only and are unavailable for one map. "
                          "Related map families, shared simulator, timing variation, and tested-policy selection limit inference."}


def summarize(matches):
    result = {}
    for candidate in sorted({game["candidate"] for game in matches}):
        games = [game for game in matches if game["candidate"] == candidate]
        result[candidate] = {"overall": _summary(games),
                             "by_opponent": {name: _summary([g for g in games if g["opponent"] == name])
                                             for name in sorted({g["opponent"] for g in games})},
                             "by_map": {name: _summary([g for g in games if g["map"] == name])
                                        for name in sorted({g["map"] for g in games})},
                             "by_family": {name: _summary([g for g in games if g["map_family"] == name])
                                           for name in sorted({g["map_family"] for g in games})}}
    return result
