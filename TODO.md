# Project task list

Work from top to bottom. A checked task has evidence in the files or verification record; a phase is complete only after its acceptance condition in [the roadmap](docs/planning/ROADMAP.md) passes.

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
- [ ] Generate a small, useful set of legal combined turns.
- [ ] Preserve a cheap legal fallback whenever a turn is playable.
- [x] Apply one-record moves without mutating the original board.
- [x] Model single-record movement to empty cells, partial movement, and friendly merging.
- [x] Enumerate exact enemy/human battle branches using rational probabilities.
- [ ] Extend outgoing budgets and transitions to complete multi-record turns.
- [ ] Verify same-target aggregation and resolution order against the official server before claiming exact multi-group simulation.
- [x] Keep uncertain single-battle outcomes explicit; never round survivors into an expected board.
- [x] Test single-move conservation, conversion, extinction, and explicit rejection of possible overflow.
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

- [ ] Implement evaluation: population advantage, reachable humans, immediate threats, and vulnerable groups.
- [ ] Implement at least our move followed by an opponent reply, with documented handling of chance.
- [ ] Demonstrate a tactical case where opponent lookahead changes the selected move.
- [ ] Add a CLI with address and port as the final arguments and a valid ASCII team name.
- [ ] Connect NME, initialization, UPD, decision, validation, MOV, END, and BYE in one process.
- [ ] Play a full match in a protocol harness, then against the official server as soon as access exists.
- [ ] Save enough logs to diagnose invalid moves, disconnects, and timing failures.

## Phase 4 Improve search within two seconds

- [ ] Add a monotonic clock deadline and return the last completed result or legal fallback.
- [ ] Start with an internal search budget below two seconds; measure send/update overhead on CTI.
- [ ] Implement deeper search and move ordering ourselves after the baseline works.
- [ ] If needed, implement our own cache of evaluated positions and bounded action candidates.
- [ ] Evaluate permitted one-destination partial splits; expand multiple outgoing records only after the record limit is resolved.
- [ ] Stress-test busy boards, many groups, and stochastic branches.
- [ ] Record worst-case response time and repeated deadline behavior.

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

## Information to confirm

- [ ] Submission deadline and tournament date.
- [ ] Team members and final AI name.
- [ ] Additional rules, report template/length, and permitted runtime versions.
- [ ] Official interpretation of ambiguous splitting and combat-resolution behavior.
