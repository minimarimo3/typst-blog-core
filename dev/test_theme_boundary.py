from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import (  # noqa: E402
    _home_page_content,
    _not_found_page_content,
    _tag_page_content,
    _tags_index_content,
    copy_static_assets,
    _pagination_page_count,
    _pagination_slice,
)
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import CalVer, load_site_config  # noqa: E402
from post_factory import make_post_record  # noqa: E402


class ThemeBoundaryTests(unittest.TestCase):
    def test_public_typst_api_exports_renderer_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            blog_root = Path(directory)
            (blog_root / "site.typ").write_text(
                '''#let site = (
  base_url: "https://example.com",
  fonts: (main: (pdf: "serif"), code: (pdf: "monospace")),
)
''',
                encoding="utf-8",
            )
            vendored_core = blog_root / "vendor" / "typst-blog-core"
            vendored_core.parent.mkdir()
            vendored_core.symlink_to(CORE_DIR, target_is_directory=True)
            result = subprocess.run(
                [
                    "typst",
                    "eval",
                    'import "vendor/typst-blog-core/typst/api.typ": api-version; api-version',
                    "--root",
                    str(blog_root),
                ],
                cwd=blog_root,
                check=False,
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
        if result.returncode != 0:
            self.fail(result.stderr)

        self.assertEqual(json.loads(result.stdout), 1)

    def test_generated_tag_entries_call_template_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            post = make_post_record(
                context.root_dir,
                authors=("Ada", "Grace"),
                abstract="Summary",
                og_image="/images/card.png",
                update=CalVer(2026, 1, 3),
                tags=("Typst",),
                extra={"course": "typst-basics"},
            )
            source = _tag_page_content(context, "Typst", "Typst", [post])
        self.assertIn('#import "/theme/theme.typ": render-tag, core', source)
        self.assertIn("core.tag-page-data", source)
        self.assertIn("update: (year: 2026, month: 1, day: 3, patch: 0)", source)
        self.assertIn('extra: json(bytes("{\\\"course\\\":\\\"typst-basics\\\"}"))', source)
        self.assertIn('authors: json(bytes("[\\\"Ada\\\",\\\"Grace\\\"]"))', source)
        self.assertIn('abstract: json(bytes("\\\"Summary\\\""))', source)
        self.assertIn('og-image: "/images/card.png"', source)
        self.assertNotIn("typst/core/tag.typ", source)
        self.assertNotIn("/vendor/typst-blog-core", source)

        index_source = _tags_index_content([("Typst", "Typst", 1)])
        self.assertIn(
            '#import "/theme/theme.typ": render-tags-index, core',
            index_source,
        )
        self.assertIn("core.tags-index-page-data", index_source)
        self.assertNotIn("/vendor/typst-blog-core", index_source)

    def test_generated_static_entries_only_import_template_facade(self) -> None:
        home_source = _home_page_content()
        self.assertIn(
            '#import "/theme/theme.typ": render-home, core',
            home_source,
        )
        self.assertIn("core.load-build-data", home_source)
        self.assertIn("core.home-page-data", home_source)
        self.assertNotIn("/vendor/typst-blog-core", home_source)

        not_found_source = _not_found_page_content()
        self.assertIn(
            '#import "/theme/theme.typ": render-not-found, core',
            not_found_source,
        )
        self.assertIn("core.not-found-page-data", not_found_source)
        self.assertNotIn("/vendor/typst-blog-core", not_found_source)

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
                    "pagination": {
                        "home": {"enabled": False, "per_page": 10},
                        "tag": {"enabled": True, "per_page": 5},
                    },
                    "asset_extensions": [".PNG", ".woff2"],
                },
            ):
                site = load_site_config(context)

            self.assertEqual(site["theme"], {"layout": "custom"})
            self.assertEqual(site["base_url"], "https://example.com")
            self.assertEqual(site["asset_extensions"], [".png", ".woff2"])

    def test_site_rejects_invalid_asset_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            with patch(
                "typst_blog_core.metadata.load_site_metadata",
                return_value={
                    "title": "Test",
                    "description": "Test site",
                    "base_url": "https://example.com",
                    "language": {"lang": "en"},
                    "pagination": {
                        "home": {"enabled": False, "per_page": 10},
                        "tag": {"enabled": False, "per_page": 10},
                    },
                    "asset_extensions": ["mp4"],
                },
            ):
                with self.assertRaisesRegex(ValueError, "site.asset_extensions\\[0\\]"):
                    load_site_config(context)

    def test_pagination_can_be_disabled_or_sized(self) -> None:
        items = list(range(23))
        disabled = {"enabled": False, "per_page": 10}
        enabled = {"enabled": True, "per_page": 10}

        self.assertEqual(_pagination_page_count(len(items), disabled), 1)
        self.assertEqual(_pagination_slice(items, disabled, 1), items)
        self.assertEqual(_pagination_page_count(len(items), enabled), 3)
        self.assertEqual(_pagination_slice(items, enabled, 2), list(range(10, 20)))

        page_source = _home_page_content(2, 3, 10)
        self.assertIn("page-number: 2", page_source)
        self.assertIn("total-pages: 3", page_source)
        self.assertIn("per-page: 10", page_source)

if __name__ == "__main__":
    unittest.main()
