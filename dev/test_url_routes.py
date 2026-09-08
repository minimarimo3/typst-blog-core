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

from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import (  # noqa: E402
    build_tag_slug_map,
    collect_posts,
    discover_post_files,
    make_calver,
    post_slug_to_url_segment,
    resolve_posts_dir,
    tag_to_slug,
    validate_post_output_routes,
    validate_post_extra,
    validate_post_slug,
    validate_post_tags,
    write_generated_site_data,
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
            "color-schemes",
            "con",
            "con.txt",
            "con .txt",
            "lpt1",
        ):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                validate_post_slug(slug)

        for slug in ("scripts", "styles"):
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


class PostExtraTests(unittest.TestCase):
    def test_collects_nested_json_compatible_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "post" / "index.typ"
            source.parent.mkdir()
            source.write_text("post", encoding="utf-8")
            extra = {
                "course": {"id": "typst-basics", "lesson": 2},
                "featured": True,
            }
            with (
                patch(
                    "typst_blog_core.metadata.discover_post_files",
                    return_value=[source],
                ),
                patch(
                    "typst_blog_core.metadata.load_post_metadata",
                    return_value={
                        "slug": "post",
                        "title": "Post",
                        "create": "2026.09.08",
                        "description": "Description",
                        "draft": False,
                        "extra": extra,
                    },
                ),
            ):
                posts = collect_posts(context)

            self.assertEqual(posts[0]["extra"], extra)

    def test_rejects_non_dictionary_or_non_json_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "dictionary"):
            validate_post_extra(["course"])
        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            validate_post_extra({"score": float("nan")})


class GeneratedRouteDataTests(unittest.TestCase):
    def test_empty_site_uses_empty_typst_dictionaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            write_generated_site_data(context, [], {})
            self.assertEqual(
                context.generated_site_data_file.read_text(encoding="utf-8"),
                "#let posts = (:)\n\n#let tag-slugs = (:)\n\n#let site-outputs = ()\n",
            )

    def test_update_date_uses_calver_data_accepted_by_article_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "post" / "index.typ"
            source.parent.mkdir()
            source.write_text("post", encoding="utf-8")
            write_generated_site_data(
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
                        "extra": {},
                        "source_file": source,
                    }
                ],
                {},
            )
            generated = context.generated_site_data_file.read_text(encoding="utf-8")
            self.assertIn(
                "update: (year: 2026, month: 3, day: 4, patch: 0)", generated
            )

    def test_extra_outputs_are_written_to_private_build_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "post" / "index.typ"
            source.parent.mkdir()
            source.write_text("post", encoding="utf-8")
            post = {
                "slug": "post",
                "url_slug": "post",
                "title": "Post",
                "create": make_calver(2026, 1, 1),
                "update": None,
                "description": "Description",
                "tags": (),
                "draft": False,
                "extra": {},
                "source_file": source,
            }
            write_generated_site_data(
                context,
                [post],
                {},
                post_outputs={
                    "post": [
                        {
                            "id": "pdf",
                            "label": "PDF",
                            "media_type": "application/pdf",
                            "path": "/post/article.pdf",
                        }
                    ]
                },
            )

            generated = context.generated_site_data_file.read_text(encoding="utf-8")
            self.assertIn('#let posts = (', generated)
            self.assertIn('id: "pdf"', generated)
            self.assertIn('media-type: "application/pdf"', generated)
            self.assertIn('path: "/post/article.pdf"', generated)

    def test_extra_round_trips_through_generated_typst_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source = context.root_dir / "post" / "index.typ"
            source.parent.mkdir()
            source.write_text("post", encoding="utf-8")
            extra = {
                "course": {"id": "Typst入門", "lesson": 2},
                "featured": True,
                "note": "first line\nsecond line",
            }
            write_generated_site_data(
                context,
                [
                    {
                        "slug": "post",
                        "url_slug": "post",
                        "title": "Post",
                        "create": make_calver(2026, 1, 1),
                        "update": None,
                        "description": "Description",
                        "tags": (),
                        "draft": False,
                        "extra": extra,
                        "source_file": source,
                    }
                ],
                {},
            )

            result = subprocess.run(
                [
                    "typst",
                    "eval",
                    "--format",
                    "json",
                    '{ import "/.build/typst/site-data.typ": posts; posts.at("post").extra }',
                    "--root",
                    str(context.root_dir),
                ],
                check=True,
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            self.assertEqual(json.loads(result.stdout), extra)

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
                "extra": {},
                "source_file": source,
            }

            write_generated_site_data(context, [draft], {"Draft": "Draft"})
            published = context.generated_site_data_file.read_text(encoding="utf-8")
            self.assertNotIn('"draft-post"', published)

            write_generated_site_data(
                context,
                [draft],
                {"Draft": "Draft"},
                include_drafts=True,
            )
            preview = context.generated_site_data_file.read_text(encoding="utf-8")
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
            for value in (
                "../outside",
                "/tmp/posts",
                "C:\\posts",
                "vendor/posts",
                "static",
                "theme/posts",
            ):
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
