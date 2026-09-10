from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent

DEFAULT_ASSET_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif",
    ".mp4", ".webm", ".ogv", ".mov",
    ".mp3", ".m4a", ".ogg", ".oga", ".wav", ".flac", ".aac",
    ".woff", ".woff2", ".ttf", ".otf",
    ".pdf", ".js", ".yaml", ".yml", ".bib", ".txt",
]


class AssetExtensionsTests(unittest.TestCase):
    def test_current_template_extensions_are_the_site_default(self) -> None:
        source = '''#import "../typst/core/site-impl.typ": _site
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
)
#metadata(site.asset_extensions) <result>
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

        if result.returncode != 0:
            raise AssertionError(result.stderr)
        self.assertEqual(json.loads(result.stdout), [DEFAULT_ASSET_EXTENSIONS])


if __name__ == "__main__":
    unittest.main()
