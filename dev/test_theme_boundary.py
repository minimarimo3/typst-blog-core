from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import (  # noqa: E402
    _home_page_content,
    _tag_page_content,
    copy_static_assets,
    _pagination_page_count,
    _pagination_slice,
)
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import CalVer, load_site_config, write_generated_site_data  # noqa: E402
from post_factory import make_post_record  # noqa: E402
from typst_fixture import create_config_blog, run_typst  # noqa: E402


class ThemeBoundaryTests(unittest.TestCase):
    def test_public_site_api_normalizes_trailing_slashes_in_base_url(self) -> None:
        for configured_url in ("https://example.com/", "https://example.com/blog///"):
            with self.subTest(configured_url=configured_url), tempfile.TemporaryDirectory() as directory:
                create_config_blog(Path(directory), base_url=json.dumps(configured_url))
                site = load_site_config(BlogContext.create(directory))
                self.assertEqual(site["base_url"], configured_url.rstrip("/"))

    def test_generated_tag_entries_pass_metadata_to_custom_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            create_config_blog(context.root_dir)
            context.theme_static_dir.parent.mkdir()
            (context.root_dir / "theme/theme.typ").write_text(
                '#import "/vendor/typst-blog-core/typst/api.typ" as core\n'
                '#let render-tag(data) = [#metadata(data.posts.first()) <result>]\n',
                encoding="utf-8",
            )
            post = make_post_record(
                context.root_dir, authors=("Ada", "Grace"), abstract="Summary",
                og_image="/images/card.png", update=CalVer(2026, 1, 3),
                tags=("Typst",), extra={"course": "typst-basics"},
            )
            result = run_typst(_tag_page_content(context, "Typst", "Typst", [post]), root=context.root_dir)
            data = json.loads(result.stdout)[0]
            self.assertEqual(data["authors"], ["Ada", "Grace"])
            self.assertEqual(data["abstract"], "Summary")
            self.assertEqual(data["og-image"], "/images/card.png")
            self.assertEqual(data["extra"], {"course": "typst-basics"})
            self.assertEqual(data["update"], {"year": 2026, "month": 1, "day": 3, "patch": 0})

    def test_static_assets_come_from_theme_then_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            context.output_dir.mkdir()
            theme_asset = context.theme_static_dir / "styles" / "theme.css"
            site_asset = context.user_static_dir / "styles" / "theme.css"
            theme_asset.parent.mkdir(parents=True)
            site_asset.parent.mkdir(parents=True)
            theme_asset.write_text("theme", encoding="utf-8")
            site_asset.write_text("site", encoding="utf-8")

            copy_static_assets(context)

            self.assertEqual(
                (context.output_dir / "styles" / "theme.css").read_text(encoding="utf-8"),
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

        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            create_config_blog(context.root_dir)
            context.theme_static_dir.parent.mkdir()
            (context.root_dir / "theme/theme.typ").write_text(
                '#import "/vendor/typst-blog-core/typst/api.typ" as core\n'
                '#let render-home(data) = [#metadata((\n'
                '  slugs: data.posts.map(post => post.slug), pagination: data.pagination,\n'
                ')) <result>]\n',
                encoding="utf-8",
            )
            write_generated_site_data(context, [
                make_post_record(context.root_dir, slug=f"post-{n}", create=CalVer(2026, 1, n))
                for n in range(1, 4)
            ], {})
            result = run_typst(_home_page_content(2, 3, 1), root=context.root_dir)
            data = json.loads(result.stdout)[0]
            self.assertEqual(data["slugs"], ["post-2"])
            self.assertEqual(data["pagination"], {
                "current": 2, "total": 3, "previous": "/", "next": "/page/3/",
                "pages": [{"number": n, "url": url} for n, url in (
                    (1, "/"), (2, "/page/2/"), (3, "/page/3/"),
                )],
            })


if __name__ == "__main__":
    unittest.main()
