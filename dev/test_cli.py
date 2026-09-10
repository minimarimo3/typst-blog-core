from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core import api  # noqa: E402


class CliTests(unittest.TestCase):
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
