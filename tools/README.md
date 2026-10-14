# Tool guide

Run these commands with Python 3.10+ from the repository root. Direct script invocation also works from another directory when given an absolute script path; map/output arguments remain relative to the caller's directory. Use `--help` for arguments. Choose fresh output files/directories to preserve previous evidence.

## Current tools

| Command | Purpose |
| --- | --- |
| `python3 tools/inspect_map.py` | Inspect a working XML map |
| `python3 tools/analyze_maps.py` | Exact local reply risks and optimistic capture-route analysis |
| `python3 tools/check_player.py` | TCP launcher smoke matches, both maps/species and restart lifecycle |
| `python3 tools/check_search.py` | Search timing and legality stress cases |
| `python3 tools/check_limits.py` | Maximum-board and budget probes |
| `python3 tools/check_tactics.py` | Candidate/reply coverage against exact tiny trees |
| `python3 tools/check_outcomes.py` | Decision regret against finite-horizon outcomes |
| `python3 tools/league.py` | Paired opponent league with immutable source snapshots and resumable records |
| `python3 tools/analyze_league.py` | Verify and diagnose recorded league replays |

`league_support.py` is an imported helper, not a separate command. The league uses POSIX file locking and runs matches serially for timing comparisons. Its records include both species, seeds, source provenance, failures and response times. See the [registered league experiment](../experiments/2026-10-13-league/EXPERIMENT.md) for the evaluation protocol.

For an existing league run, retain its `snapshots/` directory. Resume it using that run's archived `snapshots/harness/tools/league.py` with `--resume` and the run's absolute path, as documented in the experiment record. Settings are restored from the original metadata. The current replay analyzer loads recorded runtime snapshots. Never edit frozen sources or overwrite old hashes to make a changed harness resume.

## Historical tools

Earlier benchmark formats remain available under `legacy/`:

| Former path | Current path |
| --- | --- |
| `tools/benchmark_strength.py` | `tools/legacy/benchmark_strength.py` |
| `tools/benchmark_long.py` | `tools/legacy/benchmark_long.py` |
| `tools/benchmark_upgrade.py` | `tools/legacy/benchmark_upgrade.py` |
| `tools/analyze_replays.py` | `tools/legacy/analyze_replays.py` |

Invoke these directly, for example `python3 tools/legacy/benchmark_strength.py --help`. Their earlier data formats and failure-scoring conventions differ from the league; use the current league for new promotion decisions. The legacy replay analyzer requires the source version recorded by its experiments. Moving it does not make old runtime hashes compatible with current source.

Historical experiment records retain their original commands and hashes. Use the recorded Git revision when reproducing them exactly. The obsolete initial-publication helper has been removed; use the ordinary [Git workflow](../docs/REPOSITORY.md).
