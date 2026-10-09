# Tournament strategy and algorithm design

Design date: 2026-10-09. The proposed main engine is **iterative-deepening expectiminimax with a model of human-capture races, explicit tactical replies, and exact or bounded chance outcomes**. Implement it ourselves. Compare a sampled variant and MCTS experimentally before selecting the final engine. This is a design supported by rule analysis and local calculations, not a proven tournament winner.

## What winning optimally means

The target is the highest achievable match score against strong play, while retaining the ability to exploit weaker opponents. Maximizing expected population alone is insufficient: it can prefer a large but unlikely army over a position that wins reliably. Use actual terminal results when known; treat nonterminal evaluation as a heuristic, not a calibrated win probability.

An algorithm cannot guarantee victory from every position allowed by the written rules. On a 1 by 2 board with one creature of each species and no humans, the player to move has exactly one legal move: attack. The opponent survives alone with probability 1/4. This counterexample is tested in `test_forced_battle_proves_universal_win_guarantee_impossible`; it is not a claim that this map will appear in the tournament. Whether either supplied opening has a forced winning policy remains unsolved.

## Findings that change the design

See [the map analysis](../reports/map-analysis-2026-10-09.md) and [reproducible output](../reports/map-analysis-2026-10-09.json).

1. **Capture thresholds create discontinuities.** Against 20 humans, 19 attackers have 8.799375 expected survivors; 20 attackers become 40 with certainty. Smooth population/distance scoring alone misses this difference.
2. **Human denial can be worth more than immediate growth.** On `testmap2`, capturing either four-human house prevents the opponent from reaching 20 through the other small houses while the central house is untouched. Both sides starting with 10 cannot each gain 10 from only 12 peripheral humans.
3. **The same capture distance can hide different tactical risks.** On `thetrap`, a first mover can approach the four-human house through a square the opponent cannot attack immediately, or through an equally fast square that exposes the entire army to a 4-versus-4 battle.
4. **Initiative changes combat odds.** With groups of 10 and 8, the stronger group's battle-winning draw has probability .75 when it attacks, but .60 when it defends against the weaker group's attack. These are winner-selection probabilities, before survival losses. The side to move belongs in every search state and evaluation.
5. **Splitting trades travel time against local strength.** More groups can collect humans in parallel, but total population does not protect a small isolated group. Evaluate the resulting groups and opponent replies, not just their summed population.
6. **One partial move already creates two groups.** Moving a subset to one destination and leaving the rest is clearly permitted and uses one record. The unresolved restriction concerns multiple outgoing records, not all splitting.

## Architecture

```text
UPD and authoritative board
        |
        v
legal fallback and immediate threat scan
        |
        v
capture routes, resource thresholds, and opponent arrival estimates
        |
        v
ranked legal candidate turns
        |
        v
our move -> chance outcomes -> opponent replies -> chance outcomes -> ...
        |
        v
last completed search result -> independent move validation -> MOV
```

The strategic analysis helps rank moves and evaluate distant consequences. The tactical search checks the intervening actions. A route estimate must never skip the opponent's turns or assume that a contested house remains available.

## Search objective and chance handling

For each legal action, compute the probability-weighted value of its possible successor states. Maximize this value on our turn and minimize it on the opponent's turn. A random outcome is selected by its rule probability, not by the adversary. Depth counts player turns; enumerating a chance outcome does not consume an extra ply.

For one random battle with attacker win probability `p`:

- Against monsters, attacking survivors given a win follow `Binomial(A,p)`; defending survivors given a loss follow `Binomial(D,1-p)`.
- Against humans, attacking survivors given a win follow `Binomial(A+D,p)`; surviving human defenders given a loss follow `Binomial(D,1-p)`.
- Weight those conditional distributions by `p` and `1-p`. Coalesce duplicate empty-cell outcomes.

This aggregates individual survival combinations into at most `A+D+1` distinct monster-battle outcomes, or `A+2D+1` human-battle outcomes. The 14-versus-20-human battle has only 55 distinct successor cells. `simulation.battle_distribution` now supplies an exact rational reference implementation.

For the live engine, benchmark a floating-point implementation against this reference. Use exact enumeration near tactical decisions when affordable. If several battles make enumeration too expensive, compare sparse sampling with a bounded probability-mass approach. Never silently round an expected population into a successor board.

With all value estimates bounded in `[-1,1]`, a chance node with evaluated weighted sum `S` and unexpanded probability mass `r` lies in `[S-r,S+r]`. Refine that interval until it establishes a safe cutoff or changes which action is best. These are bounds on the chosen finite-depth evaluation model; they are not proof of full-game optimality. Dropping a tail and renormalizing it does not preserve this guarantee. Samples and pruned action sets must be labeled approximate.

## Candidate turns and splitting

Begin with all one-record moves, including partial amounts. At contact, preserve critical attacks, escapes, interceptions, and reinforcements in the candidate set. For larger multi-group positions, build legal joint turns from combinations of per-group choices and validate the whole ply. A group may stay if another group moves; an all-stay turn is illegal.

To control branching, prioritize meaningful population amounts: the whole group, one creature, a house's conversion threshold, an enemy's guaranteed-kill threshold `ceil(3*E/2)`, and the minimum count that avoids guaranteed defeat `floor(2*E/3)+1`. Include complements that leave useful populations behind and requirements of later capture sequences. These are candidate heuristics; they do not prove all other split amounts are dominated. Compare against exhaustive small-position enumeration.

Before accepting a split, inspect both resulting groups: what can each capture, which enemy can reach it first, when can it rejoin, and what happens while it travels? A small moving group can also let a larger group hold position while satisfying the mandatory-move rule. Count its vulnerability and cost; do not treat this as a free pass.

Joint generation must enforce the source/destination exclusion across the complete turn. Never create swaps, chains, or apparent multi-square movement by record ordering. Until server behavior is confirmed, keep wide splitting and same-target contested arrivals out of claims of exact simulation. Consider aggregate enemy reinforcements as a threat even when each enemy group alone looks harmless.

## Evaluate future growth and local safety

Use the following feature families, then select weights with held-out experiments:

| Feature | Reason |
| --- | --- |
| Current population difference | Direct relevance at game end |
| Feasible human-capture sequences | A nearby house is worthless as a safe target if we cannot convert it |
| Opponent arrival and denial | A house can enable a later conversion or prevent the opponent from reaching it |
| Local attack/defense thresholds | A small count change can turn a risky encounter into certain elimination |
| Escape squares and intercept routes | Equal movement speed makes naive pursuit and approach directions unreliable |
| Group exposure and reunion time | Splitting has tactical and travel costs |
| Side to move and known remaining horizon | Arrival ties, initiative, and ending with a lead matter |

Chebyshev distance `max(abs(dx),abs(dy))` is the empty-board travel lower bound because diagonal movement is legal. For a current player, a `d`-move arrival occurs at global ply `2*d-1`; the other player reaches a `d`-move target at ply `2*d`, assuming alternating turns without skips. Use actual intermediate board states to account for threats and occupied squares. Recompute races after each authoritative update.

Do not double-count the same house for multiple friendly groups. A candidate capture should update the future resource set and population requirements. A planner that predicts both players will capture the same house, or that a group can convert a larger house without growth, is not usable for evaluation.

Use a bounded nonterminal score strictly inside terminal win/loss values. Tune it against match results, not only population growth. Avoid a blanket rule to reject all risk: a losing position may need a gamble, while a position with a safe win should preserve it. The primary objective handles that distinction better than an arbitrary permanent penalty on randomness.

## Preserve wins that can be certified

There are useful local mathematical certificates even without solving the whole game. Total humans plus monsters never increases: conversions preserve total population and combat only removes it.

On `testmap2`, total starting population is 52. If a stack of at least 20 converts the central 20 humans, it becomes at least 40, leaving at most 12 creatures/humans everywhere else. Keeping this stack intact makes every enemy encounter deterministic in its favor, even if the opponent converts all remaining humans. The stack retains a decisive population lead until the finite game ends under the written rules. Obtaining that position is the difficult part; the opening is not proven to force it.

More generally, if an intact group `N` satisfies `2*N >= 3*(enemy_total + remaining_humans)` and has a strict lead over that sum, the opponent cannot grow enough to threaten it under the stated combat rules. On the supplied nondegenerate boards it can keep moving without a risky battle. Recognize such positions and avoid splitting away the certificate. Confirm that server behavior matches the brief before treating this as an operational guarantee.

## Deadline and search engineering

- Prepare a legal fallback before expensive work; prefer one screened for immediate danger when time permits.
- Start timing as early as UPD is recognized and include state processing and serialization overhead.
- Use monotonic deadlines and iterative deepening. Start with roughly 1.5 seconds for search within the two-second allowance; measure and adjust on CTI.
- Check the deadline inside generation, chance enumeration, and evaluation, not only between root moves.
- Reuse completed results and order promising moves first. Keep transposition records with exact/lower/upper status, depth, side to move, horizon assumptions, rule mode, and evaluator version. Do not reuse sampled estimates as exact bounds.
- Extend unstable tactical positions a bounded amount past the nominal horizon. A hypothetical pass is not legal and must not become a candidate or a pruning assumption.
- Measure completed depth, nodes, chance outcomes, approximate probability mass, allocations, and response time. Move to a faster implementation only if profiling demonstrates a need.

No fixed search depth, sample count, or group limit is claimed to fit CTI yet. The current 0.017-second map-analysis run measures small offline calculations, not a tournament search.

## Why this starting algorithm

This was a bounded comparison of primary literature, not an exhaustive review. Sources, access limits, and search queries are in [the literature matrix](../notes/literature-matrix.csv) and [search log](../notes/search-log.csv).

Ballard's work develops pruning for adversarial trees with probability nodes. Its publisher abstract and metadata were accessible through search; the full paper was not. It establishes the relevant algorithm family, not a performance forecast for this game. [Ballard, 1983](https://doi.org/10.1016/S0004-3702(83)80015-0).

Lanctot and colleagues compare sampled *-minimax with MCTS variants in four stochastic games. Their results vary by domain; the paper also describes chance-value bounds, iterative deepening, and the limitations of sparse-sampling guarantees. This motivates testing both exact and sampled chance handling here. It does not establish which wins on our maps. [Lanctot et al., 2013, sections 2-4](https://www.ijcai.org/papers13/Papers/IJCAI13-093.pdf).

Ramanujan and colleagues demonstrate that UCT can miss shallow tactical traps in their chess experiments. Our map has an immediate exposure pattern, so explicit opponent-reply coverage is a sensible design hypothesis. Their result does not imply that modern MCTS variants cannot succeed at this game. [Ramanujan et al., 2010, pp. 242-245](https://ojs.aaai.org/index.php/ICAPS/article/view/13437).

| Candidate | Role in this project | Main uncertainty |
| --- | --- | --- |
| Greedy human collection | Simple comparison player | Ignores replies and population thresholds |
| Ordinary minimax on expected boards | Reject as the main model | Replaces mutually exclusive battle outcomes with fictitious states |
| Exact expectiminimax | First tactical baseline and small-position oracle | Chance and joint-action branching may limit depth |
| Bounded/sampled expectiminimax | Proposed main tournament candidate after validation | Needs careful bounds, good evaluation, and measured sample choices |
| MCTS with tactical checks and widening | Serious benchmark challenger | Performance depends on selection, rollout/evaluation, and tactical coverage |
| Learned evaluation or policy | Revisit only with data, time, and a compliant implementation | Two maps do not justify claims of generalization; prohibited AI libraries remain prohibited |

## Proving strength through experiments

First validate transitions against the official server. Then test a tactical suite including the exposed trap approach, deterministic thresholds, bad splits, merge threats, capture denial, mandatory movement, and preserving a certified lead.

Benchmark the same candidate generator and evaluation with different search engines where possible, so results reflect search rather than unrelated differences. Include random/legal, greedy, shallow adversarial, deeper adversarial, and a tactical MCTS challenger. Swap species and starting order where the server supports it. Use separate development and held-out maps and seeds, including long races, close starts, scarce humans, many groups, and few-human endings.

Record the map hash, code/configuration hash, seed, side, opponent, result, termination reason, invalid moves, and response-time distribution. Report sample sizes and uncertainty. Treat zero timeouts in a finite sample as evidence, not a universal guarantee. Investigate every illegal move or protocol failure before interpreting win rates.

Use ablations for opponent lookahead, race/denial features, exact chance handling, and splitting. The final engine is whichever wins these controlled comparisons while meeting deployment constraints. Do not claim a tournament win rate before running matches.

## Implementation order

1. Keep the exact battle and single-move model as a reference; verify its behavior against the server.
2. Complete legal joint-turn generation and validated multi-move transitions.
3. Implement a shallow opponent-aware player, bounded evaluation, fallback, and launcher.
4. Add race/denial analysis and depth control; retain the trap and central-house regressions.
5. Compare bounded exact chance search with sparse sampling and tactical MCTS under the same time budget.
6. Select the measured winner, rehearse on CTI, and document the actual algorithm and evidence in the report.
