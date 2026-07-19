from __future__ import annotations

import datetime as dt
import re
import unicodedata
from pathlib import Path

from .context import BlogContext
from .metadata import (
    discover_post_files,
    load_site_metadata,
    portable_route_key,
    resolve_posts_dir,
    typst_string,
    validate_post_slug,
    validate_post_tags,
)


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


def _post_source(
    slug: str,
    title: str,
    description: str,
    tags: tuple[str, ...],
    create: dt.date,
    draft: bool,
) -> str:
    return f'''#import "/template.typ": article, calver, post-meta

#let meta = post-meta(
  slug: {typst_string(slug)},
  title: {typst_string(title)},
  create: calver({create.year}, {create.month}, {create.day}),
  description: {typst_string(description)},
  tags: {_format_tags(tags)},
  draft: {str(draft).lower()},
)

#metadata(meta) <post-meta>
#show: article.with(..meta)

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
) -> Path:
    context = BlogContext.create(root_dir)
    site = load_site_metadata(context)
    posts_dir = resolve_posts_dir(context, site)
    slug = validate_post_slug(unicodedata.normalize("NFC", slug))
    if not title.strip():
        raise ValueError("title must not be empty")
    if not description.strip():
        raise ValueError("description must not be empty")
    normalized_tags = validate_post_tags(tags)
    destination = posts_dir / slug
    if destination.exists():
        relative = destination.relative_to(context.root_dir)
        raise FileExistsError(f"destination already exists: {relative}")
    requested_route_key = portable_route_key(slug)
    for source_file in discover_post_files(context):
        try:
            source = source_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        match = re.search(r'\bslug\s*:\s*"([^"]+)"', source)
        if match is not None and portable_route_key(match.group(1)) == requested_route_key:
            relative = source_file.relative_to(context.root_dir)
            raise ValueError(f"slug '{slug}' is already used by {relative}")
    if context.user_static_dir.is_dir():
        static_names = {
            portable_route_key(path.name): path.name
            for path in context.user_static_dir.iterdir()
        }
        collision = static_names.get(requested_route_key)
        if collision is not None:
            raise ValueError(f"slug '{slug}' conflicts with static/{collision}")

    posts_dir.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    index_file = destination / "index.typ"
    index_file.write_text(
        _post_source(
            slug,
            title.strip(),
            description.strip(),
            normalized_tags,
            create or dt.date.today(),
            draft=not publish,
        ),
        encoding="utf-8",
    )
    return index_file
