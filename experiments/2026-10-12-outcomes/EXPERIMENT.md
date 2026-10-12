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
```

## Results

The first run (`tactics-before.json`) contains 30 vampire-to-move audits, all complete. At default candidate limit 64, seven of fifteen positions have positive decision regret; each optimal root action omitted in those cases involves a shared contested destination. These results are conditional on the declared aggregation model. The shared-capture fixture loses an exact 0.5 match-score opportunity (certain win versus certain draw). At limit 8, additional count/ranking pruning also affects the gamble and escape fixtures.

Before the next run: the initial fixtures mostly give vampires two groups and werewolves one. Repeat every position as each species to expose opponent-reply omissions. Add exact omission classifications and one branch/reply witness for an optimistic action. Keep the initial record; this is additional development diagnosis, not held-out evaluation. Save `tactics-both-species.json`.

## Next step

Use measured omissions to choose between improving tactical candidate coverage and replacing root scheduling. Any shared-target counterexample remains conditional on server semantics. Record normal-budget launcher validation after runtime changes.
