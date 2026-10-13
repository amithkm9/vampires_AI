# Parallel edge-case audit — 2026-10-12

## Follow-up audit, 2026-10-13

Three agents implemented selective partial moves, reusable search work and the
opponent league, then cross-reviewed each other's changes. The primary integrated
engine/default selection and replay checks. The suite increased from 219 to
**262 tests**. New exact references check depths four through six, interrupted
deeper search, chance caps, cache limits, both-species partial tactics and legal
bounded hybrid generation.

Independent review caught three league defects before timing runs: failed turns
were missing from maximum response statistics; changed completed result payloads
could survive resume; two writers could corrupt the same journal. Fixes include
failure-inclusive timings, configuration/record checksums and a POSIX writer lock.
Resume also verifies snapshots, maps and the schedule, and archives an interrupted
final fragment. Checksums detect accidental corruption, not malicious forgery.

Two supported finite-horizon fixtures demonstrate useful partial moves omitted by
whole-group search. Their exact values are tested against the full legal reference
with shared contested battles rejected; they do not prove general live wins.
The new modes passed 24 normal-budget stress cases and 36 maximum-area probes;
largest observed search time was 1.297874 seconds on this machine.

Remaining limits include selective source ordering, cooperative cleanup overhead,
cache entry counts rather than memory bytes, and completed values for retained
trees whose generation was truncated. See [implementation details](IMPLEMENTATION.md)
and [positive/negative league evidence](../experiments/2026-10-13-league/EXPERIMENT.md).
The original audit below is historical evidence.

The user requested multiple independent reviewers. Three agents audited search, movement and protocol/history; the protocol reviewer then separately audited combat/model invariants. The primary agent integrated fixes, engine selection and lifecycle checks. The completed suite has **219 tests**, passing in **1.969 seconds** on Python 3.14.6. Run `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

## Confirmed defects and repairs

| Defect / counterexample | Repair | Regression evidence |
| --- | --- | --- |
| A fragmented UPD header spends time between U and PD before the old timer starts | `protocol.read_message` times the first U; remaining header and payload share the deadline; late completed reads fail | `tests/test_protocol_edges.py`: fragmented-header timestamps, late reads, EOF/reset and restored timeouts |
| A chance cap of N requests successor N+1 before checking the limit | `search.choose_turn` uses `islice`; balanced search counts actual outcomes before requesting another | `test_chance_cap_does_not_request_an_unused_successor` checks both engines |
| A root with 128 simultaneous 255-vs-255 battles prepares every distribution before a cheap alternative gets work | `simulation.iter_turn_outcome_steps` yields preparation checkpoints; balanced search shares this work across roots | `test_joint_battle_preparation_does_not_starve_other_roots` finishes/selects the cheap root under a deterministic interrupted clock |
| Amount abstraction omits useful partial moves at destination byte-capacity boundaries | `turns.significant_amounts` includes remaining destination capacity and complementary amounts; fallback prefers supported movements among the first source's neighbors | `tests/test_move_edges.py`: both species, conversion/merge boundaries, no invented pass |
| Joint proposals rescan the board in validation; portfolio cleanup repeats validation after timeout | `turns.compatible_extension` checks construction invariants; policy scans check deadlines and reuse target lists | Exhaustive pair equivalence to public validation, seeded candidate legality, expired cleanup |
| A 512-position history can retain tens of millions of cell tuples | `history.PositionHistory` also limits retained cell records to 131072 by default | Eviction, repeats, empty boards, oversized snapshots and reset |
| Truthy non-boolean flags silently change policy | Configuration/candidate flags require booleans | Invalid string/integer/None flag regressions |
| Dominance scans and approach loops lack internal deadline checks | `certificates.dominant_stack` and `preserving_turn` cooperate during scans | Expired dominance-scan test |
| Programmatic live calls can select depth one; stray END packets inflate game counts | `player.play` rejects reflex-only live configurations before NME and counts END only after initialization | `tests/test_engines.py`: engine/species lifecycle, invalid modes/depths, duplicate END |

## Independent and bounded exhaustive checks

`tests/test_balanced_edges.py` compares completed search with independent eager rational expectiminimax, checks interrupted/capped interval containment, tiny caches, root ordering, joint moves, maximum-depth cycles, invalid evaluations and unknown overflow/shared-combat values. Preparation checkpoints preserve eager outcome probabilities and ordinary streaming order; they carry no probability mass.

`tests/test_model_edges.py` contains:

- 32 tiny battles compared with independent per-creature event enumeration.
- 504 threshold/byte-boundary battles checked for exact mass and expected survivors.
- 98 battle cases with 1568 seeded samples checked against exact support.
- 48 small boards and 1008 exhaustive joint turns: 2364 exact successors and 2484 sampled successors. The 180 ambiguous shared-combat turns consistently reject under the live model.
- 216 deterministic merge turns, 12 byte-boundary transitions and 12 seeded trajectories covering 206 plies.

These establish invariants in the tested domain: source remainders, untouched cells, conservation without combat, non-increasing total population, no spontaneous humans/opponents, input/sibling independence and eager/stream/sample agreement. They do not establish official-server parity. No new combat formula defect was found.

Movement checks cover all six rules, source/destination disjointness, the 255-record cap, maximum coordinates, narrow boards and both species. Protocol checks cover every truncation offset of representative packets, maximum-count packets, coalescing, arbitrary fragmentation, zero counts, atomic malformed updates and BYE during every initialization stage.

## Limits kept explicit

- This is bounded exhaustive/property coverage, not every possible game or proof of winning play.
- Shared contested destinations, wider splitting semantics, populations above 255, duplicate update-coordinate behavior, independent simultaneous draws, daylight configuration and both-extinct/tied outcomes need official-server evidence.
- Impossible movement (extinction or a 1x1 board) raises `NoLegalMove`; no forbidden pass is fabricated. Malformed/truncated TCP streams terminate because silent resynchronization could corrupt a game.
- One cooperative quantum can include a distribution, board copy, generation or evaluation. Tiny budgets cannot guarantee useful examination of every root; the default transport margin is not a hard real-time proof. CTI measurements remain required.
- Candidate pruning can omit an important reply. Cohesive engines deliberately omit partial moves for both species; chance bounds do not certify absent branches.
- History limits cell records, not exact memory bytes. Eviction forgets old evidence and never declares a draw.
- Fallback legality is not a safety/strength guarantee; supported-move preference only checks the first movable source's neighbors.

Normal-budget match and TCP/stress evidence is linked in [the upgrade experiment](../experiments/2026-10-12-upgrade/EXPERIMENT.md).
