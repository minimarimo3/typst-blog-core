from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .context import BlogContext
from .metadata import (
    PAGES_DIR_NAME,
    discover_content_files,
    portable_route_key,
    typst_string,
    validate_post_slug,
)


def _page_source(
    slug: str,
    title: str,
    description: str,
    draft: bool,
    indexed: bool,
) -> str:
    return f'''#import "/template.typ": site-page

#show: site-page.with(
  title: {typst_string(title)},
  description: {typst_string(description)},
  draft: {str(draft).lower()},
  index: {str(indexed).lower()},
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
) -> Path:
    context = BlogContext.create(root_dir)
    slug = validate_post_slug(unicodedata.normalize("NFC", slug))
    if not title.strip():
        raise ValueError("title must not be empty")
    if not description.strip():
        raise ValueError("description must not be empty")

    destination = context.root_dir / PAGES_DIR_NAME / slug
    if destination.exists():
        relative = destination.relative_to(context.root_dir)
        raise FileExistsError(f"destination already exists: {relative}")

    requested_route_key = portable_route_key(slug)
    for source_file in discover_content_files(context):
        try:
            source = source_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        match = re.search(r'\bslug\s*:\s*"([^"]+)"', source)
        if match is not None and portable_route_key(match.group(1)) == requested_route_key:
            relative = source_file.relative_to(context.root_dir)
            raise ValueError(f"slug '{slug}' is already used by {relative}")

    for static_dir in (context.theme_static_dir, context.user_static_dir):
        if not static_dir.is_dir():
            continue
        static_names = {
            portable_route_key(path.name): path.name for path in static_dir.iterdir()
        }
        collision = static_names.get(requested_route_key)
        if collision is not None:
            raise ValueError(f"slug '{slug}' conflicts with static/{collision}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    index_file = destination / "index.typ"
    index_file.write_text(
        _page_source(
            slug,
            title.strip(),
            description.strip(),
            draft=not publish,
            indexed=indexed,
        ),
        encoding="utf-8",
    )
    return index_file
