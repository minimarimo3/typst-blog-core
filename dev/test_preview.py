from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.preview import preview  # noqa: E402


class PreviewTests(unittest.TestCase):
    def test_initial_build_includes_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = Mock()
            server.server_address = ("127.0.0.1", 8000)
            with (
                patch("typst_blog_core.preview.build") as build,
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
            )
            thread.return_value.start.assert_called_once_with()
            server.serve_forever.assert_called_once_with()
            server.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
