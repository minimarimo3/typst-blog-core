from __future__ import annotations

import errno
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.preview import (  # noqa: E402
    _changed_paths,
    _rebuild_preview_changes,
    _static_output_path,
    _sync_static_changes,
    preview,
    _preview_snapshot,
)


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
            (root / "theme" / "static").mkdir(parents=True)
            (root / "theme" / "static" / "manifest.txt").write_text("asset")
            (root / "robots.txt").write_text("robots")

            snapshot = _preview_snapshot(root, frozenset({".woff2"}))

            self.assertIn("posts/article.typ", snapshot)
            self.assertIn("posts/font.woff2", snapshot)
            self.assertIn("theme/static/manifest.txt", snapshot)
            self.assertIn("robots.txt", snapshot)
            self.assertNotIn("posts/ignored.mp4", snapshot)
            self.assertNotIn(".build/typst/site-data.typ", snapshot)

    def test_initial_build_includes_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = Mock()
            server.server_address = ("127.0.0.1", 8000)
            prepared = Mock()
            prepared.asset_extensions = frozenset({".woff2"})
            with (
                patch(
                    "typst_blog_core.preview._full_preview_build",
                    return_value=prepared,
                ) as build,
                patch(
                    "typst_blog_core.preview.http.server.ThreadingHTTPServer",
                    return_value=server,
                ) as server_factory,
                patch("typst_blog_core.preview.threading.Thread") as thread,
            ):
                preview(directory)

            build.assert_called_once_with(Path(directory).resolve())
            server_factory.assert_called_once_with(("localhost", 8000), ANY)
            thread.return_value.start.assert_called_once_with()
            self.assertEqual(thread.call_args.kwargs["args"][2], prepared)
            server.serve_forever.assert_called_once_with()
            server.server_close.assert_called_once_with()

    def test_retries_with_next_port_when_starting_port_is_in_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = Mock()
            server.server_address = ("0.0.0.0", 9001)
            prepared = Mock(asset_extensions=frozenset())
            address_in_use = OSError(errno.EADDRINUSE, "Address already in use")
            with (
                patch(
                    "typst_blog_core.preview._full_preview_build",
                    return_value=prepared,
                ),
                patch(
                    "typst_blog_core.preview.http.server.ThreadingHTTPServer",
                    side_effect=[address_in_use, server],
                ) as server_factory,
                patch("typst_blog_core.preview.threading.Thread"),
            ):
                preview(directory, host="0.0.0.0", port=9000)

            self.assertEqual(
                [call.args[0] for call in server_factory.call_args_list],
                [("0.0.0.0", 9000), ("0.0.0.0", 9001)],
            )

    def test_does_not_retry_other_socket_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared = Mock(asset_extensions=frozenset())
            permission_error = OSError(errno.EACCES, "Permission denied")
            with (
                patch(
                    "typst_blog_core.preview._full_preview_build",
                    return_value=prepared,
                ),
                patch(
                    "typst_blog_core.preview.http.server.ThreadingHTTPServer",
                    side_effect=permission_error,
                ) as server_factory,
            ):
                with self.assertRaises(OSError) as raised:
                    preview(directory, port=80)

            self.assertIs(raised.exception, permission_error)
            server_factory.assert_called_once()

    def test_changed_paths_reports_added_removed_and_modified_files(self) -> None:
        before = {"same.css": (1, 1), "changed.css": (1, 1), "removed.js": (1, 1)}
        after = {"same.css": (1, 1), "changed.css": (2, 1), "added.js": (1, 1)}

        self.assertEqual(
            _changed_paths(before, after),
            {Path("changed.css"), Path("removed.js"), Path("added.js")},
        )

    def test_static_output_path_maps_theme_user_and_root_assets(self) -> None:
        self.assertEqual(
            _static_output_path(Path("theme/static/style.css")), Path("style.css")
        )
        self.assertEqual(
            _static_output_path(Path("static/images/logo.svg")),
            Path("images/logo.svg"),
        )
        self.assertEqual(_static_output_path(Path("robots.txt")), Path("robots.txt"))
        self.assertIsNone(_static_output_path(Path("theme/theme.typ")))

    def test_static_sync_preserves_full_build_precedence_and_removes_deleted_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "theme" / "static").mkdir(parents=True)
            (root / "static").mkdir()
            (root / "public").mkdir()
            (root / "theme" / "static" / "style.css").write_text("theme")
            (root / "static" / "style.css").write_text("user")
            (root / "public" / "old.js").write_text("old")
            context = SimpleNamespace(
                root_dir=root,
                output_dir=root / "public",
                user_static_dir=root / "static",
                theme_static_dir=root / "theme" / "static",
            )
            prepared = SimpleNamespace(context=context, posts=[], pages=[])
            with (
                patch("typst_blog_core.preview.validate_extension_assets"),
                patch("typst_blog_core.preview.validate_post_output_routes"),
            ):
                _sync_static_changes(
                    prepared,
                    {Path("theme/static/style.css"), Path("static/old.js")},
                )

            self.assertEqual((root / "public" / "style.css").read_text(), "user")
            self.assertFalse((root / "public" / "old.js").exists())

    def test_content_metadata_change_falls_back_to_prepared_full_build(self) -> None:
        root = Path("/tmp/blog").resolve()
        source = root / "post" / "index.typ"
        content = {"source_file": source, "source_dir": source.parent}
        previous = SimpleNamespace(
            context=SimpleNamespace(root_dir=root),
            posts=[content],
            pages=[],
            supports_incremental_preview=lambda: True,
        )
        current = SimpleNamespace(supports_incremental_preview=lambda: True)
        with (
            patch("typst_blog_core.preview.prepare_build", return_value=current),
            patch(
                "typst_blog_core.preview._same_incremental_inputs",
                return_value=False,
            ),
            patch(
                "typst_blog_core.preview.build_prepared",
                return_value=current,
            ) as full_build,
        ):
            result = _rebuild_preview_changes(
                root,
                previous,
                {Path("post/index.typ")},
            )

        self.assertIs(result, current)
        full_build.assert_called_once_with(current)

    def test_unchanged_content_metadata_rebuilds_only_that_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pages" / "about" / "index.typ"
            source.parent.mkdir(parents=True)
            source.write_text("page")
            content = {
                "source_file": source,
                "source_dir": source.parent,
                "route_path": "about",
            }
            context = SimpleNamespace(root_dir=root, output_dir=root / "public")
            previous = SimpleNamespace(
                context=context,
                posts=[],
                pages=[content],
                supports_incremental_preview=lambda: True,
            )
            current = SimpleNamespace(
                context=context,
                posts=[],
                pages=[content],
                asset_extensions=frozenset({".png"}),
                supports_incremental_preview=lambda: True,
            )
            with (
                patch("typst_blog_core.preview.prepare_build", return_value=current),
                patch(
                    "typst_blog_core.preview._same_incremental_inputs",
                    return_value=True,
                ),
                patch("typst_blog_core.preview.build_page") as build_page,
                patch("typst_blog_core.preview.build_prepared") as full_build,
            ):
                result = _rebuild_preview_changes(
                    root,
                    previous,
                    {Path("pages/about/index.typ")},
                )

            self.assertIs(result, current)
            build_page.assert_called_once_with(context, content, frozenset({".png"}))
            full_build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
