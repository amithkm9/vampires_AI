# Player implementation and limits

Updated 2026-10-16. This describes actual code, not the full proposed tournament strategy. The implementation uses Python's standard library and our own algorithms. The published 105-test baseline remains available at revision `2a08829b1935a80c3c11a37ecea5efb089425268` for comparisons; revision `5b47469ac5fec4d2e2d49913a87765ab94604085` preserves the runtime used in the historical 108-match audit. Revision `04a1e85` is the league's frozen cohesive opponent.

## Current search selection

The provisional default is `strategic`, with maximum depth five, the new
`planning.evaluate_strategic` evaluator and the existing intact-group generator.
`adaptive` retains the previous baseline evaluator at depth five. Both use the
same reusable balanced search. `engines.default_depth` keeps settings consistent
between API and launcher; an explicit SearchConfig/CLI depth wins.
`cohesive_material` retains depth three by default.

The October 15 [strategy experiment](../experiments/2026-10-15-strategy/EXPERIMENT.md)
preserves 184 development games and 72 held-out games. Strategic scored 17W/8D/11L
against adaptive's 14W/8D/14L; all 8046 plies were replay-verified. Four cases
improved and one regressed. The paired map-cluster interval includes zero, so this
is a provisional local promotion. The suite now has 280 tests. Whole-group
coverage and interception-aware route planning remain limitations.

`balanced.choose_balanced(reuse_work=True)` reuses completed deterministic
candidate lists and pure leaf evaluations and orders moves from completed earlier
searches. Values remain specific to depth and remaining plies. Four caches share
an entry cap, **not a byte/cell cap**. Truncated candidate lists are not cached,
but completed node values can still represent a truncated retained tree, as in
the earlier search. These intervals never certify omitted legal actions.
Optional iteration records expose work, completion and cache hits per depth.

The October 16 audit explicitly closes suspended root continuations and breaks
recursive local-function reference cycles in search, simulation and exhaustive
generation. Per-call data no longer waits for cyclic garbage collection after a
completed, interrupted or failed call. This does not impose a byte limit on live
caches. `simulation._survival_branch` computes the same exact rational combat
distribution through integer binomial recurrence, retaining every tail outcome
and cooperative deadline checks. See the [runtime measurements](../reports/runtime-audit-2026-10-16/results.json)
and [current validation](../STATUS.md) for scope and limitations.

`experimental.hybrid.hybrid_turns` preserves at least three quarters of a saturated cohesive
candidate set (at least one whole move at tiny caps), reserving other slots for
partial captures, attacks, reinforcement and local separation. It uses radius-two
local features, one record per source and no shared contested targets. Refinement
has an additional work cap under the same deadline. Early sources can exhaust
that cap; final bounded pool sorting adds cooperative overhead. This is not full
split coverage. `hybrid` and `hybrid_adaptive` remain experiments after negative
development evidence.

The [league record](../experiments/2026-10-13-league/EXPERIMENT.md) reports 132 new
games and exact source snapshots. Three independent agents implemented/reviewed
search, movement and benchmark integrity; that milestone had **262 tests**.
The validation section below records the preceding milestone for comparison.

## Turn processing

`run.py` locates `src/` relative to itself, so the launcher works from another directory. `player.main` validates the ASCII name, port, budget, and depth before connecting. Its address and port are the final positional arguments. The live CLI requires depth at least two; depth one remains available through the search API for ablations/tests.

`player.play` sends NME once, then uses `GameSession.apply` for initialization and authoritative updates. Only UPD triggers a decision. Predictions never modify the server board. END resets board/species state while keeping the connection; BYE exits cleanly. Malformed messages, disconnects, impossible playable states, or expired network deadlines cause a logged nonzero exit rather than a fabricated empty MOV.

## Outcome and conversion-race evaluation, October 15

`planning.evaluate_outcome` retains the baseline while humans remain. In no-human
positions it values population standing strongly, with smaller consolidation,
distance and tactical terms. A trailing group can prefer a battle with a useful
chance of recovery over preserving a small material deficit indefinitely. A
leading group favors separation. These are bounded heuristic scores, not a known
daylight deadline or calibrated win probabilities. Exact known-cutoff terminal
scoring still takes precedence in controlled tests.

`planning.conversion_race` projects sequential affordable captures by individual
groups. Each event updates that group's position, travel time and population;
its conversions may unlock a larger house. Arrival plies account for initiative,
and each house is allocated only once. Different groups cannot spend each other's
conversions. The feature is capped at twelve houses/eight groups; larger positions
fall back to the baseline evaluator. Byte-overflow conversions receive no credit.
The projection is optimistic: routes ignore interception and incidental occupied
cells, and the events need not be a feasible joint plan. They are evaluation
features, never replacement moves that skip opponent turns.

`planning.evaluate_strategic` combines that projected population balance with a
small baseline score, using the outcome evaluator after humans are exhausted.
`outcome` and `strategic` retain the adaptive engine's intact-group search and
reusable work. `tactical` combines the strategic evaluator with the existing
hybrid partial-move generator. All three default to depth five and remain subject
to the same search/network deadlines, chance intervals and final move validation.
The [registered experiment](../experiments/2026-10-15-strategy/EXPERIMENT.md)
records the ablations and promotion decision. An exact split witness passes, but
the 64-game development round did not favor the tactical combination.

## Algorithms mapped to code

| Function | Implemented behavior | Limits |
| --- | --- | --- |
| `rules.validate_moves` | Validates all six move rules against the starting board, plus byte fields and the conservative group/record limit | Wider interpretation of splitting needs official clarification |
| `turns.fallback_turn` | Finds a nonempty legal one-record turn before search | Guarantees legality only; may be strategically bad; raises on 1x1/extinct states |
| `turns.exhaustive_turns` | Enumerates canonical legal small-board turns, including multiple outgoing records from one source | Explicit node cap; repeated identical directed edges are represented by summed counts |
| `turns.candidate_turns` | Gathers single moves before joint combinations; ranks and retains partial results under explicit work/time caps | Live set has one record per source; all amounts only for stacks up to eight; threshold amounts otherwise; default 64 final turns/12 per-source combination options; incomplete generation is reported |
| `simulation.battle_distribution` | Exact rational probabilities for deterministic and random combat | No sample approximation; not proof of official-server parity |
| `simulation.turn_outcomes` | Debits sources, merges friendly arrivals, and forms exact products of distinct battle outcomes | Assumes independent battles; rejects shared-target battles by default; explicit branch and population caps |
| `simulation.iter_turn_outcomes`, `sample_turn` | Lazy exact products and seeded integer battle samples using the same live transition restrictions | Per-cell outcomes sorted by probability, depth-first product traversal; not globally ordered joint probabilities; no official-server parity claim |
| `evaluation.evaluate` | Baseline bounded population difference, current-stack house races, exposure, and approach distance | A heuristic score, not win probability; route distances ignore threats and future capture sequences |
| `planning.evaluate_strategic`, `conversion_race`, `evaluate_outcome` | Default sequential exclusive capture projection and stronger no-human outcome scoring | Heuristics, not calibrated probabilities or interception-safe plans; no known live cutoff |
| `search.choose_turn`, `chance_bounds` | Iterative expectiminimax with probability-mass intervals and chance cutoffs; root maximizes lower bound, then upper bound | Bounds apply to retained finite-depth candidates and modeled transitions, not true game-winning probability |
| `balanced.choose_balanced` | Resumable root continuations, conservative partial intervals, root elimination and iterative deepening | Cooperative work quanta and selective candidates; no bandit confidence guarantee |
| `simulation.iter_turn_outcome_steps` | Shares target-distribution preparation across resumable callers | None checkpoints have no probability; ordinary streaming filters them |
| `strategy.cohesive_turns` | Intact-group candidate abstraction used by the provisional default | Omits partial movements for both players; splitting remains legal |
| `strategy.evaluate_resources`, `portfolio_turns` | Experimental resource projection and capture/attack/merge/escape proposals | Ignore route interception; not bundled into the promoted mode |
| `engines.choose_engine`, `default_depth`, `DEFAULT_ENGINE` | Shared engine selection; provisional default strategic at depth five | Adaptive remains available at depth five and cohesive_material at depth three; sequential baseline is selectable |
| `search.state_key` | Per-search cache keyed by dimensions, complete cell contents, side to move, and remaining depth | Stores only completed node evaluations; no cross-turn or sampled-value reuse |
| `search.choose_turn(..., remaining_plies=N)` | Scores population win/draw/loss when a known total-ply horizon reaches zero; remaining horizon is part of the cache key | None is unknown; search-depth leaves before cutoff remain heuristic; the live protocol supplies no countdown |
| `endgame.ExactSolver` | Offline canonical legal finite-horizon expectiminimax with rational W/D/L and an explicit combat model | Caps states, generation, and outcomes; raises on incomplete work; aggregate shared-target combat is an unverified assumption |
| `history.PositionHistory.observe` | Bounded immutable board/side snapshots, visit counts, update periods, and population standing | Diagnostics only; eviction forgets old positions; repetition is neither an automatic draw nor a penalty |
| `certificates.dominant_stack`, `preserving_turn` | Identifies and keeps whole a stack dominating all possible enemy growth | Conditional on written population/combat rules; skips moves that could overflow a byte |
| `experimental.growth.human_arrivals`, `evaluate_growth` | Experimental subset planning for growth chains and exclusive human-resource credit | Optimistic travel ignores interception; up to eight houses, four groups, and 4096 states; target routes need not coexist |
| `experimental.mcts.choose_mcts` | Experimental finite-depth adversarial UCT, sampling actual integer battle outcomes with an explicit seed | Basic challenger, no progressive widening or tactical rollout extensions; does not produce exact value bounds |
| `budget.Deadline.check` | Cooperative monotonic interruption inside generation, simulation, evaluation, and search | Python/OS scheduling and individual operations prevent a universal hard real-time guarantee |

For a stochastic action, search accumulates `sum(probability * child_bounds)` and adds the possible contribution of unvisited mass, between minus and plus that mass. Exact rational probabilities are converted to floating-point weighted values with a small outward rounding guard. Chance outcomes do not consume a player-move depth. Terminal extinction is scored +1/-1; simultaneous extinction is neutral 0 as an explicit unverified convention. Nonterminal heuristic scores are bounded inside [-0.95, 0.95].

The baseline evaluator assigns each house to at most one side using the earliest current stack large enough to convert it. A current player's distance `d` corresponds to global ply `2*d-1`; the other side uses `2*d`. This is a distance-based heuristic, not a validated capture plan. The experimental growth evaluator additionally recomputes routes after assigning contested houses to a single side. It remains outside the live default because the limited comparison did not establish a decisive advantage.

Before search, a stack with `N > enemy_total + humans` and `2*N >= 3*(enemy_total + humans)` can invoke the preservation policy. This keeps its strict population lead and deterministic combat advantage under the stated rules. It reports a nonterminal heuristic score of 0.95, not a solved terminal result.

## Deadline and partial work

The protocol records the first `U` byte of UPD, before completing its header or payload. The default search expiry is that time plus 1.25 seconds; the CLI allows at most 1.5 seconds. Header/payload reads and MOV transmission share the two-second absolute turn expiry. Socket timeouts are restored so opponent waiting is not confused with our turn deadline. This local timestamp cannot account for network delay before that byte arrives.

Search begins at two plies. A completed iteration survives interruption at greater depth. Sequential search retains finished root actions from its first iteration; balanced search also retains valid partial intervals, selecting by lower bound then upper bound. Unknown branches and chance mass stay within [-1,1]. Before useful search, both engines retain a generated turn or legal fallback. Partial chance prefixes are never renormalized. Balanced search yields at generation, target preparation and leaf updates; an individual cooperative operation can still consume the remaining budget.

In a controlled position with exactly one ply remaining, search completes that last move without inventing an opponent turn after the cutoff. Known-horizon comparisons bypass the dominance shortcut to score outcomes explicitly. They retain live candidate restrictions and chance bounds; they are not exhaustive game solutions.

`SearchConfig(protect_tactics=True)` experimentally reserves whole-group contested moves with nonzero success probability before filling the remaining candidate budget. Final move order still uses the ordinary priority. The switch reaches both bounded search and the UCT API, is disabled by default, and has no launcher option. Reserving attacks can displace useful merges: the development audit records two improvements and one regression at limit 8. Complete tactical coverage, wall-clock root allocation, and competitive benefit remain unestablished.

The live player records repetition only after authoritative UPD application, includes that overhead inside the turn budget, and resets history on END/BYE. Logs expose `visits`, `cycle_updates`, `standing`, `trailing_cycle`, and `horizon=unknown`. History retains at most 512 positions and 131072 cell records by default; it does not change search values or moves. Controlled finite-horizon reference policies preserve safe wins/draws. The strategic evaluator repairs the recorded no-human trailing cycle without consulting history; broader unknown-horizon endgame planning remains open.

Each generation call receives at most 3% of the original search budget (with a 0.2 ms minimum, clipped to the global expiry) and a work cap. It may return partial candidates; this bounds effort without proving tactical coverage.

Diagnostics distinguish `completed_depth` from `selected_depth`. Selected depth two with completed depth zero identifies an attempted two-ply iteration; some roots or outcomes may remain unfinished. A completed depth may still contain chance intervals or selective candidate sets. `selective_nodes`, `truncated_generations`, `unsupported_actions`, and `bounded_actions` distinguish those limitations. `value_lower`/`value_upper` expose the selected interval; `value` is absent when it is wide. `preserved_dominance` identifies the conditional preservation policy. Balanced decisions additionally report root_started, root_finished, root_updates and root_pruned across iterations. A timeout is a search-budget event; the player can still send its retained move before the turn deadline.

## Explicit model restrictions

- Shared empty/friendly arrivals merge in the local model. Shared contested targets require `shared_target="aggregate"` to opt into an offline assumption. The live generator excludes those actions until the server is checked.
- Search processes up to 512 outcomes per action, retaining the remaining mass as an interval; actions with encountered ambiguity/overflow remain [-1,1]. The eager reference simulator retains its independent 4096-outcome cap. Candidate pruning can still omit important opponent replies; chance bounds do not fix that separate issue.
- Any possible population beyond 255 raises `UnsupportedPopulation`. This is a byte-model limitation, not an invented legality rule. The supplied maps' total populations are below 255.
- Live candidates are selective on multi-group or larger-stack positions. There is no proof that discarded moves are dominated. The exhaustive small-board oracle provides a reference for future pruning measurements.
- Crowded-board generation now returns partial work; time/beam limits can still prevent useful coverage and completed search depth.
- There is no server-supplied daylight countdown in the current state, no measured official tournament strength, and no universal winning guarantee. UCT and multi-house planning are experimental; sparse-sampled expectiminimax is not implemented.

## Historical validation before the league milestone

The preceding **219 tests** included independent rational search/combat references, bounded exhaustive joint transitions, interrupted deadlines, caches/horizons, byte boundaries, maximum packets, history limits and engine lifecycles. See the [parallel edge audit](EDGE_CASE_AUDIT.md) and [upgrade experiment](../experiments/2026-10-12-upgrade/EXPERIMENT.md).

The final [TCP check](../reports/player-upgrade-smoke-2026-10-12.json) passed four matches / 31 AI turns, maximum 0.028358 seconds. A separate 24-case maximum-area probe reached 1.292704 seconds on 255×255 boards. These are local measurements, not worst-case/CTI guarantees. Eight locked games scored 4W/3D/1L against the frozen pre-upgrade engine; all comparisons share our simulator. The next external gate is the supplied server and exact CTI launch environment.
