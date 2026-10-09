"""Create eight meaningful initial commits; optionally push to the specified GitHub repository.

Run in a normal terminal with GitHub authentication and permission to create .git.
The dry run only reads project files and never invokes Git.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "https://github.com/amithkm9/vampires_AI.git"
PLAN = (
    ("first commit", ("README.md",)),
    ("chore: preserve course materials and sample maps",
     (".gitignore", "materials", "vendor", "maps", "docs/reference")),
    ("docs: record assignment rules and workspace conventions",
     ("AGENTS.md", "docs/RULES.md", "docs/planning/SOURCE_AUDIT.md")),
    ("feat: implement board state and combat rules",
     ("src/vampires/__init__.py", "src/vampires/model.py", "src/vampires/rules.py", "tools/inspect_map.py")),
    ("feat: add validated TCP protocol and foundation tests",
     ("src/vampires/protocol.py", "tests/test_foundations.py", "docs/PROTOCOL.md", "reports/foundation-verification.txt")),
    ("feat: add exact simulation and tactical map analysis",
     ("src/vampires/simulation.py", "tools/analyze_maps.py", "tests/test_simulation.py")),
    ("research: document map findings and tournament strategy",
     ("docs/STRATEGY.md", "notes", "references.bib", "sources/papers/manifest.json",
      "reports/map-analysis-2026-10-09.json", "reports/map-analysis-2026-10-09.md",
      "reports/strategy-verification-2026-10-09.txt")),
    ("docs: publish roadmap status and repository setup",
     ("TODO.md", "STATUS.md", "docs/planning/ROADMAP.md", "docs/REPOSITORY.md", "tools/publish_repository.py")),
)


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def planned_files():
    groups, seen = [], set()
    for message, names in PLAN:
        paths = []
        for name in names:
            item = ROOT / name
            if not item.exists():
                raise RuntimeError(f"Missing planned path: {name}")
            candidates = sorted(item.rglob("*")) if item.is_dir() else [item]
            for path in candidates:
                relative = path.relative_to(ROOT)
                if any(part in {".git", "__pycache__", "tmp", ".venv"} for part in relative.parts):
                    continue
                if path.is_symlink():
                    raise RuntimeError(f"Review symbolic link before publishing: {relative}")
                if not path.is_file():
                    continue
                name = relative.as_posix()
                if name in seen:
                    raise RuntimeError(f"File assigned twice: {name}")
                seen.add(name)
                paths.append(name)
        if not paths:
            raise RuntimeError(f"Empty commit group: {message}")
        groups.append((message, paths))
    return groups


def verify_materials():
    manifest = json.loads((ROOT / "materials/manifest.json").read_text())
    for entry in manifest["files"] + manifest["extracted"]:
        data = (ROOT / entry["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Original material changed: {entry['path']}")


def history():
    if git("rev-parse", "--verify", "HEAD", check=False).returncode:
        return []
    lines = git("log", "--reverse", "--format=%H%x00%s").stdout.splitlines()
    records = [line.split("\0", 1) for line in lines]
    messages = [record[1] for record in records]
    expected = [message for message, _ in PLAN]
    if messages != expected[:len(messages)] or len(messages) > len(expected):
        raise RuntimeError("Existing history differs from this initial-publication plan; no history will be rewritten")
    if git("rev-list", "--merges", "HEAD").stdout.strip():
        raise RuntimeError("Existing history contains a merge; review it before publishing")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Show exact file groups without invoking Git")
    mode.add_argument("--push", action="store_true", help="Create/resume eight commits and push main")
    args = parser.parse_args()
    groups = planned_files()
    verify_materials()
    for number, (message, paths) in enumerate(groups, 1):
        print(f"{number}. {message} ({len(paths)} files)")
        if args.dry_run:
            for path in paths:
                print(f"   {path}")
    if args.dry_run:
        print(f"Dry run complete: {sum(len(paths) for _, paths in groups)} files; eight nonempty commits; no Git changes.")
        return
    if not args.push:
        parser.error("Use --dry-run to inspect, or --push to create commits and publish")

    # Read-only checks happen before initialization or staging.
    existing = git("rev-parse", "--show-toplevel", check=False)
    if existing.returncode == 0 and Path(existing.stdout.strip()).resolve() != ROOT:
        raise RuntimeError("Project is inside another repository; refusing to modify that repository")
    initialized = existing.returncode == 0
    if not initialized and (ROOT / ".git").exists():
        raise RuntimeError("A .git path exists but is not a readable repository; inspect it manually")
    for key in ("user.name", "user.email"):
        if not git("config", "--get", key, check=False).stdout.strip():
            raise RuntimeError(f"Configure Git {key} before publishing")
    completed = history() if initialized else []
    if initialized:
        branch = git("symbolic-ref", "--short", "HEAD").stdout.strip()
        if branch != "main":
            raise RuntimeError(f"Current branch is {branch!r}; expected main; refusing to rename an existing branch")
        if git("diff", "--cached", "--name-only").stdout.strip():
            raise RuntimeError("The index contains staged changes; review or unstage them before running this script")
        previous_paths = [p for _, paths in groups[:len(completed)] for p in paths]
        if previous_paths and git("diff", "--name-only", "HEAD", "--", *previous_paths).stdout.strip():
            raise RuntimeError("Files in completed commits have changed; review them before resuming")
    origin = git("remote", "get-url", "origin", check=False).stdout.strip() if initialized else ""
    if origin and origin != REMOTE:
        raise RuntimeError(f"Existing origin differs from the requested repository: {origin}")
    # This also checks transport authentication without creating any remote objects.
    remote_refs = git("ls-remote", REMOTE).stdout.splitlines()
    remote_main = None
    local_shas = {sha for sha, _ in completed}
    for line in remote_refs:
        sha, ref = line.split()
        if ref in {"HEAD", "refs/heads/main"} and sha in local_shas:
            if ref == "refs/heads/main":
                remote_main = sha
            continue
        raise RuntimeError("Remote is no longer empty or contains unrelated history; refusing to overwrite it")

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                   cwd=ROOT, env=environment, check=True)
    if not initialized:
        print(git("init", "-b", "main").stdout.strip())
    if not origin:
        git("remote", "add", "origin", REMOTE)
    for message, paths in groups[len(completed):]:
        git("add", "--", *paths)
        changed = git("diff", "--cached", "--quiet", check=False)
        if changed.returncode == 0:
            raise RuntimeError(f"No content to commit for {message!r}; no empty commits will be created")
        if changed.returncode != 1:
            raise RuntimeError(changed.stderr)
        print(git("commit", "-m", message).stdout.strip())
    final_history = history()
    if len(final_history) != 8:
        raise RuntimeError("Expected exactly eight commits")
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise RuntimeError("Tracked files changed during publication; inspect them before pushing")
    head = git("rev-parse", "HEAD").stdout.strip()
    # Ordinary push: never force-push or rewrite remote history.
    pushed = git("push", "-u", "origin", "main")
    print(pushed.stdout.strip())
    print(pushed.stderr.strip())
    remote = git("ls-remote", "origin", "refs/heads/main").stdout.split()
    if not remote or remote[0] != head:
        raise RuntimeError("Could not verify that GitHub main matches the local head")
    print(f"Verified eight commits on main: https://github.com/amithkm9/vampires_AI/commits/main/")
    print(git("status", "--short", "--branch").stdout.strip())


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Publication stopped: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr or "", file=sys.stderr)
        sys.exit(1)
