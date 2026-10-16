"""Compare live-search decisions against exact development-position outcomes."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools.check_tactics import fraction, outcome, packed, positions
from vampires.budget import Deadline
from vampires.endgame import ExactSolver
from vampires.model import Species
from vampires.search import SearchConfig, choose_turn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=float, default=1.25)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path")
    if not 0 < args.budget <= 1.5:
        parser.error("budget must be in (0, 1.5]")
    started = monotonic()
    results = []
    summary = {str(limit): {comparison: {"improved": 0, "tied": 0, "worse": 0}
                           for comparison in ("known_vs_unknown", "protected_vs_known")}
               for limit in (64, 8)}
    for name, (board, horizon) in positions().items():
        for species in Species:
            reference = ExactSolver(species, shared_target="aggregate",
                                    check=Deadline(monotonic() + 10).check)
            exact = reference.action_values(board, species, horizon)
            best = max(o.score for o in exact.values())
            for limit in (64, 8):
                record = {"position": name, "species": species.value, "board": packed(board),
                          "remaining_plies": horizon, "candidate_limit": limit,
                          "optimal_score": fraction(best), "variants": {}}
                scores = {}
                for variant in ("unknown", "known", "protected"):
                    config = SearchConfig(max_depth=horizon, candidates=limit,
                                          preserve_dominance=False, protect_tactics=variant == "protected")
                    decision = choose_turn(board, species, time_budget=args.budget, config=config,
                                           remaining_plies=None if variant == "unknown" else horizon)
                    actual = exact[decision.moves]
                    scores[variant] = actual.score
                    record["variants"][variant] = {"config": asdict(config), "decision": asdict(decision),
                                                   "actual_outcome": outcome(actual),
                                                   "regret": fraction(best - actual.score)}
                for comparison, a, b in (("known_vs_unknown", "known", "unknown"),
                                         ("protected_vs_known", "protected", "known")):
                    delta = scores[a] - scores[b]
                    record[comparison] = fraction(delta)
                    summary[str(limit)][comparison]["improved" if delta > 0 else "worse" if delta < 0 else "tied"] += 1
                results.append(record)
            print(name, species.value, "checked", flush=True)
    paths = sorted((ROOT / "src/vampires").rglob("*.py")) + [Path(__file__), ROOT / "tools/check_tactics.py"]
    data = {"generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
            "platform": platform.platform(), "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "command": shlex.join([sys.executable, *sys.argv]), "budget_seconds": args.budget,
            "elapsed_seconds": monotonic() - started, "seed_range": [1201, 1208],
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "limits": "Development positions and known horizons of one/two total plies. Same depth and time budget across variants. "
                      "Dominance shortcut disabled to isolate evaluation/generation. Exact outcomes assume aggregate shared-target combat; "
                      "live candidates still exclude those attacks. No match-strength, global safety, CTI, or official-server claim.",
            "summary": summary, "records": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps(summary, indent=2), flush=True)
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
