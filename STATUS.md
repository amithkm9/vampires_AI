# Project status

Updated: 2026-10-09.

## Current milestone

Phases 0 and 1 are complete. Phase 2 has started: exact battle distributions, all one-record moves, and single-move transitions are implemented. The full suite passes 56 tests. **The project cannot yet play a match autonomously.**

Completed work:

- Read all nine PDF pages, including the move diagram and protocol layouts; reviewed both Python files, the server configuration, and both XML maps.
- Extracted all three ZIPs safely and preserved their originals. Recorded hashes for four original inputs and nine extracted files.
- Identified the Windows .NET binary format and the missing local compatibility runtime. Binary internals have not been audited or executed.
- Implemented board updates, both species, END reset, BYE termination, packet codecs, exact reads, complete writes, legal-move validation, and single-battle calculations.
- Verified 41 tests, including a socket-pair fixture that completes two game initializations on one connection and changes our species between games.
- Re-examined all supplied text materials and maps; verified all 13 original/extracted material hashes again.
- Added an exact rational single-move reference model and 15 additional tests. No AI, tree-search, or graph library was introduced.
- Calculated the trap map's exposed/safe approach risks and the large map's human-resource bottleneck. Saved reproducible results in `reports/map-analysis-2026-10-09.json`.
- Saved a [tournament strategy design](docs/STRATEGY.md), bounded literature comparison, search log, verified source matrix, references, and two primary papers.

## Next work

Continue Phase 2 in [TODO.md](TODO.md): complete legal joint turns and clarify multi-record resolution, retaining the exact single-move model as a reference. Implement an opponent-aware expectiminimax baseline, race/denial evaluation, a deadline, and launcher next. The [strategy design](docs/STRATEGY.md) specifies the comparison with sampled search and MCTS; neither engine is implemented yet.

## Repository publication

Repository: https://github.com/amithkm9/vampires_AI. The initial project history is organized into eight meaningful commits, ending with the roadmap, status, and repository instructions. Standard Git successfully pushed `main` on 2026-10-09 and configured `origin/main` as its upstream. No plugin was used for the successful publication.

Before publication, all 56 tests passed again and all 13 original/extracted material hashes matched. Downloaded research PDFs remain excluded; their citations and provenance are versioned. See [the repository instructions](docs/REPOSITORY.md) for verification commands. Publication does not change the unfinished gameplay and official-server validation milestones.

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/inspect_map.py maps/testmap2.xml
python3 tools/inspect_map.py maps/thetrap.xml
python3 tools/analyze_maps.py --output reports/map-analysis-2026-10-09.json
```

The full 56-test run passed on Python 3.14.6. The original material hashes were verified again. The initial 41-test record remains in [the foundation record](reports/foundation-verification.txt); current evidence is in [the strategy analysis record](reports/strategy-verification-2026-10-09.txt) and [map analysis](reports/map-analysis-2026-10-09.md). The recorded 0.017-second offline analysis is not a live-search timing benchmark.

## Open dependencies

- Submission and tournament dates, team details, and any additional course instructions.
- CTI operating system, available Python version, launch command, and server access.
- Official-server validation: this Mac has no `dotnet`, `mono`, or `wine` command available. The supplied server targets .NET Framework 4.5 on Windows.
- Clarification of the move-record/group limit and same-target combat resolution. See [the rule decisions](docs/RULES.md).

There is no measured playing strength, completed multi-record simulator, tested search deadline, final report, or presentation yet. Local exact probabilities and mathematical consequences are not full-game solutions or official-server observations.
