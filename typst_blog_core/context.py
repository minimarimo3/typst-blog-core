from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parent.parent
STATIC_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".js",
    ".yaml",
    ".yml",
    ".bib",
    ".txt",
}
ROOT_STATIC_FILES = {
    "CNAME",
    "favicon.ico",
    "favicon.svg",
    "robots.txt",
    "site.webmanifest",
    "manifest.webmanifest",
}


@dataclass(frozen=True)
class BlogContext:
    root_dir: Path
    output_dir: Path
    generated_posts_file: Path
    core_dir: Path
    core_static_dir: Path
    user_static_dir: Path
    base_path: str | None = None

    @classmethod
    def create(
        cls,
        root_dir: Path | str | None = None,
        base_path: str | None = None,
    ) -> "BlogContext":
        root = Path(root_dir).resolve() if root_dir is not None else Path.cwd().resolve()
        return cls(
            root_dir=root,
            output_dir=root / "public",
            generated_posts_file=root / "typst" / "generated" / "posts.typ",
            core_dir=CORE_DIR,
            core_static_dir=CORE_DIR / "static",
            user_static_dir=root / "static",
            base_path=base_path,
        )


def run_typst(
    context: BlogContext,
    *args: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["typst", *args]
    if context.base_path is not None:
        command[2:2] = [
            "--input",
            f"base-path={context.base_path}",
            "--input",
            "preview=true",
        ]
    try:
        return subprocess.run(
            command,
            cwd=context.root_dir,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr, end="")
        raise
