"""Compare exact combat cost and per-call memory with a recorded Git revision.

No matches or strength estimates: use check_search/check_player for real-clock
deadlines, and the paired league for any strategy promotion. This probe uses a
constant search clock to compare identical completed trees under tracemalloc.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.league_support import Runtime

BATTLES = ((6, 7, False), (10, 10, False), (255, 255, False),
           (255, 171, False), (127, 128, True), (1, 255, True))
REPEATS, BATCH_SIZE, MEMORY_CALLS = 7, 30, 4


def write_new(path, data):
    with path.open("x") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def export_revision(revision, destination):
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", revision, "src/vampires"], cwd=ROOT, text=True).splitlines()
    hashes = {}
    for name in names:
        if not name.endswith(".py"):
            continue
        data = subprocess.check_output(["git", "show", revision + ":" + name], cwd=ROOT)
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    if not hashes:
        raise ValueError("No runtime in reference revision")
    return hashes


def decision(runtime, map_name, side):
    board = runtime.model.load_map(ROOT / "maps" / (map_name + ".xml"))
    return runtime.engines.choose_engine(
        board, runtime.model.Species(side), engine="strategic", time_budget=10,
        config=runtime.search.SearchConfig(max_depth=3, preserve_dominance=False), clock=lambda: 0.)


def memory_probe(runtime):
    # Deliberately disable cyclic GC to reveal unreachable per-call retention.
    # This is NOT the production GC setting or a measure of process RSS.
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    tracemalloc.start()
    observations = []
    try:
        for _ in range(MEMORY_CALLS):
            result = decision(runtime, "testmap2", "vampires")
            retained, peak = tracemalloc.get_traced_memory()
            observations.append({"retained_bytes": retained, "peak_bytes": peak,
                                 "nodes": result.nodes, "completed_depth": result.completed_depth})
        gc.collect()
        after_collection = tracemalloc.get_traced_memory()[0]
    finally:
        tracemalloc.stop()
        if enabled:
            gc.enable()
        gc.collect()
    return {"calls": observations, "retained_after_collection_bytes": after_collection}


def compare(reference, current):
    battles = []
    for attackers, defenders, humans in BATTLES:
        arguments = dict(humans=humans)
        old = reference.simulation.battle_distribution(attackers, defenders, **arguments)
        new = current.simulation.battle_distribution(attackers, defenders, **arguments)
        if old != new:
            raise AssertionError("Exact combat probabilities changed")
        timings = {"reference": [], "current": []}
        # Alternate order to reduce systematic warmup/order bias.
        for repeat in range(REPEATS):
            labels = ("reference", "current") if repeat % 2 == 0 else ("current", "reference")
            for label in labels:
                runtime = reference if label == "reference" else current
                started = perf_counter()
                for _ in range(BATCH_SIZE):
                    runtime.simulation.battle_distribution(attackers, defenders, **arguments)
                timings[label].append((perf_counter() - started) / BATCH_SIZE)
        medians = {label: statistics.median(values) for label, values in timings.items()}
        battles.append({"attackers": attackers, "defenders": defenders, "humans": humans,
                        "exact_probabilities_equal": True, "outcomes": len(new),
                        "seconds_per_call": timings, "median_seconds": medians,
                        "speedup": medians["reference"] / medians["current"]})
    decisions = []
    for map_name in ("thetrap", "testmap2"):
        for side in ("vampires", "werewolves"):
            old = decision(reference, map_name, side)
            new = decision(current, map_name, side)
            # Dataclasses from separate runtime modules cannot compare directly.
            if asdict(old) != asdict(new):
                raise AssertionError("Completed fixed-tree decision or diagnostics changed")
            decisions.append({"map": map_name, "species": side,
                              "identical_decision_and_work": True, "decision": asdict(new)})
    return {"battles": battles, "fixed_tree_decisions": decisions,
            "memory": {"reference": memory_probe(reference), "current": memory_probe(current)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="Git revision to compare")
    parser.add_argument("--output", required=True, type=Path, help="Fresh report directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path")
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.reference + "^{commit}"], cwd=ROOT, text=True).strip()
    paths = sorted((ROOT / "src/vampires").rglob("*.py"))
    paths += [Path(__file__).resolve(), ROOT / "tools/league_support.py",
              ROOT / "maps/thetrap.xml", ROOT / "maps/testmap2.xml"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with tempfile.TemporaryDirectory(prefix="vampires-runtime-reference-") as directory:
        reference_hashes = export_revision(revision, Path(directory))
        args.output.mkdir(parents=True, exist_ok=False)
        plan = {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "platform": platform.platform(), "command": sys.argv, "seed": None,
                "reference_revision": revision, "reference_sha256": reference_hashes,
                "current_sha256": hashes, "battles": BATTLES, "repeats": REPEATS,
                "batch_size": BATCH_SIZE, "memory_calls": MEMORY_CALLS,
                "search": {"engine": "strategic", "depth": 3, "preserve_dominance": False,
                           "clock": "constant zero; completed trees, no wall-clock cutoff",
                           "maps": ["thetrap", "testmap2"], "species": ["vampires", "werewolves"],
                           "memory_position": "testmap2/vampires"},
                "limitations": "Microbenchmarks and traced Python allocations on this machine. GC is disabled only "
                               "for retention diagnosis. No process-RSS, worst-case timing, strength, CTI or server claim."}
        write_new(args.output / "plan.json", plan)
        print("Registered runtime comparison:", args.output / "plan.json", flush=True)
        reference = Runtime.load(Path(directory) / "src/vampires", "runtime_reference")
        current = Runtime.load(ROOT / "src/vampires", "runtime_current")
        started = perf_counter()
        try:
            results = compare(reference, current)
            if hashes != {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:
                raise ValueError("Measured sources changed during the run")
            results["elapsed_seconds"] = perf_counter() - started
            results["plan_sha256"] = hashlib.sha256((args.output / "plan.json").read_bytes()).hexdigest()
            write_new(args.output / "results.json", results)
        finally:
            reference.close()
            current.close()
            gc.collect()
    print("Verified exact combat and completed-tree equivalence; saved", args.output / "results.json")


if __name__ == "__main__":
    main()
