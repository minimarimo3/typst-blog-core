from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.git_dates import apply_update_policy  # noqa: E402
from typst_blog_core.metadata import make_calver  # noqa: E402


class GitUpdateDateTests(unittest.TestCase):
    def _git(self, root: Path, *args: str, date: str | None = None) -> str:
        env = os.environ.copy()
        if date is not None:
            env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00+00:00"
            env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00+00:00"
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
        )
        return result.stdout.strip()

    def _repository(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.name", "Test User")
        self._git(root, "config", "user.email", "test@example.com")

    def _post(self, root: Path, directory: str = "post") -> dict:
        source_dir = root.resolve() / directory
        return {
            "create": make_calver(2026, 1, 1),
            "update": make_calver(2026, 2, 1),
            "source_file": source_dir / "index.typ",
            "source_dir": source_dir,
        }

    def test_manual_policy_preserves_authored_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = self._post(root)
            apply_update_policy(
                BlogContext.create(root), {"update_policy": "manual"}, [post]
            )
            self.assertEqual(post["update"], make_calver(2026, 2, 1))

    def test_first_article_commit_has_no_update_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            post = self._post(root)
            post["source_dir"].mkdir()
            post["source_file"].write_text("first", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "create post", date="2026-01-01")

            apply_update_policy(BlogContext.create(root), {"update_policy": "git"}, [post])

            self.assertIsNone(post["update"])

    def test_latest_article_asset_commit_becomes_update_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            post = self._post(root)
            post["source_dir"].mkdir()
            post["source_file"].write_text("first", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "create post", date="2026-01-01")
            (post["source_dir"] / "figure.svg").write_text("<svg/>", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "add figure", date="2026-03-04")

            apply_update_policy(BlogContext.create(root), {"update_policy": "git"}, [post])

            self.assertEqual(post["update"], make_calver(2026, 3, 4))

    def test_article_rename_keeps_earlier_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            old = self._post(root, "old-name")
            old["source_dir"].mkdir()
            old["source_file"].write_text("first", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "create post", date="2026-01-01")
            self._git(root, "mv", "old-name", "new-name")
            self._git(root, "commit", "-q", "-m", "rename post", date="2026-05-06")
            renamed = self._post(root, "new-name")

            apply_update_policy(
                BlogContext.create(root), {"update_policy": "git"}, [renamed]
            )

            self.assertEqual(renamed["update"], make_calver(2026, 5, 6))

    def test_shallow_repository_falls_back_to_manual_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = self._post(Path(directory))
            with patch(
                "typst_blog_core.git_dates._run_git",
                side_effect=["true", "true"],
            ):
                apply_update_policy(
                    BlogContext.create(directory), {"update_policy": "git"}, [post]
                )
            self.assertEqual(post["update"], make_calver(2026, 2, 1))


if __name__ == "__main__":
    unittest.main()
