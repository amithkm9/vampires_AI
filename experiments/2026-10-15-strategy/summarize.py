"""Summarize registered strategy comparisons without changing their evidence.

Run only after all three leagues and their replay checks complete. Bootstrap
intervals resample the few observed maps; they do not cover arbitrary opponents,
new map families or the official server's unknown semantics.
"""

import argparse
from collections import defaultdict
import hashlib
from itertools import product
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def summarize(directory):
    raw = (directory / "matches.jsonl").read_bytes()
    games = [json.loads(line) for line in raw.splitlines()]
    metadata = json.loads((directory / "metadata.json").read_text())
    verified = json.loads((directory / "replay-analysis.json").read_text())
    if (len(games) != len(metadata["schedule"]) or len(games) != verified["verified_matches"]
            or verified["input_sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Incomplete or unverified experiment: " + str(directory))
    by_engine = defaultdict(dict)
    for game in games:
        key = (game["opponent"], game["map"], game["combat_seed"],
               game["policy_seed"], game["species"])
        if key in by_engine[game["candidate"]]:
            raise ValueError("Duplicate comparison case")
        by_engine[game["candidate"]][key] = game
    control = by_engine["adaptive:d5"]
    results = {}
    for engine, cases in sorted(by_engine.items()):
        if set(cases) != set(control):
            raise ValueError("Candidates do not have identical comparison schedules")
        valid = [g for g in cases.values() if g["score"] is not None]
        differences = defaultdict(list)
        improved = regressed = unchanged = 0
        for key, game in cases.items():
            baseline = control[key]
            if game["score"] is None or baseline["score"] is None:
                continue
            delta = game["score"] - baseline["score"]
            differences[game["map"]].append(delta)
            improved += delta > 0
            regressed += delta < 0
            unchanged += delta == 0
        clusters = [sum(values) / len(values) for values in differences.values()]
        bootstraps = (sorted(sum(draw) / len(clusters)
                             for draw in product(clusters, repeat=len(clusters))) if clusters else [])
        last = len(bootstraps) - 1
        responses = [t["elapsed_seconds"] for g in cases.values()
                     for t in g["turns"] if t["role"] == "candidate"]
        results[engine] = {
            "games": len(cases), "failures": len(cases) - len(valid),
            "wins": sum(g["score"] == 1 for g in valid),
            "draws": sum(g["score"] == .5 for g in valid),
            "losses": sum(g["score"] == 0 for g in valid),
            "score": sum(g["score"] for g in valid) / len(valid) if valid else None,
            "improved_cases": improved, "regressed_cases": regressed,
            "unchanged_cases": unchanged,
            "mean_map_paired_delta": sum(clusters) / len(clusters) if clusters else None,
            "map_cluster_bootstrap_95_delta": [bootstraps[int(.025 * last)],
                                               bootstraps[min(last, int(.975 * last) + 1)]] if clusters else None,
            "map_deltas": {name: sum(values) / len(values) for name, values in differences.items()},
            "maximum_candidate_response_seconds": max(responses, default=None),
        }
    return {"matches": len(games), "verified_plies": verified["verified_plies"],
            "matches_sha256": hashlib.sha256(raw).hexdigest(), "engines": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {name: summarize(ROOT / name)
              for name in ("development-01", "development-02", "holdout-01")}
    result["limitations"] = ("Descriptive paired comparisons with exact empirical map-cluster bootstrap. "
                              "Few related map clusters, two held-out combat seeds, shared simulator and "
                              "timing-sensitive search limit generalization. Draws at the unknown live cutoff "
                              "are a local convention. These are not tournament win probabilities.")
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
