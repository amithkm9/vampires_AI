# Project status

Updated: 2026-10-11.

## Current milestone

Phases 0 and 1 are complete. The local Phase 2 forward model and Phase 3 playable baseline are implemented, with initial Phase 4 deadline/depth control. The full suite passes **105 tests**. **The player now completes autonomous local TCP matches; official-server parity, CTI deployment, and competitive strength remain unverified.**

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
- Implemented joint-turn generation, an exhaustive small-board oracle, legal fallback, and exact joint transitions with explicit ambiguity/overflow/branch limits.
- Added bounded population/house-race/exposure evaluation and hand-written expectiminimax with exact chance distributions, iterative depth, and a per-search cache. The normal player starts at two plies; large candidate sets remain selective.
- Verified the trap regression: vampire one-ply evaluation selects the exposed approach; two-ply opponent lookahead selects the safe approach. Both species select their safe approach at two plies.
- Added `run.py` and the persistent client loop: name once, authoritative updates, validated MOV, END reset, BYE exit, and error diagnostics. UPD payload reads and MOV sends share the two-second turn deadline.
- Passed eight local TCP harness matches across two configurations, covering both supplied maps and species, 80 AI turns total, and launch from an unrelated working directory. Four matches ended by extinction and four at the harness ply cap. These are integration smoke tests, not competitive benchmarks.
- Passed eight synthetic search timing probes, including crowded boards and byte-boundary populations. Under the 0.05-second stress budget, crowded boards used the legality fallback; this is a known search-quality limitation.

## Next work

Prioritize the next build in [TODO.md](TODO.md): make candidate generation return useful partial work on crowded boards; replace skipped large chance distributions with bounded handling; implement multi-house growth/denial and dominant-stack preservation; and obtain official-server/CTI evidence. The [implementation notes](docs/IMPLEMENTATION.md) describe the current baseline. Sampled search and MCTS remain planned comparisons.

## Repository publication

Repository: https://github.com/amithkm9/vampires_AI. The initial project history is organized into eight meaningful commits, ending with the roadmap, status, and repository instructions. Standard Git successfully pushed `main` on 2026-10-09 and configured `origin/main` as its upstream. No plugin was used for the successful publication.

Before publication, all 56 tests passed again and all 13 original/extracted material hashes matched. Downloaded research PDFs remain excluded; their citations and provenance are versioned. See [the repository instructions](docs/REPOSITORY.md) for verification commands. Publication does not change the unfinished gameplay and official-server validation milestones.

The playable-baseline update is organized into **10 additional commits**, preserving the original eight: deadlines; joint simulation; turn generation/tests; evaluation; search/tests; protocol timing; launcher; TCP harness/tests; validation records; and documentation. Pre-publication validation on 2026-10-11 passed all 105 tests in 0.578 seconds. All 13 original material hashes and all source hashes in the saved smoke/stress records matched. The October 9 integration records remain historical evidence; those matches were not rerun for this publication.

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/inspect_map.py maps/testmap2.xml
python3 tools/inspect_map.py maps/thetrap.xml
python3 tools/analyze_maps.py --output reports/map-analysis-2026-10-09.json
python3 tools/check_player.py --output reports/player-smoke-2026-10-09.json
python3 tools/check_player.py --budget 1.25 --depth 3 --max-plies 20 --output reports/player-default-smoke-2026-10-09.json
python3 tools/check_search.py --output reports/search-stress-2026-10-09.json
```

The full 105-test run passed on Python 3.14.6, and all 13 original/extracted material hashes were verified again. See [the baseline verification record](reports/baseline-verification-2026-10-09.md), the linked JSON records, and the retained earlier foundation/map-analysis records. The normal-configuration harness observed a maximum response of 1.25023 seconds across 30 AI turns on this Mac. This is finite local evidence, not a CTI or universal deadline guarantee.

## Open dependencies

- Submission and tournament dates, team details, and any additional course instructions.
- CTI operating system, available Python version, launch command, and server access.
- Official-server validation: this Mac has no `dotnet`, `mono`, or `wine` command available. The supplied server targets .NET Framework 4.5 on Windows.
- Clarification of the move-record/group limit and same-target combat resolution. See [the rule decisions](docs/RULES.md).

There is no measured competitive playing strength, official-server parity, CTI launch check, final course report, or presentation yet. Shared-target battles, overflow, and simultaneous extinction remain unresolved server behaviors. Candidate pruning and outcome limits can omit important actions. Local exact probabilities and tactical regressions are not full-game solutions.
