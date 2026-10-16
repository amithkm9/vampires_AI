# Project status

Updated: 2026-10-16.

## Current state

The persistent client, legal move generation, local simulator, opponent-aware search and exact small-position references are implemented. The provisional default is `strategic` at depth five, using a 1.25-second search budget within the two-second full-turn deadline. It adds outcome-oriented no-human scoring and exclusive sequential conversion races to reusable expectiminimax. The player uses Python 3.10+ and the standard library only.

The latest locked comparison scored **17 wins, 8 draws, 11 losses**, versus **14/8/14** for the previous `adaptive:5` default. Four cases improved and one regressed. Improvement was concentrated in no-human endings; one dispersed-map game regressed. The paired map-cluster interval for score gain is **[-0.0833, 0.3333]**, including zero. This is a provisional promotion, not established general superiority. The [strategy record](experiments/2026-10-15-strategy/EXPERIMENT.md) preserves 184 development and 72 held-out games; all **8046 plies** were verified. Earlier adaptive/cohesive results remain in the [October 13 league](experiments/2026-10-13-league/EXPERIMENT.md).

**Official-server parity, CTI launch/timing and strength against tournament opponents remain unverified.** The unresolved move/protocol interpretations remain explicit in [RULES.md](docs/RULES.md).

## Whole-project audit, 2026-10-16

Reviewed the runtime, experimental engines, tools, tests, documentation and assignment PDF. The strategy/default and unresolved rule interpretations are unchanged. Repairs:

- Search and recursive transition/generation helpers now release their closures and suspended continuations on completion, timeout and errors. This removes avoidable retention between turns without forcing garbage collection during play. Weak-reference tests reproduce the previous failures with cyclic collection disabled.
- `simulation._survival_branch` constructs exact binomial probabilities using integer recurrence. It preserves all outcomes, including rare tails and both ways to reach an empty cell. Eight additional large/asymmetric probability comparisons complement the independent small-battle and joint-transition references.
- Current report commands reject existing outputs before doing work and create reports exclusively. Replay analysis now rejects an unfinished final append even when its JSON parses; it does not modify the journal.

The [registered runtime comparison](reports/runtime-audit-2026-10-16/plan.json) uses reference commit `edf2c1b`, six explicit battle cases, seven alternating timing batches of thirty calls, and four identical completed depth-three strategic searches. Exact combat construction was **1.43–4.60× faster** on this machine. Decisions and diagnostics matched on both supplied maps/species. With cyclic collection disabled for diagnosis, four repeated testmap2 searches retained **580597 bytes before versus 81126 after**; these are traced Python allocations, not process RSS or cache-memory guarantees. [Raw results](reports/runtime-audit-2026-10-16/results.json). No new competitive-strength result is claimed.

Validation:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q`: **280 tests passed in 3.412 seconds**.
- `tools/check_search.py` at 1.25 seconds: strategic/tactical depth five and baseline depth three, both species, **24 cases**, maximum **1.252386 seconds**.
- `tools/check_limits.py --engines strategic baseline tactical --depth 5`: **36 maximum-area probes**, maximum **1.304241 seconds**. Timing commands ran serially; these are local cooperative measurements, not worst-case guarantees.
- `tools/check_player.py --engine strategic --depth 5 --budget 1.25 --max-plies 20 --seed 20261016`: **four matches / 25 AI turns**, both supplied maps/species, unrelated working directory, persistent restart and clean BYE. Maximum full response **0.716670 seconds**. Sandbox localhost binding was denied; authorized execution succeeded. [TCP report](reports/player-audit-2026-10-16.json).
- The current replay analyzer verified all five league journals: **388 matches / 12433 plies**, with archived runtime hashes intact. All **13 original-material hashes** match `materials/manifest.json`. Runtime imports remain standard-library-only; Python 3.10 syntax parsing passed. This does not replace running on the CTI interpreter.
- All **15 direct CLI entry points** passed `--help` from another directory, plus five module entry points. Changed documentation links, final timing-report source hashes, unused-import checks and `git diff --check` passed. Original materials and earlier experiment records were preserved.

Reproduce the performance comparison with `PYTHONDONTWRITEBYTECODE=1 python3 tools/check_runtime.py --reference edf2c1b --output reports/NEW_RUNTIME_RUN`. It saves configuration, environment, source/map hashes and the reference revision before measurement. Stress reports are `reports/search-audit-*-2026-10-16.json` and `reports/maximum-board-audit-2026-10-16.json`; use fresh output paths for repeats.

## Agent strategy, 2026-10-15

- `planning.evaluate_outcome` makes useful recovery attempts preferable to indefinitely preserving a no-human deficit. It changes the recorded 6-versus-7 cycle decision without inventing a live cutoff.
- `planning.conversion_race` credits each house once, carries individual groups' travel times and populations across captures, and can recognize newly affordable houses. Routes still ignore interception and incidental occupied cells.
- `strategic` combines these features with the existing intact-group generator, balanced search, exact chance probabilities and conservative unvisited-mass intervals. `adaptive` is unchanged and explicitly selectable.
- `outcome` isolates the no-human feature. `tactical` combines strategic evaluation with hybrid partial moves: it repairs an exact split witness, but did not improve aggregate development score and remains experimental.
- Tests cover growth/ownership invariants, deadlines, bounded and antisymmetric values, the recorded cycle, safe known-cutoff leads/ties and an exact partial-capture win for the tactical variant.

Validation after default selection: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q` passed **274 tests in 3.172 seconds**. All three new modes passed eight normal-budget search cases each, both species (**24 total**), maximum about **1.2501 seconds**. They passed **36 maximum-area probes**, maximum **1.285958 seconds**. Exact commands, source hashes and local-runtime limitations are retained in the [experiment record](experiments/2026-10-15-strategy/EXPERIMENT.md) and `reports/*strategy*-2026-10-15.json` / `reports/search-*-2026-10-15.json`.

The [new TCP smoke record](reports/player-strategic-smoke-2026-10-15.json) passed **four matches / 31 AI turns**, both supplied maps/species, persistent restart, unrelated launch directory and clean BYE. Maximum full response was **0.713226 seconds**. Initial sandbox localhost binding was blocked; authorized execution succeeded. This remains a local simulator check.

## Repository cleanup, 2026-10-14

- Grouped optional growth, UCT and partial-move algorithms under `src/vampires/experimental/`; engine names, defaults and search behavior are unchanged.
- Moved four older benchmark/replay tools into `tools/legacy/`. Current launch, validation and league command paths are stable.
- Removed the obsolete initial-publication helper and five unused imports. Retained tested algorithm variants and the evidence needed to reproduce their results.
- Made source capture recursive and preserved nested packages in historical Git exports.
- Replaced long status/task histories with these active pages; archived the previous versions under [docs/history](docs/history/STATUS_2026-10-13.md).
- Added a [code map](docs/STRUCTURE.md) and [tool guide](tools/README.md). Original materials and historical experiment records remain in place.

Validation: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q` passed **262 tests in 2.915 seconds**. All 13 tool CLIs and the launcher passed `--help` from `/tmp`; four package-style tool entry points also passed. Legacy Git exports loaded both the original flat baseline and the reorganized package, with legal decisions from each. The current replay analyzer reverified **132 matches / 4387 plies** without rewriting their records. All **167 preserved evidence/material files** and all **13 original-material hashes** are unchanged. The import scan found no remaining unused imports; documentation links and `git diff --check` passed. Removed seven generated bytecode cache directories.

The fresh [TCP smoke record](reports/player-cleanup-smoke-2026-10-14.json) covers **four matches / 30 AI turns**, both maps/species, persistent restart, unrelated launch directory and clean BYE. Maximum full response was **0.728035 seconds**. Command: `PYTHONDONTWRITEBYTECODE=1 python3 tools/check_player.py --engine adaptive --depth 5 --budget 1.25 --max-plies 20 --output reports/player-cleanup-smoke-2026-10-14.json`. The sandbox initially blocked localhost binding; authorized execution succeeded. All recorded source hashes match the reorganized runtime. This remains a local harness check.

## Earlier gameplay evidence

The October 13 milestone passed 262 tests, 24 normal-budget stress cases and 36 maximum-area probes; the largest observed search time was 1.297874 seconds. Its [TCP launcher check](reports/player-league-smoke-2026-10-13.json) covered four matches and 30 AI turns, both supplied maps/species, persistent restart, unrelated working directory and clean BYE; maximum full response was 0.711339 seconds. These are local measurements, not CTI or official-server validation.

## Next work

The [active task list](TODO.md) prioritizes the dispersed-map regression, independent evaluation, resource interception, selective split coverage and external validation. The recorded 6-to-7 cycle now has a tested heuristic repair; unknown-horizon endgames are still not solved. The report, five-minute presentation and final submission package remain open.

Earlier milestones and their original validation commands are retained in the [archived status](docs/history/STATUS_2026-10-13.md) and [completed task history](docs/history/TASK_LOG_2026-10-13.md). Historical experiment results refer to their recorded source versions.
