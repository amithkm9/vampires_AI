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
