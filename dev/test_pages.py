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
)
from typst_blog_core.new_page import (  # noqa: E402
    PageTemplateContext,
    create_page,
)
from post_factory import make_post_record  # noqa: E402


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
                        "title": "About",
                        "description": "About this site",
                        "draft": False,
                        "index": True,
                        "extra": {"layout": "wide"},
                    },
                ),
            ):
                pages = collect_pages(context)

            self.assertEqual(pages[0]["route_path"], "about")
            self.assertEqual(pages[0]["url_slug"], "about")
            self.assertEqual(pages[0]["extra"], {"layout": "wide"})

    def test_rejects_post_and_page_route_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = make_post_record(Path(directory), route_path="About")
            with self.assertRaisesRegex(ValueError, "content URL collision"):
                validate_content_route_collisions(
                    [post],
                    [{"route_path": "about", "aliases": ()}],
                )

    def test_rejects_alias_that_claims_a_canonical_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = make_post_record(root, route_path="first", aliases=("second",))
            second = make_post_record(root, slug="second", route_path="second")
            with self.assertRaisesRegex(ValueError, "content URL collision"):
                validate_content_route_collisions([first, second], [])


class NewPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_metadata = patch(
            "typst_blog_core.new_page.load_site_metadata",
            return_value={"posts_dir": "."},
        )
        self.site_metadata.start()

    def tearDown(self) -> None:
        self.site_metadata.stop()

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

    def test_rejects_route_used_by_existing_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "duplicate" / "index.typ"
            existing.parent.mkdir()
            existing.write_text("post without a slug field\n", encoding="utf-8")
            with patch(
                "typst_blog_core.metadata.load_post_metadata",
                return_value={
                    "title": "Duplicate",
                    "description": "Description",
                    "create": "2026.09.10",
                    "draft": False,
                },
            ):
                with self.assertRaisesRegex(ValueError, "content URL /duplicate/"):
                    create_page(
                        root_dir=directory,
                        slug="duplicate",
                        title="Duplicate",
                        description="Description",
                    )

    def test_default_template_writes_extra_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_page(
                root_dir=directory,
                slug="course-overview",
                title="Course overview",
                description="Course contents",
                extra={"course": "typst-basics", "lesson": 1},
            )
            source = index_file.read_text(encoding="utf-8")
            self.assertIn(
                'extra: json(bytes("{\\\"course\\\":\\\"typst-basics\\\",\\\"lesson\\\":1}"))',
                source,
            )

    def test_custom_template_receives_validated_context(self) -> None:
        def template(page: PageTemplateContext) -> str:
            self.assertEqual(page.slug, "course-overview")
            self.assertEqual(page.title, "Course overview")
            self.assertEqual(page.description, "Course contents")
            self.assertTrue(page.draft)
            self.assertTrue(page.indexed)
            return f"course={page.extra['course']}\n"

        with tempfile.TemporaryDirectory() as directory:
            index_file = create_page(
                root_dir=directory,
                slug="course-overview",
                title=" Course overview ",
                description=" Course contents ",
                extra={"course": "typst-basics"},
                template=template,
            )
            self.assertEqual(index_file.read_text(encoding="utf-8"), "course=typst-basics\n")

    def test_template_failure_does_not_leave_destination(self) -> None:
        def invalid_template(_page: PageTemplateContext) -> int:
            return 1

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TypeError, "new-page template"):
                create_page(
                    root_dir=directory,
                    slug="invalid-template",
                    title="Invalid template",
                    description="Description",
                    template=invalid_template,  # type: ignore[arg-type]
                )
            self.assertFalse((Path(directory) / "pages" / "invalid-template").exists())


if __name__ == "__main__":
    unittest.main()
