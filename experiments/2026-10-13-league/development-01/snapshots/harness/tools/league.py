"""Serial paired opponent league with immutable snapshots and resumable records.

Example: python3 tools/league.py --engines cohesive_material:3 --opponents
frozen:3 collector --maps thetrap contact --map-seeds 101 --combat-seeds 201
--policy-seeds 301 --budget .05 --max-plies 60 --output experiments/FRESH_RUN

Resume with --resume RUN_DIR; experiment settings are restored, not overridden.
Scripted opponents are benchmark probes, never candidate tournament strategies.
"""

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from time import monotonic


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.league_support import (FROZEN_REVISION, MAP_FAMILIES, POLICY_DESCRIPTIONS,
                                  SCRIPTED, EngineSpec, Runtime, canonical_json,
                                  digest, generated_board, packed, parse_spec,
                                  run_match, summarize, unpacked)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    # Metadata/summary replacement is atomic. Completed JSONL matches are only
    # appended; a killed process cannot replace earlier valid evidence.
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def snapshot_sources(output, *, root=ROOT):
    """Save exact working runtime, pinned opponent, and harness before any timing."""
    root, output = Path(root), Path(output)
    paths = sorted((root / "src/vampires").rglob("*.py"))
    originals = {str(path.relative_to(root)): path.read_bytes() for path in paths}
    harness = {"tools/league.py": Path(__file__).read_bytes(),
               "tools/league_support.py": Path(__file__).with_name("league_support.py").read_bytes()}
    frozen_paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", FROZEN_REVISION, "src/vampires"], cwd=root, text=True).splitlines()
    frozen = {path: subprocess.check_output(["git", "show", FROZEN_REVISION + ":" + path], cwd=root)
              for path in frozen_paths if path.endswith(".py")}
    if not originals or not frozen:
        raise ValueError("Both runtime source snapshots must be nonempty")
    hashes = {}
    for label, files in (("current", originals), ("frozen", frozen), ("harness", harness)):
        for path, data in files.items():
            relative = "snapshots/" + label + "/" + path
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes[relative] = hashlib.sha256(data).hexdigest()
    if {str(path.relative_to(root)) for path in (root / "src/vampires").rglob("*.py")} != set(originals):
        raise RuntimeError("Runtime source file set changed while taking the snapshot")
    for path, data in originals.items():
        if (root / path).read_bytes() != data:
            raise RuntimeError("Runtime changed while taking the snapshot: " + path)
    return {"current_package": "snapshots/current/src/vampires",
            "frozen_package": "snapshots/frozen/src/vampires",
            "harness_root": "snapshots/harness", "sha256": hashes}


def verify_snapshots(output, snapshots, *, verify_harness=True):
    output = Path(output).resolve()
    for relative, expected in snapshots["sha256"].items():
        path = (output / relative).resolve()
        if not path.is_relative_to(output) or not path.is_file() or file_hash(path) != expected:
            raise ValueError("Missing, changed, or invalid snapshot: " + relative)
    if verify_harness:
        for name in ("league.py", "league_support.py"):
            expected = snapshots["sha256"]["snapshots/harness/tools/" + name]
            if file_hash(Path(__file__).with_name(name)) != expected:
                raise ValueError("Harness source changed; resume using the archived snapshots/harness/tools/league.py")


def make_boards(runtime, names, map_seeds, *, root=ROOT):
    result = {}
    for name in names:
        if name in MAP_FAMILIES:
            items = [(f"{name}_{seed}", generated_board(name, seed, runtime.model), name, seed)
                     for seed in map_seeds]
        else:
            path = Path(root) / "maps" / (name + ".xml")
            if not path.is_file():
                path = Path(name).expanduser()
            if not path.is_file():
                raise ValueError("Unknown map/family or missing XML map: " + name)
            items = [(path.stem, runtime.model.load_map(path), "supplied" if name in ("thetrap", "testmap2") else "external", None)]
        for label, board, family, seed in items:
            if label in result:
                raise ValueError("Duplicate map identifier: " + label)
            value = packed(board)
            result[label] = {"family": family, "map_seed": seed, "board": value, "sha256": digest(value)}
    return result


def make_schedule(candidates, opponents, boards, combat_seeds, policy_seeds):
    schedule = []
    for candidate in candidates:
        for opponent in opponents:
            for name in boards:
                for combat_seed in combat_seeds:
                    for policy_seed in policy_seeds:
                        for species in ("vampires", "werewolves"):
                            case = {"candidate": asdict(candidate), "opponent": asdict(opponent),
                                    "map": name, "species": species,
                                    "combat_seed": combat_seed, "policy_seed": policy_seed}
                            case["match_id"] = digest(case)
                            schedule.append(case)
    if len({case["match_id"] for case in schedule}) != len(schedule):
        raise ValueError("Duplicate engine/opponent/seed settings would repeat match IDs")
    return schedule


def read_records(path, *, recover=False):
    """Preserve an interrupted final fragment before recovering the append log."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    records, offset = [], 0
    for index, line in enumerate(lines):
        try:
            # An unterminated JSON object is still an incomplete append, even
            # if it happens to parse: archive it and replay that match.
            if not line.endswith(b"\n"):
                raise ValueError("unterminated append")
            record = json.loads(line)
            if not isinstance(record, dict) or "match_id" not in record:
                raise ValueError("invalid match record")
        except (ValueError, UnicodeDecodeError) as exc:
            if index != len(lines) - 1 or not recover or line.endswith(b"\n"):
                raise ValueError(f"Invalid JSONL record at byte {offset}") from exc
            recovery = path.parent / "recovery"
            recovery.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            (recovery / (stamp + ".jsonl-fragment")).write_bytes(line)
            with path.open("r+b") as stream:
                stream.truncate(offset)
                stream.flush()
                os.fsync(stream.fileno())
            break
        records.append(record)
        offset += len(line)
    if len({record["match_id"] for record in records}) != len(records):
        raise ValueError("Duplicate completed match IDs in raw records")
    return records


def validate_existing_records(records, schedule, boards):
    cases = {case["match_id"]: case for case in schedule}
    for record in records:
        if record.get("record_sha256") != digest({key: value for key, value in record.items() if key != "record_sha256"}):
            raise ValueError("Completed record checksum does not match its contents")
        case = cases.get(record["match_id"])
        if case is None:
            raise ValueError("Completed record is not in the saved schedule")
        for field in ("map", "species", "combat_seed", "policy_seed"):
            if record.get(field) != case[field]:
                raise ValueError("Completed record disagrees with its saved schedule: " + field)
        if record.get("candidate") != EngineSpec(**case["candidate"]).label:
            raise ValueError("Completed record candidate disagrees with its saved schedule")
        if record.get("opponent") != EngineSpec(**case["opponent"]).label:
            raise ValueError("Completed record opponent disagrees with its saved schedule")
        if record.get("initial_sha256") != boards[case["map"]]["sha256"]:
            raise ValueError("Completed record initial board hash disagrees with the saved board")


def configuration_hash(metadata):
    return digest({name: metadata[name] for name in
                   ("frozen_revision", "budget_seconds", "max_plies", "live_cutoff_supplied",
                    "starting_species", "candidates", "opponents", "snapshots", "boards_sha256", "schedule_sha256")})


@contextmanager
def writer_lock(output):
    # This offline harness runs on the project's macOS/Linux research hosts.
    # Kernel advisory locks release automatically after interruption/crash;
    # retaining the small lock file does not leave a stale process lock.
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeError("League writer locking requires POSIX fcntl (macOS/Linux)") from exc
    with (Path(output) / ".league.lock").open("a+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another league writer already holds this run directory") from exc
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(str(os.getpid()) + "\n")
            stream.flush()
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_saved(output, *, max_matches=None):
    with writer_lock(output):
        return _run_saved_unlocked(output, max_matches=max_matches)


def _run_saved_unlocked(output, *, max_matches=None):
    output = Path(output)
    metadata = json.loads((output / "metadata.json").read_text())
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported league schema version")
    if configuration_hash(metadata) != metadata["configuration_sha256"]:
        raise ValueError("Saved experiment configuration changed")
    verify_snapshots(output, metadata["snapshots"])
    if file_hash(output / "boards.json") != metadata["boards_sha256"]:
        raise ValueError("Saved board file changed")
    boards = json.loads((output / "boards.json").read_text())
    for entry in boards.values():
        if digest(entry["board"]) != entry["sha256"]:
            raise ValueError("Saved board hash does not match its contents")
    if digest(metadata["schedule"]) != metadata["schedule_sha256"]:
        raise ValueError("Saved schedule hash does not match its contents")
    records = read_records(output / "matches.jsonl", recover=True)
    validate_existing_records(records, metadata["schedule"], boards)
    if any(record.get("configuration_sha256") != metadata["configuration_sha256"] for record in records):
        raise ValueError("Completed record configuration differs from the saved experiment")
    completed = {record["match_id"] for record in records}
    runtime = Runtime.load(output / metadata["snapshots"]["current_package"], "current")
    frozen = Runtime.load(output / metadata["snapshots"]["frozen_package"], "frozen")
    started, added = monotonic(), 0
    try:
        with (output / "matches.jsonl").open("a") as stream:
            for case in metadata["schedule"]:
                if case["match_id"] in completed:
                    continue
                if max_matches is not None and added >= max_matches:
                    break
                candidate, opponent = EngineSpec(**case["candidate"]), EngineSpec(**case["opponent"])
                entry = boards[case["map"]]
                board = unpacked(entry["board"], runtime.model)
                result = run_match(runtime, frozen, board, candidate, opponent, case["species"],
                                   budget=metadata["budget_seconds"], max_plies=metadata["max_plies"],
                                   combat_seed=case["combat_seed"], policy_seed=case["policy_seed"])
                result.update(match_id=case["match_id"], map=case["map"], map_family=entry["family"],
                              initial_sha256=entry["sha256"], candidate_depth=candidate.depth,
                              opponent_depth=None if opponent.name in SCRIPTED else opponent.depth,
                              configuration_sha256=metadata["configuration_sha256"])
                result["record_sha256"] = digest(result)
                stream.write(canonical_json(result) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                records.append(result)
                completed.add(case["match_id"])
                added += 1
                print(candidate.label, opponent.label, case["map"], case["species"], result["score"],
                      result["termination"], len(result["turns"]), result["populations"], flush=True)
                # Summary survives an interruption and never replaces raw games.
                write_json(output / "summary.json", {"scheduled_games": len(metadata["schedule"]),
                           "completed_games": len(records), "complete": len(records) == len(metadata["schedule"]),
                           "engines": summarize(records)})
        verify_snapshots(output, metadata["snapshots"])
        summary = {"scheduled_games": len(metadata["schedule"]), "completed_games": len(records),
                   "complete": len(records) == len(metadata["schedule"]),
                   "latest_invocation_added_games": added, "latest_invocation_seconds": monotonic() - started,
                   "engines": summarize(records)}
        write_json(output / "summary.json", summary)
        return summary
    finally:
        runtime.close()
        frozen.close()


def create_run(output, *, engines, opponents, maps, map_seeds, combat_seeds,
               policy_seeds, budget, max_plies, depth=3, root=ROOT, command=None):
    if type(budget) not in (int, float) or not isfinite(budget) or not 0 < budget <= 1.5:
        raise ValueError("budget must be finite and in (0, 1.5]")
    if type(max_plies) is not int or max_plies < 1:
        raise ValueError("max-plies must be a positive integer")
    candidates = [parse_spec(value, default_depth=depth) for value in engines]
    rivals = [parse_spec(value, default_depth=depth, opponent=True) for value in opponents]
    if not all((candidates, rivals, maps, map_seeds, combat_seeds, policy_seeds)):
        raise ValueError("Engine, opponent, map, and seed lists must be nonempty")
    output, root = Path(output), Path(root)
    output.mkdir(parents=True, exist_ok=False)
    snapshots = snapshot_sources(output, root=root)
    runtime = Runtime.load(output / snapshots["current_package"], "setup")
    frozen = Runtime.load(output / snapshots["frozen_package"], "setup_frozen")
    try:
        for spec in candidates:
            if spec.name not in runtime.engines.ENGINE_NAMES:
                raise ValueError("Unknown snapshotted candidate engine: " + spec.name)
        boards = make_boards(runtime, maps, map_seeds, root=root)
        schedule = make_schedule(candidates, rivals, boards, combat_seeds, policy_seeds)
        write_json(output / "boards.json", boards)
        metadata = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "frozen_revision": FROZEN_REVISION,
                    "working_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                    "working_tree_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
                    "command": command, "python": sys.version, "platform": platform.platform(),
                    "machine": platform.machine(), "cpu_count": os.cpu_count(),
                    "budget_seconds": budget, "max_plies": max_plies, "live_cutoff_supplied": False,
                    "starting_species": "vampires", "species_pairing": ["vampires", "werewolves"],
                    "candidates": [{**asdict(spec), "label": spec.label,
                                    "config": asdict(runtime.search.SearchConfig(max_depth=spec.depth))} for spec in candidates],
                    "opponents": [{**asdict(spec), "label": spec.label,
                                    "description": POLICY_DESCRIPTIONS[spec.name],
                                    "config": None if spec.name in SCRIPTED else asdict(
                                        (frozen if spec.name == "frozen" else runtime).search.SearchConfig(max_depth=spec.depth))}
                                   for spec in rivals],
                    "map_names": maps, "map_seeds": map_seeds, "combat_seeds": combat_seeds,
                    "policy_seeds": policy_seeds, "seed_rule": "SHA256([base_seed, role_or_combat, ply]) first 64 bits; combat and policy streams separate.",
                    "snapshots": snapshots, "boards_sha256": file_hash(output / "boards.json"),
                    "schedule": schedule, "schedule_sha256": digest(schedule),
                    "limitations": "Local shared simulator with unverified server semantics; no CTI/official-server claim. "
                                   "Shared contested attacks and byte overflow remain unsupported. Local ply cap scores population, "
                                   "including a conventional draw for ties; agents receive no cutoff. Scripts are diagnostic probes. "
                                   "Failures have score=null and must not be interpreted as wins. Paired seeds do not imply identical "
                                   "random events when policies take different actions. Confidence intervals are conditional on tested map clusters."}
        metadata["configuration_sha256"] = configuration_hash(metadata)
        write_json(output / "metadata.json", metadata)
        verify_snapshots(output, snapshots)
    finally:
        runtime.close()
        frozen.close()
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path, help="new directory, must not already exist")
    destination.add_argument("--resume", type=Path, help="resume saved configuration and exact source snapshots")
    parser.add_argument("--engines", nargs="+", help="candidate NAME[:DEPTH] values")
    parser.add_argument("--opponents", nargs="+", help="frozen[:DEPTH], baseline[:DEPTH], collector, raider, escape, split_merge")
    parser.add_argument("--depth", type=int, help="depth for unspecified engine/opponent depths; default 3")
    parser.add_argument("--maps", nargs="+", help="supplied map names, XML paths, or " + ", ".join(MAP_FAMILIES))
    parser.add_argument("--map-seeds", nargs="+", type=int)
    parser.add_argument("--combat-seeds", nargs="+", type=int)
    parser.add_argument("--policy-seeds", nargs="+", type=int)
    parser.add_argument("--budget", type=float)
    parser.add_argument("--max-plies", type=int)
    parser.add_argument("--max-matches", type=int, help="stop this invocation after N new games; resume later")
    args = parser.parse_args(argv)
    experiment_keys = ("engines", "opponents", "depth", "maps", "map_seeds", "combat_seeds",
                       "policy_seeds", "budget", "max_plies")
    try:
        if args.max_matches is not None and args.max_matches < 1:
            raise ValueError("max-matches must be positive")
        if args.resume:
            if any(getattr(args, key) is not None for key in experiment_keys):
                raise ValueError("--resume restores saved experiment settings; do not supply new settings")
            output = args.resume
        else:
            output = args.output
            create_run(output, engines=args.engines or ["cohesive_material:3"],
                       opponents=args.opponents or ["frozen:3", "baseline:3", *SCRIPTED],
                       maps=args.maps or ["thetrap", "testmap2", *MAP_FAMILIES],
                       map_seeds=args.map_seeds or [101], combat_seeds=args.combat_seeds or [201],
                       policy_seeds=args.policy_seeds or [301], budget=.05 if args.budget is None else args.budget,
                       max_plies=60 if args.max_plies is None else args.max_plies,
                       depth=3 if args.depth is None else args.depth,
                       command=shlex.join([sys.executable, *sys.argv]) if argv is None else shlex.join([sys.executable, __file__, *argv]))
        summary = run_saved(output, max_matches=args.max_matches)
        print(f"Saved {summary['completed_games']}/{summary['scheduled_games']} games to {output}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
