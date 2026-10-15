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

Development 01 completed all 120 games with no failures. Each candidate scored
24W/6D/10L (0.675). Outcome/strategic changed two paired endgame results against
adaptive, one win-to-loss and one loss-to-win. The aggregate result is neutral.
Maximum candidate responses: adaptive 0.058333 s, outcome 0.059497 s, strategic
0.062098 s. The exact trailing-cycle fixture improves, but there is no measured
overall promotion evidence yet. All 273 unit tests passed before these matches.

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/league.py --engines adaptive:5 outcome:5 strategic:5 --opponents adaptive:5 collector raider split_merge --maps thetrap testmap2 resource_race contact endgame --map-seeds 25101501 --combat-seeds 25101511 --policy-seeds 25101531 --budget .05 --max-plies 50 --output experiments/2026-10-15-strategy/development-01
```

## Development extension registered before execution

The first development round does not establish improvement. Add `tactical:5`,
combining the unchanged strategic evaluator with the already-tested hybrid
partial-move generator and reusable search. This isolates the interaction of
evaluation and partial moves; it does not change the earlier frozen variants.

Compare adaptive:5, outcome:5, strategic:5 and tactical:5 at 0.15 seconds and
50 plies, against adaptive:5 and split_merge, on thetrap, contact, dispersed and
endgame. Development map seed 25101503, combat seed 25101513, policy seed
25101533; both species, 64 games. Select the challenger using this round's paired
score, fewer losses, then maximum latency. The original held-out protocol,
seeds and promotion conditions remain untouched. If all challengers fail to
improve, still evaluate the best challenger, without presuming promotion.

Development 02 completed 64/64 games without failures. Results (16 games each):
adaptive 8W/1D/7L (0.53125), outcome 9W/1D/6L (0.59375), strategic 10W/1D/5L
(0.65625), tactical 8W/1D/7L (0.53125). Largest response was 0.154878 seconds.
Partial moves repair the exact witness but again did not improve total score.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/league.py --engines adaptive:5 outcome:5 strategic:5 tactical:5 --opponents adaptive:5 split_merge --maps thetrap contact dispersed endgame --map-seeds 25101503 --combat-seeds 25101513 --policy-seeds 25101533 --budget .15 --max-plies 50 --output experiments/2026-10-15-strategy/development-02
```

**Locked before evaluation:** select `strategic:5`, with its existing evaluator
constants, intact-group generator and depth. No algorithm changes will be made
based on held-out results. Compare it and adaptive:5 under the original 72-game
normal-budget protocol. The default remains adaptive pending the outcome.

## Locked results and selection

All 72 games completed without failures, 36 games per candidate:

| Engine | Wins | Draws | Losses | Paired score | Maximum candidate response |
| --- | ---: | ---: | ---: | ---: | ---: |
| adaptive:5 | 14 | 8 | 14 | 0.500000 | 1.255335 s |
| strategic:5 | 17 | 8 | 11 | 0.583333 | 1.250948 s |

Per-opponent scores (control to challenger): adaptive 0.500000 to 0.583333,
escape 0.583333 to 0.583333, split_merge 0.416667 to 0.583333. Four matched
cases improved, one regressed and 31 were unchanged. All four improvements were
on the endgame family; one dispersed-map case against escape regressed. Testmap2
results were unchanged. The result does not isolate the human-race feature's
normal-budget benefit; outcome-only versus strategic on a new set is a priority.

The mean paired gain was 0.083333. Exact empirical resampling of the three map
clusters gives a descriptive 95% interval **[-0.083333, 0.333333]**. It includes
zero and is conditional on only these related maps. Two combat seeds, scripted
probes, timing-sensitive decisions and a shared simulator limit generalization.
The game cap and draw rule are local proxies, not verified server information.

**Decision:** provisionally promote `strategic` at depth five and 1.25 seconds.
It meets the registered overall/per-opponent score, legality, timing and
correctness gates. Preserve `adaptive:5` unchanged. Retain outcome and tactical
as explicit ablations; do not claim that strategic is a globally optimal agent.
No evaluator constants or search behavior were changed after the locked run.
The default-selection change affects routing/CLI help only.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/league.py --engines adaptive:5 strategic:5 --opponents adaptive:5 escape split_merge --maps testmap2 dispersed endgame --map-seeds 25101502 --combat-seeds 25101521 25101522 --policy-seeds 25101532 --budget 1.25 --max-plies 60 --output experiments/2026-10-15-strategy/holdout-01
```

## Final verification

- Python 3.14.6, macOS arm64; exact runtime/platform strings and configurations
  are in each run's metadata. No third-party runtime dependencies to lock.
- All **256 matches / 8046 plies** reconstructed with the saved source snapshots
  and combat seeds: 3453 development-01, 1928 development-02, 2665 held-out plies.
- **274 tests** passed in 3.172 seconds after default selection, including
  independent exact references and both-species engine lifecycle checks.
- Three new engines passed eight normal-budget search stress cases each:
  **24 cases**, maximum about 1.2501 seconds.
- They passed **36 maximum-area probes**, maximum **1.285958 seconds**.
- The actual launcher passed **four local TCP matches / 31 AI turns**, both
  supplied maps/species, persistent restart, unrelated working directory and clean
  BYE. Maximum complete response was **0.713226 seconds**. Sandbox localhost
  binding was initially blocked; authorized execution succeeded. This uses our
  own simulator and does not establish official-server parity or CTI timing.
- Every new live turn still passes `rules.validate_moves`; the six written move
  rules, conservative p. 6 record limit, combat model, chance bounds and two-second
  network deadline are unchanged. Split omission is a strength limitation, not
  a rule violation. Shared-target combat/tie interpretations remain unresolved.
- All 13 original-material hashes match. The final import scan found only
  standard-library absolute runtime imports, and all five stress/TCP records'
  recursive source hashes match the final runtime. `git diff --check` passed.

Reproduce verification with fresh output paths (the paths below identify the
actual records; do not overwrite them):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_league.py experiments/2026-10-15-strategy/development-01 --output experiments/2026-10-15-strategy/development-01/replay-analysis.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_league.py experiments/2026-10-15-strategy/development-02 --output experiments/2026-10-15-strategy/development-02/replay-analysis.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/analyze_league.py experiments/2026-10-15-strategy/holdout-01 --output experiments/2026-10-15-strategy/holdout-01/replay-analysis.json
python3 experiments/2026-10-15-strategy/summarize.py --output experiments/2026-10-15-strategy/comparison.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_search.py --engine strategic --depth 5 --budget 1.25 --output reports/search-strategic-2026-10-15.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_search.py --engine outcome --depth 5 --budget 1.25 --output reports/search-outcome-2026-10-15.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_search.py --engine tactical --depth 5 --budget 1.25 --output reports/search-tactical-2026-10-15.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_limits.py --engines strategic outcome tactical --depth 5 --output reports/maximum-board-strategy-2026-10-15.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_player.py --engine strategic --depth 5 --budget 1.25 --max-plies 20 --output reports/player-strategic-smoke-2026-10-15.json
```

Current stress/TCP records hash the final runtime recursively. Historical league
snapshots retain their exact pre-promotion engine routing. The unchanged search,
simulation, candidate generators, baseline evaluator and new planning evaluator
must match their held-out snapshots; future reproductions should use those
snapshots, not silently substitute later source.
