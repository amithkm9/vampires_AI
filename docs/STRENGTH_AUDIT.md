# Is the player strong enough to win?

Audit date: 2026-10-11. The published baseline is a working opponent-aware player. Its previous 105 tests and local smoke matches establish useful correctness/integration evidence, not superiority over strong competitors. There is no basis for a guaranteed-win or globally best-algorithm claim.

## What can and cannot be guaranteed

Even an exhaustive optimal algorithm cannot force a win in every legal position. On a 1x2 board with one creature per species, movement is mandatory and the only move attacks. The written random-battle rule gives a 1/4 probability that the opponent survives alone. `test_forced_battle_proves_universal_win_guarantee_impossible` verifies this counterexample.

The useful target is a high match score against strong opponents under the actual time and deployment constraints. A search algorithm's name does not establish that. Evaluation quality, legal tactical coverage, transition accuracy, and how unfinished work is handled can decide the result.

## Audit findings and implemented changes

| Finding in the published baseline | Consequence | Current change |
| --- | --- | --- |
| Generation could use the whole deadline before returning anything | Crowded boards fell back to the first legal move | Gather singles across sources first, cap joint expansion work, preserve partial candidates, and limit each generation call to a fraction of the turn budget |
| A large Cartesian product raised `OutcomeLimit` and the search skipped the action | A dangerous opponent reply could disappear and make an unsafe move look attractive | Stream exact outcomes and retain unvisited probability as a value interval; unsupported model actions also remain unknown instead of disappearing |
| An already dominant stack could be split | The player could throw away a position that is safe under all future enemy growth | Recognize `N > enemy_total + humans` and `2*N >= 3*(enemy_total + humans)`, then move that stack whole without uncertain combat |
| Evaluation used only currently affordable individual houses | It missed growth chains and resource denial | Add an experimental subset-based multi-house reachability evaluator, including exclusive allocation/rechecking of human resources |
| No alternative search engine had been measured | The architecture was an untested preference | Add a seeded adversarial UCT challenger and compare all variants with the immutable published baseline |

The default engine remains bounded expectiminimax. The growth evaluator and UCT are experimental API/benchmark variants, not silently enabled in the launcher.

## How chance bounds work

For processed outcomes, let `L = sum(p_i * child_lower_i)` and `U = sum(p_i * child_upper_i)`. If their probability mass is `m`, unvisited outcomes still contribute between `-(1-m)` and `+(1-m)`. Therefore the action lies in `[L-(1-m), U+(1-m)]`, with a small outward floating-point guard. Probabilities themselves remain exact fractions.

Our decision nodes take the componentwise maximum of child bounds; opponent nodes take the componentwise minimum. A candidate can be cut off once its upper bound is below a known better lower bound (or the corresponding minimum-node condition). The root selects the greatest lower bound, breaking ties by upper bound. No prefix is renormalized into a falsely complete distribution.

These are bounds on the **retained finite-depth candidate tree and its heuristic evaluator**, not on all legal actions or true full-game win probability. Candidate pruning remains a limitation. A wide interval can also make the conservative policy avoid a useful gamble; the sampling comparison helps expose that tradeoff.

This follows the probability-mass bound described in section 2.1 of [Lanctot et al., Monte Carlo *-Minimax Search (IJCAI 2013)](https://www.ijcai.org/papers13/Papers/IJCAI13-093.pdf). That paper compares stochastic search methods across several games; it does not establish which engine wins this assignment. Our UCT challenger is a basic finite-depth implementation, not a reproduction of their enhanced MCTS/DPW system.

## Multi-house planning is still an approximation

`growth.human_arrivals` tracks captured-house subsets, last location, population gained, and minimum travel time. It cannot use a house twice, and cannot convert an unaffordable house. The experimental evaluator assigns each house to one side and recomputes reachability without houses assigned to the opponent. It detects that losing a four-human house prevents a starting stack of ten from reaching the central twenty-human conversion threshold using the remaining small houses.

It still ignores enemy interception and occupied intermediate squares, and target-wise shortest routes need not form one joint itinerary. Computation also competes with tactical search time. A more detailed heuristic is only useful if its decision improvement outweighs that cost.

## Evidence and selection

The [experiment record](../experiments/2026-10-11-strength/EXPERIMENT.md) specifies the pinned baseline, map provenance, variants, budgets, seeds, pairing, raw records, and limitations before comparison. Tests independently compare streaming and eager transitions, full tiny expectiminimax trees and interval results, sampled support, partial generation, growth thresholds, and dominant-stack preservation.

Read the experiment results before making a strength claim. The generated evaluation maps are separate from the supplied development maps, but the set is small. Budget sensitivity repeats those cases; it is not a second independent held-out sample. The local simulator is shared with the agent and has not been matched to the supplied server.

All variants played the same immutable historical engine. Score means win=1, draw=0.5, loss=0; it is not win probability. These are 108 matches in total:

| Budget / ply cap | Variant | Wins / draws / losses | Score |
| --- | --- | --- | --- |
| 0.03 s / 60 | Bounded | 6 / 8 / 2 | 62.5% |
| 0.03 s / 60 | Growth | 2 / 12 / 2 | 50.0% |
| 0.03 s / 60 | UCT | 1 / 2 / 13 | 12.5% |
| 0.10 s / 60 | Bounded | 2 / 12 / 2 | 50.0% |
| 0.10 s / 60 | Growth | 4 / 10 / 2 | 56.25% |
| 0.10 s / 60 | UCT | 0 / 2 / 14 | 6.25% |
| 0.10 s / 200 | Bounded | 1 / 2 / 1 | 50.0% |
| 0.10 s / 200 | Growth | 1 / 2 / 1 | 50.0% |
| 0.10 s / 200 | UCT | 1 / 0 / 3 | 25.0% |

The short-budget bounded gain did not persist at the larger budget. Growth's small short-horizon advantage is not enough evidence to promote it, and it also consumes tactical search time. The basic UCT challenger performed poorly; this does not reject stronger MCTS designs. No failures were recorded in 6778 combined candidate/baseline turns. A short stress probe overlapped pilot 01; the later budget/horizon runs had no concurrent CPU tests. The 200-ply run used only supplied maps and one new seed, so its coverage is especially limited.

Keep bounded expectiminimax for its explicit uncertainty handling and generation fixes, while treating its competitive superiority as unproven. The 122 tests and four new normal-budget TCP smoke matches support correctness/integration, not a tournament-strength claim. Normal-budget head-to-head comparison and official-server/CTI checks remain necessary.

A subsequent [replay audit](../reports/replay-analysis-2026-10-11.md) reconstructed all 108 games. The default engine's three trap losses at 0.1 seconds involved no monster or random combat: vampires collected four humans, werewolves collected five, and the result was 8–9 at the local cap. The 200-ply loss contained 160 repeated-state visits. This makes final-outcome handling, capture denial, and unfinished root comparison concrete improvement targets. It does not prove that an alternative policy forces a win. Follow [the next-algorithm plan](NEXT_ALGORITHM.md) for implementation order and acceptance checks.

## Remaining work before calling it tournament ready

1. Verify the server's shared-target attacks, wider splits, overflow, both-extinct outcomes, and exact CTI launch environment.
2. Audit candidate coverage on small exhaustive positions and difficult multi-group tactical suites. Shared-target enemy threats cannot be ignored merely because the live player avoids those moves itself.
3. Improve uncertain root decisions with measured refinement or sampling, and consider tactical extensions at unstable depth boundaries.
4. Add contested route/interception planning and test growth features through ablations under the real time budget.
5. Expand opponents, held-out map families, seeds, species swaps, and starting-order swaps. Measure invalid moves, timing failures, worst-case responses, and match scores separately.
6. Compare stronger sampled/MCTS variants using the same move/evaluation components before rejecting an algorithm family from one basic pilot.

Hand-written expectiminimax with bounds and game-specific planning is a defensible current design. Search optimization, stochastic sampling, MCTS, endgame reasoning, and better route models are complementary possibilities to test; none substitutes for official-server validation and competitive evidence.
