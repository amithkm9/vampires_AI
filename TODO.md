# Active tasks

Use [STATUS.md](STATUS.md) for current behavior and evidence, the [roadmap](docs/planning/ROADMAP.md) for course phases, and the [archived task log](docs/history/TASK_LOG_2026-10-13.md) for earlier completed work.

## Improve demonstrated weaknesses

- [ ] Investigate the repeated no-human endgame trailing 6 to 7. Compare a small endgame planner against opponent replies; preserve safe leads/ties and keep the live horizon unknown unless the server supplies it.
- [ ] Expand locked evaluation with independent maps/seeds and stronger opponents. The current one-game gain is insufficient to establish broad superiority.
- [ ] Model resource interception and denial; validate trap-map capture plans against opponent responses.
- [ ] Improve selective partial-move coverage only when exact witnesses and paired matches support the branching/strength tradeoff.
- [ ] Evaluate tactical extensions or sparse chance sampling as isolated experiments, retaining negative results and prior baselines.
- [ ] Profile retained search data and memory on the target runtime; cache entry caps are not byte-memory bounds.

See [NEXT_ALGORITHM.md](docs/NEXT_ALGORITHM.md) for the technical rationale and earlier evidence.

## Validate the official server and CTI launch

- [ ] Confirm CTI operating system, Python version and automatic launch convention; obtain access to an environment that can run the supplied Windows server.
- [ ] Create a separate working server configuration with a valid map, appropriate players and the two-second limit.
- [ ] Verify initialization, empty first UPD, legal MOV, END/restart and BYE against the supplied server.
- [ ] Resolve the recorded splitting, group-limit, shared-target combat and cutoff/tie ambiguities with instructor or server evidence; update [RULES.md](docs/RULES.md).
- [ ] Launch using the exact tournament command from a fresh working directory, with IP address and port last.
- [ ] Play both species on each supplied map while measuring the full UPD-to-MOV response time and recording failures.
- [ ] Repeat official-server and CTI checks after final strategy changes.

## Prepare and deliver

- [ ] Confirm submission deadline, tournament date, team members, final AI name, report format and permitted runtime versions.
- [ ] Write the report: rules, algorithms, complexity, timing, experiments, limitations and conclusions; map descriptions to actual files/functions.
- [ ] Prepare and rehearse a five-minute presentation with a strategy example and measured results.
- [ ] Package the source, launch instructions, required working assets and version assumptions.
- [ ] Audit final imports, run the relevant tests and verify original material integrity.
- [ ] Rehearse the clean package on CTI and against the official server.
- [ ] Submit source on edunao before the tournament and confirm report/presentation delivery requirements.
- [ ] Preserve the exact submitted commit and final result records.

Keep commits small and meaningful. Record seeds, maps, species, configuration and runtime before experiments; use fresh output paths and preserve earlier evidence.
