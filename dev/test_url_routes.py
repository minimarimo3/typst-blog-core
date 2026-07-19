from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("typst_blog_core_build", CORE_DIR / "build.py")
assert SPEC is not None and SPEC.loader is not None
BUILD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILD
SPEC.loader.exec_module(BUILD)


class PostSlugTests(unittest.TestCase):
    def test_accepts_canonical_slug(self) -> None:
        self.assertEqual(BUILD.validate_post_slug("my-first-post"), "my-first-post")

    def test_rejects_unsafe_or_ambiguous_slugs(self) -> None:
        for slug in ("../outside", "two words", "Uppercase", "two--hyphens", "/root"):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                BUILD.validate_post_slug(slug)

    def test_rejects_generated_and_portability_reservations(self) -> None:
        for slug in ("tags", "pagefind", "themes", "con", "lpt1"):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                BUILD.validate_post_slug(slug)

    def test_rejects_collision_with_static_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            static_dir = Path(directory)
            (static_dir / "my-first-post").mkdir()
            with self.assertRaisesRegex(ValueError, "conflicts with static"):
                BUILD.validate_post_output_routes(
                    [{"slug": "my-first-post"}],
                    static_dir,
                )


class TagSlugTests(unittest.TestCase):
    def test_preserves_simple_existing_tags(self) -> None:
        self.assertEqual(BUILD.tag_to_slug("Typst"), "Typst")
        self.assertEqual(BUILD.tag_to_slug("web-dev"), "web-dev")

    def test_encodes_unsafe_tag_as_portable_ascii(self) -> None:
        self.assertEqual(BUILD.tag_to_slug("foo bar"), "~666f6f20626172")
        self.assertEqual(BUILD.tag_to_slug("../escape"), "~2e2e2f657363617065")
        self.assertEqual(BUILD.tag_to_slug("日本語"), "~e697a5e69cace8aa9e")

    def test_space_and_hyphen_tags_get_distinct_urls(self) -> None:
        result = BUILD.build_tag_slug_map([
            {"tags": ("foo bar", "foo-bar")},
        ])
        self.assertNotEqual(result["foo bar"], result["foo-bar"])

    def test_rejects_case_insensitive_filesystem_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "tag URL collision"):
            BUILD.build_tag_slug_map([{"tags": ("Tag", "tag")}])

    def test_rejects_unicode_equivalent_duplicates_in_one_post(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate tag"):
            BUILD.validate_post_tags(["é", "e\N{COMBINING ACUTE ACCENT}"])


class GeneratedRouteDataTests(unittest.TestCase):
    def test_empty_site_uses_empty_typst_dictionaries(self) -> None:
        original_path = BUILD.GENERATED_POSTS_FILE
        try:
            with tempfile.TemporaryDirectory() as directory:
                generated = Path(directory) / "posts.typ"
                BUILD.GENERATED_POSTS_FILE = generated
                BUILD.write_generated_posts([], {})
                self.assertEqual(
                    generated.read_text(encoding="utf-8"),
                    "#let post-data = (:)\n\n#let tag-slugs = (:)\n",
                )
        finally:
            BUILD.GENERATED_POSTS_FILE = original_path


if __name__ == "__main__":
    unittest.main()
