# vampires_AI

Build an AI for the Foundation of AI tournament. The game is a fully observable grid contest: convert humans, grow your species, anticipate the opponent, and finish with the dominant population. Battles can be random. Each turn must be sent to the supplied server within **two seconds**.

The project has a **playable opponent-aware engine with 262 passing tests**. The provisional default, `adaptive`, adds reusable search work and a depth-five ceiling to intact-group expectiminimax. In the latest locked league it scored **6 wins, 10 draws, 2 losses**, compared with **5/10/3** for the previous default against the same opponents. This one-game difference is limited local evidence. Split-move refinements repair exact tactical examples but remain experimental after weaker development results. **Official-server and CTI validation are still required; this is not a tournament-readiness or winning guarantee.**

## Start here

1. Read [the course rules and implementation decisions](docs/RULES.md).
2. Follow [the roadmap from setup to submission](docs/planning/ROADMAP.md).
3. Work through [the live task list](TODO.md), starting with the next build priorities.
4. Read [the current status](STATUS.md) before resuming work.
5. Read [the tournament algorithm design](docs/STRATEGY.md) and [exact map findings](reports/map-analysis-2026-10-09.md) before implementing search.
6. Read [the baseline implementation and limitations](docs/IMPLEMENTATION.md) to distinguish implemented behavior from planned improvements.
7. Read [the strength audit](docs/STRENGTH_AUDIT.md) and [all comparison results](experiments/2026-10-11-strength/EXPERIMENT.md) before choosing an experimental engine.
8. Follow [the next algorithm improvements](docs/NEXT_ALGORITHM.md), prioritized from [verified match replays](reports/replay-analysis-2026-10-11.md).
9. Read [the outcome and tactical-coverage experiment](experiments/2026-10-12-outcomes/EXPERIMENT.md): known cutoffs improve some exact development decisions; attack reservation also exposes a regression and remains disabled by default.
10. Read [the latest upgrade comparison](experiments/2026-10-12-upgrade/EXPERIMENT.md), [research rationale](docs/UPGRADE_RESEARCH.md) and [parallel edge-case audit](docs/EDGE_CASE_AUDIT.md).
11. Read [the opponent league protocol and results](experiments/2026-10-13-league/EXPERIMENT.md): 96 development games and 36 locked evaluation games, exact snapshots and verified replays.

## Launch the player

Requires Python 3.10 or newer and the standard library only. Put the server IP and port last:

```sh
python3 run.py --name vampires_AI --budget 1.25 127.0.0.1 5555
```

Replace the example IP/port with the official server's values. From another directory, use the absolute path to `run.py`; no `PYTHONPATH` setup is needed. The default search budget is 1.25 seconds inside the brief's two-second turn deadline. Timing on CTI remains unmeasured. Diagnostics go to stderr; `--quiet` suppresses routine turn logs.

The default is `--engine adaptive --depth 5`. It preserves completed shallower decisions when deeper work runs out of time. Use `--engine cohesive_material --depth 3` for the previous default or `--engine baseline` for the sequential engine. Other experiments are `balanced`, `resources`, `balanced_resources`, `portfolio`, `cohesive`, `hybrid` and `hybrid_adaptive`. Adaptive modes default to depth five; other modes default to three, with explicit `--depth` always taking precedence. Adaptive/cohesive modes omit partial moves for both species. Hybrid modes add selected partial moves, with measured branching/strength tradeoffs. The promoted mode keeps the original evaluator.

## What was supplied

| Material | Location | Purpose |
| --- | --- | --- |
| Nine-page project brief | [Projectv10.pdf](docs/reference/Projectv10.pdf) | Authoritative assignment, game rules, and protocol |
| Searchable brief | [Projectv10.txt](docs/reference/Projectv10.txt) | Extracted text; use the PDF for diagrams and formulas |
| Original ZIPs | `materials/archives/` | Preserved source archives |
| Starter kit | `vendor/starterkit/` | Original incomplete Python example |
| Server version 3.2.1 | `vendor/server/` | Windows .NET server, two DLLs, original configuration |
| Map generator | `vendor/map-generator/` | Windows executable and original XML maps |
| Working maps | `maps/` | Copies of `testmap2.xml` and `thetrap.xml` |
| Integrity record | [manifest.json](materials/manifest.json) | Sizes, original names, and SHA-256 hashes |

Original file contents were preserved; only their locations changed. See the [source audit](docs/planning/SOURCE_AUDIT.md) for starter-kit defects and configuration discrepancies.

## Working code

| File | Responsibility |
| --- | --- |
| `src/vampires/model.py` | Board, XML map loading, species identity, and game reset |
| `src/vampires/protocol.py` | Exact TCP reads, packet parsing, complete sends, validated MOV packets |
| `src/vampires/rules.py` | All six move rules, combat probabilities, expected survivors, battle sampling |
| `src/vampires/simulation.py` | Exact rational reference and streaming transitions; integer battle sampling; explicit ambiguity and overflow limits |
| `src/vampires/turns.py` | Legal fallback, bounded joint candidates, exhaustive small-position oracle |
| `src/vampires/evaluation.py`, `search.py`, `budget.py` | Bounded evaluation, iterative expectiminimax, per-search cache, cooperative deadlines |
| `src/vampires/balanced.py`, `strategy.py`, `engines.py` | Resumable root/chance search, strategic alternatives, explicit engine selection and provisional default |
| `src/vampires/hybrid.py` | Experimental critical partial captures, attacks, reinforcement and separation for both sides |
| `src/vampires/certificates.py` | Preserves an intact stack whose dominance follows conditionally from the written rules |
| `src/vampires/growth.py`, `mcts.py` | Experimental multi-house planning and sampled adversarial UCT; neither is the live default |
| `src/vampires/endgame.py`, `history.py` | Exact finite-horizon offline outcome reference and bounded authoritative repetition diagnostics |
| `src/vampires/player.py`, `run.py` | Persistent game loop and launch command |
| `tests/` | 262 tests covering rules, independent exact references, transitions, chance bounds, interrupted search, byte boundaries, memory, deadlines, protocol lifecycle and league integrity |
| `tools/inspect_map.py` | Read a map without running the Windows generator |
| `tools/analyze_maps.py` | Reproduce exact local reply risks and optimistic capture-route calculations |
| `tools/check_player.py`, `tools/check_search.py` | Reproducible local TCP matches and synthetic timing checks |
| `tools/benchmark_strength.py`, `tools/benchmark_long.py` | Paired engine comparisons against the immutable published baseline, with raw records and provenance |
| `tools/analyze_replays.py` | Reconstruct stored matches and diagnose combat, repetition, resource deficits, and unfinished root comparisons |
| `tools/check_tactics.py`, `tools/check_outcomes.py` | Measure candidate/reply omissions and search decision regret against exact tiny outcome trees |
| `tools/league.py`, `tools/league_support.py`, `tools/analyze_league.py` | Paired opponent league, immutable source snapshots, checksummed resumable records and seeded replay diagnosis |

All working Python code uses the standard library. The current syntax targets Python 3.10 or newer; local validation used Python 3.14.6. Confirm the Python version available on CTI before selecting the final runtime. No dependency installation is needed for the current code.

From this project directory on macOS or Linux:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/inspect_map.py maps/testmap2.xml
python3 tools/inspect_map.py maps/thetrap.xml
python3 tools/analyze_maps.py --output reports/map-analysis-2026-10-09.json
python3 tools/check_player.py --output reports/player-smoke-2026-10-09.json
python3 tools/check_search.py --output reports/search-stress-2026-10-09.json
```

On Windows PowerShell, set `$env:PYTHONPATH = "src"` and use `python -m unittest discover -s tests -v`.

The server executables target Windows .NET Framework; they have not been run here. The local harness checks our protocol and launcher against a fixture sharing our simulator, not against the official server. Shared-target combat is excluded from live candidates pending verification. See [the validation record](reports/baseline-verification-2026-10-09.md) for evidence and limits.

## Completion requirements

The finished project needs an opponent-aware AI, successful CTI launch and official-server communication, benchmark evidence on both species, a report mapping algorithms to code, a five-minute presentation, and source submission on edunao before the tournament. The deadline and CTI environment remain to be confirmed.
