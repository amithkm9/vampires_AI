# Outcome and conversion-race strategy

Registered 2026-10-15 before new strategy matches. This is an original local
agent experiment, not a reproduction of a published game's results.

## Question and baseline

Can outcome-oriented endgame values and sequential, exclusive human conversion
races improve the existing `adaptive:5` agent under the same search allowance?
The starting revision is `8c41cc0`. Preserve the existing adaptive algorithm,
evaluator and generator as the control. The recorded 6-versus-7 no-human cycles
are development evidence, not held-out tests.

Candidate `outcome:5` changes only no-human evaluation. Candidate `strategic:5`
also projects sequential human captures with population growth and exclusive
resource ownership. Both retain opponent-aware balanced search, intact-group
generation, chance intervals, deadline checks and the existing dominance policy.
Additional partial-move refinement may be evaluated separately if these results
justify it; it is not implicitly enabled by either evaluator.

## Rules and modeling

The six move rules, p. 6 record limit, binary protocol and two-second full turn
limit remain unchanged. No AI/tree/graph libraries. Live daylight remains unknown.
Outcome-oriented leaf scores are heuristics, not exact win probabilities or a
fabricated countdown. Shared contested arrivals remain an explicit unresolved
server interpretation. Safe lead/tie fixtures and opponent replies must be tested.

## Development protocol

Budget 0.05 seconds, maximum 50 plies, both species (vampires start).
Maps: thetrap, testmap2, resource_race, contact, endgame.
Generated-map seed 25101501, combat seed 25101511, policy seed 25101531.
Opponents: adaptive:5, collector, raider, split_merge.
Compare adaptive:5, outcome:5 and strategic:5: 120 games total.
Select by paired match score; break ties by fewer losses then lower maximum time.
Keep unsuccessful versions with their exact source snapshots. Any iteration
after development must use a new directory and be recorded before its matches.

## Locked evaluation

Freeze one challenger before viewing held-out results. Compare challenger and
adaptive:5 against adaptive:5, escape and split_merge on testmap2, dispersed and
endgame, generated-map seed 25101502, combat seeds 25101521 and 25101522,
policy seed 25101532. Budget 1.25 seconds, maximum 60 plies, both species:
72 games. No tuning on these results. Population at the local cap is an offline
proxy; neither agent is told the cap.

Promote only with higher overall paired score, no aggregate regression against
adaptive or split_merge, no legality or two-second failures, passing unit/exact
checks and normal-budget stress tests. Otherwise retain adaptive. Report the
per-map/opponent results and paired uncertainty; a small local league cannot
establish universal superiority or official tournament readiness.

## Provenance and validation

Use the existing serial league, which freezes recursive runtime/harness source
snapshots, maps, configuration, interpreter/platform and per-ply seeds. Preserve
all match records, failures and timings. Reverify replays against those snapshots.
Run the relevant unit suite and both-species search/maximum-board checks. No
parallel CPU-heavy runs during timing. Original material hashes must still match.

Research context: [Moraes and Lelis, AAAI 2018](https://cdn.aaai.org/ojs/11432/11432-13-14960-1-2-20201228.pdf)
motivates testing selective action refinement under a fixed time budget, but
its RTS results do not establish benefit for this game. [Lanctot et al., IJCAI
2013](https://arxiv.org/abs/1304.6057) motivates a possible later sampled-chance
challenger; this experiment keeps exact modeled chance probabilities.

## Results

Pending. Commands and actual results will be appended after execution.
