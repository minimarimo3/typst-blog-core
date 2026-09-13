from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Sequence

from .builder import build
from .new_page import PageTemplate, create_page
from .new_post import PostTemplate, create_post, parse_post_date
from .preview import preview


ConfigureNewPostParser = Callable[[argparse.ArgumentParser], None]
ConfigureNewPageParser = Callable[[argparse.ArgumentParser], None]


def _preview_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _parser(
    configure_new_post: ConfigureNewPostParser | None = None,
    configure_new_page: ConfigureNewPageParser | None = None,
    *,
    preview_host: str = "localhost",
    preview_port: int = 8000,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, build, and preview a Typst blog.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("build", help="build the deployable site")
    preview_parser = subparsers.add_parser(
        "preview", help="build, serve, watch, and live-reload locally"
    )
    preview_parser.add_argument(
        "--host",
        default=preview_host,
        help=f"server host (default: {preview_host})",
    )
    preview_parser.add_argument(
        "--port",
        type=_preview_port,
        default=str(preview_port),
        help=f"starting server port (default: {preview_port})",
    )

    new_parser = subparsers.add_parser("new", help="create a post or page")
    new_subparsers = new_parser.add_subparsers(dest="content_type", required=True)

    post_parser = new_subparsers.add_parser("post", help="create a new post")
    post_parser.add_argument("slug", help="post directory name (also the default URL path)")
    post_parser.add_argument("--title", default="", help="post title (default: empty)")
    post_parser.add_argument(
        "--description",
        default="",
        help="short post description (default: empty)",
    )
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
    core_post_arguments = {action.dest for action in post_parser._actions}
    if configure_new_post is not None:
        configure_new_post(post_parser)
    custom_post_arguments = tuple(
        action.dest
        for action in post_parser._actions
        if action.dest not in core_post_arguments
    )
    post_parser.set_defaults(_custom_post_arguments=custom_post_arguments)

    page_parser = new_subparsers.add_parser("page", help="create a new general page")
    page_parser.add_argument("slug", help="page directory name (also the default URL path)")
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
    core_page_arguments = {action.dest for action in page_parser._actions}
    if configure_new_page is not None:
        configure_new_page(page_parser)
    custom_page_arguments = tuple(
        action.dest
        for action in page_parser._actions
        if action.dest not in core_page_arguments
    )
    page_parser.set_defaults(_custom_page_arguments=custom_page_arguments)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    root_dir: Path | str | None = None,
    configure_new_post: ConfigureNewPostParser | None = None,
    new_post_template: PostTemplate | None = None,
    configure_new_page: ConfigureNewPageParser | None = None,
    new_page_template: PageTemplate | None = None,
    preview_host: str = "localhost",
    preview_port: int = 8000,
) -> int:
    args = _parser(
        configure_new_post,
        configure_new_page,
        preview_host=preview_host,
        preview_port=preview_port,
    ).parse_args(argv)
    command = args.command or "build"
    try:
        if command == "build":
            build(root_dir=root_dir)
        elif command == "preview":
            preview(root_dir=root_dir, host=args.host, port=args.port)
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
                    extra={
                        name: getattr(args, name)
                        for name in args._custom_post_arguments
                        if getattr(args, name, None) is not None
                    },
                    template=new_post_template,
                )
            else:
                index_file = create_page(
                    root_dir=root_dir,
                    slug=args.slug,
                    title=args.title,
                    description=args.description,
                    publish=args.publish,
                    indexed=not args.no_index,
                    extra={
                        name: getattr(args, name)
                        for name in args._custom_page_arguments
                        if getattr(args, name, None) is not None
                    },
                    template=new_page_template,
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
