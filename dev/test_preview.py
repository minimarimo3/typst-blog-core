from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.preview import _preview_snapshot, preview  # noqa: E402


class PreviewTests(unittest.TestCase):
    def test_snapshot_ignores_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".build" / "typst").mkdir(parents=True)
            (root / ".build" / "typst" / "site-data.typ").write_text("generated")
            (root / "posts").mkdir()
            (root / "posts" / "article.typ").write_text("source")
            (root / "posts" / "font.woff2").write_text("font")
            (root / "posts" / "ignored.mp4").write_text("video")

            snapshot = _preview_snapshot(root, frozenset({".woff2"}))

            self.assertIn("posts/article.typ", snapshot)
            self.assertIn("posts/font.woff2", snapshot)
            self.assertNotIn("posts/ignored.mp4", snapshot)
            self.assertNotIn(".build/typst/site-data.typ", snapshot)

    def test_initial_build_includes_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = Mock()
            server.server_address = ("127.0.0.1", 8000)
            with (
                patch("typst_blog_core.preview.build") as build,
                patch(
                    "typst_blog_core.preview.load_site_config",
                    return_value={"asset_extensions": [".woff2"]},
                ),
                patch(
                    "typst_blog_core.preview.http.server.ThreadingHTTPServer",
                    return_value=server,
                ),
                patch("typst_blog_core.preview.threading.Thread") as thread,
            ):
                preview(directory)

            build.assert_called_once_with(
                root_dir=Path(directory).resolve(),
                base_path="",
                include_drafts=True,
                mode="preview",
            )
            thread.return_value.start.assert_called_once_with()
            self.assertEqual(
                thread.call_args.kwargs["args"][2],
                frozenset({".woff2"}),
            )
            server.serve_forever.assert_called_once_with()
            server.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
