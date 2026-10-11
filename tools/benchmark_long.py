"""Longer-horizon development-map follow-up to the paired strength pilot."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import sys
import tempfile
from time import monotonic

from benchmark_strength import BASELINE, ROOT, load_baseline, match, packed, summarize
from vampires.model import Species, load_map
from vampires.search import SearchConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output directory to preserve prior evidence")
    args.output.mkdir(parents=True)
    maps = {name: load_map(ROOT / "maps" / (name + ".xml")) for name in ("thetrap", "testmap2")}
    inputs = {name: packed(board) for name, board in maps.items()}
    (args.output / "boards.json").write_text(json.dumps(inputs, indent=2) + "\n")
    paths = sorted((ROOT / "src/vampires").glob("*.py")) + [Path(__file__), ROOT / "tools/benchmark_strength.py"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "baseline_revision": BASELINE,
                "python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(),
                "command": shlex.join([sys.executable, *sys.argv]), "budget_seconds": .1, "max_plies": 200,
                "seeds": [20261013], "search_config": asdict(SearchConfig()), "source_sha256": hashes,
                "map_sha256": {name: hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest() for name, data in inputs.items()},
                "limits": "Two supplied development maps, one new seed, both species; horizon sensitivity only, not an independent broad evaluation. "
                          "200 plies matches the supplied configuration; actual tournament limits and CTI timing remain unverified."}
    games = []
    started = monotonic()
    with tempfile.TemporaryDirectory(prefix="vampires-baseline-") as directory:
        model, search, baseline_hashes = load_baseline(directory)
        metadata["baseline_source_sha256"] = baseline_hashes
        (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        with (args.output / "matches.jsonl").open("w") as stream:
            for engine in ("bounded", "growth", "uct"):
                for name, board in maps.items():
                    for species in Species:
                        result = match(board, engine, species, 20261013, .1, 200, model, search)
                        result["map"] = name
                        games.append(result)
                        stream.write(json.dumps(result) + "\n")
                        stream.flush()
                print(engine, summarize(games)[engine], flush=True)
    for path, digest in hashes.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Source changed during experiment: " + path)
    (args.output / "summary.json").write_text(json.dumps({"elapsed_seconds": monotonic() - started,
                                                         "engines": summarize(games)}, indent=2) + "\n")
    print(f"Saved {len(games)} longer-horizon matches to {args.output}", flush=True)


if __name__ == "__main__":
    main()
