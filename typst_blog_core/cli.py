from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .builder import build
from .new_post import create_post, parse_post_date
from .new_page import create_page
from .preview import preview


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, build, and preview a Typst blog.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("build", help="build the deployable site")
    subparsers.add_parser("preview", help="build, serve, watch, and live-reload locally")

    new_parser = subparsers.add_parser("new", help="create a post or page")
    new_subparsers = new_parser.add_subparsers(dest="content_type", required=True)

    post_parser = new_subparsers.add_parser("post", help="create a new post")
    post_parser.add_argument("slug", help="URL slug and directory name")
    post_parser.add_argument("--title", required=True, help="post title")
    post_parser.add_argument("--description", required=True, help="short post description")
    post_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="post tag; repeat this option for multiple tags",
    )
    post_parser.add_argument(
        "--date",
        type=parse_post_date,
        help="creation date in YYYY-MM-DD (default: today)",
    )
    post_parser.add_argument(
        "--publish",
        action="store_true",
        help="create as published instead of the safer draft default",
    )

    page_parser = new_subparsers.add_parser("page", help="create a new general page")
    page_parser.add_argument("slug", help="URL slug and directory name")
    page_parser.add_argument("--title", required=True, help="page title")
    page_parser.add_argument("--description", required=True, help="short page description")
    page_parser.add_argument(
        "--publish",
        action="store_true",
        help="create as published instead of the safer draft default",
    )
    page_parser.add_argument(
        "--no-index",
        action="store_true",
        help="exclude the page from search engines, Pagefind, and the sitemap",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    root_dir: Path | str | None = None,
) -> int:
    args = _parser().parse_args(argv)
    command = args.command or "build"
    try:
        if command == "build":
            build(root_dir=root_dir)
        elif command == "preview":
            preview(root_dir=root_dir)
        elif command == "new":
            if args.content_type == "post":
                index_file = create_post(
                    root_dir=root_dir,
                    slug=args.slug,
                    title=args.title,
                    description=args.description,
                    tags=args.tag,
                    create=args.date,
                    publish=args.publish,
                )
            else:
                index_file = create_page(
                    root_dir=root_dir,
                    slug=args.slug,
                    title=args.title,
                    description=args.description,
                    publish=args.publish,
                    indexed=not args.no_index,
                )
            display_path = (
                index_file.relative_to(Path(root_dir).resolve())
                if root_dir
                else index_file
            )
            content_name = "post" if args.content_type == "post" else "page"
            status = f"published {content_name}" if args.publish else f"draft {content_name}"
            print(f"Created {status}: {display_path}")
        else:
            raise AssertionError(f"unknown command: {command}")
    except Exception as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        return 1
    return 0
