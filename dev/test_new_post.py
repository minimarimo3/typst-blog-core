from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.new_post import (  # noqa: E402
    PostTemplateContext,
    create_post,
    parse_post_date,
)


class NewPostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_metadata = patch(
            "typst_blog_core.new_post.load_site_metadata",
            return_value={"posts_dir": "."},
        )
        self.site_metadata.start()

    def tearDown(self) -> None:
        self.site_metadata.stop()

    def test_creates_minimal_draft_with_escaped_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_file = create_post(
                root_dir=root,
                slug="hello-world",
                title='Hello "Typst"',
                description="A \\ short description",
                tags=["Typst", "日本語"],
                create=dt.date(2026, 7, 19),
            )
            self.assertEqual(index_file, root.resolve() / "hello-world" / "index.typ")
            source = index_file.read_text(encoding="utf-8")
            self.assertIn('#import "/template.typ": post, calver', source)
            self.assertIn("#show: post.with(", source)
            self.assertNotIn("#let meta = post-meta(", source)
            self.assertNotIn("#metadata(meta) <post-meta>", source)
            self.assertNotIn("#show: article.with(..meta)", source)
            self.assertNotIn('slug:', source)
            self.assertIn('title: "Hello \\"Typst\\""', source)
            self.assertIn('description: "A \\\\ short description"', source)
            self.assertIn('tags: ("Typst", "日本語")', source)
            self.assertIn("create: calver(2026, 7, 19)", source)
            self.assertIn("draft: true", source)

    def test_creates_unfinished_draft_with_empty_text_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="unfinished",
                title="",
                description="",
            )
            source = index_file.read_text(encoding="utf-8")
            self.assertIn('title: ""', source)
            self.assertIn('description: ""', source)

    def test_publish_flag_creates_published_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="published-post",
                title="Published",
                description="Description",
                publish=True,
            )
            self.assertIn("draft: false", index_file.read_text(encoding="utf-8"))

    def test_default_template_writes_extra_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="lesson-one",
                title="Lesson one",
                description="Description",
                extra={"course": "typst-basics", "lesson": 1},
            )
            source = index_file.read_text(encoding="utf-8")
            self.assertIn(
                'extra: json(bytes("{\\\"course\\\":\\\"typst-basics\\\",\\\"lesson\\\":1}"))',
                source,
            )

    def test_custom_template_receives_validated_context(self) -> None:
        received: list[PostTemplateContext] = []

        def template(post: PostTemplateContext) -> str:
            received.append(post)
            return f"custom template for {post.extra['course']}\n"

        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="custom",
                title=" Custom title ",
                description=" Custom description ",
                tags=["Typst"],
                create=dt.date(2026, 9, 9),
                extra={"course": "typst-basics"},
                template=template,
            )

            self.assertEqual(
                index_file.read_text(encoding="utf-8"),
                "custom template for typst-basics\n",
            )
            self.assertEqual(received[0].title, "Custom title")
            self.assertEqual(received[0].description, "Custom description")
            self.assertEqual(received[0].tags, ("Typst",))
            self.assertEqual(received[0].create, dt.date(2026, 9, 9))
            self.assertTrue(received[0].draft)

    def test_template_failure_does_not_leave_destination(self) -> None:
        def invalid_template(_post: PostTemplateContext) -> int:
            return 42

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TypeError, "must return a string"):
                create_post(
                    root_dir=directory,
                    slug="invalid-template",
                    title="Invalid",
                    description="Description",
                    template=invalid_template,  # type: ignore[arg-type]
                )
            self.assertFalse((Path(directory) / "invalid-template").exists())

    def test_creates_post_with_title_like_slug(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            slug = "Zoteroのエクスポート形式にHayagrivaを追加する"
            index_file = create_post(
                root_dir=directory,
                slug=slug,
                title="Zoteroのエクスポート形式にHayagrivaを追加する",
                description="説明",
            )
            self.assertEqual(
                index_file,
                Path(directory).resolve() / slug / "index.typ",
            )
            self.assertNotIn("slug:", index_file.read_text(encoding="utf-8"))

    def test_normalizes_new_post_slug_to_nfc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="カ\N{COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK}",
                title="正規化",
                description="説明",
            )
            self.assertEqual(
                index_file,
                Path(directory).resolve() / "ガ" / "index.typ",
            )
            self.assertEqual(index_file.parent.name, "ガ")

    def test_creates_post_under_configured_posts_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_post.load_site_metadata",
                return_value={"posts_dir": "posts"},
            ):
                index_file = create_post(
                    root_dir=directory,
                    slug="nested-post",
                    title="Nested",
                    description="Description",
                )
            self.assertEqual(
                index_file,
                Path(directory).resolve() / "posts" / "nested-post" / "index.typ",
            )

    def test_rejects_existing_destination_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing"
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create_post(
                    root_dir=directory,
                    slug="existing",
                    title="Existing",
                    description="Description",
                )
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_rejects_route_used_by_existing_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "pages" / "duplicate" / "index.typ"
            existing.parent.mkdir(parents=True)
            existing.write_text("page without a slug field\n", encoding="utf-8")
            with patch(
                "typst_blog_core.metadata.load_page_metadata",
                return_value={
                    "title": "Duplicate",
                    "description": "Description",
                    "draft": False,
                    "index": True,
                },
            ):
                with self.assertRaisesRegex(ValueError, "content URL /duplicate/"):
                    create_post(
                        root_dir=directory,
                        slug="duplicate",
                        title="Duplicate",
                        description="Description",
                    )

    def test_rejects_route_owned_by_theme_static(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            theme_route = Path(directory) / "theme" / "static" / "downloads"
            theme_route.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "conflicts with static/downloads"):
                create_post(
                    root_dir=directory,
                    slug="downloads",
                    title="Downloads",
                    description="Description",
                )

    def test_parses_iso_date(self) -> None:
        self.assertEqual(parse_post_date("2026-07-19"), dt.date(2026, 7, 19))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            parse_post_date("2026.07.19")


if __name__ == "__main__":
    unittest.main()
