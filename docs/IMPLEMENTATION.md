# Playable baseline: implementation and limits

Updated 2026-10-09. This describes actual code, not the full proposed tournament strategy. The implementation uses Python's standard library and our own algorithms.

## Turn processing

`run.py` locates `src/` relative to itself, so the launcher works from another directory. `player.main` validates the ASCII name, port, budget, and depth before connecting. Its address and port are the final positional arguments. The live CLI requires depth at least two; depth one remains available through the search API for ablations/tests.

`player.play` sends NME once, then uses `GameSession.apply` for initialization and authoritative updates. Only UPD triggers a decision. Predictions never modify the server board. END resets board/species state while keeping the connection; BYE exits cleanly. Malformed messages, disconnects, impossible playable states, or expired network deadlines cause a logged nonzero exit rather than a fabricated empty MOV.

## Algorithms mapped to code

| Function | Implemented behavior | Limits |
| --- | --- | --- |
| `rules.validate_moves` | Validates all six move rules against the starting board, plus byte fields and the conservative group/record limit | Wider interpretation of splitting needs official clarification |
| `turns.fallback_turn` | Finds a nonempty legal one-record turn before search | Guarantees legality only; may be strategically bad; raises on 1x1/extinct states |
| `turns.exhaustive_turns` | Enumerates canonical legal small-board turns, including multiple outgoing records from one source | Explicit node cap; repeated identical directed edges are represented by summed counts |
| `turns.candidate_turns` | Ranks amounts/directions and combines per-source options in a bounded beam | Live set has one record per source; all amounts only for stacks up to eight; threshold amounts otherwise; default 64 final turns/12 per-source combination options |
| `simulation.battle_distribution` | Exact rational probabilities for deterministic and random combat | No sample approximation; not proof of official-server parity |
| `simulation.turn_outcomes` | Debits sources, merges friendly arrivals, and forms exact products of distinct battle outcomes | Assumes independent battles; rejects shared-target battles by default; explicit branch and population caps |
| `evaluation.evaluate` | Bounded population difference, current-stack house races, exposure, and approach distance | A heuristic score, not win probability; route distances ignore obstacles/threats and future capture sequences |
| `search.choose_turn` | Iterative expectiminimax, maximizing our turns, minimizing opponent turns, taking expectation over chance | Values apply to retained candidates and modeled transitions, not the full game |
| `search.state_key` | Per-search cache keyed by dimensions, complete cell contents, side to move, and remaining depth | Stores only completed node evaluations; no cross-turn or sampled-value reuse |
| `budget.Deadline.check` | Cooperative monotonic interruption inside generation, simulation, evaluation, and search | Python/OS scheduling and individual operations prevent a universal hard real-time guarantee |

For a stochastic action, search evaluates `sum(probability * child_value)`. Chance outcomes do not consume a player-move depth. Terminal extinction is scored +1/-1; simultaneous extinction is neutral 0 as an explicit unverified convention. Nonterminal scores are bounded inside [-0.95, 0.95].

The evaluator assigns each house to at most one side using the earliest current stack large enough to convert it. A current player's distance `d` corresponds to global ply `2*d-1`; the other side uses `2*d`. This is a distance-based heuristic, not a validated capture plan. House growth chains, strategic denial, and the dominant-stack certificate remain next-build tasks.

## Deadline and partial work

The protocol records the time when the UPD header is recognized, before reading its payload. The default search expiry is that time plus 1.25 seconds; the CLI allows at most 1.5 seconds. Payload reads and MOV transmission share the two-second absolute turn expiry. Socket timeouts are restored so opponent waiting is not confused with our turn deadline.

Search begins at two plies. Once a complete root iteration exists, an interrupted deeper iteration cannot replace it. Before the first iteration completes, the engine may retain the best fully evaluated root action from that first iteration. If none completes, it uses the legal fallback. A partially enumerated chance distribution never becomes a completed score.

Diagnostics distinguish `completed_depth` from `selected_depth`. A selected depth of two with completed depth zero means some root actions were evaluated to two plies, not that all candidates were covered. `selective_nodes` records candidate-restricted nodes; `unsupported_actions` records branch-limit/overflow/ambiguity skips. A timeout is a search-budget event; the player can still send its retained move before the turn deadline.

## Explicit model restrictions

- Shared empty/friendly arrivals merge in the local model. Shared contested targets require `shared_target="aggregate"` to opt into an offline assumption. The live generator excludes those actions until the server is checked.
- Exact joint distributions exceeding 512 outcomes in search are skipped and counted. The reference simulator defaults to a 4096-outcome cap. No probability tails are dropped or renormalized. Missing opponent actions can make scores optimistic; bounded handling is a priority improvement.
- Any possible population beyond 255 raises `UnsupportedPopulation`. This is a byte-model limitation, not an invented legality rule. The supplied maps' total populations are below 255.
- Live candidates are selective on multi-group or larger-stack positions. There is no proof that discarded moves are dominated. The exhaustive small-board oracle provides a reference for future pruning measurements.
- Crowded-board generation can consume its whole budget before returning candidates; in that case the search returns its legal fallback. The stress record demonstrates this under a 0.05-second budget. Retaining useful partial generation is the next performance task.
- There is no server-supplied daylight countdown in the current state, no measured tournament strength, no MCTS/sampled engine, and no universal winning guarantee.

## Validation and next gate

See [baseline verification](../reports/baseline-verification-2026-10-09.md). Tests cover all six rules, exact chance products, independent small-board move enumeration, source isolation, thresholds, byte boundaries, deadline interruption, both species, restarts, malformed packets, and launch from another directory.

The local harness uses our simulator and a seeded random opponent. It checks executable integration, not model independence or playing strength. The next external acceptance gate is the supplied server and exact CTI launch environment. Keep [TODO.md](../TODO.md) and [RULES.md](RULES.md) current as evidence arrives.
