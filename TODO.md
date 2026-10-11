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

1. [ ] Make candidate generation retain useful partial results when crowded boards exhaust its budget; measure opponent-reply coverage against the exhaustive small-board oracle.
2. [ ] Replace skipped over-limit chance actions with explicit value bounds or a measured sampled mode; avoid optimistic estimates caused by missing opponent replies.
3. [ ] Add multi-house growth and denial analysis, including the central-house bottleneck and the dominant-stack preservation certificate.
4. [ ] Verify shared-target attacks, wider splitting, overflow, and both-extinct outcomes on the official server; then extend the live candidate set.
5. [ ] Rehearse the exact launch command on CTI and measure receive/search/send timing there.
6. [ ] Start paired strength benchmarks, ablations, and the sampled-search/MCTS comparison. Keep integration smoke results separate from win-rate claims.

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
- [ ] Implement capture-race and denial features without double-counting humans.
- [ ] Preserve all tactical replies on small positions; measure effects of candidate pruning on larger ones.
- [ ] Compare exact/bounded and sampled expectiminimax with a tactical MCTS challenger under equal budgets.
- [ ] Implement and test the dominant-stack preservation certificate.

## Phase 3 Produce the first playable opponent-aware AI

- [x] Implement evaluation: population advantage, current-stack house races, immediate threats, and vulnerable groups. Safe routes and multi-house growth remain future work.
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
- [ ] Benchmark paired games with sides swapped on both supplied maps and additional varied maps.
- [ ] Record seeds, map, species, opponent, algorithm settings, win/loss/draw, failures, and timing.
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

## Information to confirm

- [ ] Submission deadline and tournament date.
- [ ] Team members and final AI name.
- [ ] Additional rules, report template/length, and permitted runtime versions.
- [ ] Official interpretation of ambiguous splitting and combat-resolution behavior.
