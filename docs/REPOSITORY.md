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

The initial history contains eight commits. After a successful push, the two head hashes should match and the working tree should be clean. Future development should use ordinary new commits; the helper is limited to the initial eight-commit publication plan.
