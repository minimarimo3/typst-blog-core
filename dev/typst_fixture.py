"""Small Typst fixtures shared by contract tests; no user blog is required."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]


def site_source(body: str = "#metadata(site) <result>", **settings: str) -> str:
    """Build a minimal site using raw Typst expressions for setting values."""
    values = {
        "title": '"Test"',
        "description": '"Test site"',
        "base_url": '"https://example.com"',
        "language": '"en"',
        "fonts": '(main: (pdf: "serif", web: none), code: (pdf: "monospace", web: none))',
        "author": '(name: "Test", bio: "", links: ())',
    }
    values.update(settings)
    arguments = "\n".join(f"  {key}: {value}," for key, value in values.items())
    return (
        '#import "/vendor/typst-blog-core/typst/site-api.typ": site as make-site\n'
        f"#let site = make-site(\n{arguments}\n)\n{body}\n"
    )


def create_config_blog(root: Path, **settings: str) -> None:
    vendored = root / "vendor/typst-blog-core"
    vendored.parent.mkdir(parents=True, exist_ok=True)
    vendored.symlink_to(CORE_DIR, target_is_directory=True)
    (root / "site.typ").write_text(
        site_source("#metadata(site) <site-meta>", **settings), encoding="utf-8"
    )


def run_typst(
    source: str,
    *,
    root: Path | None = None,
    expression: str = "query(<result>).map(it => it.value)",
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        if root is None:
            root = Path(directory)
            create_config_blog(root)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".typ", dir=root, encoding="utf-8"
        ) as source_file:
            source_file.write(source)
            source_file.flush()
            result = subprocess.run(
                ["typst", "eval", expression, "--in", source_file.name,
                 "--root", str(root), "--features", "html"],
                cwd=root, capture_output=True, text=True, encoding="utf-8",
            )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result
