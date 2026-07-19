from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .context import BlogContext
from .metadata import make_calver


@dataclass(frozen=True)
class GitCommit:
    oid: str
    timestamp: int
    date: str


def _run_git(context: BlogContext, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=context.root_dir,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return result.stdout.strip()


def _git_log(context: BlogContext, path: Path, *, follow: bool = False) -> list[GitCommit]:
    args = ["log", "--format=%H%x09%ct%x09%cs"]
    if follow:
        args.append("--follow")
    args.extend(["--", path.as_posix()])
    output = _run_git(context, *args)
    commits: list[GitCommit] = []
    for line in output.splitlines():
        oid, timestamp, date = line.split("\t", maxsplit=2)
        commits.append(GitCommit(oid=oid, timestamp=int(timestamp), date=date))
    return commits


def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def apply_update_policy(context: BlogContext, site: dict, posts: list[dict]) -> None:
    """Resolve post update dates according to the site-level policy.

    The Git policy treats the commit that first introduced the post's index.typ
    as the baseline. Later commits touching either that file (across renames) or
    another file in the article directory become update candidates.
    """

    if site["update_policy"] == "manual":
        return

    try:
        if _run_git(context, "rev-parse", "--is-inside-work-tree") != "true":
            raise RuntimeError("the blog root is not in a Git work tree")
        if _run_git(context, "rev-parse", "--is-shallow-repository") == "true":
            raise RuntimeError("the Git checkout is shallow")
    except (FileNotFoundError, subprocess.CalledProcessError, RuntimeError) as exc:
        _warn(f"cannot calculate Git update dates ({exc}); keeping manual update values")
        return

    for post in posts:
        source_path = post["source_file"].relative_to(context.root_dir)
        source_dir = post["source_dir"].relative_to(context.root_dir)
        try:
            source_commits = _git_log(context, source_path, follow=True)
            directory_commits = _git_log(context, source_dir)
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
            _warn(
                f"cannot calculate the Git update date for {source_path} ({exc}); "
                "keeping its manual update value"
            )
            continue

        if not source_commits:
            _warn(f"{source_path} has no Git history; keeping its manual update value")
            continue

        initial_commit = source_commits[-1]
        commits_by_oid = {
            commit.oid: commit for commit in (*source_commits, *directory_commits)
        }
        update_candidates = [
            commit
            for commit in commits_by_oid.values()
            if commit.oid != initial_commit.oid
            and commit.timestamp >= initial_commit.timestamp
        ]
        if not update_candidates:
            post["update"] = None
            continue

        latest = max(update_candidates, key=lambda commit: commit.timestamp)
        year, month, day = (int(part) for part in latest.date.split("-"))
        calculated = make_calver(year, month, day)
        post["update"] = calculated if calculated > post["create"] else None
