# Project instructions

This directory is the active Foundation of AI course project. Keep project code, notes, experiments, and deliverables here.

Before continuing, read `README.md`, `STATUS.md`, `TODO.md`, and `docs/RULES.md`. The authoritative assignment is `docs/reference/Projectv10.pdf`. Record conflicts and unresolved details rather than silently deciding that a supplied example overrides the brief.

## Course requirements

- Do not use libraries implementing AI, trees, graphs, or similar algorithms. Implement the search, evaluation, move generation, and board algorithms ourselves. Current code uses the Python standard library only; that does not authorize a prohibited algorithm library just because it is available locally.
- The finished strategy must consider the opponent's moves; a reflex-only agent does not satisfy the assignment.
- Obey all six move rules and the binary protocol described in the brief.
- Use the brief's two-second turn deadline. The supplied five-second server setting is not permission to exceed it.
- The final launch command must accept the IP address and port as its last two arguments, and run on CTI machines.
- Keep report explanations traceable to actual files and functions. Do not invent experimental results or claim tournament readiness without an official-server and CTI launch check.
- Deliver the source before the tournament, a report, and a five-minute presentation. Preserve the course's requirement to play both species on each map.

## Workspace conventions

- Keep completed work in frequent, small, meaningful Git commits with descriptive messages. Separate distinct features, tests, experiments, and documentation when their dependencies permit.
- Preserve `materials/archives/`, original files in `vendor/`, and the reference PDF. Edit working source under `src/` and working map copies under `maps/`.
- Use `materials/manifest.json` to verify original material integrity.
- Update `TODO.md` and `STATUS.md` when a milestone changes. Record validation commands and material limitations.
- Keep multi-move and server-behavior ambiguities visible in `docs/RULES.md`; distinguish tested facts from assumptions.
- Record experiment seeds, map, species, configuration, runtime, and results when experiments begin.
- Run the relevant tests after behavioral changes. Do not confuse mock protocol tests with official-server validation.
