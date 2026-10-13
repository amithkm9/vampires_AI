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
