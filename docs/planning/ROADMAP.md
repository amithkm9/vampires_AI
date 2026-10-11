# Roadmap from supplied materials to tournament submission

Build a reliable player first, then improve its decisions using measured results. Protocol failure can cap the grade regardless of strategy (brief p. 2), while a reflex-only player does not meet the AI requirement. Both concerns shape the order below.

No calendar dates are assumed. Add them after the submission date, tournament date, and CTI access are confirmed. The detailed work items are in [TODO.md](../../TODO.md).

| Phase | Deliverable | Completion condition | Status |
| --- | --- | --- | --- |
| 0 Understand and organize | Preserved materials, audit, rules, roadmap | Every source inventoried; brief and supplied text files read; originals verified | Complete |
| 1 Establish foundations | Packet codec, state model, move rules, battle helpers | Rule boundary tests and persistent mock protocol exchange pass | Complete: 41 tests |
| 2 Build a forward model | Legal candidate turns and simulated successors | Known movement/conversion/battle cases match expected results; uncertain server behavior remains explicit | Local model complete; shared-target parity pending; 105 total tests |
| 3 Make the first player | Small opponent-aware search and complete launcher | Autonomous harness match; a demonstrated opponent-reply decision; correct restart and shutdown | Local baseline complete; official-server check pending |
| 4 Improve search and timing | Bounded deeper search with a fallback | Tactical improvement over baseline and measured response headroom below 2 seconds | Initial depth/deadline/cache implemented; local timing recorded; tuning and CTI pending |
| 5 Validate deployment | Official-server and CTI rehearsal | Exact launch command works; both species complete matches; no protocol or legality failures | Pending; start environment work early |
| 6 Measure strength | Paired benchmark records and final strategy choice | Reproducible comparisons, side swaps, failure counts, timing, and ablations | Pending |
| 7 Explain and submit | Source package, report, five-minute presentation | Clean CTI rehearsal, algorithms mapped to code, required deliveries completed on time | Pending |

## Phase 2 Forward model

Start with moving a whole group or part of a group to one neighboring cell. Enumerate candidates ourselves from the board. Apply outgoing populations from the original board, then resolve arrivals without changing the original search state. Add friendly merging, deterministic human conversion, guaranteed monster combat, and explicit random outcomes.

Validate the local model against the official server as soon as it becomes available, especially when multiple groups target one battle. Exact multi-move handling must not be inferred from a convenient simulator design. One-destination partial movement is already permitted; keep wider splitting within the conservative record limit until its ambiguity is resolved.

## Phase 3 Opponent-aware baseline

The initial algorithm should evaluate our candidate move and possible opponent replies. Use a small candidate set with an explicit treatment of chance; implement the search ourselves. A useful first evaluation combines population advantage, access to humans, immediate losses the opponent can force, and exposed small groups. Test a position where greedily taking humans loses to an opponent reply and verify that lookahead changes the move.

Integrate this into a launcher that takes optional settings first and the server address/port last. Start the clock on UPD, update state, choose a move, validate it, and send it. Preserve the connection through END. Record diagnostics without making ordinary turn processing expensive.

## Phase 4 Search under a deadline

Use a monotonic clock, a cheap legal fallback, and the last fully evaluated result. Initially reserve roughly half a second of the two-second allowance for overhead; this is a starting choice to measure, not a guarantee. Check the deadline inside costly loops, including candidate generation and chance expansion.

Improve the baseline incrementally: deeper bounded search, move ordering, and a cache of evaluated states if profiling justifies it. Implement any search tree, cache key, and traversal directly. Chance nodes require expectation handling; do not silently replace them with ordinary deterministic minimax. If outcomes are sampled or candidates pruned, explain the approximation in the report and measure its effect.

## Phase 5 Official environment

Obtain CTI access details now and rehearse as soon as Phase 3 can play; do not defer the first official-server test until strategy tuning finishes. Prepare a separate runnable server copy with a valid map and the course's two-second limit. Keep the supplied binaries and original configuration intact.

Confirm that the exact command works from a clean directory on CTI, identify runtime assumptions, and play both species. Test END followed by a new game on the same socket, BYE shutdown, and expected failure logs. Repeat the rehearsal on the final package.

## Phase 6 Experiments

Use both supplied maps and additional shapes/populations to avoid tuning only to one opening. Run paired games with sides swapped. For random battles, record seeds where the simulator permits them and report variability across repeated matches; do not claim control over the official server's random seed without support.

Record win/loss/draw, opponent, species, population outcome, time per turn, invalid moves, disconnects, and timeouts. Compare against simple legal/greedy players and the previous working strategy. Disable one feature at a time to show whether lookahead, capture terms, danger terms, or splitting improved results. These comparisons belong in the report.

## Phase 7 Report and delivery

Write the report alongside implementation: problem and rules, algorithm choices, evaluation, chance handling, complexity, timing design, experiments, and limitations. Identify each algorithm's actual file and function. Replace planned claims with observed results before submission.

Plan the five-minute presentation around the strategic idea, one understandable board example, measured strengths, and a concise demonstration. Rehearse the timing. Finally preserve a clean source package, verify imports and launch instructions, run it on CTI, and submit to edunao before the tournament. Confirm any separate report and presentation deadlines.

## Immediate next task

The joint model, shallow opponent-aware baseline, and launcher are implemented. See [implementation details](../IMPLEMENTATION.md) and [baseline verification](../../reports/baseline-verification-2026-10-09.md). Improve crowded-board candidate generation and large chance-action handling next, then add multi-house growth/denial and dominant-stack preservation. Obtain official-server and CTI evidence in parallel with that work. The [map analysis](../../reports/map-analysis-2026-10-09.md) supplies concrete tactical and resource regressions; it does not establish optimal full-game play.
