from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .context import BlogContext
from .metadata import (
    PAGES_DIR_NAME,
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
)


@dataclass(frozen=True)
class PageTemplateContext:
    """Validated values available to a site-owned new-page template."""

    slug: str
    title: str
    description: str
    draft: bool
    indexed: bool
    extra: Mapping[str, object]


PageTemplate = Callable[[PageTemplateContext], str]


def default_page_template(page: PageTemplateContext) -> str:
    extra = (
        f"\n  extra: {format_typst_json(dict(page.extra))},"
        if page.extra
        else ""
    )
    return f'''#import "/template.typ": site-page

#show: site-page.with(
  title: {typst_string(page.title)},
  description: {typst_string(page.description)},{extra}
  draft: {str(page.draft).lower()},
  index: {str(page.indexed).lower()},
)

// Write the page body below.
'''


def create_page(
    *,
    root_dir: Path | str | None,
    slug: str,
    title: str,
    description: str,
    publish: bool = False,
    indexed: bool = True,
    extra: Mapping[str, object] | None = None,
    template: PageTemplate | None = None,
) -> Path:
    context = BlogContext.create(root_dir)
    slug = validate_post_slug(unicodedata.normalize("NFC", slug))
    if not title.strip():
        raise ValueError("title must not be empty")
    if not description.strip():
        raise ValueError("description must not be empty")
    normalized_extra = validate_post_extra(dict(extra or {}))

    destination = context.root_dir / PAGES_DIR_NAME / slug
    if destination.exists():
        relative = destination.relative_to(context.root_dir)
        raise FileExistsError(f"destination already exists: {relative}")

    site = load_site_metadata(context)
    posts_dir = resolve_posts_dir(context, site)
    validate_content_route_available(
        slug,
        collect_posts(context, posts_dir),
        collect_pages(context),
    )
    requested_route_key = portable_route_key(slug)

    for static_dir in (context.theme_static_dir, context.user_static_dir):
        if not static_dir.is_dir():
            continue
        static_names = {
            portable_route_key(path.name): path.name for path in static_dir.iterdir()
        }
        collision = static_names.get(requested_route_key)
        if collision is not None:
            raise ValueError(f"slug '{slug}' conflicts with static/{collision}")

    page_context = PageTemplateContext(
        slug=slug,
        title=title.strip(),
        description=description.strip(),
        draft=not publish,
        indexed=indexed,
        extra=normalized_extra,
    )
    source = (template or default_page_template)(page_context)
    if not isinstance(source, str):
        raise TypeError("new-page template must return a string")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    index_file = destination / "index.typ"
    index_file.write_text(source, encoding="utf-8")
    return index_file
