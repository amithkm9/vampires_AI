# Project status

Updated: 2026-10-12.

## Current milestone

Phases 0 and 1 are complete. The local forward model, playable client, bounded search, finite-horizon references and history are implemented. The latest upgrade adds resumable search, explicit strategy alternatives and parallel edge-case repairs. The full suite passes **219 tests**. `cohesive_material` is provisionally promoted after **4 wins, 3 draws, 1 loss** in eight locked normal-budget games against the pre-upgrade engine. **Official-server parity, CTI deployment and strength against tournament opponents remain unverified.**

## Resumable search and edge-hardening milestone, 2026-10-12

- Pushed the prior nine commits first; remote main was verified at `d28c5179a721bb7812c14d277a5cc327c641d47c`, which is the frozen opponent for this upgrade.
- Implemented `balanced.choose_balanced`, sharing root work and battle preparation while preserving conservative intervals, complete shallower decisions and explicit model limits. Implemented resource projection, policy portfolios and intact-group abstraction as separately selectable modes.
- Ran 48 development games across six variants and 8 locked evaluation games, with source hashes, map/species, seeds, runtime and all losses preserved. Best development candidate `cohesive_material`: 3W/5D/0L. Locked evaluation at a 1.25-second allowance: 4W/3D/1L; supplied maps 2W/2D/0L; unseen generated maps 2W/1D/1L. Maximum candidate response 0.153828 seconds. This small sample does not establish universal superiority.
- Promoted that exact candidate provisionally. `--engine baseline` retains the former algorithm; resource and portfolio variants remain alternatives. Intact-group abstraction explicitly omits potentially useful own/opponent splits.
- At the user's request, three parallel reviewers found and repaired fragmented-UPD deadline accounting, chance-cap overfetch, eager preparation starving roots, byte-boundary partial-move omissions, repeated board-wide candidate validation, and history memory growth. Added independent bounded exhaustive combat/transition checks; see [edge audit](docs/EDGE_CASE_AUDIT.md).
- Final suite: `PYTHONPATH=src python3 -m unittest discover -s tests -q`, **219 passed in 1.919 seconds** on Python 3.14.6. All 13 original/extracted material hashes match; runtime imports remain standard-library/project-only.
- Final local TCP smoke: four matches / **31 AI turns**, both supplied maps/species, persistent restart, unrelated launch directory, legal MOV and clean BYE; maximum response **0.028358 seconds**. Loopback binding required authorized execution outside the sandbox. Record: `reports/player-upgrade-smoke-2026-10-12.json`.
- Passed **56 search stress cases** across all seven engine modes and **24 maximum-area probes** on fully occupied 255×255 boards with zero, 0.05 and 1.25-second budgets. Largest observed search time **1.292704 seconds**; cooperative overhead can exceed the nominal search allowance while remaining below the two-second local limit. No CTI guarantee is inferred.
- [Research synthesis](docs/UPGRADE_RESEARCH.md), [registered experiment/results](experiments/2026-10-12-upgrade/EXPERIMENT.md), and [implementation mapping](docs/IMPLEMENTATION.md) record limitations and negative ablations.

## Outcome and coverage milestone, 2026-10-12

- Added `endgame.ExactSolver`: full canonical legal finite-horizon trees with rational W/D/L outcomes, explicit offline combat assumptions, horizon/side-aware caching, and failure on resource/ambiguity limits. An exact score tie minimizes the acting side's loss probability. This is a small offline reference, not a live map solver.
- Added `choose_turn(..., remaining_plies=N)` for known controlled cutoffs. Counts include both species' moves. At zero, population win/draw/loss replaces the heuristic. The live protocol still passes no horizon; it does not infer 200 plies from the example configuration.
- Added bounded `PositionHistory` to the persistent player. Authoritative repeated positions record visits, update periods, leading/tied/trailing status, and a trailing-cycle review flag. END/BYE clear history. No automatic draw rule, blanket repetition penalty, or strategic cycle-breaking claim is introduced.
- Added 24 tests (146 total), including independent tiny outcome trees, necessary gambles, safe wins/draws, cutoff handling, repetition reset, and exact tactical-omission witnesses. Full suite: `PYTHONPATH=src python3 -m unittest discover -s tests`, 146 passed in 0.651 seconds on Python 3.14.6.
- Recorded 60 two-sided exact coverage cases (15 development positions, two species, limits 64/8), plus an initial 30-case vampire pilot. At limit 64, seven of thirty decisions lose value through omitted root moves, and four positions contain optimistic action values from omitted replies. The reported default-limit witnesses involve unverified shared-target combat under the explicit offline aggregation assumption.
- Implemented optional `SearchConfig(protect_tactics=True)` to reserve whole-group attacks with a nonzero chance of success. The 60-case follow-up fixes two decisions at limit 8 but worsens one by displacing a merge; limit-64 decision scores are unchanged. **Keep this experiment disabled by default.**
- Evaluated 180 search decisions at a 1.25-second budget against exact outcomes. At limit 64, known cutoff improves 8/30 position/species cases, ties 22, worsens none. At limit 8 it improves 9, ties 21, worsens none. These reused tiny development fixtures are not matches or independent evidence of tournament strength. Maximum observed search time was 0.079753 seconds; most tiny trees finish before the budget.
- Preserved commands, source hashes, full boards, assumptions, all negative results, and exact scores in [the experiment record](experiments/2026-10-12-outcomes/EXPERIMENT.md). Historical 108-match data are unchanged; replaying them after runtime changes requires their recorded source revision.
- Passed four new local TCP matches / 30 AI turns at the normal 1.25-second budget, both maps/species, restart, unrelated working directory, and clean BYE. Maximum response: **1.250297 seconds**. Record: `reports/player-outcomes-smoke-2026-10-12.json`. Socket binding required authorized execution outside the sandbox. Original material hashes and the current experiment/TCP source hashes match; imports remain standard-library only. Official-server/CTI checks are still pending.

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
- The earlier baseline passed eight synthetic search timing probes, including crowded boards and byte-boundary populations. Its crowded-board generation could consume the budget and leave only the legality fallback; this prompted the current partial-generation change.
- Streamed exact chance outcomes and retained unvisited probability mass as intervals instead of dropping large actions. Added bounded partial generation and conditional dominant-stack preservation.
- Added experimental multi-house growth/denial and seeded adversarial UCT, with 17 additional tests for transitions, bounds, planning, and preservation. Both alternatives remain outside the live default.
- Ran 108 paired local matches against immutable revision `2a08829b1935a80c3c11a37ecea5efb089425268`, covering two budgets, two horizons, both species, supplied maps, and two generated maps. Preserved all results, including negative ones. At 0.1 seconds/60 plies, bounded search scored 2 wins/12 draws/2 losses; growth scored 4/10/2; UCT scored 0/2/14. At 200 plies on supplied maps, bounded and growth both scored 1/2/1. These small comparisons do not establish superiority.
- Rechecked the normal launcher with four local TCP matches and 30 AI turns at a 1.25-second search budget; maximum observed response 1.250434 seconds. Both maps/species, persistent connection, unrelated launch directory, legal MOV, and clean BYE passed.
- Added replay diagnostics and reconstructed the same 108 matches/6778 plies without rerunning search. All recorded outcomes matched. The default engine's three trap losses at the 0.1-second budget had no monster/random battles and ended 8–9; the long loss revisited states on 160 of 200 plies. This motivates outcome/horizon handling, resource denial, and root comparison, without proving that the starting position or any particular move was avoidably lost. See [the replay findings](reports/replay-analysis-2026-10-11.md).

## Next work

Follow [the next-algorithm plan](docs/NEXT_ALGORITHM.md) and [TODO.md): expand the opponent league and map families, quantify the intact-group abstraction's missed split replies, test interception-aware resource plans and repetition-guided endings, and obtain official-server/CTI evidence. Root allocation and bounded exhaustive edge checks are implemented. The provisional default is cohesive_material; resource projection, portfolio, growth, UCT and attack reservation remain experiments. The 56 new games provide limited local evidence, not tournament validation.

## Repository publication

Repository: https://github.com/amithkm9/vampires_AI. The initial project history is organized into eight meaningful commits, ending with the roadmap, status, and repository instructions. Standard Git successfully pushed `main` on 2026-10-09 and configured `origin/main` as its upstream. No plugin was used for the successful publication.

Before publication, all 56 tests passed again and all 13 original/extracted material hashes matched. Downloaded research PDFs remain excluded; their citations and provenance are versioned. See [the repository instructions](docs/REPOSITORY.md) for verification commands. Publication does not change the unfinished gameplay and official-server validation milestones.

The playable-baseline update is organized into **10 additional commits**, preserving the original eight: deadlines; joint simulation; turn generation/tests; evaluation; search/tests; protocol timing; launcher; TCP harness/tests; validation records; and documentation. Pre-publication validation on 2026-10-11 passed all 105 tests in 0.578 seconds. All 13 original material hashes and all source hashes in the saved smoke/stress records matched. The October 9 integration records remain historical evidence; those matches were not rerun for this publication.

The strength-audit update is organized into **20 additional commits**: streaming simulation; partial generation; dominance preservation; chance-bounded search; experimental growth; experimental UCT; regression tests; player diagnostics; two benchmark tools; three complete experiment runs; experiment interpretation; stress evidence; TCP evidence; rule decisions; implementation notes; strength/strategy audit; and project guidance/status. These preserve the existing 18 commits and the exact benchmarked runtime sources. The standing preference is frequent, small, meaningful commits, recorded in `AGENTS.md`.

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

Those October 9 records describe the historical baseline. Current validation on Python 3.14.6 passed 122 tests in 0.635 seconds. All 13 original material hashes, all three experiment source records, and the two new smoke/stress source records match their saved hashes. New commands:

```sh
python3 tools/check_search.py --output reports/search-stress-2026-10-11.json
python3 tools/check_player.py --budget 1.25 --depth 3 --max-plies 20 --output reports/player-strength-smoke-2026-10-11.json
python3 tools/benchmark_strength.py --output experiments/2026-10-11-strength/pilot-01
python3 tools/benchmark_strength.py --budget .1 --output experiments/2026-10-11-strength/pilot-02
python3 tools/benchmark_long.py --output experiments/2026-10-11-strength/long-01
```

Use fresh output paths for reruns; the benchmark deliberately refuses to replace raw records. See [the experiment record](experiments/2026-10-11-strength/EXPERIMENT.md) for exact results and the overlapping-probe caveat on pilot 01. The [normal-budget TCP check](reports/player-strength-smoke-2026-10-11.json) observed a maximum response of 1.250434 seconds across 30 AI turns on this Mac. This is finite local evidence, not a CTI or universal deadline guarantee.

Replay validation: `python3 tools/analyze_replays.py --output reports/replay-analysis-2026-10-11.json` matched all 108 stored games and 6778 plies. These are diagnostics of existing data, not additional trials. No new runtime or competitive match result is implied.

## Open dependencies

- Submission and tournament dates, team details, and any additional course instructions.
- CTI operating system, available Python version, launch command, and server access.
- Official-server validation: this Mac has no `dotnet`, `mono`, or `wine` command available. The supplied server targets .NET Framework 4.5 on Windows.
- Clarification of the move-record/group limit and same-target combat resolution. See [the rule decisions](docs/RULES.md).

There is preliminary strength evidence against one historical engine, but no demonstrated superiority against strong tournament opponents, official-server parity, CTI launch check, final course report, or presentation yet. Shared-target battles, overflow, and simultaneous extinction remain unresolved server behaviors. Candidate pruning can omit important actions; chance intervals can remain too wide for useful decisions. Local exact probabilities and tactical regressions are not full-game solutions.
