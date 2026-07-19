from __future__ import annotations

import calendar
import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

from .context import BlogContext, run_typst


SITE_METADATA_LABEL = "<site-meta>"
POST_METADATA_LABEL = "<post-meta>"
EXCLUDED_DIRS = {".git", ".github", "public", "typst", "vendor", "__pycache__"}
CALVER_TEXT_RE = re.compile(r"(\d{2}|\d{4})\.(\d{1,2})\.(\d{1,2})(?:\.(\d+))?")
THEME_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
TAG_PLAIN_SLUG_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?")
GENERATED_ROUTE_NAMES = {"pagefind", "tags", "themes"}
PORTABLE_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
RESERVED_POST_SLUGS = GENERATED_ROUTE_NAMES | PORTABLE_RESERVED_NAMES
RESERVED_POST_DIRS = EXCLUDED_DIRS | {"static"}


@dataclass(frozen=True, order=True)
class CalVer:
    year: int
    month: int
    day: int
    patch: int = 0

    def as_datetime(self) -> dt.datetime:
        return dt.datetime(self.year, self.month, self.day, tzinfo=dt.timezone.utc)


def load_site_metadata(context: BlogContext) -> dict:
    data = eval_metadata_values(context, "site.typ", SITE_METADATA_LABEL)
    if not data:
        raise ValueError("site.typ must include #metadata(site) <site-meta>")
    return data[0]


def eval_metadata_values(
    context: BlogContext,
    input_path: str,
    label: str,
) -> list:
    result = run_typst(
        context,
        "eval",
        f"query({label}).map(it => it.value)",
        "--in",
        input_path,
        "--root",
        ".",
        "--features",
        "html",
        capture_output=True,
    )
    return json.loads(result.stdout)


def resolve_posts_dir(context: BlogContext, site: dict) -> Path:
    value = site.get("posts_dir", ".")
    if not isinstance(value, str) or not value:
        raise ValueError("site.posts_dir must be a non-empty string")
    if "\\" in value or "\0" in value:
        raise ValueError("site.posts_dir must use a portable relative path")

    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute() or ".." in path.parts:
        raise ValueError("site.posts_dir must stay inside the blog root")
    if path.parts and path.parts[0].casefold() in RESERVED_POST_DIRS:
        raise ValueError(
            f"site.posts_dir may not use the managed directory '{path.parts[0]}'"
        )

    resolved = (context.root_dir / Path(*path.parts)).resolve()
    if not resolved.is_relative_to(context.root_dir):
        raise ValueError("site.posts_dir must stay inside the blog root")
    return resolved


def load_site_config(context: BlogContext) -> dict:
    site = load_site_metadata(context)

    for field in ("title", "description", "base_url", "language"):
        if not site.get(field):
            raise ValueError(f"site.{field} is required")

    theme = site.get("theme", "dark")
    if not isinstance(theme, str) or not theme:
        raise ValueError("site.theme must be a non-empty string")
    if not THEME_NAME_RE.fullmatch(theme):
        raise ValueError("site.theme may only contain letters, numbers, underscores, and hyphens")
    theme_paths = (
        context.user_static_dir / "themes" / f"{theme}.css",
        context.core_static_dir / "themes" / f"{theme}.css",
    )
    if not any(path.is_file() for path in theme_paths):
        raise ValueError(
            f"site.theme '{theme}' does not exist in static/themes "
            "or vendor/typst-blog-core/static/themes"
        )

    site["base_url"] = site["base_url"].rstrip("/")
    site["theme"] = theme
    update_policy = site.get("update_policy", "git")
    if update_policy not in {"git", "manual"}:
        raise ValueError("site.update_policy must be 'git' or 'manual'")
    site["update_policy"] = update_policy
    return site


def normalize_calver_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def make_calver(year: int, month: int, day: int, patch: int = 0) -> CalVer:
    if year < 0:
        raise ValueError("CalVer year must be 0 or greater")
    year = normalize_calver_year(year)
    if not 1 <= month <= 12:
        raise ValueError("CalVer month must be between 1 and 12")
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        raise ValueError("CalVer day is not a valid day for the year and month")
    if patch < 0:
        raise ValueError("CalVer patch must be 0 or greater")
    return CalVer(year, month, day, patch)


def parse_calver(raw: object) -> CalVer | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        try:
            return make_calver(
                int(raw["year"]),
                int(raw["month"]),
                int(raw["day"]),
                int(raw.get("patch", 0)),
            )
        except KeyError as exc:
            raise ValueError("CalVer must include year, month, and day") from exc
    if not isinstance(raw, str):
        raise ValueError("CalVer must be a calver(...) value or YYYY.MM.DD[.PATCH] string")
    match = CALVER_TEXT_RE.fullmatch(raw.strip())
    if not match:
        raise ValueError("CalVer must be YYYY.MM.DD or YYYY.MM.DD.PATCH")
    return make_calver(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4) or 0),
    )


def typst_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def format_typst_calver(value: CalVer) -> str:
    return f"(year: {value.year}, month: {value.month}, day: {value.day}, patch: {value.patch})"


def discover_post_files(
    context: BlogContext,
    posts_dir: Path | None = None,
) -> list[Path]:
    post_files: list[Path] = []
    search_root = posts_dir or context.root_dir
    if not search_root.is_dir():
        return post_files
    for path in search_root.rglob("index.typ"):
        if path == context.root_dir / "index.typ":
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(context.root_dir).parts):
            continue
        post_files.append(path)
    return sorted(post_files)


def load_post_metadata(context: BlogContext, path: Path) -> dict | None:
    data = eval_metadata_values(
        context,
        str(path.relative_to(context.root_dir)),
        POST_METADATA_LABEL,
    )
    return data[0] if data else None


def validate_post_slug(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("slug is required and must be a string")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        raise ValueError("slug must use Unicode NFC normalization")
    words = value.split("-")
    if any(
        not word
        or not all(
            character.isalnum() and character == character.lower()
            for character in word
        )
        for word in words
    ):
        raise ValueError(
            "slug must contain only lowercase Unicode letters, numbers, and single hyphens "
            "between words (examples: my-first-post, 日本語の記事)"
        )
    if value.casefold() in RESERVED_POST_SLUGS:
        raise ValueError(f"slug '{value}' is reserved for site output")
    return value


def post_slug_to_url_segment(slug: str) -> str:
    return quote(slug, safe="-")


def portable_route_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def validate_post_tags(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("tags must be an array of strings")
    tags: list[str] = []
    seen: set[str] = set()
    for tag in value:
        if not isinstance(tag, str) or not tag:
            raise ValueError("each tag must be a non-empty string")
        if tag != tag.strip():
            raise ValueError(f"tag {tag!r} must not start or end with whitespace")
        normalized = unicodedata.normalize("NFC", tag)
        if normalized in seen:
            raise ValueError(f"duplicate tag: {tag}")
        seen.add(normalized)
        tags.append(tag)
    return tuple(tags)


def tag_to_slug(tag: str) -> str:
    normalized = unicodedata.normalize("NFC", tag)
    if (
        TAG_PLAIN_SLUG_RE.fullmatch(normalized)
        and normalized.casefold() not in PORTABLE_RESERVED_NAMES
    ):
        return normalized
    return "~" + normalized.encode("utf-8").hex()


def build_tag_slug_map(posts: list[dict]) -> dict[str, str]:
    tag_slugs: dict[str, str] = {}
    slug_owners: dict[str, str] = {}
    for post in posts:
        for tag in post["tags"]:
            if tag in tag_slugs:
                continue
            slug = tag_to_slug(tag)
            portable_slug = slug.casefold()
            previous = slug_owners.get(portable_slug)
            if previous is not None and previous != tag:
                raise ValueError(
                    f"tag URL collision: {previous!r} and {tag!r} both map to {slug!r}"
                )
            slug_owners[portable_slug] = tag
            tag_slugs[tag] = slug
    return tag_slugs


def validate_post_output_routes(posts: list[dict], static_dir: Path) -> None:
    if not static_dir.is_dir():
        return
    static_routes = {portable_route_key(path.name): path.name for path in static_dir.iterdir()}
    for post in posts:
        collision = static_routes.get(portable_route_key(post["slug"]))
        if collision is not None:
            raise ValueError(f"post slug {post['slug']!r} conflicts with static/{collision}")


def collect_posts(context: BlogContext, posts_dir: Path | None = None) -> list[dict]:
    posts: list[dict] = []
    seen_slugs: dict[str, str] = {}
    for source_file in discover_post_files(context, posts_dir):
        meta = load_post_metadata(context, source_file)
        if meta is None:
            continue
        relative = source_file.relative_to(context.root_dir)
        try:
            slug = validate_post_slug(meta.get("slug"))
            create = parse_calver(meta.get("create"))
            update = parse_calver(meta.get("update"))
            tags = validate_post_tags(meta.get("tags", []))
        except ValueError as exc:
            raise ValueError(f"{relative}: {exc}") from exc
        title = meta.get("title")
        description = meta.get("description")
        draft = meta.get("draft", True)
        if not isinstance(draft, bool):
            raise ValueError(f"{relative}: draft must be true or false")
        route_key = portable_route_key(slug)
        previous_slug = seen_slugs.get(route_key)
        if previous_slug is not None:
            raise ValueError(f"post URL collision: {previous_slug!r} and {slug!r}")
        seen_slugs[route_key] = slug
        if not title:
            raise ValueError(f"{relative}: title is required")
        if create is None:
            raise ValueError(f"{relative}: create is required")
        if not description:
            raise ValueError(f"{relative}: description is required")
        posts.append(
            {
                "slug": slug,
                "url_slug": post_slug_to_url_segment(slug),
                "title": title,
                "create": create,
                "update": update,
                "description": description,
                "tags": tags,
                "draft": draft,
                "source_file": source_file,
                "source_dir": source_file.parent,
            }
        )
    posts.sort(key=lambda post: post["create"], reverse=True)
    return posts


def write_generated_posts(
    context: BlogContext,
    posts: list[dict],
    tag_slugs: dict[str, str],
    *,
    include_drafts: bool = False,
) -> None:
    context.generated_posts_file.parent.mkdir(parents=True, exist_ok=True)
    visible_posts = (
        posts if include_drafts else [post for post in posts if not post["draft"]]
    )
    lines: list[str] = []
    if visible_posts:
        lines.append("#let post-data = (")
        for post in visible_posts:
            tags = post["tags"]
            tag_value = (
                "("
                + ", ".join(typst_string(tag) for tag in tags)
                + ("," if len(tags) == 1 else "")
                + ")"
                if tags
                else "()"
            )
            source_url_path = quote(
                post["source_file"].relative_to(context.root_dir).as_posix(),
                safe="/",
            )
            update = post["update"]
            lines.extend(
                [
                    f"  {typst_string(post['slug'])}: (",
                    f"    url-slug: {typst_string(post['url_slug'])},",
                    f"    title: {typst_string(post['title'])},",
                    f"    create: {format_typst_calver(post['create'])},",
                    f"    update: {format_typst_calver(update) if update else 'none'},",
                    f"    description: {typst_string(post['description'])},",
                    f"    tags: {tag_value},",
                    f"    draft: {'true' if post['draft'] else 'false'},",
                    f"    source_url_path: {typst_string(source_url_path)},",
                    "  ),",
                ]
            )
        lines.append(")")
    else:
        lines.append("#let post-data = (:)")
    lines.append("")
    if tag_slugs:
        lines.append("#let tag-slugs = (")
        for tag, slug in tag_slugs.items():
            lines.append(f"  {typst_string(tag)}: {typst_string(slug)},")
        lines.append(")")
    else:
        lines.append("#let tag-slugs = (:)")
    context.generated_posts_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
