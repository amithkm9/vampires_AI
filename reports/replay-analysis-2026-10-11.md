# Replay findings that change the next algorithm priorities

Date: 2026-10-11. These are diagnostics of the existing 108 matches, not 108 new games or new performance results. No runtime engine was changed.

`tools/analyze_replays.py` reconstructs all 6778 recorded plies using each stored board, move sequence, and combat seed. It checks recorded source and board hashes, species/engine alternation, legal transitions, extinction, final populations, winner, score, and the local ply cap. All 108 replays matched. The [JSON record](replay-analysis-2026-10-11.json) contains provenance, combat events, repetition counts, and first-deficit/unfinished-search positions.

```sh
python3 tools/analyze_replays.py --output reports/replay-analysis-2026-10-11.json
```

Use a fresh output path for another run. A repeated state here means identical occupied cells and side to move; it excludes elapsed horizon. It is a diagnostic, not a server draw rule or proof that repetition is bad.

## Default-engine losses were not all random-combat losses

In `pilot-02`, both bounded-engine losses were as vampires on `thetrap`, with seeds 20261011 and 20261012. Each ended at 60 plies with vampires 8, werewolves 9, and no humans. There were no monster battles or random battles. Both had 20 repeated-state visits.

The same pattern appears in `long-01`, seed 20261013: bounded vampires lost 8–9 at the 200-ply cap, with no monster or random battle and 160 repeated-state visits. Of 100 candidate turns, four did not finish a complete root iteration. The first such turn was ply 8, during the opponent's resource-gathering sequence, not the final repetitive endgame.

The recorded sequence is explicit: vampires convert the central four-human house at ply 2 and reach eight; werewolves collect the peripheral houses of two, two, and one at plies 9, 11, and 13, then merge into nine at ply 15. The initial population advantage was not a dominance certificate: the opponent plus remaining humans could still reach nine.

This rules out combat luck as the cause of these three recorded losses. It does **not** prove the supplied vampire opening is winnable, identify a uniquely losing move, or show that a repetition penalty will improve the result. Counterfactual move comparisons and adversarial resource/escape analysis are needed.

## Draws also reveal a planning limit

Every bounded and growth game in `pilot-02` ended at the local 60-ply cap: 32 games in total, including wins/losses by population. Every bounded and growth game in `long-01` also reached its 200-ply cap: eight more games. Extending the horizon alone did not remove the pattern.

Both bounded games on `testmap2` in `long-01` ended tied with the central twenty humans still present. Each had 103 repeated-state visits. Neither starting side can safely convert those twenty using its own remaining sixteen creatures, but a draw does not by itself establish bad play. We have not proved that a stronger policy can force improvement against the recorded opponent's alternatives.

## Mechanisms worth testing

`evaluation.evaluate` scores nonterminal population difference smoothly. A population deficit at the actual match cutoff is a loss, but the search is not given a remaining-game horizon and continues to see a small heuristic disadvantage. This is a plausible source of unproductive play; it is not a counterfactually established cause.

`search.choose_turn` starts with two plies and processes root actions sequentially. An expensive early action can leave later candidates without evaluation. The replay exposes that this happened during the losing trap game's capture race. Root scheduling and tactical reply coverage therefore belong alongside strategic evaluation in the next comparison.

`growth.evaluate_growth` credits optimistic capture chains but still lacks interception and a joint plan for all groups. In the three loss cases above, growth did not change the result. More route detail needs a measured benefit that outweighs its search cost.

Next: follow [the improvement plan](../docs/NEXT_ALGORITHM.md), starting with these replay positions, explicit outcome/horizon handling in controlled benchmarks, tactical coverage, and fairer root work allocation. Keep original experiment records immutable and evaluate changes on new maps and seeds.

## Limits

Reconstruction shares the original simulator and therefore cannot independently verify the official server. Replay diagnoses what happened under recorded moves; it does not recompute the engines, estimate the result of unplayed moves, prove avoidability, or provide additional independent statistical trials. Actual tournament daylight, ties, shared-target combat, and CTI timing remain unresolved.
