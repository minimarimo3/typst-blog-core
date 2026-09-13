from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import (  # noqa: E402
    copy_content_assets,
    reserved_output_paths,
    validate_content_asset_output_paths,
)
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import load_site_config  # noqa: E402
from post_factory import make_post_record  # noqa: E402
from typst_fixture import create_config_blog  # noqa: E402


class ContentAssetTests(unittest.TestCase):
    def test_copies_default_assets_and_respects_custom_allowlist(self) -> None:
        for settings, expected in (
            ({}, {"movie.MP4", "audio.mp3", "font.woff2", "image.png", "document.pdf"}),
            ({"asset_extensions": '(".mp4", ".woff2")'}, {"movie.MP4", "font.woff2"}),
        ):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as directory:
                self.check_copied_assets(Path(directory), settings, expected)

    def check_copied_assets(self, root: Path, settings: dict, expected: set[str]) -> None:
        create_config_blog(root, **settings)
        site = load_site_config(BlogContext.create(root))
        source_dir = root / "post"
        output_dir = root / "public" / "post"
        source_dir.mkdir()
        source_file = source_dir / "index.typ"
        source_file.write_text("post", encoding="utf-8")
        (source_dir / "movie.MP4").write_bytes(b"video")
        (source_dir / "audio.mp3").write_bytes(b"audio")
        (source_dir / "font.woff2").write_bytes(b"font")
        (source_dir / "image.png").write_bytes(b"image")
        (source_dir / "document.pdf").write_bytes(b"document")
        (source_dir / "ignored.bin").write_bytes(b"ignored")

        copy_content_assets(
            {"source_dir": source_dir, "source_file": source_file},
            output_dir,
            frozenset(site["asset_extensions"]),
        )

        self.assertEqual({path.name for path in output_dir.iterdir()}, expected)
        for name in expected:
            self.assertEqual((output_dir / name).read_bytes(), (source_dir / name).read_bytes())

    def test_configured_assets_reserve_pipeline_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            source_dir = context.root_dir / "post"
            source_dir.mkdir()
            source_file = source_dir / "index.typ"
            source_file.write_text("post", encoding="utf-8")
            (source_dir / "audio.mp3").write_bytes(b"audio")
            (source_dir / "ignored.bin").write_bytes(b"ignored")
            post = make_post_record(
                context.root_dir,
                slug="post",
                url_slug="post",
                source_dir=source_dir,
                source_file=source_file,
            )

            paths = reserved_output_paths(
                context,
                [post],
                [],
                {},
                frozenset({".mp3"}),
                {
                    "pagination": {
                        "home": {"enabled": True, "per_page": 1},
                        "tag": {"enabled": True, "per_page": 1},
                    }
                },
            )

            self.assertIn("post/audio.mp3", paths)
            self.assertNotIn("page/2/index.html", paths)
            self.assertNotIn("post/ignored.bin", paths)

    def test_rejects_html_asset_that_would_overwrite_generated_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "post"
            source_dir.mkdir()
            source_file = source_dir / "index.typ"
            source_file.write_text("post", encoding="utf-8")
            conflicting_asset = source_dir / "index.HTML"
            conflicting_asset.write_text("source asset", encoding="utf-8")
            content = {
                "source_dir": source_dir,
                "source_file": source_file,
            }

            with self.assertRaisesRegex(
                ValueError,
                "conflicts with generated index.html",
            ):
                validate_content_asset_output_paths(
                    [content],
                    frozenset({".html"}),
                )

            output_dir = root / "public" / "post"
            output_dir.mkdir(parents=True)
            generated = output_dir / "index.html"
            generated.write_text("generated page", encoding="utf-8")
            with self.assertRaises(ValueError):
                copy_content_assets(content, output_dir, frozenset({".html"}))
            self.assertEqual(generated.read_text(encoding="utf-8"), "generated page")


if __name__ == "__main__":
    unittest.main()
