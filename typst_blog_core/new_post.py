from __future__ import annotations

import datetime as dt
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .context import BlogContext
from .metadata import (
    collect_pages,
    collect_posts,
    format_typst_json,
    load_site_metadata,
    portable_route_key,
    resolve_posts_dir,
    typst_string,
    validate_content_route_available,
    validate_post_extra,
    validate_post_slug,
    validate_post_tags,
)


@dataclass(frozen=True)
class PostTemplateContext:
    """Validated values available to a site-owned new-post template."""

    slug: str
    title: str
    description: str
    tags: tuple[str, ...]
    create: dt.date
    draft: bool
    extra: Mapping[str, object]


PostTemplate = Callable[[PostTemplateContext], str]


def parse_post_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc


def _format_tags(tags: tuple[str, ...]) -> str:
    if not tags:
        return "()"
    values = ", ".join(typst_string(tag) for tag in tags)
    return f"({values}{',' if len(tags) == 1 else ''})"


def default_post_template(post: PostTemplateContext) -> str:
    extra = (
        f"\n  extra: {format_typst_json(dict(post.extra))},"
        if post.extra
        else ""
    )
    return f'''#import "/template.typ": post, calver

#show: post.with(
  title: {typst_string(post.title)},
  create: calver({post.create.year}, {post.create.month}, {post.create.day}),
  description: {typst_string(post.description)},
  tags: {_format_tags(post.tags)},{extra}
  draft: {str(post.draft).lower()},
)

// Write the post body below.
'''


def create_post(
    *,
    root_dir: Path | str | None,
    slug: str,
    title: str,
    description: str,
    tags: list[str] | tuple[str, ...] = (),
    create: dt.date | None = None,
    publish: bool = False,
    extra: Mapping[str, object] | None = None,
    template: PostTemplate | None = None,
) -> Path:
    context = BlogContext.create(root_dir)
    site = load_site_metadata(context)
    posts_dir = resolve_posts_dir(context, site)
    slug = validate_post_slug(unicodedata.normalize("NFC", slug))
    normalized_tags = validate_post_tags(tags)
    normalized_extra = validate_post_extra(dict(extra or {}))
    destination = posts_dir / slug
    if destination.exists():
        relative = destination.relative_to(context.root_dir)
        raise FileExistsError(f"destination already exists: {relative}")
    validate_content_route_available(
        slug,
        collect_posts(context, posts_dir),
        collect_pages(context),
    )
    requested_route_key = portable_route_key(slug)
    for static_dir in (context.theme_static_dir, context.user_static_dir):
        if static_dir.is_dir():
            static_names = {
                portable_route_key(path.name): path.name
                for path in static_dir.iterdir()
            }
            collision = static_names.get(requested_route_key)
            if collision is not None:
                raise ValueError(f"slug '{slug}' conflicts with static/{collision}")

    post_context = PostTemplateContext(
        slug=slug,
        title=title.strip(),
        description=description.strip(),
        tags=normalized_tags,
        create=create or dt.date.today(),
        draft=not publish,
        extra=normalized_extra,
    )
    source = (template or default_post_template)(post_context)
    if not isinstance(source, str):
        raise TypeError("new-post template must return a string")

    posts_dir.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    index_file = destination / "index.typ"
    index_file.write_text(source, encoding="utf-8")
    return index_file
