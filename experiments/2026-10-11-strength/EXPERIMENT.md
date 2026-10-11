# Strength audit and engine comparison

- Date and experiment ID: 2026-10-11-strength.
- Question: do generation-budget control, explicit chance bounds, and preservation of dominant stacks improve the published baseline under equal time limits? Does a sampled adversarial UCT challenger outperform either engine on the same local model?
- Baseline: immutable Git revision `2a08829b1935a80c3c11a37ecea5efb089425268`; current baseline has 105 passing tests and no competitive-strength measurement.
- Candidate changes: bounded partial generation; no silent deletion of large chance actions; dominant-stack preservation; an optional multi-house reachability heuristic. Every algorithm is implemented in this project with the standard library.
- Data: supplied XML maps and separately generated symmetric small maps. Original XML bytes remain unchanged. Record full generated boards and hashes with results.
- Split: supplied maps are development data. Generated maps are evaluation data; do not adjust constants to their match results. This is a small pilot, not a definitive held-out tournament evaluation.
- Metrics: paired match score (win=1, draw=0.5, loss=0); counts of invalid moves, failures, over-budget turns, completed depth, and time. Swap species and keep the starting species fixed within each pair. Preserve per-match seeds and raw turn records.
- Selection: correctness and legal responses first. Use paired outcomes and timing to decide whether an experimental engine warrants promotion; an uncertain pilot is not evidence of a universal best algorithm. Keep negative results.
- Compute: local CPU only, Python standard library, no training or paid compute. Initial comparison uses 0.03 seconds per turn and a 60-ply local cap; this is not the official two-second or CTI environment. Run a separate normal-budget smoke check after code validation.
- Seeds: 20261011 and 20261012 for matches; 71 and 83 for generated maps. Search sampling uses explicit per-turn seeds, separate from combat randomness.
- Reproducibility: benchmark exports the baseline modules read-only from Git into a temporary directory. Record Git revision plus hashes of dirty working sources, interpreter, platform, maps, settings, and exact commands. No third-party dependency lockfile is needed because there are no dependencies to install; interpreter version is recorded.

## Results

Pilot 01 completed 48 matches at 0.03 seconds per turn. Bounded search scored 6 wins / 8 draws / 2 losses; growth scored 2 / 12 / 2; UCT scored 1 / 2 / 13. No failures were recorded. Raw data and metadata are under `pilot-01/`. A short search-stress probe overlapped part of this run; retain these data as exploratory and check budget sensitivity without that overlapping work.

Before running the follow-up: repeat all three variants with the same unchanged code, maps, seeds, species swaps, and 60-ply cap, but a 0.1-second budget. Do not tune constants from the generated-map outcomes. Do not run other CPU tests during this comparison. This reuses the pilot cases, so it is budget sensitivity evidence rather than an independent held-out sample. Save it separately as `pilot-02/`.

Model parity with the supplied server remains unverified. The local simulator and harness cannot establish official-server correctness or tournament win probability.

Before the horizon follow-up: the 60-ply pilot cap permits only 30 moves per side, less than the documented optimistic 37-own-turn route to the central house. The supplied configuration has `MaxPlays=200`. Keep both short pilots and add a separate 200-ply development-map check with unchanged engines, 0.1 seconds per turn, seed 20261013, both supplied maps and both species: 12 matches total. This is horizon sensitivity on known maps, not new held-out evidence. Save it as `long-01/`; keep the course's two-second deadline distinct from the supplied five-second setting.

## Interpretation

All planned runs completed, totaling 108 matches and 6778 combined candidate/baseline turns. Each variant played the pinned baseline, not the other variants directly. Score is win=1, draw=0.5, loss=0.

| Run | Variant | Games / pairs | Wins / draws / losses | Paired score | Conditional bootstrap 95% interval |
| --- | --- | --- | --- | --- | --- |
| pilot-01: 0.03 s, 60 plies | bounded | 16 / 8 | 6 / 8 / 2 | 0.625 | [0.500, 0.813] |
| pilot-01 | growth | 16 / 8 | 2 / 12 / 2 | 0.500 | [0.500, 0.500] |
| pilot-01 | uct | 16 / 8 | 1 / 2 / 13 | 0.125 | [0.031, 0.250] |
| pilot-02: 0.1 s, 60 plies | bounded | 16 / 8 | 2 / 12 / 2 | 0.500 | [0.500, 0.500] |
| pilot-02 | growth | 16 / 8 | 4 / 10 / 2 | 0.5625 | [0.500, 0.656] |
| pilot-02 | uct | 16 / 8 | 0 / 2 / 14 | 0.0625 | [0.000, 0.125] |
| long-01: 0.1 s, 200 plies | bounded | 4 / 2 | 1 / 2 / 1 | 0.500 | [0.500, 0.500] |
| long-01 | growth | 4 / 2 | 1 / 2 / 1 | 0.500 | [0.500, 0.500] |
| long-01 | uct | 4 / 2 | 1 / 0 / 3 | 0.250 | [0.000, 0.500] |

No invalid move, exception, or two-second deadline failure was recorded. Maximum measured candidate responses were 0.034471 s, 0.125792 s, and 0.102534 s across the respective runs. Some responses exceeded the requested search budget, so those settings are cooperative limits, not hard timing guarantees. Total runtimes were approximately 70.11, 243.13, and 195.26 seconds. The UCT engine has no completed-depth metric; its reported zero count must not be interpreted as a depth-completion advantage.

The bootstrap resamples the observed map/seed pair scores. Identical pair scores produce a degenerate [0.5,0.5] interval: this is **not certainty about true strength or exact equality**. There are only four map layouts in each short pilot and two in the horizon check; seed repetition does not create new independent map families. Timing can change decisions despite fixed combat seeds. Neither the generated-map pilot nor its reused budget comparison establishes broad generalization. The longer run addresses one horizon limitation on known maps, not the official daylight/time limit.

Bounded search's initial gain did not persist at the larger budget. Growth has a small gain at 0.1 seconds/60 plies, but tied overall in the longer known-map check. Growth also recorded 120 zero-completed-depth decisions in pilot 02, compared with 25 for bounded search, showing its computation cost. Basic finite-depth UCT performed poorly in all three settings; this is a negative result for this implementation, not the entire MCTS family. It lacks progressive widening and tactical rollout improvements.

Retain bounded expectiminimax as the default for its generation and uncertainty-handling fixes, with no claim of proven match superiority. Keep growth and UCT experimental. Do not tune constants to make the generated-map pilot look better. Future changes need new evaluation cases and normal-budget comparisons.

## Artifacts and commands

- [Pilot 01 summary](pilot-01/summary.json), [metadata](pilot-01/metadata.json), [boards](pilot-01/boards.json), [raw matches](pilot-01/matches.jsonl).
- [Pilot 02 summary](pilot-02/summary.json), [metadata](pilot-02/metadata.json), [boards](pilot-02/boards.json), [raw matches](pilot-02/matches.jsonl).
- [Long-horizon summary](long-01/summary.json), [metadata](long-01/metadata.json), [boards](long-01/boards.json), [raw matches](long-01/matches.jsonl).

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/benchmark_strength.py --output experiments/2026-10-11-strength/pilot-01
python3 tools/benchmark_strength.py --budget .1 --output experiments/2026-10-11-strength/pilot-02
python3 tools/benchmark_long.py --output experiments/2026-10-11-strength/long-01
python3 tools/check_search.py --output reports/search-stress-2026-10-11.json
python3 tools/check_player.py --budget 1.25 --depth 3 --max-plies 20 --output reports/player-strength-smoke-2026-10-11.json
```

Use new output directories for repetitions; the tools preserve existing raw records. Python 3.14.6 on macOS arm64 was used. Metadata includes the precise interpreter/platform, CPU count, command, pinned baseline, and source hashes. Map hashes identify canonical serialized boards; original XML hashes remain in `materials/manifest.json`. No dependencies were installed and no prohibited algorithm libraries were used.

All 122 tests passed in 0.635 seconds, including independent eager/streaming comparisons and tiny full-tree interval references. All 13 original material hashes and all saved experiment/current smoke source hashes were verified. The [synthetic stress record](../../reports/search-stress-2026-10-11.json) covers eight positions. The [normal-budget TCP check](../../reports/player-strength-smoke-2026-10-11.json) passed four matches and 30 AI turns, both supplied maps/species, with a maximum observed response of 1.250434 seconds. These checks share our model and do not substitute for official-server or CTI evidence.

## Next step

Measure retained tactical replies against the exhaustive small-board oracle, refine wide root chance intervals, and add interception to growth routes. Compare feature ablations against stronger opponents on new map families at the normal budget. Obtain official-server transition evidence and the exact CTI launch check before tournament-readiness claims.
