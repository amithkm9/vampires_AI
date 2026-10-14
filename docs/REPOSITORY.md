# Repository workflow

Repository: [amithkm9/vampires_AI](https://github.com/amithkm9/vampires_AI). Development uses ordinary, focused commits on `main`, tracking `origin/main`.

Before committing a behavioral change, run the relevant tests and review the diff:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
git diff --check
git diff
git status --short
```

Stage the intended files explicitly, commit with a descriptive message, and push with `git push origin main`. Separate distinct features, experiments and documentation when their dependencies permit. Preserve existing history.

Verify local and remote state with:

```sh
git status --short --branch
git log -5 --oneline
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

After a successful push, the local and remote head hashes should match. The initial eight-commit publication helper was removed during the October 14 cleanup: it only supported the original publication plan and was no longer usable for ongoing development. That history remains available in Git.

## What stays versioned

Supplied archives, the course brief, original vendor files, working maps, source code, tests, research provenance and experiment evidence are versioned. Downloaded research-paper PDFs stay local; their URLs, citations and SHA-256 provenance remain in `references.bib`, `notes/` and `sources/papers/manifest.json`.

Python caches, local environments, temporary files, environment secrets and league lock files are ignored. Preserve `materials/manifest.json` and the immutable source snapshots inside experiment directories. Historical records describe their exact recorded revisions; reorganizing current code does not justify rewriting earlier hashes or commands.

See the [structure guide](STRUCTURE.md), [tool guide](../tools/README.md) and [archived milestones](history/STATUS_2026-10-13.md) for navigation and older validation records.
