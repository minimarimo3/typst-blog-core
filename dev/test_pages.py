from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


import sys


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import (  # noqa: E402
    collect_pages,
    validate_content_route_collisions,
    write_generated_site_data,
)
from typst_blog_core.new_page import create_page  # noqa: E402


class PageMetadataTests(unittest.TestCase):
    def test_collects_general_page_without_article_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "pages" / "about" / "index.typ"
            source.parent.mkdir(parents=True)
            source.write_text("page", encoding="utf-8")
            with (
                patch(
                    "typst_blog_core.metadata.discover_page_files",
                    return_value=[source],
                ),
                patch(
                    "typst_blog_core.metadata.load_page_metadata",
                    return_value={
                        "slug": "このサイトについて",
                        "title": "About",
                        "description": "About this site",
                        "draft": False,
                        "index": True,
                        "extra": {"layout": "wide"},
                    },
                ),
            ):
                pages = collect_pages(context)

            self.assertEqual(pages[0]["slug"], "このサイトについて")
            self.assertTrue(pages[0]["url_slug"].startswith("%E3%81%93"))
            self.assertEqual(pages[0]["extra"], {"layout": "wide"})

    def test_rejects_post_and_page_route_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "content URL collision"):
            validate_content_route_collisions(
                [{"slug": "About"}],
                [{"slug": "about"}],
            )

    def test_generated_data_contains_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            write_generated_site_data(
                context,
                [],
                {},
                pages=[
                    {
                        "slug": "about",
                        "url_slug": "about",
                        "draft": False,
                        "index": True,
                        "extra": {"layout": "wide"},
                    }
                ],
            )
            generated = context.generated_site_data_file.read_text(encoding="utf-8")
            self.assertIn('#let pages = (', generated)
            self.assertIn('"about": (', generated)
            self.assertIn('index: true', generated)


class NewPageTests(unittest.TestCase):
    def test_creates_page_under_pages_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_page(
                root_dir=directory,
                slug="about",
                title="About",
                description="About this site",
            )
            self.assertEqual(
                index_file,
                Path(directory).resolve() / "pages" / "about" / "index.typ",
            )
            source = index_file.read_text(encoding="utf-8")
            self.assertIn('#import "/template.typ": site-page', source)
            self.assertIn('#show: site-page.with(', source)
            self.assertIn('draft: true', source)
            self.assertIn('index: true', source)

    def test_can_create_published_unindexed_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_page(
                root_dir=directory,
                slug="thanks",
                title="Thanks",
                description="Thank you",
                publish=True,
                indexed=False,
            )
            source = index_file.read_text(encoding="utf-8")
            self.assertIn('draft: false', source)
            self.assertIn('index: false', source)


if __name__ == "__main__":
    unittest.main()
