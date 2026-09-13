from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.builder import generate_alias_redirects  # noqa: E402
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
    validate_permalink,
    validate_post_slug,
    validate_post_tags,
    write_generated_site_data,
)
from post_factory import make_post_record  # noqa: E402
from typst_fixture import create_config_blog, run_typst  # noqa: E402


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
            "index.html",
            "404.html",
            "feed.xml",
            "FEED.XML",
            "sitemap.xml",
            "tags",
            "pagefind",
            "color-schemes",
            "CNAME",
            "favicon.ico",
            "favicon.svg",
            "robots.txt",
            "site.webmanifest",
            "manifest.webmanifest",
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
                validate_post_output_routes(
                    [{"route_path": "my-first-post", "aliases": ()}], static_dir
                )

    def test_rejects_non_nfc_slug(self) -> None:
        with self.assertRaisesRegex(ValueError, "NFC"):
            validate_post_slug("カ\N{COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK}")


class PermalinkTests(unittest.TestCase):
    def test_accepts_nested_directory_urls(self) -> None:
        self.assertEqual(
            validate_permalink("/記事/Typst 入門/"),
            "記事/Typst 入門",
        )
        self.assertEqual(validate_permalink("/blog/tags/"), "blog/tags")

    def test_requires_absolute_directory_url(self) -> None:
        for value in ("blog/post/", "/blog/post", "/", "/blog//post/"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_permalink(value)

    def test_collects_default_nested_route_and_permalink_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            posts_dir = context.root_dir / "posts"
            source = posts_dir / "fugafuga" / "piyo" / "index.typ"
            source.parent.mkdir(parents=True)
            source.write_text("post", encoding="utf-8")
            metadata = {
                "title": "Post",
                "create": "2026.09.09",
                "description": "Description",
                "draft": False,
            }
            with patch("typst_blog_core.metadata.load_post_metadata", return_value=metadata):
                post = collect_posts(context, posts_dir)[0]
            self.assertEqual(post.route_path, "fugafuga/piyo")
            self.assertEqual(post.url_slug, "fugafuga/piyo")

            metadata["permalink"] = "/piyopiyo/"
            metadata["aliases"] = ["/fugafuga/piyo/", "/old/piyo/"]
            with patch("typst_blog_core.metadata.load_post_metadata", return_value=metadata):
                post = collect_posts(context, posts_dir)[0]
            self.assertEqual(post.route_path, "piyopiyo")
            self.assertEqual(post.aliases, ("fugafuga/piyo", "old/piyo"))

    def test_alias_redirect_preserves_query_and_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            post = make_post_record(
                context.root_dir,
                route_path="new/path",
                url_slug="new/path",
                aliases=("old/path",),
            )
            generate_alias_redirects(
                context,
                {"base_url": "https://example.com/blog", "language": "ja"},
                [post],
            )
            redirect = (context.output_dir / "old/path/index.html").read_text(encoding="utf-8")
            self.assertIn('href="/blog/new/path/"', redirect)
            self.assertIn("location.search + location.hash", redirect)


class TagSlugTests(unittest.TestCase):
    def test_preserves_simple_existing_tags(self) -> None:
        self.assertEqual(tag_to_slug("Typst"), "Typst")
        self.assertEqual(tag_to_slug("web-dev"), "web-dev")

    def test_encodes_unsafe_tag_as_portable_ascii(self) -> None:
        self.assertEqual(tag_to_slug("foo bar"), "~666f6f20626172")
        self.assertEqual(tag_to_slug("../escape"), "~2e2e2f657363617065")
        self.assertEqual(tag_to_slug("日本語"), "~e697a5e69cace8aa9e")

    def test_space_and_hyphen_tags_get_distinct_urls(self) -> None:
        post = make_post_record(Path.cwd(), tags=("foo bar", "foo-bar"))
        result = build_tag_slug_map([post])
        self.assertNotEqual(result["foo bar"], result["foo-bar"])

    def test_rejects_case_insensitive_filesystem_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "tag URL collision"):
            build_tag_slug_map([make_post_record(Path.cwd(), tags=("Tag", "tag"))])

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
                        "authors": ["Ada", "Grace"],
                        "create": "2026.09.08",
                        "description": "Description",
                        "abstract": "Summary",
                        "og-image": "/images/card.png",
                        "draft": False,
                        "extra": extra,
                    },
                ),
            ):
                posts = collect_posts(context)

            self.assertEqual(posts[0].extra, extra)
            self.assertEqual(posts[0].authors, ("Ada", "Grace"))
            self.assertEqual(posts[0].abstract, "Summary")
            self.assertEqual(posts[0].og_image, "/images/card.png")

    def test_rejects_non_dictionary_or_non_json_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "dictionary"):
            validate_post_extra(["course"])
        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            validate_post_extra({"score": float("nan")})


class GeneratedRouteDataTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.context = BlogContext.create(directory.name)
        create_config_blog(self.context.root_dir)

    def read_data(self) -> dict:
        result = run_typst(
            '#import "/vendor/typst-blog-core/typst/api.typ" as core\n'
            '#let data = core.load-build-data()\n'
            '#metadata(data) <result>\n',
            root=self.context.root_dir,
        )
        return json.loads(result.stdout)[0]

    def test_empty_site_data_is_readable_by_typst(self) -> None:
        write_generated_site_data(self.context, [], {})
        self.assertEqual(self.read_data(), {
            "posts": {}, "pages": {}, "tag-slugs": {}, "site-outputs": [],
        })

    def test_metadata_and_outputs_round_trip_through_typst(self) -> None:
        extra = {
            "course": {"id": "Typst入門", "lesson": 2},
            "featured": True,
            "note": 'first "line"\nsecond line',
        }
        post = make_post_record(
            self.context.root_dir, authors=("Ada", "Grace"), abstract="Summary",
            og_image="/images/card.png", update=make_calver(2026, 3, 4), extra=extra,
        )
        output = {"id": "pdf", "label": "PDF", "media_type": "application/pdf", "path": "/hello/article.pdf"}
        page = {"slug": "about", "url_slug": "about", "draft": False, "index": True, "extra": {"layout": "wide"}}
        write_generated_site_data(
            self.context, [post], {"Typst": "Typst"},
            post_outputs={"hello": [output]}, site_outputs=[output], pages=[page],
        )
        data = self.read_data()
        generated = data["posts"]["hello"]
        for key, expected in {
            "authors": ["Ada", "Grace"], "abstract": "Summary",
            "og-image": "/images/card.png", "extra": extra,
        }.items():
            with self.subTest(field=key):
                self.assertEqual(generated[key], expected)
        expected_output = {"id": "pdf", "label": "PDF", "media-type": "application/pdf", "path": "/hello/article.pdf"}
        self.assertEqual(generated["outputs"], [expected_output])
        self.assertEqual(data["site-outputs"], [expected_output])
        self.assertEqual(data["tag-slugs"], {"Typst": "Typst"})
        self.assertEqual(data["pages"]["about"], {
            "url-slug": "about", "draft": False, "index": True, "extra": {"layout": "wide"},
        })
        result = run_typst(
            '#import "/vendor/typst-blog-core/typst/api.typ" as core\n'
            '#metadata(core.calver-display(core.load-build-data().posts.at("hello").update)) <result>',
            root=self.context.root_dir,
        )
        self.assertEqual(json.loads(result.stdout), ["2026.03.04"])

    def test_draft_posts_and_pages_are_only_generated_for_preview(self) -> None:
        draft = make_post_record(self.context.root_dir, slug="draft-post", draft=True)
        page = {"slug": "draft-page", "url_slug": "draft-page", "draft": True, "index": True, "extra": {}}
        for preview in (False, True):
            with self.subTest(preview=preview):
                write_generated_site_data(self.context, [draft], {}, pages=[page], include_drafts=preview)
                data = self.read_data()
                self.assertEqual(set(data["posts"]), {"draft-post"} if preview else set())
                self.assertEqual(set(data["pages"]), {"draft-page"} if preview else set())
                if preview:
                    self.assertTrue(data["posts"]["draft-post"]["draft"])
                    self.assertTrue(data["pages"]["draft-page"]["draft"])


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
