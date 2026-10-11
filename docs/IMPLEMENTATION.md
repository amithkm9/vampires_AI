# Player implementation and limits

Updated 2026-10-11. This describes actual code, not the full proposed tournament strategy. The implementation uses Python's standard library and our own algorithms. The published 105-test baseline remains available at revision `2a08829b1935a80c3c11a37ecea5efb089425268` for comparisons.

## Turn processing

`run.py` locates `src/` relative to itself, so the launcher works from another directory. `player.main` validates the ASCII name, port, budget, and depth before connecting. Its address and port are the final positional arguments. The live CLI requires depth at least two; depth one remains available through the search API for ablations/tests.

`player.play` sends NME once, then uses `GameSession.apply` for initialization and authoritative updates. Only UPD triggers a decision. Predictions never modify the server board. END resets board/species state while keeping the connection; BYE exits cleanly. Malformed messages, disconnects, impossible playable states, or expired network deadlines cause a logged nonzero exit rather than a fabricated empty MOV.

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
| `evaluation.evaluate` | Bounded population difference, current-stack house races, exposure, and approach distance | A heuristic score, not win probability; route distances ignore obstacles/threats and future capture sequences |
| `search.choose_turn`, `chance_bounds` | Iterative expectiminimax with probability-mass intervals and chance cutoffs; root maximizes lower bound, then upper bound | Bounds apply to retained finite-depth candidates and modeled transitions, not true game-winning probability |
| `search.state_key` | Per-search cache keyed by dimensions, complete cell contents, side to move, and remaining depth | Stores only completed node evaluations; no cross-turn or sampled-value reuse |
| `certificates.dominant_stack`, `preserving_turn` | Identifies and keeps whole a stack dominating all possible enemy growth | Conditional on written population/combat rules; skips moves that could overflow a byte |
| `growth.human_arrivals`, `evaluate_growth` | Experimental subset planning for growth chains and exclusive human-resource credit | Optimistic travel ignores interception; up to eight houses, four groups, and 4096 states; target routes need not coexist |
| `mcts.choose_mcts` | Experimental finite-depth adversarial UCT, sampling actual integer battle outcomes with an explicit seed | Basic challenger, no progressive widening or tactical rollout extensions; does not produce exact value bounds |
| `budget.Deadline.check` | Cooperative monotonic interruption inside generation, simulation, evaluation, and search | Python/OS scheduling and individual operations prevent a universal hard real-time guarantee |

For a stochastic action, search accumulates `sum(probability * child_bounds)` and adds the possible contribution of unvisited mass, between minus and plus that mass. Exact rational probabilities are converted to floating-point weighted values with a small outward rounding guard. Chance outcomes do not consume a player-move depth. Terminal extinction is scored +1/-1; simultaneous extinction is neutral 0 as an explicit unverified convention. Nonterminal heuristic scores are bounded inside [-0.95, 0.95].

The default evaluator assigns each house to at most one side using the earliest current stack large enough to convert it. A current player's distance `d` corresponds to global ply `2*d-1`; the other side uses `2*d`. This is a distance-based heuristic, not a validated capture plan. The experimental growth evaluator additionally recomputes routes after assigning contested houses to a single side. It remains outside the live default because the limited comparison did not establish a decisive advantage.

Before search, a stack with `N > enemy_total + humans` and `2*N >= 3*(enemy_total + humans)` can invoke the preservation policy. This keeps its strict population lead and deterministic combat advantage under the stated rules. It reports a nonterminal heuristic score of 0.95, not a solved terminal result.

## Deadline and partial work

The protocol records the time when the UPD header is recognized, before reading its payload. The default search expiry is that time plus 1.25 seconds; the CLI allows at most 1.5 seconds. Payload reads and MOV transmission share the two-second absolute turn expiry. Socket timeouts are restored so opponent waiting is not confused with our turn deadline.

Search begins at two plies. Once a complete root iteration exists, an interrupted deeper iteration cannot replace it. Before the first iteration completes, the engine may retain the best fully evaluated root action from that first iteration. If none completes, it uses the best ranked generated turn, or the legal fallback if generation returned nothing. A partially enumerated chance distribution retains an explicit interval and is never renormalized into a complete point estimate.

Each generation call receives at most 3% of the original search budget (with a 0.2 ms minimum, clipped to the global expiry) and a work cap. It may return partial candidates; this bounds effort without proving tactical coverage.

Diagnostics distinguish `completed_depth` from `selected_depth`. A selected depth of two with completed depth zero means some root actions were evaluated to two plies, not that all candidates were covered. A completed depth may still contain chance intervals or selective candidate sets. `selective_nodes`, `truncated_generations`, `unsupported_actions`, and `bounded_actions` distinguish those limitations. `value_lower`/`value_upper` expose the selected interval; `value` is absent when it is wide. `preserved_dominance` identifies the conditional preservation policy. A timeout is a search-budget event; the player can still send its retained move before the turn deadline.

## Explicit model restrictions

- Shared empty/friendly arrivals merge in the local model. Shared contested targets require `shared_target="aggregate"` to opt into an offline assumption. The live generator excludes those actions until the server is checked.
- Search processes up to 512 outcomes per action, retaining the remaining mass as an interval; actions with encountered ambiguity/overflow remain [-1,1]. The eager reference simulator retains its independent 4096-outcome cap. Candidate pruning can still omit important opponent replies; chance bounds do not fix that separate issue.
- Any possible population beyond 255 raises `UnsupportedPopulation`. This is a byte-model limitation, not an invented legality rule. The supplied maps' total populations are below 255.
- Live candidates are selective on multi-group or larger-stack positions. There is no proof that discarded moves are dominated. The exhaustive small-board oracle provides a reference for future pruning measurements.
- Crowded-board generation now returns partial work; time/beam limits can still prevent useful coverage and completed search depth.
- There is no server-supplied daylight countdown in the current state, no measured official tournament strength, and no universal winning guarantee. UCT and multi-house planning are experimental; sparse-sampled expectiminimax is not implemented.

## Validation and next gate

The current 122 tests add streaming/reference agreement, sample support, interval comparisons against independently enumerated tiny trees, partial generation, dominance preservation, growth bottlenecks, and seeded UCT decisions to the earlier rule/protocol tests. See [the strength audit](STRENGTH_AUDIT.md), [experimental results](../experiments/2026-10-11-strength/EXPERIMENT.md), and the historical [baseline verification](../reports/baseline-verification-2026-10-09.md).

The new normal-budget [TCP check](../reports/player-strength-smoke-2026-10-11.json) passed four matches and 30 AI turns, observing a maximum response of 1.250434 seconds on this Mac. The harness uses our simulator and a seeded random opponent; it checks executable integration, not model independence or competitive strength. The 108 comparative matches also share that model and use smaller budgets. The next external acceptance gate is the supplied server and exact CTI launch environment. Keep [TODO.md](../TODO.md) and [RULES.md](RULES.md) current as evidence arrives.
