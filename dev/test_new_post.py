from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.new_post import create_post, parse_post_date  # noqa: E402


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
            self.assertIn('slug: "hello-world"', source)
            self.assertIn('title: "Hello \\"Typst\\""', source)
            self.assertIn('description: "A \\\\ short description"', source)
            self.assertIn('tags: ("Typst", "日本語")', source)
            self.assertIn("create: calver(2026, 7, 19)", source)
            self.assertIn("draft: true", source)

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

    def test_creates_post_with_japanese_slug(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_file = create_post(
                root_dir=directory,
                slug="日本語の記事",
                title="日本語の記事",
                description="説明",
            )
            self.assertEqual(
                index_file,
                Path(directory).resolve() / "日本語の記事" / "index.typ",
            )
            self.assertIn(
                'slug: "日本語の記事"',
                index_file.read_text(encoding="utf-8"),
            )

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
            self.assertIn('slug: "ガ"', index_file.read_text(encoding="utf-8"))

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

    def test_rejects_slug_used_in_different_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "articles" / "index.typ"
            existing.parent.mkdir()
            existing.write_text('#let meta = (slug: "duplicate")\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already used"):
                create_post(
                    root_dir=directory,
                    slug="duplicate",
                    title="Duplicate",
                    description="Description",
                )

    def test_parses_iso_date(self) -> None:
        self.assertEqual(parse_post_date("2026-07-19"), dt.date(2026, 7, 19))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            parse_post_date("2026.07.19")


if __name__ == "__main__":
    unittest.main()
