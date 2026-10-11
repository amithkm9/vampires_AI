# First playable baseline: local verification

Date: 2026-10-09. Runtime: Python 3.14.6 on this Mac. Source remains compatible with Python 3.10+ syntax; that minimum version has not been executed here. No external dependency was installed.

## Automated checks

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Observed result: **105 tests passed**, 0.525 seconds. The suite includes the previous 56 foundation/simulation tests, 19 combined-turn tests, 13 evaluation/search tests, and 17 player/timed-protocol/launcher tests.

| Area | Evidence |
| --- | --- |
| Six movement rules | Existing rule tests plus whole-turn rejection of overspending, swaps, chains, illegal ownership, empty turns, and border errors |
| Combined movement | Source remainders, wider offline splits, independent moves, empty/friendly shared arrivals, and 255-record turns |
| Exact chance | Product probabilities for two battles, normalization, order independence, full comparison with the independent single-move model |
| Isolation and limits | Input/sibling boards do not share mutable dictionaries; overflow and branch-limit actions fail explicitly |
| Candidate correctness | Exhaustive small-board enumeration compared with a separate combinations/filter construction; 30 seeded positions checked for legality and total-population conservation |
| Opponent lookahead | On `thetrap`, vampire depth one chooses `(4,3)->(3,2)`; depth two chooses `(4,3)->(3,3)` with the whole group. Werewolf depth two chooses `(4,1)->(3,1)` |
| Chance search | Forced equal one-creature battle has expected neutral score, rather than a worst-outcome score; a separate nested reference agrees with two-ply evaluation |
| Deadline retention | Expired budgets return legal fallback; interruption of a deeper iteration retains the complete shallower result; unfinished chance work is not scored as complete |
| Protocol lifecycle | Empty UPD triggers a move, MAP alone does not, authoritative updates replace predictions, END resets species, NME is sent once, BYE exits |
| Transport errors | Fragmentation, EOF, unknown/non-ASCII commands, malformed updates, stalled UPD payload, shared absolute fragment deadline, late-send rejection, restored socket timeouts |
| Launch contract | Help and argument validation from another working directory; invalid budget/depth/name/port fail before network access |

All **13 original/extracted material hashes** in `materials/manifest.json` matched after implementation. Runtime imports were inspected: only the standard library and project modules are used. Originals under `vendor/`, `materials/archives/`, and `docs/reference/` were not edited.

## Real local TCP smoke runs

```sh
python3 tools/check_player.py --output reports/player-smoke-2026-10-09.json
python3 tools/check_player.py --budget 1.25 --depth 3 --max-plies 20 --output reports/player-default-smoke-2026-10-09.json
```

The harness starts the real `run.py` subprocess from a temporary unrelated directory and uses a loopback TCP listener. Each run keeps one connection for four matches: both species on both maps. The harness verifies every MOV against the pre-move board and waits for a clean BYE exit. Local socket binding needed an approved command escalation in this session.

| Configuration | Matches | AI turns | Observed maximum response | Termination |
| --- | ---: | ---: | ---: | --- |
| 0.05-second search, depth 2, 40-ply cap | 4 | 50 | 0.050185 s | Two extinction, two harness ply-cap endings |
| Normal 1.25-second search, depth 3, 20-ply cap | 4 | 30 | 1.250229 s | Two extinction, two harness ply-cap endings |

All 80 observed AI turns were legal and below two seconds on this Mac. JSON records include seeds 20261009–20261012, map/species, starting species, settings, source/map hashes, per-turn timings, termination reasons, and final populations. Records: [short-budget run](player-smoke-2026-10-09.json), [normal-budget run](player-default-smoke-2026-10-09.json).

These are integration tests against a seeded random whole-group opponent and our own simulator. They are not win-rate estimates, independent model verification, or evidence of official-server/CTI compatibility. Wall-clock interruption can change actions even with fixed random seeds.

## Search edge cases

```sh
python3 tools/check_search.py --output reports/search-stress-2026-10-09.json
```

Eight probes covered both species on a crowded 8x8 board, 255-versus-255 combat, a 255-row one-column board, and a possible conversion-overflow position. All returned legal moves. Maximum observed search time under the 0.05-second budget was **0.050120 seconds**. The [JSON record](search-stress-2026-10-09.json) stores complete positions, configuration, source hashes, and decision diagnostics.

The crowded boards reached the budget during generation and used the legality fallback. Large random battles retained completed root-action work without finishing the root iteration. Long-column positions completed depth three. Overflow probes counted an unsupported action and eventually fell back. These observations identify next-build priorities; they do not establish a worst-case timing bound.

## Outstanding acceptance gates

- Official interpretation and testing of shared-target combat, split-record limits, overflow, and simultaneous extinction.
- Official-server handshake, matches, restart/shutdown, and exact CTI launcher/runtime checks.
- Better partial candidate generation, bounded large chance nodes, multi-house growth/denial, and dominant-stack preservation.
- Paired strength benchmarks, held-out maps, ablations, alternative search comparisons, and CTI timing measurements.
- Final course report, five-minute presentation, and source submission.
