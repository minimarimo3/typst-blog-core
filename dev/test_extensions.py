from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typst_blog_core.context import BlogContext
from typst_blog_core.metadata import validate_extension_assets


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent


def evaluate(
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


class ExtensionTests(unittest.TestCase):
    def test_collects_local_and_https_assets_in_registration_order(self) -> None:
        result = evaluate(
            '''#import "../typst/core/extensions.typ": extension, extension-assets
#let extensions = (
  extension("alerts", styles: ("extensions/alerts.css",)),
  extension(
    "bluesky",
    styles: ("extensions/bluesky/style.css",),
    scripts: ("extensions/bluesky/main.js", "https://example.com/embed.js"),
  ),
)
#metadata(extension-assets(extensions)) <result>
'''
        )
        self.assertEqual(
            json.loads(result.stdout)[0],
            {
                "styles": ["extensions/alerts.css", "extensions/bluesky/style.css"],
                "scripts": ["extensions/bluesky/main.js", "https://example.com/embed.js"],
            },
        )

    def test_duplicate_names_are_rejected(self) -> None:
        result = evaluate(
            '''#import "../typst/core/extensions.typ": extension, extension-assets
#let extensions = (extension("same"), extension("same"))
#metadata(extension-assets(extensions)) <result>
''',
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("拡張名 same が重複", result.stderr)

    def test_parent_segments_are_rejected(self) -> None:
        result = evaluate(
            '''#import "../typst/core/extensions.typ": extension
#metadata(extension("unsafe", scripts: ("../outside.js",))) <result>
''',
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("安全な相対パスか HTTPS URL", result.stderr)

    def test_registered_local_assets_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            context = BlogContext.create(root)
            with patch(
                "typst_blog_core.metadata.eval_metadata_values",
                return_value=[
                    [
                        {
                            "name": "missing",
                            "styles": ["extensions/missing.css"],
                            "scripts": [],
                        }
                    ]
                ],
            ):
                with self.assertRaisesRegex(ValueError, "static/extensions/missing.css"):
                    validate_extension_assets(context)

    def test_https_assets_do_not_require_a_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            context = BlogContext.create(root)
            with patch(
                "typst_blog_core.metadata.eval_metadata_values",
                return_value=[
                    [
                        {
                            "name": "remote",
                            "styles": [],
                            "scripts": ["https://example.com/embed.js"],
                        }
                    ]
                ],
            ):
                validate_extension_assets(context)

    def test_hand_written_invalid_descriptor_has_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            context = BlogContext.create(root)
            with patch(
                "typst_blog_core.metadata.eval_metadata_values",
                return_value=[[{"name": "broken"}]],
            ):
                with self.assertRaisesRegex(ValueError, "created with extension"):
                    validate_extension_assets(context)


if __name__ == "__main__":
    unittest.main()
