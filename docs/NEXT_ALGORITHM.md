# Next algorithm: recognize consequential moves and reduce avoidable losses

Updated: 2026-10-15. The latest provisional default is strategic at depth five:
resumable expectiminimax, intact-group abstraction, sequential conversion races,
outcome-oriented no-human scoring and reused completed search work. The new
72-game evaluation scored 17W/8D/11L for it and 14W/8D/14L for adaptive. Four
endgame cases improved and one dispersed-map case regressed. The paired interval
includes zero. The [strategy experiment](../experiments/2026-10-15-strategy/EXPERIMENT.md)
retains all 256 new development/evaluation games, including negative partial-move
results. The [earlier league](../experiments/2026-10-13-league/EXPERIMENT.md) remains
historical evidence for the adaptive promotion.

Current priorities: verify official-server rules and CTI timing; test whether the
small advantage survives more independent maps/combat seeds; investigate the
dispersed regression and compare outcome-only scoring at normal budget; analyze
intercepted resource routes and recorded repetitions; make partial refinement selective enough to
retain its exact tactical repairs without the observed match regressions. Root
allocation, reusable work, per-depth diagnostics and the opponent league are now
implemented. The sections below preserve the broader design; features remain
proposed unless explicitly marked implemented.

October 12 implementation: exact finite-horizon references, known-cutoff search, bounded repetition diagnostics, and an exact two-sided candidate/reply audit are implemented. At limit 64, known cutoff improves 8/30 tiny development decisions and worsens none. Optional attack reservation improves two limit-8 decisions but worsens one by displacing a merge, so it remains disabled. See [the complete experiment](../experiments/2026-10-12-outcomes/EXPERIMENT.md). Live history currently logs diagnostics only; strategic cycle handling and better root allocation remain next work.

## What the evidence changes

The [replay audit](../reports/replay-analysis-2026-10-11.md) verified all 108 stored matches. The default engine's three trap-map losses at the 0.1-second budget contained no monster combat: it collected four humans, allowed the opponent to collect five, and finished 8–9. The 200-ply loss contained 160 repeated-state visits. More time steps alone did not repair the strategic decisions.

The next implementation should target resource denial, the value of the final result, and incomplete root comparison together. Merely increasing depth or replacing the search with a fashionable algorithm has no demonstrated benefit here.

## Recommended architecture

Keep hand-written opponent-aware expectiminimax as the tactical core. Add an outcome-aware evaluator and strategic capture/interception plans, a protected set of critical moves and replies, adaptive root/chance refinement, bounded tactical extensions, and small exact endgame references. Benchmark alternative engines against that common foundation.

The decision order is: establish a legal fallback; preserve a conditional dominant stack when possible; identify threats and resource races; examine serious moves and the opponent's best replies; refine competing uncertain actions; validate and send the retained result within the two-second deadline.

## 1. Make final outcomes and repetition visible

Current terminal extinction values are already correct under our model convention. The missing piece is distinguishing a small nonterminal population deficit from a certain population-based loss at a **known** game cutoff.

- Add explicit remaining-ply input to controlled benchmarks and the search API, using exact win/draw/loss utility at that cutoff. Include remaining horizon in cached state values.
- The live protocol supplies no daylight countdown. Use only a verified server configuration or a documented uncertain-horizon model; do not silently treat the supplied 200-ply setting as universal or infer a known deadline from the count of our own UPDs.
- Record repeated board/side states across authoritative updates. Use repetition to trigger endgame/route analysis and break equally valued unproductive choices. Do not declare an automatic draw or apply an unconditional repetition penalty: retaining a lead or a defensible draw can be correct.
- Compare explicit loss probability and expected match score. Avoid treating a heuristic population score as a win probability. When no safe outcome is available, a calculated gamble can be better than a certain loss; when a non-loss can be proved, preserve it.

Acceptance: exact tiny finite-horizon examples distinguish safe wins, draws, unavoidable losses, and useful gambles; losing and leading repetition fixtures behave differently. A live horizon assumption remains labeled until checked with the official server. Replay counterfactuals must consider opponent alternatives, not just a frozen opponent move script.

## 2. Protect the moves that can decide the game

`turns.candidate_turns` currently uses thresholds, one record per source, and a bounded beam. Critical actions can be absent before search even begins.

- Compare its retained turns and best-response values with `exhaustive_turns` on tractable small positions. Report tactical omissions and value regret, not just the percentage of all moves retained.
- Reserve consideration for certain kills, emergency escapes, threatened-human captures, defensive merges, reinforcement, safe partial splits, and interception. Evaluate both the moving group and the population left behind.
- Protect opponent threats with the same rigor. A move the player avoids using can still be available to its opponent.
- Keep shared-target battle semantics and wider splitting conditional on official evidence. Test competing resolution assumptions offline; do not turn an unknown enemy action into an invented illegal move.

Acceptance: a hand-built and exhaustively checked tactical suite finds no missed decisive reply within its declared scope. A saturated budget returns an explicitly incomplete result, not a safety certificate.

## 3. Compare root moves before spending the whole budget on one

The current search can spend most of the deadline on early root actions. In the long trap loss it failed to complete root comparison on four turns during the capture race.

- Retain an inexpensive initial ranking, then allocate work across serious root moves and their dangerous replies. Ensure opponent lookahead remains part of the submitted strategy.
- Refine chance outcomes where uncertainty could change the selected move. Prioritize probability mass and competing value intervals, rather than applying the same work limit everywhere.
- Retain exact enumeration for cheap deterministic/small battles. Benchmark sparse-sampled expectiminimax for expensive distributions, with seed and uncertainty labels. Do not report sample confidence bounds as exact mathematical bounds.
- If one action's lower bound exceeds every other action's upper bound, its choice is established only for the covered candidate tree, evaluator, horizon, and transition assumptions. Global optimality additionally requires complete legal coverage and correct terminal values.
- Extend a limited number of unstable tactical leaves involving attack, escape, or capture thresholds. Mandatory movement forbids a fabricated pass or a free stand-still leaf action.

Acceptance: compare ranking accuracy on independent exact tiny trees, initial-root coverage, worst reply omissions, completed depth, interval widths, allocations, and full receive/search/send timing. Measure actual match benefit under the same total budget.

## 4. Plan captures and denial through the opponent's turns

The existing growth prototype models affordable house sequences but ignores interception and incidental occupied squares. Its individual target routes need not form one executable joint plan.

- Build explicit per-group capture/merge plans with population changes, turn of arrival, remaining humans, and movement-rule constraints. Do not credit one house to two groups or let separate routes spend the same resources.
- Model the opponent's reachable attack squares at each relevant turn. Check whether a route can be intercepted, whether a split survives, and whether reinforcements arrive before contact.
- Value denial through future thresholds. On the trap map, the four-human capture cannot be judged separately from the opponent's five peripheral humans. On the large map, taking a four-human house can deny the opponent safe access to the central twenty.
- Use strategic plans for ordering/evaluation while retaining tactical reply checks. Do not jump over intervening opponent moves in a macro-action simulation.

Acceptance: growth, denial, interception, reunion, and resource-sharing fixtures agree with exact short references. An ablation must beat the same engine without the feature under equal time; better-looking routes alone are insufficient.

## 5. Solve tractable endings and preserve established advantages

Dominant-stack preservation already exists and is useful. Extend it only with independently checked reasoning.

- Build an offline finite-horizon stochastic solver for tiny boards/populations as an oracle, with all legal moves and exact chance probabilities under declared combat semantics.
- Use it to test chase/escape, initiative, forced movement, lead preservation, and risk when trailing. Stochastic cycles require explicit horizon or well-defined termination handling; a repeated board is not automatically solved.
- Reuse solved entries in live play only when board, species, rule mode, population, and horizon match. Wider endgame tables are a later optimization if state-space and CTI limits permit.

Acceptance: compare against an independently enumerated reference and distinguish exact solved entries from heuristic results. No full-game solution is claimed from a small table.

## 6. Spend computation where it changes the decision

Profile before changing language. Candidate scoring, board copies, exact rational combat construction, repeated distance calculations, and evaluation are plausible costs to measure, not established bottlenecks.

Test compact state representations, cached battle distributions, incremental features, move ordering, and correctly keyed transposition reuse individually. Preserve the rational simulator as a reference if a floating-point fast path is introduced. Cache horizon/history when values depend on them, and respect authoritative updates.

A stronger MCTS challenger could add progressive widening and explicit tactical checks; sparse-sampled expectiminimax is another candidate. The published comparison of stochastic search methods motivates testing these choices, but does not select a winner for this game. [Lanctot et al., IJCAI 2013, sections 2–4](https://www.ijcai.org/papers13/Papers/IJCAI13-093.pdf).

UCT can miss shallow tactical traps in the cited chess experiments. That supports testing tactical safeguards here; it does not prove all MCTS variants are unsuitable. [Ramanujan et al., ICAPS 2010](https://ojs.aaai.org/index.php/ICAPS/article/view/13437).

Learned evaluation is a later option only after diverse trace data exist. Any training and inference must satisfy the course's algorithm-library ban. Do not begin with a large neural system or tune against the same two supplied maps without independent validation.

## Build and promotion order

1. **Completed diagnostic:** immutable replay reconstruction and extraction of real losing/unfinished-search positions.
2. **Completed first implementation:** finite-horizon outcome references, known-cutoff search, repetition diagnostics, and initial tactical candidate-coverage measurement. These now supply exact counterexamples and policy diagnostics; they do not solve live unknown-horizon endings.
3. **Implemented and tested:** resumable root allocation, conservative partial intervals, shared battle preparation, resource projection and diverse policy proposals. The successful intact-group candidate is provisional; critical partial moves, omitted split replies and tactical extensions need further work.
4. **Strategic candidate:** add contested growth/interception. Initial resource projection and portfolio ablations were inconsistent; they remain selectable and outside the promoted mode.
5. **Optimization/challengers:** profile, improve caches/representation, then compare sampled expectiminimax and stronger MCTS under equal time.
6. **Promotion:** test one change at a time against the frozen baseline, greedy growth, tactical adversarial, lead-preserving/escape, and split/merge opponents. Include unseen map families and seeds, both species, verified starting-order variants, and the normal 1.25-second search budget. Preserve losses and raw diagnostics.
7. **Deployment gate:** verify shared-target/split/tie behavior and exact launch on the official server and CTI. Measure full response time under the brief's two-second limit. Then select and package the final engine.

Use separate development and locked evaluation sets. Fix a comparison protocol before seeing the results; report paired match score, loss rate, timing failures, tactical regret, and uncertainty across map/seed clusters. A passing promotion needs a reproducible advantage with acceptable timing and no legality regressions in the tested suite. Zero observed losses is evidence for that suite, never proof that no future match can be lost.

## The attainable claim

The defensible objective is to eliminate demonstrated avoidable mistakes and maximize performance against strong play within the course constraints. A best move can sometimes be proved in a restricted solved position. No algorithm can force a win in every allowed position: the existing one-versus-one mandatory-battle test has a positive probability of defeat. The supplied openings have not been solved, so neither forced victory nor inevitable defeat is established for them.
