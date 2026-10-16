# Code and repository structure

`run.py` is the public player entry point. It finds `src/` relative to its own location and accepts the server IP address and port as its final two arguments. The repository needs no third-party runtime dependencies.

## Runtime code

All module names below are relative to `src/vampires/`.

| Module | Responsibility |
| --- | --- |
| `model.py` | Board, species, XML maps and authoritative session updates |
| `protocol.py` | Binary messages, exact TCP reads, complete writes and network deadlines |
| `rules.py` | Move legality, combat probabilities and sampled single battles |
| `simulation.py` | Exact and streaming joint transitions, sampled turns and explicit model limits |
| `turns.py` | Legal fallback, bounded candidates and exhaustive small-position moves |
| `budget.py` | Cooperative monotonic deadlines |
| `evaluation.py` | Baseline bounded heuristic and terminal scores |
| `planning.py` | Default strategic evaluation: outcome-oriented endings and sequential exclusive conversion races |
| `search.py` | Sequential expectiminimax and shared search configuration |
| `balanced.py` | Resumable search, chance intervals, root scheduling and reusable work |
| `strategy.py` | Intact-group generator and alternative resource/portfolio policies |
| `certificates.py` | Conditional dominant-stack preservation |
| `endgame.py` | Exact finite-horizon offline outcome reference |
| `history.py` | Bounded authoritative repetition diagnostics |
| `engines.py` | Selectable engines, default depth and routing |
| `player.py` | Persistent protocol loop and CLI |
| `experimental/growth.py` | Optional multi-house growth planning |
| `experimental/mcts.py` | Optional sampled adversarial UCT |
| `experimental/hybrid.py` | Optional critical partial-move generation |

The experimental package contains tested alternatives, not abandoned code. `hybrid` and `hybrid_adaptive` remain selectable player modes; growth and UCT remain available to historical benchmarks. The cleanup preserved engine names and its then-default adaptive engine. The October 15 experiment subsequently selected `strategic` at depth five; `outcome` and `tactical` retain its ablations. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for function-level behavior and limitations.

## Tools and tests

The [tool guide](../tools/README.md) separates current commands from older experiment formats. `tools/league_support.py` is shared league infrastructure. `tools` remains a namespace package so archived harness imports continue to work; `tools/legacy/` groups the earlier scripts.

Tests stay in `tests/test_*.py`, grouped by behavior. Run discovery with `PYTHONPATH=src python3 -m unittest discover -s tests -q`. Tools that record current runtime provenance capture Python files recursively, including the experimental package. Historical Git exports preserve that package hierarchy.

`test_lifecycle.py` checks that temporary search/transition state releases after
normal completion, timeouts and errors. `test_report_outputs.py` protects existing
evidence from accidental overwrite. `tools/check_runtime.py` records repeatable
combat and allocation comparisons against a Git revision, separately from match
strength and end-to-end timing checks.

## Documentation and evidence

- Root `README.md`, `STATUS.md` and `TODO.md` provide entry points, current evidence and open work.
- `docs/` holds current technical explanations; `docs/planning/` holds the course roadmap and initial source audit.
- `docs/history/` preserves earlier status/task pages, with historical commands identified as such.
- `experiments/` and `reports/` retain seeds, configurations, outcomes, diagnostics and exact source snapshots. Repeated source files are intentional evidence.
- `notes/`, `sources/` and `references.bib` retain research and provenance.
- `maps/` contains working copies; `materials/archives/`, `vendor/` and `docs/reference/` preserve the supplied inputs. Verify them against `materials/manifest.json`.

The cleanup removed the obsolete initial-publication script and five unused imports. It moved three experimental algorithm modules and four historical tools, without removing an engine or changing gameplay. Generated Python bytecode caches can be deleted; experiment snapshots and original materials must be retained. To reproduce an old run, use its recorded revision or snapshot rather than expecting its hashes to match reorganized current code.
