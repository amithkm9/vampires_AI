# vampires_AI

Build an AI for the Foundation of AI tournament. The game is a fully observable grid contest: convert humans, grow your species, anticipate the opponent, and finish with the dominant population. Battles can be random. Each turn must be sent to the supplied server within **two seconds**.

The supplied materials have been organized and the first implementation milestone is complete. The project contains a tested protocol, board model, move validator, exact single-move simulator, and reproducible map analysis. **There is no playable strategy or tournament launcher yet.**

## Start here

1. Read [the course rules and implementation decisions](docs/RULES.md).
2. Follow [the roadmap from setup to submission](docs/planning/ROADMAP.md).
3. Work through [the live task list](TODO.md), starting at Phase 2.
4. Read [the current status](STATUS.md) before resuming work.
5. Read [the tournament algorithm design](docs/STRATEGY.md) and [exact map findings](reports/map-analysis-2026-10-09.md) before implementing search.

## What was supplied

| Material | Location | Purpose |
| --- | --- | --- |
| Nine-page project brief | [Projectv10.pdf](docs/reference/Projectv10.pdf) | Authoritative assignment, game rules, and protocol |
| Searchable brief | [Projectv10.txt](docs/reference/Projectv10.txt) | Extracted text; use the PDF for diagrams and formulas |
| Original ZIPs | `materials/archives/` | Preserved source archives |
| Starter kit | `vendor/starterkit/` | Original incomplete Python example |
| Server version 3.2.1 | `vendor/server/` | Windows .NET server, two DLLs, original configuration |
| Map generator | `vendor/map-generator/` | Windows executable and original XML maps |
| Working maps | `maps/` | Copies of `testmap2.xml` and `thetrap.xml` |
| Integrity record | [manifest.json](materials/manifest.json) | Sizes, original names, and SHA-256 hashes |

Original file contents were preserved; only their locations changed. See the [source audit](docs/planning/SOURCE_AUDIT.md) for starter-kit defects and configuration discrepancies.

## Working code

| File | Responsibility |
| --- | --- |
| `src/vampires/model.py` | Board, XML map loading, species identity, and game reset |
| `src/vampires/protocol.py` | Exact TCP reads, packet parsing, complete sends, validated MOV packets |
| `src/vampires/rules.py` | All six move rules, combat probabilities, expected survivors, battle sampling |
| `src/vampires/simulation.py` | Exact rational battle outcomes and one-record turn transitions |
| `tests/test_foundations.py`, `tests/test_simulation.py` | 56 tests, including a persistent local socket exchange and tactical/map regressions |
| `tools/inspect_map.py` | Read a map without running the Windows generator |
| `tools/analyze_maps.py` | Reproduce exact local reply risks and optimistic capture-route calculations |

All working Python code uses the standard library. The current syntax targets Python 3.10 or newer; local validation used Python 3.14.6. Confirm the Python version available on CTI before selecting the final runtime. No dependency installation is needed for the current code.

From this project directory on macOS or Linux:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/inspect_map.py maps/testmap2.xml
python3 tools/inspect_map.py maps/thetrap.xml
python3 tools/analyze_maps.py --output reports/map-analysis-2026-10-09.json
```

On Windows PowerShell, set `$env:PYTHONPATH = "src"` and use `python -m unittest discover -s tests -v`.

The server executables target Windows .NET Framework; they have not been run here. The local socket test checks our protocol against a small fixture, not against the official server. The future tournament command must accept the server address and port as its final two arguments (brief p. 9).

## Completion requirements

The finished project needs an opponent-aware AI, successful CTI launch and official-server communication, benchmark evidence on both species, a report mapping algorithms to code, a five-minute presentation, and source submission on edunao before the tournament. The deadline and CTI environment remain to be confirmed.
