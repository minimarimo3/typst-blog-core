from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import (  # noqa: E402
    _tag_page_content,
    _tags_index_content,
    copy_static_assets,
)
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import CalVer, load_site_config  # noqa: E402


class ThemeBoundaryTests(unittest.TestCase):
    def test_generated_tag_entries_call_template_theme(self) -> None:
        post = {
            "slug": "hello",
            "url_slug": "hello",
            "title": "Hello",
            "create": CalVer(2026, 1, 2),
            "update": CalVer(2026, 1, 3),
            "description": "Description",
            "tags": ["Typst"],
            "draft": False,
        }
        source = _tag_page_content("Typst", "Typst", [post])
        self.assertIn('#import "/theme/theme.typ": render-tag', source)
        self.assertIn("tag-page-data", source)
        self.assertIn("update: (year: 2026, month: 1, day: 3, patch: 0)", source)
        self.assertNotIn("typst/core/tag.typ", source)

        index_source = _tags_index_content([("Typst", "Typst", 1)])
        self.assertIn('#import "/theme/theme.typ": render-tags-index', index_source)
        self.assertIn("tags-index-page-data", index_source)

    def test_static_assets_come_from_theme_then_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            context.output_dir.mkdir()
            theme_asset = context.theme_static_dir / "styles" / "theme.css"
            site_asset = context.user_static_dir / "images" / "site.svg"
            theme_asset.parent.mkdir(parents=True)
            site_asset.parent.mkdir(parents=True)
            theme_asset.write_text("theme", encoding="utf-8")
            site_asset.write_text("site", encoding="utf-8")

            copy_static_assets(context)

            self.assertEqual(
                (context.output_dir / "styles" / "theme.css").read_text(encoding="utf-8"),
                "theme",
            )
            self.assertEqual(
                (context.output_dir / "images" / "site.svg").read_text(encoding="utf-8"),
                "site",
            )

    def test_core_keeps_theme_configuration_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            with patch(
                "typst_blog_core.metadata.load_site_metadata",
                return_value={
                    "title": "Test",
                    "description": "Test site",
                    "base_url": "https://example.com/",
                    "language": {"lang": "en"},
                    "theme": {"layout": "custom"},
                },
            ):
                site = load_site_config(context)

            self.assertEqual(site["theme"], {"layout": "custom"})
            self.assertEqual(site["base_url"], "https://example.com")

if __name__ == "__main__":
    unittest.main()
