from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core import api  # noqa: E402
from typst_blog_core.context import warn_if_typst_version_mismatch  # noqa: E402


class CliTests(unittest.TestCase):
    def test_preview_uses_configured_defaults(self) -> None:
        with (
            patch("typst_blog_core.cli.preview") as preview,
            patch(
                "typst_blog_core.cli.warn_if_typst_version_mismatch"
            ) as check_version,
        ):
            result = api.main(
                ["preview"],
                root_dir="blog",
                preview_host="0.0.0.0",
                preview_port=9000,
            )

        self.assertEqual(result, 0)
        check_version.assert_called_once_with()
        preview.assert_called_once_with(root_dir="blog", host="0.0.0.0", port=9000)

    def test_preview_options_override_configured_defaults(self) -> None:
        with (
            patch("typst_blog_core.cli.preview") as preview,
            patch("typst_blog_core.cli.warn_if_typst_version_mismatch"),
        ):
            result = api.main(
                ["preview", "--host", "127.0.0.1", "--port", "9100"],
                root_dir="blog",
                preview_host="0.0.0.0",
                preview_port=9000,
            )

        self.assertEqual(result, 0)
        preview.assert_called_once_with(root_dir="blog", host="127.0.0.1", port=9100)

    def test_build_checks_typst_version_before_building(self) -> None:
        with (
            patch("typst_blog_core.cli.build") as build,
            patch(
                "typst_blog_core.cli.warn_if_typst_version_mismatch"
            ) as check_version,
        ):
            result = api.main(["build"], root_dir="blog")

        self.assertEqual(result, 0)
        check_version.assert_called_once_with()
        build.assert_called_once_with(root_dir="blog")

    def test_warns_when_typst_version_differs_from_pin(self) -> None:
        completed = subprocess.CompletedProcess(
            ["typst", "--version"],
            0,
            stdout="typst 0.14.2 (test build)\n",
            stderr="",
        )
        stderr = io.StringIO()
        with (
            patch(
                "typst_blog_core.context.subprocess.run", return_value=completed
            ) as run,
            patch("sys.stderr", stderr),
        ):
            warn_if_typst_version_mismatch()

        run.assert_called_once_with(
            ["typst", "--version"],
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        self.assertEqual(
            stderr.getvalue(),
            "Warning: Typst version mismatch: expected 0.15.0 "
            "(typst-version), but found 0.14.2.\n",
        )

    def test_matching_typst_version_does_not_warn(self) -> None:
        completed = subprocess.CompletedProcess(
            ["typst", "--version"],
            0,
            stdout="typst 0.15.0 (test build)\n",
            stderr="",
        )
        stderr = io.StringIO()
        with (
            patch("typst_blog_core.context.subprocess.run", return_value=completed),
            patch("sys.stderr", stderr),
        ):
            warn_if_typst_version_mismatch()

        self.assertEqual(stderr.getvalue(), "")

    def test_new_post_defaults_title_and_description_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_post.load_site_metadata",
                return_value={"posts_dir": "."},
            ):
                result = api.main(
                    ["new", "post", "unfinished"],
                    root_dir=directory,
                )

            self.assertEqual(result, 0)
            source = (Path(directory) / "unfinished" / "index.typ").read_text(
                encoding="utf-8"
            )
            self.assertIn('title: ""', source)
            self.assertIn('description: ""', source)

    def test_custom_new_post_arguments_use_default_template(self) -> None:
        def configure(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--course", required=True)
            parser.add_argument("--lesson", required=True, type=int)

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_post.load_site_metadata",
                return_value={"posts_dir": "."},
            ):
                result = api.main(
                    [
                        "new",
                        "post",
                        "lesson-one",
                        "--title",
                        "Lesson one",
                        "--description",
                        "Description",
                        "--course",
                        "typst-basics",
                        "--lesson",
                        "1",
                    ],
                    root_dir=directory,
                    configure_new_post=configure,
                )

            self.assertEqual(result, 0)
            source = (Path(directory) / "lesson-one" / "index.typ").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                'extra: json(bytes("{\\\"course\\\":\\\"typst-basics\\\",\\\"lesson\\\":1}"))',
                source,
            )

    def test_custom_new_post_template_receives_custom_arguments(self) -> None:
        def configure(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--course", required=True)

        def template(post: api.PostTemplateContext) -> str:
            return f"course={post.extra['course']}\n"

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_post.load_site_metadata",
                return_value={"posts_dir": "."},
            ):
                result = api.main(
                    [
                        "new",
                        "post",
                        "custom",
                        "--title",
                        "Custom",
                        "--description",
                        "Description",
                        "--course",
                        "advanced",
                    ],
                    root_dir=directory,
                    configure_new_post=configure,
                    new_post_template=template,
                )

            self.assertEqual(result, 0)
            self.assertEqual(
                (Path(directory) / "custom" / "index.typ").read_text(encoding="utf-8"),
                "course=advanced\n",
            )

    def test_custom_new_page_arguments_use_default_template(self) -> None:
        def configure(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--layout", required=True)
            parser.add_argument("--priority", type=int)

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_page.load_site_metadata",
                return_value={"posts_dir": "."},
            ):
                result = api.main(
                    [
                        "new",
                        "page",
                        "about",
                        "--title",
                        "About",
                        "--description",
                        "About this site",
                        "--layout",
                        "wide",
                        "--priority",
                        "1",
                    ],
                    root_dir=directory,
                    configure_new_page=configure,
                )

            self.assertEqual(result, 0)
            source = (Path(directory) / "pages" / "about" / "index.typ").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                'extra: json(bytes("{\\\"layout\\\":\\\"wide\\\",\\\"priority\\\":1}"))',
                source,
            )

    def test_custom_new_page_template_receives_custom_arguments(self) -> None:
        def configure(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--layout", required=True)

        def template(page: api.PageTemplateContext) -> str:
            return f"layout={page.extra['layout']}\n"

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "typst_blog_core.new_page.load_site_metadata",
                return_value={"posts_dir": "."},
            ):
                result = api.main(
                    [
                        "new",
                        "page",
                        "custom",
                        "--title",
                        "Custom",
                        "--description",
                        "Description",
                        "--layout",
                        "landing",
                    ],
                    root_dir=directory,
                    configure_new_page=configure,
                    new_page_template=template,
                )

            self.assertEqual(result, 0)
            self.assertEqual(
                (Path(directory) / "pages" / "custom" / "index.typ").read_text(
                    encoding="utf-8"
                ),
                "layout=landing\n",
            )


if __name__ == "__main__":
    unittest.main()
