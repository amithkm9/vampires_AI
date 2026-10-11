# Project task list

Work from top to bottom. A checked task has evidence in the files or verification record; a phase is complete only after its acceptance condition in [the roadmap](docs/planning/ROADMAP.md) passes.

## Active build: first playable baseline

1. [x] Implement legal combined turns, a mandatory-move fallback, and independent small-board enumeration checks.
2. [x] Extend exact transitions to joint turns; reject unverified shared-target battles by default and make branch/overflow limits explicit.
3. [x] Implement bounded evaluation and opponent-aware expectiminimax, with deadline checks inside expensive work.
4. [x] Integrate the persistent protocol loop and a launcher whose last arguments are IP address and port.
5. [x] Exercise complete local harness matches, both species, restart, disconnects, malformed input, and deadline fallback.
6. [x] Record evidence, limitations, and the next improvement tasks. Official-server and CTI checks remain separate acceptance gates.

## Next build priorities

Follow [the next-algorithm plan](docs/NEXT_ALGORITHM.md), using [verified replay findings](reports/replay-analysis-2026-10-11.md) to prioritize changes.

1. [ ] Add exact finite-horizon outcome references and repetition diagnostics; distinguish a known cutoff from the live protocol's unknown remaining horizon. Preserve leading/drawing repetitions when appropriate.
2. [ ] Measure tactical value lost through candidate pruning against the exhaustive small-board oracle; protect critical opponent replies and compare serious root actions before deep refinement.
3. [ ] Refine competing root chance intervals and add bounded tactical extensions; compare sparse-sampled expectiminimax under the normal budget.
4. [ ] Add interception and contested-route checks to the growth planner; explicitly test the trap's four-versus-five human race and the large map's central-house denial.
5. [ ] Verify shared-target attacks, wider splitting, overflow, and both-extinct outcomes on the official server; then extend the live candidate set.
6. [ ] Rehearse the exact launch command on CTI and measure receive/search/send timing there.
7. [ ] Expand paired benchmarks to stronger opponents, new map families, normal budgets, and feature ablations before selecting the final engine.

## Replay diagnosis completed on 2026-10-11

- [x] Reconstruct all 108 stored matches and 6778 plies with recorded moves/seeds, verifying final outcomes and input/source hashes.
- [x] Preserve per-match combat events, repeated states, and first trailing/unfinished-search positions with a reusable replay tool.
- [x] Identify three default-engine trap losses at 0.1 seconds without monster or random combat; record the 8–9 resource outcome and repeated-state behavior.
- [x] Turn those observations into prioritized methods and acceptance checks. Do not label the losses proven avoidable without counterfactual/adversarial analysis.
- [ ] Compare alternative decisions from the recorded resource-race positions under opponent responses; create regression fixtures for any demonstrated avoidable mistake.

## Strength audit completed on 2026-10-11

- [x] Retain useful partial candidate generation and cap joint-combination work.
- [x] Replace silent removal of large chance actions with explicit unvisited-mass bounds.
- [x] Implement and test conditional dominant-stack preservation.
- [x] Implement experimental multi-house reachability with exclusive house credit and central-house denial regression.
- [x] Implement a seeded sampled adversarial UCT challenger using integer battle outcomes.
- [x] Compare all three variants against the immutable published baseline: 108 local matches across two budgets and two horizons, both species.
- [x] Preserve raw records, negative results, configurations, source/map hashes, and limitations in the [experiment record](experiments/2026-10-11-strength/EXPERIMENT.md).
- [x] Pass 122 tests. Keep growth and UCT experimental because the comparison does not establish a decisive improvement.

## Phase 0 Understand and organize

- [x] Inventory all inputs and inspect ZIP members before extraction.
- [x] Preserve the PDF and archives; extract the starter kit, server, and map generator.
- [x] Copy supplied maps into a working maps directory.
- [x] Record sizes and SHA-256 hashes; verify extracted content.
- [x] Read every PDF page and every supplied text source/configuration/map.
- [x] Record requirements, starter-kit defects, ambiguities, and roadmap.

## Phase 1 Build the rules and protocol foundation

- [x] Use only the Python standard library for working code.
- [x] Implement exact packet reads, EOF handling, and `sendall` writes.
- [x] Parse SET, HUM, HME, MAP, UPD, END, and BYE.
- [x] Encode ASCII NME and correctly ordered MOV bytes.
- [x] Implement rectangular coordinates, replacement updates, and cleared cells.
- [x] Identify our species from HME and MAP; reset state after END.
- [x] Validate all six movement rules before sending.
- [x] Implement deterministic thresholds, random battle odds, and seeded battle sampling.
- [x] Test fragmented packets, illegal turns, thresholds, both species, and persistent game reset.

## Phase 2 Implement candidate turns and the forward model

- [x] Enumerate all one-record turns, including every partial movement amount.
- [x] Generate a small, useful set of legal combined turns.
- [x] Preserve a cheap legal fallback whenever a turn is playable.
- [x] Apply one-record moves without mutating the original board.
- [x] Model single-record movement to empty cells, partial movement, and friendly merging.
- [x] Enumerate exact enemy/human battle branches using rational probabilities.
- [x] Extend outgoing budgets and transitions to complete multi-record turns under an explicit shared-target policy.
- [ ] Verify same-target aggregation and resolution order against the official server before claiming exact multi-group simulation.
- [x] Keep uncertain single-battle outcomes explicit; never round survivors into an expected board.
- [x] Test single/joint-move conservation, conversion, extinction, input isolation, exact chance products, and explicit overflow/branch rejection.
- [ ] Resolve official-server overflow and both-species-extinct behavior; verify multi-record cases.

## Strategy analysis and decision evidence

- [x] Re-read the supplied materials and verify original hashes.
- [x] Audit safe and exposed trap-map approaches against every legal immediate one-record reply.
- [x] Verify the central-house resource bottleneck, exact battle expectations, and optimistic route bounds.
- [x] Save a bounded primary-literature comparison, source matrix, and algorithm design in `docs/STRATEGY.md`.
- [x] Prototype capture-race and denial features without double-counting human credit; validate contested routes before promoting them.
- [ ] Preserve all tactical replies on small positions; measure effects of candidate pruning on larger ones.
- [x] Run an initial equal-budget bounded-search/basic-UCT comparison; stronger sampled expectiminimax and tactical MCTS remain future work.
- [x] Implement and test the dominant-stack preservation certificate.

## Phase 3 Produce the first playable opponent-aware AI

- [x] Implement evaluation: population advantage, current-stack house races, immediate threats, and vulnerable groups. Safe routes remain future work; multi-house growth is experimental.
- [x] Implement at least our move followed by an opponent reply, with documented handling of chance.
- [x] Demonstrate a tactical case where opponent lookahead changes the selected move.
- [x] Add a CLI with address and port as the final arguments and a valid ASCII team name.
- [x] Connect NME, initialization, UPD, decision, validation, MOV, END, and BYE in one process.
- [x] Play complete local TCP harness matches on both maps as both species, including END/restart and BYE.
- [ ] Play against the official server as soon as access exists.
- [x] Log turn depth, nodes, selective/unsupported actions, timing, moves, and explicit protocol failures.

## Phase 4 Improve search within two seconds

- [x] Add a monotonic clock deadline and return the last completed result or legal fallback.
- [x] Use a 1.25-second default search budget and time UPD parsing through MOV transmission.
- [ ] Measure receive/send/update overhead and deadline behavior on CTI.
- [x] Implement deeper search and move ordering ourselves: iterative depth, exact chance values, and cheap move priorities.
- [x] Implement a bounded per-search cache and bounded action candidates.
- [x] Evaluate permitted one-destination partial splits; support wider splitting in the offline oracle within the conservative record limit.
- [ ] Extend live wider splitting only after server verification and measured pruning coverage.
- [x] Stress-test busy boards, many groups, byte-boundary populations, and stochastic branches locally.
- [x] Record the observed maximum response and deadline behavior for the tested local cases; no universal timing bound claimed.

## Phase 5 Validate the official server and CTI launch

- [ ] Confirm CTI operating system, Python version, and automatic launch convention.
- [ ] Create a separate working server configuration with a valid map, two AI players when appropriate, and the two-second limit.
- [ ] Verify handshake, empty first UPD, legal MOV, END/restart, and BYE against the supplied server.
- [ ] Check protocol/group-limit ambiguities and update the rule decisions with evidence.
- [ ] Launch using the exact tournament command from a fresh working directory.
- [ ] Play both species on each supplied map without launch, protocol, or illegal-move failures.
- [ ] Rehearse on CTI early; repeat after the final strategy changes.

## Phase 6 Measure and improve playing strength

- [ ] Build a small random/legal and greedy comparison player for experiments only.
- [x] Run initial paired games with species swapped on both supplied maps and two generated maps; expand coverage before final selection.
- [x] Record seeds, map, species, opponent, algorithm settings, win/loss/draw, failures, and timing.
- [ ] Run ablations for lookahead, human capture terms, threat terms, and optional splitting.
- [ ] Inspect losses and improve the demonstrated weakness; keep the prior working baseline.
- [ ] Choose the final configuration using reproducible evidence.

## Phase 7 Prepare and deliver

- [ ] Write the report: problem, rules, algorithms, complexity, timing, experiments, limitations, and conclusions.
- [ ] Map every described algorithm to its actual file and function.
- [ ] Prepare and rehearse a five-minute presentation with a strategy example and measured results.
- [ ] Package source, launch instructions, required working assets, and version assumptions.
- [ ] Audit imports and verify no prohibited algorithm libraries are included.
- [ ] Rehearse the clean package on CTI and against the official server.
- [ ] Submit source on edunao before the tournament; confirm required report/presentation delivery details.
- [ ] Preserve the exact submitted version and final result records.

## Repository publication

- [x] Organize the initial project into eight meaningful commit groups.
- [x] Verify original material hashes and rerun all 56 tests before publication.
- [x] Publish to `amithkm9/vampires_AI` using standard Git and configure `main` to track `origin/main`.
- [x] Organize the playable baseline into 10 additional meaningful commits and rerun all 105 tests before publication on 2026-10-11.
- [x] Organize the strength audit, algorithms, 122-test regression suite, and 108-match evidence into 20 additional meaningful commits; retain frequent focused commits as a project convention.

## Information to confirm

- [ ] Submission deadline and tournament date.
- [ ] Team members and final AI name.
- [ ] Additional rules, report template/length, and permitted runtime versions.
- [ ] Official interpretation of ambiguous splitting and combat-resolution behavior.
