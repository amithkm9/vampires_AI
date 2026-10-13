# Opponent league and selective refinement

Registered 2026-10-13 before league matches. This is an original local experiment,
not a reproduction of published RTS strength results. All runtime algorithms use
the Python standard library and project code.

Question: does selective partial-move coverage or deeper iterative search with
reused deterministic work improve the current intact-group player against more
than one opponent? Preserve unsuccessful variants and avoid claiming a universally
best strategy from a small local league.

## Design locked before development matches

Frozen player: revision `04a1e855cc78fbab6f0ddef63fbaf085ea46b520`, engine
`cohesive_material`, depth 3. Current control: `cohesive_material:3` with the same
evaluation and candidate abstraction. Challengers: `adaptive:5` (cohesive search
with reusable work), `hybrid:3` (critical partial moves), `hybrid_adaptive:5`
(both). Candidate cap 64, chance cap 512, unchanged dominance policy. All sides
receive the same search allowance; this does not require equal CPU consumption.

Development: 0.05 seconds per search, 50 total plies; maps `thetrap`,
`resource_race`, `contact`; map seed 1301, combat seed 2026101301, policy seed
731. Four opponents: frozen depth 3, collector, raider and split_merge. Each
configuration/opponent/map plays both species; vampires start. Expected 96 games.
The scripted policies are deliberately different probes, not assignment-compliant
submission agents and not a representative sample of tournament opponents.

Choose one challenger by average paired score across opponents, then minimum
opponent score, then lower latency. Require no legality/two-second failures and
passing independent correctness checks. If no challenger improves the development
control, retain the control while still evaluating the highest scoring challenger.
No constants may be tuned on the held-out outcomes.

Locked evaluation: compare that one challenger and the current control at 1.25
seconds, 60 total plies, maps `testmap2`, `chokepoint`, `endgame`; map seed 1709,
combat seed 2026101317, policy seed 947. Opponents: frozen depth 3, escape and
split_merge. Both species: expected 36 games. This tests new generated families
and seeds, but remains a small, related, single-combat-seed evaluation.

Promotion requires higher held-out paired score than the current control, no
per-opponent regression against frozen or split_merge, no legality or two-second
failure, and successful final launcher/stress checks. Otherwise retain the
existing default and ship challengers as explicit experimental modes. Report
uncertainty and negative outcomes; do not treat a point estimate as proof.

## Evidence and limitations

Run timing matches serially without other CPU-heavy tests. Freeze exact runtime
source files, harness files, source hashes, interpreter/platform, maps, depths,
budgets and independent combat/policy seeds before timing. Persist each match
incrementally, including every move, successor, search diagnostics, elapsed time,
termination, failures and final populations. Resume only against the same manifest.

Failures have no score and must be reported separately; never count an opponent
exception as a strength win. A population comparison at the local ply cap is an
offline outcome proxy, not a known live horizon. Search is not told that cap.
Both-extinct draws and shared contested destinations retain the existing explicit
model limitations. No official-server or CTI validation is implied.

Use bounded exact references to check a supported split witness, compare cached
and uncached search values, test interruption and conservative chance intervals,
and verify repeatable replay reconstruction. Diagnose repeated positions and
unfinished searches without declaring a loss avoidable absent counterfactual
evidence. Any protocol amendment must be recorded before its dependent run.

## Development results and locked challenger

Completed all 96 registered development games without a failed match. Each mode
played 24 games. Control `cohesive_material:3`: 15W/1D/8L, score 0.645833;
`adaptive:5`: 15W/0D/9L, score 0.625; `hybrid:3`: 13W/1D/10L, score 0.5625;
`hybrid_adaptive:5`: 12W/1D/11L, score 0.520833. Largest observed candidate
response: 0.057924 seconds. The tight-budget comparison provides negative
evidence for automatically enabling partial refinement everywhere. In particular,
the split_merge opponent score falls from 1.0 for the control to 0.5/0.333333 for
the hybrid modes. Exact tactical repairs do not imply stronger match play.

**Locked before evaluation:** `adaptive:5` is the highest-scoring challenger,
despite falling below the development control. Evaluate it and the unchanged
`cohesive_material:3` control using the registered 36-game normal-budget schedule.
No hybrid parameters or evaluator weights are changed in response to these
results. The launcher default remains unchanged pending evaluation.

## Locked normal-budget results

All 36 games completed without failures. Each candidate played 18 games:

| Mode | Wins | Draws | Losses | Paired score | Maximum response |
| --- | ---: | ---: | ---: | ---: | ---: |
| cohesive_material:3 | 5 | 10 | 3 | 0.555556 | 0.156862 s |
| adaptive:5 | 6 | 10 | 2 | 0.611111 | 1.252710 s |

Per-opponent scores (control → challenger): frozen 0.5 → 0.5; escape
0.666667 → 0.666667; split_merge 0.5 → 0.666667. Per-map scores: testmap2
0.666667 → 0.666667; chokepoint 0.5 → 0.5; endgame 0.5 → 0.666667.
The entire score improvement is one werewolf endgame against split_merge.
Both conditional three-map bootstrap intervals are [0.5, 0.666667]. These related
maps and one combat seed do not support a claim of statistically established or
general superiority. Population-at-cap outcomes remain proxies: 12 control games
and 13 challenger games reached the 60-ply cap.

Adaptive completed depth five on 433 of 463 turns. Another 22 completed depth
three, six completed depth four, and two used dominance preservation. Its 28
search-budget timeouts retained completed shallower decisions. The control
completed depth three on 443 of 445 turns, with two dominance decisions.
Equal allowances therefore produced substantially different CPU consumption.

**Decision:** provisionally promote `adaptive` with maximum depth five at the
normal 1.25-second allowance. It meets the registered score, per-opponent,
correctness and local timing criteria; the margin is small and tight-budget
development was worse. Keep `cohesive_material:3` available, and retain both
hybrid modes as experiments. Do not describe this as a globally best algorithm.
Promotion changes engine/default-depth routing only; the explicitly tested
algorithm, evaluator and candidate source files remain unchanged.

## Replay diagnosis and next evidence

`tools/analyze_league.py` verified all 132 records and **4387 plies** using each
run's exact transition snapshot, configuration/source/record checksums and seeds.
It retains first repeated and first trailing positions for further analysis.
In evaluation, repeated-state visits were 311 for control and 364 for adaptive
(counts across both participants' turns). Deeper search has not solved repetition
or contested resource planning. Those are stronger next targets than increasing
the depth cap without further analysis. These diagnostics do not prove a move
avoidable or infer a live countdown.

## Reproduction commands

```sh
python3 tools/league.py --engines cohesive_material:3 adaptive:5 hybrid:3 hybrid_adaptive:5 --opponents frozen:3 collector raider split_merge --maps thetrap resource_race contact --map-seeds 1301 --combat-seeds 2026101301 --policy-seeds 731 --budget .05 --max-plies 50 --output experiments/NEW_DEVELOPMENT_RUN
python3 tools/league.py --engines cohesive_material:3 adaptive:5 --opponents frozen:3 escape split_merge --maps testmap2 chokepoint endgame --map-seeds 1709 --combat-seeds 2026101317 --policy-seeds 947 --budget 1.25 --max-plies 60 --output experiments/NEW_EVALUATION_RUN
python3 tools/league.py --resume experiments/2026-10-13-league/holdout-01
python3 tools/analyze_league.py experiments/2026-10-13-league/holdout-01 --output reports/NEW_REPLAY_REPORT.json
```

Fresh runs freeze the current working source. To resume historical evidence after
harness changes, invoke the saved `snapshots/harness/tools/league.py` with
`--resume` and the run's absolute path. Timed decisions can differ between reruns
despite fixed combat/policy seeds. The offline writer lock requires POSIX fcntl;
this does not change the live player's platform requirements.

## Final validation

- Full suite: 262 passed in 2.859 seconds on Python 3.14.6.
- `python3 tools/check_search.py --engine ENGINE --depth DEPTH --budget 1.25 --output FRESH_PATH`: adaptive:5, hybrid:3 and hybrid_adaptive:5 passed eight cases each (24 total), both species; maximum 1.2516 seconds.
- `python3 tools/check_limits.py --engines adaptive hybrid hybrid_adaptive --depth 5 --output reports/maximum-board-league-2026-10-13.json`: 36 maximum-area cases, both species, zero/0.05/1.25-second budgets; maximum 1.297874 seconds.
- `python3 tools/check_player.py --engine adaptive --budget 1.25 --depth 5 --max-plies 20 --output reports/player-league-smoke-2026-10-13.json`: four local TCP matches / 30 AI turns, maximum full response 0.711339 seconds, both maps/species, persistent restart, unrelated launch directory, legal MOV and clean BYE. Sandbox loopback binding failed first; authorized execution succeeded.
- All 13 original/extracted material hashes match; runtime imports are standard-library/project-only. Final stress/TCP records include source hashes. Search can exceed its nominal allowance slightly because checks are cooperative; all observed full responses stayed below two seconds. CTI and official-server checks remain outstanding.
