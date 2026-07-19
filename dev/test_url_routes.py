from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import (  # noqa: E402
    build_tag_slug_map,
    discover_post_files,
    make_calver,
    post_slug_to_url_segment,
    resolve_posts_dir,
    tag_to_slug,
    validate_post_output_routes,
    validate_post_slug,
    validate_post_tags,
    write_generated_posts,
)


class PostSlugTests(unittest.TestCase):
    def test_accepts_safe_human_readable_slugs(self) -> None:
        self.assertEqual(validate_post_slug("my-first-post"), "my-first-post")
        self.assertEqual(validate_post_slug("日本語の記事"), "日本語の記事")
        title_slug = "Zoteroのエクスポート形式にHayagrivaを追加する"
        self.assertEqual(validate_post_slug(title_slug), title_slug)
        self.assertEqual(
            validate_post_slug("C++ と Rust 100% #1"),
            "C++ と Rust 100% #1",
        )
        self.assertEqual(
            post_slug_to_url_segment(title_slug),
            "Zotero%E3%81%AE%E3%82%A8%E3%82%AF%E3%82%B9%E3%83%9D%E3%83%BC%E3%83%88"
            "%E5%BD%A2%E5%BC%8F%E3%81%ABHayagriva%E3%82%92%E8%BF%BD%E5%8A%A0%E3%81%99"
            "%E3%82%8B",
        )

    def test_rejects_unsafe_or_non_portable_slugs(self) -> None:
        for slug in (
            "../outside",
            "/root",
            r"folder\child",
            "bad:name",
            "bad\nname",
            " leading-space",
            "trailing-space ",
            ".hidden",
            "trailing.",
            "a" * 256,
        ):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                validate_post_slug(slug)

    def test_rejects_generated_and_portability_reservations(self) -> None:
        for slug in (
            "tags",
            "pagefind",
            "themes",
            "con",
            "con.txt",
            "con .txt",
            "lpt1",
        ):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                validate_post_slug(slug)

    def test_rejects_collision_with_static_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            static_dir = Path(directory)
            (static_dir / "my-first-post").mkdir()
            with self.assertRaisesRegex(ValueError, "conflicts with static"):
                validate_post_output_routes([{"slug": "my-first-post"}], static_dir)

    def test_rejects_non_nfc_slug(self) -> None:
        with self.assertRaisesRegex(ValueError, "NFC"):
            validate_post_slug("カ\N{COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK}")


class TagSlugTests(unittest.TestCase):
    def test_preserves_simple_existing_tags(self) -> None:
        self.assertEqual(tag_to_slug("Typst"), "Typst")
        self.assertEqual(tag_to_slug("web-dev"), "web-dev")

    def test_encodes_unsafe_tag_as_portable_ascii(self) -> None:
        self.assertEqual(tag_to_slug("foo bar"), "~666f6f20626172")
        self.assertEqual(tag_to_slug("../escape"), "~2e2e2f657363617065")
        self.assertEqual(tag_to_slug("日本語"), "~e697a5e69cace8aa9e")

    def test_space_and_hyphen_tags_get_distinct_urls(self) -> None:
        result = build_tag_slug_map([{"tags": ("foo bar", "foo-bar")}])
        self.assertNotEqual(result["foo bar"], result["foo-bar"])

    def test_rejects_case_insensitive_filesystem_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "tag URL collision"):
            build_tag_slug_map([{"tags": ("Tag", "tag")}])

    def test_rejects_unicode_equivalent_duplicates_in_one_post(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate tag"):
            validate_post_tags(["é", "e\N{COMBINING ACUTE ACCENT}"])


class GeneratedRouteDataTests(unittest.TestCase):
    def test_empty_site_uses_empty_typst_dictionaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            write_generated_posts(context, [], {})
            self.assertEqual(
                context.generated_posts_file.read_text(encoding="utf-8"),
                "#let post-data = (:)\n\n#let tag-slugs = (:)\n",
            )

    def test_update_date_uses_calver_data_accepted_by_article_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "post" / "index.typ"
            source.parent.mkdir()
            source.write_text("post", encoding="utf-8")
            write_generated_posts(
                context,
                [
                    {
                        "slug": "post",
                        "url_slug": "post",
                        "title": "Post",
                        "create": make_calver(2026, 1, 1),
                        "update": make_calver(2026, 3, 4),
                        "description": "Description",
                        "tags": (),
                        "draft": False,
                        "source_file": source,
                    }
                ],
                {},
            )
            generated = context.generated_posts_file.read_text(encoding="utf-8")
            self.assertIn(
                "update: (year: 2026, month: 3, day: 4, patch: 0)", generated
            )

    def test_drafts_are_only_generated_for_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "draft-post" / "index.typ"
            source.parent.mkdir()
            source.write_text("draft", encoding="utf-8")
            draft = {
                "slug": "draft-post",
                "url_slug": "draft-post",
                "title": "Draft Post",
                "create": make_calver(2026, 7, 19),
                "update": None,
                "description": "Description",
                "tags": ("Draft",),
                "draft": True,
                "source_file": source,
            }

            write_generated_posts(context, [draft], {"Draft": "Draft"})
            published = context.generated_posts_file.read_text(encoding="utf-8")
            self.assertNotIn('"draft-post"', published)

            write_generated_posts(
                context,
                [draft],
                {"Draft": "Draft"},
                include_drafts=True,
            )
            preview = context.generated_posts_file.read_text(encoding="utf-8")
            self.assertIn('"draft-post"', preview)
            self.assertIn("draft: true", preview)


class PostsDirectoryTests(unittest.TestCase):
    def test_resolves_configured_directory_inside_blog_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            self.assertEqual(
                resolve_posts_dir(context, {"posts_dir": "content/posts"}),
                context.root_dir / "content" / "posts",
            )

    def test_defaults_to_blog_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            self.assertEqual(resolve_posts_dir(context, {}), context.root_dir)

    def test_rejects_unsafe_or_managed_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            for value in ("../outside", "/tmp/posts", "C:\\posts", "vendor/posts", "static"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resolve_posts_dir(context, {"posts_dir": value})

    def test_discovery_can_be_limited_to_configured_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            inside = context.root_dir / "posts" / "inside" / "index.typ"
            outside = context.root_dir / "outside" / "index.typ"
            inside.parent.mkdir(parents=True)
            outside.parent.mkdir(parents=True)
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            self.assertEqual(discover_post_files(context, context.root_dir / "posts"), [inside])


if __name__ == "__main__":
    unittest.main()
