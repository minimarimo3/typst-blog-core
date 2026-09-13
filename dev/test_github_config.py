from __future__ import annotations

import json
import unittest

from typst_fixture import run_typst, site_source


def branch_source(branch: str | None = None) -> str:
    settings = {} if branch is None else {"github_branch": branch}
    return site_source("#metadata(site.github_branch) <result>", **settings)


class GitHubConfigTests(unittest.TestCase):
    def test_github_branch_defaults_to_main(self) -> None:
        result = run_typst(branch_source())
        self.assertEqual(json.loads(result.stdout), ["main"])

    def test_custom_github_branch_is_preserved(self) -> None:
        result = run_typst(branch_source('"master"'))
        self.assertEqual(json.loads(result.stdout), ["master"])

    def test_github_branch_must_not_be_empty(self) -> None:
        result = run_typst(branch_source('" "'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.github_branch", result.stderr)

    def test_history_url_uses_custom_branch(self) -> None:
        result = run_typst(
            '''#import "/vendor/typst-blog-core/typst/core/github.typ": github-commits-url
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
