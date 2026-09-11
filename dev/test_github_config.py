from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent


def run_typst(
    source: str, *, expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".typ", dir=DEV_DIR, encoding="utf-8"
    ) as source_file:
        source_file.write(source)
        source_file.flush()
        result = subprocess.run(
            [
                "typst",
                "eval",
                "query(<result>).map(it => it.value)",
                "--in",
                source_file.name,
                "--root",
                str(CORE_DIR),
            ],
            check=False,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def site_source(github_branch: str = "") -> str:
    return f'''#import "../typst/core/site-impl.typ": _site
#let site = _site(
  title: "Test",
  description: "Test site",
  base_url: "https://example.com",
  language: "ja",
  fonts: (
    main: (pdf: "Noto Serif CJK JP", web: none),
    code: (pdf: "Fira Code", web: none),
  ),
  author: (name: "Test", bio: "", links: ()),
  github_repo: "https://github.com/example/blog",
  {github_branch}
)
#metadata(site.github_branch) <result>
'''


class GitHubConfigTests(unittest.TestCase):
    def test_github_branch_defaults_to_main(self) -> None:
        result = run_typst(site_source())
        self.assertEqual(json.loads(result.stdout), ["main"])

    def test_custom_github_branch_is_preserved(self) -> None:
        result = run_typst(site_source('github_branch: "master",'))
        self.assertEqual(json.loads(result.stdout), ["master"])

    def test_github_branch_must_not_be_empty(self) -> None:
        result = run_typst(site_source('github_branch: " ",'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.github_branch", result.stderr)

    def test_history_url_uses_custom_branch(self) -> None:
        result = run_typst(
            '''#import "../typst/core/github.typ": github-commits-url
#metadata(github-commits-url(
  "https://github.com/example/blog/",
  "feature/docs",
  "posts/hello/index.typ",
)) <result>
'''
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                "https://github.com/example/blog/commits/"
                "feature/docs/posts/hello/index.typ"
            ],
        )


if __name__ == "__main__":
    unittest.main()
