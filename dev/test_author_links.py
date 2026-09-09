from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent


def evaluate_author(author: str, *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    source = f'''#import "../typst/core/site-impl.typ": _site
#let site = _site(
  title: "Test",
  description: "Test site",
  base_url: "https://example.com",
  language: "en",
  asset_extensions: (".png",),
  fonts: (
    main: (pdf: "Noto Serif CJK JP", web: none),
    code: (pdf: "Fira Code", web: none),
  ),
  author: {author},
)
#metadata(site.author.links) <result>
'''
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
