from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import (  # noqa: E402
    _build_task,
    _run_after_html,
    _run_outputs,
    _run_post_build,
)
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.pipeline import Pipeline, load_pipeline  # noqa: E402
from post_factory import make_post_record  # noqa: E402


def make_post(root: Path):
    source = root / "hello" / "index.typ"
    source.parent.mkdir(parents=True)
    source.write_text("Hello", encoding="utf-8")
    return make_post_record(
        root,
        source_file=source,
        extra={"course": "typst-basics"},
    )


class PipelineConfigurationTests(unittest.TestCase):
    def test_loads_blog_configuration_on_each_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            config = context.root_dir / "blog.py"
            config.write_text(
                "def configure(pipeline):\n"
                "    pipeline.post_build(id='first', run=lambda task: None)\n",
                encoding="utf-8",
            )

            first = load_pipeline(context)
            self.assertEqual(first.active_post_build("build")[0].id, "first")

            config.write_text(
                "def configure(pipeline):\n"
                "    pipeline.post_build(id='second', run=lambda task: None)\n",
                encoding="utf-8",
            )
            second = load_pipeline(context)
            self.assertEqual(second.active_post_build("build")[0].id, "second")

    def test_rejects_unsafe_output_paths_and_duplicate_ids(self) -> None:
        for filename in ("../escape.pdf", "/absolute.pdf", r"dir\file.pdf", ".hidden"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                Pipeline().site_output(
                    id="unsafe",
                    filename=filename,
                    label="Unsafe",
                    media_type="application/pdf",
                    build=lambda task: None,
                )

        pipeline = Pipeline()
        pipeline.post_build(id="same", run=lambda task: None)
        with self.assertRaisesRegex(ValueError, "duplicate pipeline id"):
            pipeline.after_html(id="same", run=lambda task: None)

    def test_rejects_output_collision_before_running_callback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            post = make_post(context.root_dir)
            pipeline = Pipeline()
            pipeline.post_output(
                id="html",
                filename="index.html",
                label="HTML",
                media_type="text/html",
                build=lambda task: None,
            )
            with self.assertRaisesRegex(ValueError, "conflicts"):
                pipeline.plan_outputs(
                    context,
                    [post],
                    "build",
                    {"hello/index.html"},
                )

    def test_rejects_parent_child_file_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            pipeline = Pipeline()
            pipeline.site_output(
                id="nested",
                filename="assets/report.pdf",
                label="Report",
                media_type="application/pdf",
                build=lambda task: None,
            )
            with self.assertRaisesRegex(ValueError, "conflicts"):
                pipeline.plan_outputs(context, [], "build", {"assets"})


class PipelineExecutionTests(unittest.TestCase):
    def test_outputs_run_before_html_and_are_exposed_as_theme_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            post = make_post(context.root_dir)
            pipeline = Pipeline()

            def build_pdf(task) -> None:
                self.assertEqual(task.post.slug, "hello")
                self.assertEqual(task.post.extra["course"], "typst-basics")
                task.destination.write_text("PDF", encoding="utf-8")

            pipeline.post_output(
                id="pdf",
                filename="article.pdf",
                label="PDF",
                media_type="application/pdf",
                build=build_pdf,
            )
            post_outputs, site_outputs = pipeline.plan_outputs(
                context, [post], "build", {"hello/index.html"}
            )
            task = _build_task(context, "build", {"title": "Site"}, [post])
            planned = post_outputs["hello"]
            _run_outputs(task, planned + site_outputs)

            self.assertEqual(
                planned[0].destination.read_text(encoding="utf-8"), "PDF"
            )
            self.assertEqual(
                planned[0].as_theme_data(),
                {
                    "id": "pdf",
                    "label": "PDF",
                    "media_type": "application/pdf",
                    "path": "/hello/article.pdf",
                },
            )

    def test_pipeline_receives_complete_post_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            post = make_post_record(
                context.root_dir,
                authors=("Ada",),
                abstract="Summary",
                og_image="/images/card.png",
            )
            pipeline = Pipeline()
            pipeline.post_output(
                id="text",
                filename="record.txt",
                label="Record",
                media_type="text/plain",
                build=lambda task: None,
            )

            post_outputs, _ = pipeline.plan_outputs(context, [post], "build", set())
            pipeline_post = post_outputs[post.slug][0].post

            self.assertIs(pipeline_post, post)
            self.assertEqual(pipeline_post.authors, ("Ada",))
            self.assertEqual(pipeline_post.abstract, "Summary")
            self.assertEqual(pipeline_post.og_image, "/images/card.png")

    def test_preview_only_runs_hooks_that_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            context.output_dir.mkdir()
            html = context.output_dir / "index.html"
            html.write_text("original", encoding="utf-8")
            pipeline = Pipeline()
            calls: list[str] = []
            pipeline.after_html(
                id="html",
                run=lambda task: calls.append(task.output_path),
            )
            pipeline.post_build(
                id="build-only",
                run=lambda task: calls.append("build-only"),
            )
            pipeline.post_build(
                id="preview",
                run=lambda task: calls.append("preview"),
                modes={"preview"},
            )
            task = _build_task(context, "preview", {"title": "Site"}, [])

            _run_after_html(pipeline, task)
            _run_post_build(pipeline, task)

            self.assertEqual(calls, ["/", "preview"])


if __name__ == "__main__":
    unittest.main()
