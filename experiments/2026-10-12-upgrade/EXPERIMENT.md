# Balanced search and resource control experiment

Registered before match results, 2026-10-12. Local development, not a reproduction of another game's published performance.

Question: can resumable root allocation and stronger resource valuation improve on the just-pushed engine within equal computation budgets? Does a diverse legal policy portfolio add value beyond those two features?

Frozen opponent: `d28c5179a721bb7812c14d277a5cc327c641d47c`. Export its source from Git to a temporary import package without modifying it. No third-party libraries. Live-model combat uses independent integer sampling; shared contested targets remain excluded and their server semantics remain unresolved. Vampires start; each candidate plays both species per map. No live countdown is inferred or passed into the search; the local ply cap is a documented outcome proxy.

Development variants, separately switchable:

- `balanced`: round-robin resumable expectiminimax; baseline evaluation and candidates.
- `resources`: baseline sequential search with exclusive currently-affordable human projections and nonlinear advantage evaluation.
- `balanced_resources`: both features.
- `portfolio`: both features plus legal collect/attack/merge/escape proposals alongside baseline candidates.

Use the same depth 3, candidate cap 64, chance cap 512 and dominance policy for every variant and frozen opponent. First compare at 0.05 seconds, 60 total plies, supplied maps plus symmetric generated maps with development seeds 271 and 383. Combat seed 20261013. These are ablations, not independent evaluation. Do not tune constants against the later holdout results.

Lock the best development candidate, then evaluate at the normal 1.25 seconds, 100 total plies, supplied maps and unseen generated seeds 411 and 587, combat seed 20261017, both species. Separately report supplied-map and unseen-map results. The map generator family is shared with development, so this is not evidence across all map families. Save every match, moves, search diagnostics, board inputs, configurations, source hashes, interpreter/platform, seeds and timing. Runs are serial; no competing CPU-heavy validation during timing runs.

Promotion rule: no default promotion from a small pilot alone. Require positive held-out paired score over 0.5, no legality or two-second failures, and correct independent tiny-tree checks. Even a positive eight-game result has substantial uncertainty: report the per-map pairs and conditional bootstrap interval; distinguish an experimental selectable engine from an established tournament improvement. If held-out evidence is inconclusive, retain the baseline default and expose the tested alternatives explicitly.

Additional acceptance: resumable complete values agree with sequential expectiminimax on tiny two-sided trees; chance truncation preserves unknown probability mass; forced interruption starts multiple roots; deeper interruption preserves a completed shallower result; resource projection is antisymmetric, credits each house once and respects current affordability/overflow. TCP launcher still uses IP and port last and must be checked locally. Official server/CTI remain a separate gate.

## Results and commands

The initial test invocation omitted PYTHONPATH and failed to import the local package; the correct command is `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

Development 01: `python3 tools/benchmark_upgrade.py --output experiments/2026-10-12-upgrade/development-01` completed 32 matches. Balanced: 0 wins/3 draws/5 losses; resources: 2/3/3; balanced_resources: 1/2/5; portfolio: 3/2/3. No two-second or legality failures. Portfolio wins both trap-map games 9–8, but does not beat the baseline overall. Balanced scheduling alone performs poorly under this tight budget. Retain all failures as strength evidence; no promotion.

Before viewing holdout results, add a second development ablation: `cohesive` and `cohesive_material` use only intact-group moves for both players, with resource and baseline evaluation respectively. Same budget, depth, maps, seeds and opponent as Development 01. This substantially reduces branching, but explicitly omits potentially valuable own/opponent splits. It is an action abstraction, not a proof that splitting is bad. No held-out seed has been evaluated yet. Save Development 02 separately.

Development 02: `python3 tools/benchmark_upgrade.py --engines cohesive cohesive_material --output experiments/2026-10-12-upgrade/development-02`. Cohesive: 1 win/6 draws/1 loss. Cohesive_material: 3 wins/5 draws/0 losses, score 0.6875; pair scores [1, 0.5, 0.5, 0.75], conditional pair bootstrap [0.5, 0.875]. No legality or timing failures. Zero observed losses in eight development games is not a guarantee.

**Candidate locked before holdout:** `cohesive_material`, unchanged depth 3/cap 64/evaluator constants. Parallel edge audits subsequently repaired fragmented-header timing, chance-cap overfetch, resumable battle preparation, destination-capacity amount coverage, bounded history, and generation deadline overhead. These are correctness/robustness changes recorded in the candidate source hashes; no held-out outcomes were inspected to tune them. Holdout command: `python3 tools/benchmark_upgrade.py --engines cohesive_material --budget 1.25 --max-plies 100 --map-seeds 411 587 --combat-seeds 20261017 --output experiments/2026-10-12-upgrade/holdout-01`. Full receive/send timing remains a separate TCP check.

## Locked normal-budget evaluation

Completed all eight games: **4 wins, 3 draws, 1 loss**, paired score **0.6875**, no failures. Per-map pair scores: thetrap 0.75, testmap2 0.75, generated_411 0.75, generated_587 0.5. Supplied maps: 2W/2D/0L; unseen generated maps: 2W/1D/1L. The conditional four-cluster bootstrap interval is [0.5625, 0.75]; with only four related map clusters and one combat seed this should not be read as broad statistical certainty. A trap draw is simultaneous extinction under our unverified neutral convention.

Maximum candidate response was **0.153828 seconds**, below its 1.25-second allowance; every candidate turn completed a depth. The intact-group tree can finish all configured work early. Both engines receive the same time limit; this is not equal CPU consumption. Search depth remains 3, not silently increased after seeing results.

Decision: provisionally promote `cohesive_material` as the launcher default because it meets the registered positive-score, correctness and timing criteria. Keep `--engine baseline` available. This is local model evidence against one frozen opponent, not proof against all strategies. In particular, the abstraction omits opponent splits; broaden the opponent league and map families before tournament selection. Resource projection and policy portfolios remain explicit alternatives rather than being bundled into the promoted mode.

The benchmarked runtime is recorded by commit/source hashes (pre-promotion default selector). Promotion only changes the default selection to the exact explicitly benchmarked mode. TCP and stress checks below verify the final launcher. No official-server or CTI validation is claimed.

## Final validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -q`: 219 passed in 1.919 seconds after promotion. Coverage is detailed in `docs/EDGE_CASE_AUDIT.md`.
- `python3 tools/check_player.py --engine cohesive_material --budget 1.25 --depth 3 --max-plies 20 --output reports/player-upgrade-smoke-2026-10-12.json`: four matches / 31 AI turns; both maps/species, unrelated working directory, restart, legal packets, clean BYE; maximum 0.028358 seconds. Initial sandbox loopback bind failed; authorized execution succeeded.
- Ran `python3 tools/check_search.py --engine ENGINE --output reports/search-upgrade-ENGINE-2026-10-12.json` serially for all seven modes: 56 cases, all legal and under two seconds. Includes crowded boards, 255-vs-255 random combat, a 255-row column and unsupported conversion overflow. Unsupported states remain explicitly unknown.
- `python3 tools/check_limits.py --output reports/maximum-board-upgrade-2026-10-12.json`: 24 probes, two fully occupied 255×255 boards, both species, baseline/promoted engine, budgets 0/0.05/1.25. Every result legal; maximum 1.292704 seconds. Exact deterministic generator and source hashes reproduce the full inputs.
- All 13 original/extracted material hashes match; runtime imports are standard-library or project-relative.

There are 48 new development games and 8 locked evaluation games. The 108 earlier games and all prior raw records remain unchanged. Historical records identify their own runtime hashes, which may differ from the final launcher after fixes/default selection changes.
