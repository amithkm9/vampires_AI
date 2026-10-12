# Outcome and tactical-coverage development experiment

- Date / ID: 2026-10-12-outcomes.
- Question: does a known match cutoff change a decision from certain loss to a useful gamble? Which decisive moves or replies are absent from the current candidate tree?
- Baseline: runtime before this work is immutable revision `5b47469ac5fec4d2e2d49913a87765ab94604085`; the candidate generator is initially unchanged. Compare full finite-horizon exact trees with generator-restricted exact trees, then evaluate selected actions against the full tree. Search-time truncation is a separate issue.
- Development data: seven declared handcrafted positions (gamble, lead, draw, shared capture, shared attack, escape/reinforcement, joint resource race) and eight seeded 2x3 positions from seeds 1201 through 1208. Every board is stored in the raw result. These are development fixtures, not independent promotion evidence.
- Rule assumptions: strict move-record limit; independent random battles; explicit offline aggregation of shared-target attacks; equal populations and both-extinct states draw. These assumptions remain unverified against the official server.
- Metrics: exact W/D/L and expected match score; legal and retained root counts; root omission regret; selected-action regret against full replies; largest optimism caused by omitted opponent replies. Exact tied scores prefer lower loss risk for the acting side. Record unsolved cases explicitly.
- Limits: horizons one or two total plies, 20,000 states per solver, five seconds per case, candidate limits 64 (default) and 8 (stress). No live generation timeout in the restricted tree, isolating structural and count pruning.
- Environment: local Python standard library only; no dependencies to install or lock. Raw records include interpreter, platform, exact command, Git revision, complete source hashes, runtime, and deterministic seeds. The exact oracle uses the eager transition reference; live search uses the separate streaming transition path. Both share combat rules and therefore do not independently establish server parity.
- Before viewing results: keep negative findings and failures; use counterexamples as regression fixtures, never infer full-game superiority. No final engine promotion is planned from this development suite alone.

## Commands

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tools/check_tactics.py --output experiments/2026-10-12-outcomes/tactics-before.json
python3 tools/check_tactics.py --output experiments/2026-10-12-outcomes/tactics-both-species.json
python3 tools/check_tactics.py --protect-tactics --output experiments/2026-10-12-outcomes/tactics-protected.json
python3 tools/check_outcomes.py --output experiments/2026-10-12-outcomes/outcome-comparison.json
python3 tools/check_player.py --budget 1.25 --depth 3 --max-plies 20 --output reports/player-outcomes-smoke-2026-10-12.json
```

Use fresh paths for reruns. The first command used the initial vampire-only edition of the audit tool; the current tool includes both species. The initial raw record retains that edition's source digest and its 30 complete boards/configurations. The two-sided tool before protection is committed at `51d4932`; the protected tool is at `291a3f9`; the outcome comparison is at `9e4b430`. Raw records additionally identify dirty-source hashes because initial measurements preceded their commits. Historical records must be interpreted with their recorded versions, not required to match the latest working files.

## Results

The first run (`tactics-before.json`) contains 30 vampire-to-move audits, all complete. At default candidate limit 64, seven of fifteen positions have positive decision regret; each optimal root action omitted in those cases involves a shared contested destination. These results are conditional on the declared aggregation model. The shared-capture fixture loses an exact 0.5 match-score opportunity (certain win versus certain draw). At limit 8, additional count/ranking pruning also affects the gamble and escape fixtures.

Before the next run: the initial fixtures mostly give vampires two groups and werewolves one. Repeat every position as each species to expose opponent-reply omissions. Add exact omission classifications and one branch/reply witness for an optimistic action. Keep the initial record; this is additional development diagnosis, not held-out evaluation. Save `tactics-both-species.json`.

The two-sided audit completed all 60 cases. At limit 64, seven of thirty decisions have positive regret and four positions contain overvalued root actions due to missing opponent replies; all reported default-limit witnesses involve shared contested targets. At limit 8, nine decisions have positive regret and seven positions contain optimistic actions. The attack by three against a merged four-stack is incorrectly discarded by ranking in the shared-attack fixture, adding exact optimism `21981/65536` to that action's match-score estimate.

Before the protection comparison: add an optional `protect_tactics` switch, reserving whole-group contested moves with a nonzero success probability before filling remaining candidate slots. Keep it disabled by default. This specifically targets the measured risky-capture and risky-reply omissions, without claiming complete tactical coverage or enabling unverified shared-target attacks. Rerun the same development trees into `tactics-protected.json`; retain any regressions. No constants or generated boards will be tuned.

Before the live-search outcome comparison: use `tools/check_outcomes.py` on the same fifteen positions, both species and limits 64/8, at the normal 1.25-second budget. Compare unknown-horizon evaluation, known-cutoff evaluation, and known cutoff plus protected attacks. Match search depth to the declared one/two-ply horizon for every variant and disable the dominance shortcut for every variant, isolating the objective and candidate changes. Evaluate each chosen action using full exact opponent replies. Save all decisions, actual model W/D/L, source hashes, timing, regrets, and negative cases in `outcome-comparison.json`. These are exact development decisions, not competitive matches or new held-out data.

## Completed comparisons and interpretation

All 60 protected-tree audits completed. At limit 64, expected decision scores are unchanged. At limit 8, attack reservation improves two decisions, ties twenty-seven, and worsens one. In `generated_1203` as vampires, reserving attacks displaces the merge `(1,0):2 -> (2,0)`. The selected action's exact score drops from `241/243` to `15/16`. Root regret rises from `2/243` to `1/16`. Preserve this negative result; do not promote attack-only reservation or tune the fixture away.

The actual bounded-search comparison evaluated 180 decisions (30 position/species cases, two candidate limits, three variants):

| Comparison | Candidate limit | Improved / tied / worse exact match score |
| --- | ---: | --- |
| Known cutoff vs unknown-horizon heuristic | 64 | 8 / 22 / 0 |
| Known cutoff vs unknown-horizon heuristic | 8 | 9 / 21 / 0 |
| Known cutoff + attack reservation vs known cutoff | 64 | 0 / 30 / 0 |
| Known cutoff + attack reservation vs known cutoff | 8 | 2 / 27 / 1 |

These are actual selected moves evaluated against exhaustive opponent replies under the declared model. Maximum observed search time was 0.079753 seconds with a 1.25-second allowance. The tiny trees usually finish early. No confidence interval or tournament win rate is appropriate for these handpicked/reused deterministic development cases. Correct cutoff scoring removes demonstrated objective errors, but it does not repair omitted moves or supply a countdown absent from the live protocol.

All 146 unit tests passed in 0.651 seconds on Python 3.14.6. All 13 original-material hashes matched; runtime import inspection found no third-party modules. The current protected-audit, outcome-comparison, and TCP-check source hashes match the final runtime/tools.

The [normal-budget TCP check](../../reports/player-outcomes-smoke-2026-10-12.json) passed four local matches and 30 AI turns, covering both species on both supplied maps, persistent connection, restart, unrelated launch directory, legal moves, and clean BYE. Maximum measured receive/send round-trip response was 1.250297 seconds. The initial sandboxed attempt could not bind the loopback listener; the authorized retry completed. This is a local shared-simulator integration check, not official-server or CTI validation.

Raw records: [initial audit](tactics-before.json), [two-sided audit](tactics-both-species.json), [protected audit](tactics-protected.json), [selected-move outcome comparison](outcome-comparison.json). The historical 108 competitive local matches remain separate and unchanged; no new head-to-head match-strength claim follows from this milestone.

## Next step

Keep bounded expectiminimax as the live engine and attack reservation disabled. Build a balanced tactical set covering attacks, emergency escapes, defensive merges, and critical partial moves, then compare serious root actions before deep refinement. A new scheduler must preserve opponent lookahead and explicit incomplete-work diagnostics. Shared-target root/reply counterexamples make official-server verification urgent. Use repetition diagnostics to drive endgame/resource analysis; no cycle-breaking policy was promoted here. Evaluate changes on fresh positions and normal-budget matches before claiming strength gains.
