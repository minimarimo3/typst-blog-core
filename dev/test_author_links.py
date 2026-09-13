from __future__ import annotations

import json
import unittest

from typst_fixture import run_typst, site_source


def evaluate_author(author: str, *, expect_success: bool = True):
    return run_typst(
        site_source("#metadata(site.author.links) <result>", author=author),
        expect_success=expect_success,
    )


class AuthorLinkTests(unittest.TestCase):
    def test_optional_custom_icon_is_preserved(self) -> None:
        result = evaluate_author(
            '''(
  name: "Test",
  bio: "",
  links: (
    (id: "bluesky", label: "Bluesky", url: "https://bsky.app/profile/test", icon: "icons/bluesky.svg"),
    (id: "github", label: "GitHub", url: "https://github.com/test"),
  ),
)'''
        )
        links = json.loads(result.stdout)[0]
        self.assertEqual(links[0]["icon"], "icons/bluesky.svg")
        self.assertNotIn("icon", links[1])

    def test_custom_icon_rejects_paths_outside_static(self) -> None:
        result = evaluate_author(
            '''(
  name: "Test",
  bio: "",
  links: ((id: "bad", label: "Bad", url: "https://example.com", icon: "../bad.svg"),),
)''',
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("static/", result.stderr)


if __name__ == "__main__":
    unittest.main()
