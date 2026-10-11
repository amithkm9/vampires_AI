# GitHub repository

Repository: https://github.com/amithkm9/vampires_AI

The publishing script organizes the initial project into eight commits: project introduction; supplied materials and maps; assignment rules; board and combat model; TCP protocol and foundation tests; exact simulation; strategy research and map analysis; and roadmap/status documentation.

Downloaded research-paper PDFs are local reference copies, excluded by `.gitignore`. Their original URLs, citations, and SHA-256 provenance remain in `references.bib`, `notes/`, and `sources/papers/manifest.json`. The user-supplied course brief, archives, server files, starter kit, and maps are versioned.

## Publish from this folder

Run the prepared script in a normal terminal with GitHub authentication and permission to create `.git`:

```sh
cd "/Users/amithkm/Documents/MS in Foundation of AI"
python3 tools/publish_repository.py --dry-run
python3 tools/publish_repository.py --push
```

The script checks original material hashes, repository identity, existing history, and all tests before committing. It stages explicit file groups, makes eight nonempty commits, pushes `main` without force, sets its upstream, and checks that GitHub's head matches. It can resume a partially completed run when earlier commits and their files still match this plan. Unexpected local or remote history stops publication rather than being overwritten.

The dry run only reads project files and does not invoke Git. Downloaded research PDFs, Python caches, temporary files, and environment files are excluded. If terminal Git requests authentication, complete GitHub authentication locally; do not paste tokens into project files or chat.

## Publication status

Standard Git successfully pushed `main` to the repository on 2026-10-09 and configured `origin/main` as its upstream. The successful publication used ordinary `git add`, `git commit`, and `git push` commands following the eight groups above. The helper script was checked in dry-run mode; its write mode was not used. No plugin was used for the successful publication.

Earlier attempts were blocked by session restrictions on `.git` writes and terminal network access. User-approved command escalation allowed the Git commands to complete. All 56 tests passed before committing, and all 13 original/extracted material hashes matched.

Verify the final history and compare the local head with GitHub using:

```sh
git log --oneline --reverse
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

The initial history contains eight commits. After a successful push, the two head hashes should match and the working tree should be clean. Future development uses ordinary new commits; the helper is limited to the initial eight-commit publication plan.

## Playable-baseline update, 2026-10-11

This update adds 10 meaningful commits on top of the original eight, without rewriting their history:

1. Cooperative monotonic search deadlines.
2. Exact joint-turn simulation and explicit model limits.
3. Legal combined-turn generation and edge-case tests.
4. Bounded board evaluation and human-house races.
5. Opponent-aware expectiminimax and tactical/deadline tests.
6. Absolute deadlines for UPD reads and MOV sends.
7. Persistent player loop and portable launcher.
8. Local TCP match harness and client lifecycle tests.
9. Reproducible smoke/stress checks and validation records.
10. Launch documentation, implementation notes, rules, and next-work checklist.

Before this update, `PYTHONPATH=src python3 -m unittest discover -s tests -q` passed all 105 tests in 0.578 seconds. All 13 original material hashes matched, as did the source hashes in the three October 9 smoke/stress JSON records. Those records describe the earlier runs; publishing them does not imply new official-server or CTI validation.

Use `git rev-list --count HEAD` to inspect the total history (18 commits at this update), and the commands above to verify remote synchronization. Do not use the initial-publication helper for subsequent development commits.
