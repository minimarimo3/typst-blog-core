from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import copy_content_assets, reserved_output_paths  # noqa: E402
from typst_blog_core.context import BlogContext  # noqa: E402
from post_factory import make_post_record  # noqa: E402


class ContentAssetTests(unittest.TestCase):
    def test_copies_only_site_configured_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "post"
            output_dir = root / "public" / "post"
            source_dir.mkdir()
            source_file = source_dir / "index.typ"
            source_file.write_text("post", encoding="utf-8")
            (source_dir / "movie.MP4").write_bytes(b"video")
            (source_dir / "font.woff2").write_bytes(b"font")
            (source_dir / "ignored.bin").write_bytes(b"ignored")

            copy_content_assets(
                {"source_dir": source_dir, "source_file": source_file},
                output_dir,
                frozenset({".mp4", ".woff2"}),
            )

            self.assertEqual((output_dir / "movie.MP4").read_bytes(), b"video")
            self.assertEqual((output_dir / "font.woff2").read_bytes(), b"font")
            self.assertFalse((output_dir / "ignored.bin").exists())

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
            )

            self.assertIn("post/audio.mp3", paths)
            self.assertNotIn("post/ignored.bin", paths)


if __name__ == "__main__":
    unittest.main()
