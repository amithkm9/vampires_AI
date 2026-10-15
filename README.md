# vampires_AI

An opponent-aware AI for the Foundation of AI tournament. Convert humans, anticipate the opponent, and finish with the dominant population. The implementation uses Python 3.10+ and the standard library only. Each turn must reach the server within **two seconds**.

## Run

Put the server IP address and port last:

```sh
python3 run.py --name vampires_AI --budget 1.25 127.0.0.1 5555
```

Replace the address and port with the server's values. From another directory, use the absolute path to `run.py`; no installation or `PYTHONPATH` setup is needed. Use `python3 run.py --help` for options.

The provisional default is `strategic` at depth five, with a 1.25-second search budget. It adds outcome-oriented endgame scoring and sequential human conversion races to the existing opponent-aware search. The previous default remains available as `--engine adaptive --depth 5`; `cohesive_material --depth 3` is also retained. Completed shallower decisions survive a deeper search timeout.

The project has **274 passing tests**. In the latest locked local comparison, the new agent scored **17 wins, 8 draws, 11 losses**, versus **14/8/14** for adaptive. Four cases improved and one regressed; the benefit was concentrated in endgames, and statistical uncertainty remains wide. **Official-server and CTI validation remain pending.** See [current status](STATUS.md) and the [strategy experiment](experiments/2026-10-15-strategy/EXPERIMENT.md).

## Project layout

| Location | Contents |
| --- | --- |
| `run.py`, `src/vampires/` | Launcher, protocol, board, rules, search and engine selection |
| `src/vampires/experimental/` | Optional growth, UCT and partial-move algorithms |
| `tests/` | Rules, search, protocol, timing and experiment-integrity tests |
| `tools/` | Current validation, map analysis and opponent-league commands |
| `tools/legacy/` | Earlier benchmark and replay formats |
| `maps/` | Working map copies |
| `docs/`, `docs/history/` | Current technical documentation and archived milestones |
| `experiments/`, `reports/` | Reproducible experiment records, snapshots and validation results |
| `notes/`, `sources/`, `references.bib` | Research notes, source provenance and bibliography |
| `materials/`, `vendor/`, `docs/reference/` | Preserved supplied materials and authoritative assignment |

Use the [code map](docs/STRUCTURE.md) and [tool guide](tools/README.md) to find implementation details and commands. Experiment source snapshots are intentional: their exact contents are required to verify earlier results.

## Develop and validate

From the project directory on macOS or Linux:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
python3 tools/inspect_map.py maps/thetrap.xml
python3 tools/check_player.py --engine strategic --depth 5 --budget 1.25 --max-plies 20 --output reports/NEW_SMOKE.json
python3 tools/league.py --help
```

Choose a fresh output path for each recorded run. In Windows PowerShell, set `$env:PYTHONPATH = "src"` and use `python -m unittest discover -s tests -q`. The offline league requires POSIX file locking; this is separate from the player runtime.

The TCP harness checks our launcher and protocol against our own simulator. It does not replace official-server testing. CTI interpreter availability and timing still need measurement.

## Read next

- [Current work](TODO.md), [status](STATUS.md) and [course roadmap](docs/planning/ROADMAP.md).
- [Assignment rules and unresolved server behavior](docs/RULES.md), plus the [binary protocol](docs/PROTOCOL.md).
- [Implemented algorithms and limitations](docs/IMPLEMENTATION.md), [next algorithm priorities](docs/NEXT_ALGORITHM.md) and [edge-case audit](docs/EDGE_CASE_AUDIT.md).
- [Repository workflow](docs/REPOSITORY.md) and [original-material manifest](materials/manifest.json).

The [project brief](docs/reference/Projectv10.pdf) is authoritative. Completion requires source submission before the tournament, successful official-server and CTI launch checks, play as both species on each map, an implementation-linked report, and a five-minute presentation.
