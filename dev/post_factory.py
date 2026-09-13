from __future__ import annotations

from pathlib import Path

from typst_blog_core.metadata import PostRecord, make_calver


def make_post_record(root: Path, **overrides: object) -> PostRecord:
    source_file = Path(overrides.pop("source_file", root / "hello" / "index.typ"))
    values: dict[str, object] = {
        "slug": "hello",
        "route_path": "hello",
        "url_slug": "hello",
        "aliases": (),
        "title": "Hello",
        "authors": None,
        "create": make_calver(2026, 1, 2),
        "update": None,
        "description": "Description",
        "abstract": None,
        "og_image": None,
        "tags": (),
        "draft": False,
        "extra": {},
        "source_file": source_file,
        "source_dir": source_file.parent,
    }
    values.update(overrides)
    if "slug" in overrides and "route_path" not in overrides:
        values["route_path"] = overrides["slug"]
    if "slug" in overrides and "url_slug" not in overrides:
        values["url_slug"] = overrides["slug"]
    return PostRecord(**values)  # type: ignore[arg-type]
