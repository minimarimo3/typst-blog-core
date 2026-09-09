from __future__ import annotations

import calendar
import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Sequence
from urllib.parse import quote

from .context import BlogContext, ROOT_STATIC_FILES, run_typst


SITE_METADATA_LABEL = "<site-meta>"
EXTENSIONS_METADATA_LABEL = "<extensions-meta>"
POST_METADATA_LABEL = "<post-meta>"
PAGE_METADATA_LABEL = "<page-meta>"
PAGES_DIR_NAME = "pages"
EXCLUDED_DIRS = {
    ".git",
    ".github",
    "extensions",
    "public",
    "theme",
    "typst",
    "vendor",
    "__pycache__",
}
CALVER_TEXT_RE = re.compile(r"(\d{2}|\d{4})\.(\d{1,2})\.(\d{1,2})(?:\.(\d+))?")
TAG_PLAIN_SLUG_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?")
GENERATED_ROUTE_NAMES = {
    "404.html",
    "color-schemes",
    "feed.xml",
    "index.html",
    "pagefind",
    "scripts",
    "sitemap.xml",
    "styles",
    "tags",
    *(filename.casefold() for filename in ROOT_STATIC_FILES),
}
PORTABLE_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
RESERVED_POST_DIRS = EXCLUDED_DIRS | {"static", PAGES_DIR_NAME}
WINDOWS_FORBIDDEN_FILENAME_CHARS = frozenset('<>:"/\\|?*')
MAX_PORTABLE_FILENAME_BYTES = 255
ASSET_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]+")


@dataclass(frozen=True, order=True)
class CalVer:
    year: int
    month: int
    day: int
    patch: int = 0

    def as_datetime(self) -> dt.datetime:
        return dt.datetime(self.year, self.month, self.day, tzinfo=dt.timezone.utc)


@dataclass(frozen=True)
class PostRecord:
    slug: str
    route_path: str
    url_slug: str
    aliases: tuple[str, ...]
    title: str
    authors: tuple[str, ...] | None
    create: CalVer
    update: CalVer | None
    description: str
    abstract: object | None
    og_image: str | None
    tags: tuple[str, ...]
    draft: bool
    extra: dict[str, object]
    source_file: Path
    source_dir: Path


def load_site_metadata(context: BlogContext) -> dict:
    data = eval_metadata_values(context, "site.typ", SITE_METADATA_LABEL)
    if not data:
        raise ValueError("site.typ must include #metadata(site) <site-meta>")
    return data[0]


def validate_extension_assets(context: BlogContext) -> None:
    data = eval_metadata_values(
        context,
        "extensions.typ",
        EXTENSIONS_METADATA_LABEL,
    )
    if not data:
        raise ValueError(
            "extensions.typ must include #metadata(extensions) <extensions-meta>"
        )

    extensions = data[0]
    if not isinstance(extensions, list):
        raise ValueError("extensions must be an array")
    for extension in extensions:
        if not isinstance(extension, dict) or not all(
            field in extension for field in ("name", "styles", "scripts")
        ):
            raise ValueError(
                "extensions must contain entries created with extension(...)"
            )
        for field in ("styles", "scripts"):
            if not isinstance(extension[field], list):
                raise ValueError(
                    f"extension '{extension['name']}' {field} must be an array"
                )
            for asset in extension[field]:
                if not isinstance(asset, str):
                    raise ValueError(
                        f"extension '{extension['name']}' {field} must contain strings"
                    )
                if asset.startswith("https://"):
                    continue
                candidates = (
                    context.user_static_dir / asset,
                    context.theme_static_dir / asset,
                )
                if not any(path.is_file() for path in candidates):
                    raise ValueError(
                        f"extension '{extension['name']}' references missing "
                        f"static asset: static/{asset}"
                    )


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

    site["base_url"] = site["base_url"].rstrip("/")
    update_policy = site.get("update_policy", "git")
    if update_policy not in {"git", "manual"}:
        raise ValueError("site.update_policy must be 'git' or 'manual'")
    site["update_policy"] = update_policy
    asset_extensions = site.get("asset_extensions")
    if not isinstance(asset_extensions, list) or not asset_extensions:
        raise ValueError("site.asset_extensions must be a non-empty array")
    normalized_asset_extensions = []
    for index, extension in enumerate(asset_extensions):
        if not isinstance(extension, str) or not ASSET_EXTENSION_RE.fullmatch(extension):
            raise ValueError(
                f"site.asset_extensions[{index}] must be a dot followed by "
                "ASCII letters or digits"
            )
        normalized_asset_extensions.append(extension.lower())
    site["asset_extensions"] = normalized_asset_extensions
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
        if path.is_relative_to(context.root_dir / PAGES_DIR_NAME):
            continue
        post_files.append(path)
    return sorted(post_files)


def discover_page_files(context: BlogContext) -> list[Path]:
    pages_dir = context.root_dir / PAGES_DIR_NAME
    if not pages_dir.is_dir():
        return []
    return sorted(
        path
        for path in pages_dir.rglob("index.typ")
        if not any(part in EXCLUDED_DIRS for part in path.relative_to(pages_dir).parts)
    )


def discover_content_files(context: BlogContext) -> list[Path]:
    return sorted({*discover_post_files(context), *discover_page_files(context)})


def load_post_metadata(context: BlogContext, path: Path) -> dict | None:
    data = eval_metadata_values(
        context,
        str(path.relative_to(context.root_dir)),
        POST_METADATA_LABEL,
    )
    return data[0] if data else None


def load_page_metadata(context: BlogContext, path: Path) -> dict | None:
    data = eval_metadata_values(
        context,
        str(path.relative_to(context.root_dir)),
        PAGE_METADATA_LABEL,
    )
    return data[0] if data else None


def validate_post_slug(value: object, *, allow_generated: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("slug is required and must be a string")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        raise ValueError("slug must use Unicode NFC normalization")
    if value != value.strip():
        raise ValueError("slug must not start or end with whitespace")
    if value.startswith(".") or value.endswith("."):
        raise ValueError("slug must not start or end with a period")
    if any(character in WINDOWS_FORBIDDEN_FILENAME_CHARS for character in value):
        raise ValueError('slug must not contain any of <>:"/\\|?*')
    if any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError("slug must not contain control or non-portable Unicode characters")
    if len(value.encode("utf-8")) > MAX_PORTABLE_FILENAME_BYTES:
        raise ValueError(
            f"slug must be at most {MAX_PORTABLE_FILENAME_BYTES} UTF-8 bytes"
        )

    portable_name = value.casefold()
    windows_stem = portable_name.split(".", 1)[0].rstrip(" ")
    if (
        not allow_generated and portable_name in GENERATED_ROUTE_NAMES
    ) or windows_stem in PORTABLE_RESERVED_NAMES:
        raise ValueError(f"slug '{value}' is reserved for site output")
    return value


def post_slug_to_url_segment(slug: str) -> str:
    return quote(slug, safe="-")


def validate_permalink(value: object, *, field: str = "permalink") -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if not value.startswith("/") or not value.endswith("/"):
        raise ValueError(f"{field} must start and end with '/'")
    if value == "/":
        raise ValueError(f"{field} may not use the site root")
    if "?" in value or "#" in value or "//" in value:
        raise ValueError(f"{field} must be a clean directory URL")
    parts = value[1:-1].split("/")
    for index, part in enumerate(parts):
        try:
            validate_post_slug(part, allow_generated=index > 0)
        except ValueError as exc:
            message = str(exc).replace("slug", "path segment")
            raise ValueError(f"{field}: {message}") from exc
    return "/".join(parts)


def validate_aliases(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("aliases must be an array of permalink strings")
    aliases = tuple(validate_permalink(alias, field="alias") for alias in value)
    keys = [portable_route_key(alias) for alias in aliases]
    if len(keys) != len(set(keys)):
        raise ValueError("aliases must not contain duplicate URLs")
    return aliases


def route_to_url_path(route_path: str) -> str:
    return "/".join(post_slug_to_url_segment(part) for part in route_path.split("/"))


def default_content_route(source_file: Path, content_root: Path) -> str:
    relative_dir = source_file.parent.relative_to(content_root)
    if not relative_dir.parts:
        raise ValueError("index.typ must be inside a content directory")
    return validate_permalink("/" + relative_dir.as_posix() + "/")


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


def validate_post_extra(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("extra must be a dictionary")
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("extra must contain only JSON-compatible values") from exc
    return value


def format_typst_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return f"json(bytes({typst_string(encoded)}))"


def tag_to_slug(tag: str) -> str:
    normalized = unicodedata.normalize("NFC", tag)
    if (
        TAG_PLAIN_SLUG_RE.fullmatch(normalized)
        and normalized.casefold() not in PORTABLE_RESERVED_NAMES
    ):
        return normalized
    return "~" + normalized.encode("utf-8").hex()


def build_tag_slug_map(posts: list[PostRecord]) -> dict[str, str]:
    tag_slugs: dict[str, str] = {}
    slug_owners: dict[str, str] = {}
    for post in posts:
        for tag in post.tags:
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


def validate_post_output_routes(
    posts: Sequence[PostRecord | dict],
    static_dir: Path,
) -> None:
    if not static_dir.is_dir():
        return
    static_routes = {portable_route_key(path.name): path.name for path in static_dir.iterdir()}
    for post in posts:
        routes = (
            (post.route_path, *post.aliases)
            if isinstance(post, PostRecord)
            else (post["route_path"], *post["aliases"])
        )
        for route in routes:
            top_level = route.split("/", 1)[0]
            collision = static_routes.get(portable_route_key(top_level))
            if collision is not None:
                raise ValueError(f"content URL /{route}/ conflicts with static/{collision}")


def collect_posts(
    context: BlogContext,
    posts_dir: Path | None = None,
) -> list[PostRecord]:
    posts: list[PostRecord] = []
    posts_root = posts_dir or context.root_dir
    for source_file in discover_post_files(context, posts_root):
        meta = load_post_metadata(context, source_file)
        if meta is None:
            continue
        relative = source_file.relative_to(context.root_dir)
        try:
            default_route = default_content_route(source_file, posts_root)
            route_path = (
                default_route
                if meta.get("permalink") is None
                else validate_permalink(meta.get("permalink"))
            )
            aliases = validate_aliases(meta.get("aliases", ()))
            create = parse_calver(meta.get("create"))
            update = parse_calver(meta.get("update"))
            tags = validate_post_tags(meta.get("tags", []))
            extra = validate_post_extra(meta.get("extra", {}))
        except ValueError as exc:
            raise ValueError(f"{relative}: {exc}") from exc
        title = meta.get("title")
        description = meta.get("description")
        authors = meta.get("authors")
        abstract = meta.get("abstract")
        og_image = meta.get("og-image")
        draft = meta.get("draft", True)
        if not isinstance(title, str) or not title:
            raise ValueError(f"{relative}: title is required")
        if not isinstance(description, str) or not description:
            raise ValueError(f"{relative}: description is required")
        if authors is not None and (
            not isinstance(authors, (list, tuple))
            or not all(isinstance(author, str) and author for author in authors)
        ):
            raise ValueError(f"{relative}: authors must be an array of non-empty strings or none")
        if og_image is not None and not isinstance(og_image, str):
            raise ValueError(f"{relative}: og-image must be a string or none")
        if not isinstance(draft, bool):
            raise ValueError(f"{relative}: draft must be true or false")
        if create is None:
            raise ValueError(f"{relative}: create is required")
        posts.append(
            PostRecord(
                slug=relative.as_posix(),
                route_path=route_path,
                url_slug=route_to_url_path(route_path),
                aliases=aliases,
                title=title,
                authors=tuple(authors) if authors is not None else None,
                create=create,
                update=update,
                description=description,
                abstract=abstract,
                og_image=og_image,
                tags=tags,
                draft=draft,
                extra=extra,
                source_file=source_file,
                source_dir=source_file.parent,
            )
        )
    posts.sort(key=lambda post: post.create, reverse=True)
    return posts


def collect_pages(context: BlogContext) -> list[dict]:
    pages: list[dict] = []
    pages_dir = context.root_dir / PAGES_DIR_NAME
    for source_file in discover_page_files(context):
        meta = load_page_metadata(context, source_file)
        if meta is None:
            continue
        relative = source_file.relative_to(context.root_dir)
        try:
            default_route = default_content_route(source_file, pages_dir)
            route_path = (
                default_route
                if meta.get("permalink") is None
                else validate_permalink(meta.get("permalink"))
            )
            aliases = validate_aliases(meta.get("aliases", ()))
            extra = validate_post_extra(meta.get("extra", {}))
        except ValueError as exc:
            raise ValueError(f"{relative}: {exc}") from exc
        title = meta.get("title")
        description = meta.get("description")
        draft = meta.get("draft", True)
        indexed = meta.get("index", True)
        og_image = meta.get("og-image")
        authors = meta.get("authors")
        if not isinstance(title, str) or not title:
            raise ValueError(f"{relative}: title is required")
        if not isinstance(description, str) or not description:
            raise ValueError(f"{relative}: description is required")
        if not isinstance(draft, bool):
            raise ValueError(f"{relative}: draft must be true or false")
        if not isinstance(indexed, bool):
            raise ValueError(f"{relative}: index must be true or false")
        if og_image is not None and not isinstance(og_image, str):
            raise ValueError(f"{relative}: og-image must be a string or none")
        if authors is not None and (
            not isinstance(authors, (list, tuple))
            or not all(isinstance(author, str) and author for author in authors)
        ):
            raise ValueError(f"{relative}: authors must be an array of non-empty strings or none")
        pages.append(
            {
                "slug": relative.as_posix(),
                "route_path": route_path,
                "url_slug": route_to_url_path(route_path),
                "aliases": aliases,
                "title": title,
                "description": description,
                "authors": tuple(authors) if authors is not None else None,
                "og_image": og_image,
                "draft": draft,
                "index": indexed,
                "extra": extra,
                "source_file": source_file,
                "source_dir": source_file.parent,
            }
        )
    return pages


def validate_content_route_collisions(posts: list[PostRecord], pages: list[dict]) -> None:
    owners: dict[str, tuple[str, str]] = {}
    for post in posts:
        for route in (post.route_path, *post.aliases):
            key = portable_route_key(route)
            previous = owners.get(key)
            if previous is not None:
                previous_kind, previous_route = previous
                raise ValueError(
                    f"content URL collision: {previous_kind} /{previous_route}/ "
                    f"and post /{route}/"
                )
            owners[key] = ("post", route)
    for page in pages:
        for route in (page["route_path"], *page["aliases"]):
            key = portable_route_key(route)
            previous = owners.get(key)
            if previous is not None:
                previous_kind, previous_route = previous
                raise ValueError(
                    f"content URL collision: {previous_kind} /{previous_route}/ "
                    f"and page /{route}/"
                )
            owners[key] = ("page", route)


def format_post_typst_record(
    context: BlogContext,
    post: PostRecord,
    *,
    outputs: list[dict[str, str]] | None = None,
    indent: str = "",
) -> list[str]:
    source_url_path = quote(
        post.source_file.relative_to(context.root_dir).as_posix(),
        safe="/",
    )
    authors = "none" if post.authors is None else format_typst_json(post.authors)
    abstract = "none" if post.abstract is None else format_typst_json(post.abstract)
    og_image = "none" if post.og_image is None else typst_string(post.og_image)
    update = format_typst_calver(post.update) if post.update else "none"
    return [
        f"{indent}{typst_string(post.slug)}: (",
        f"{indent}  url-slug: {typst_string(post.url_slug)},",
        f"{indent}  title: {typst_string(post.title)},",
        f"{indent}  authors: {authors},",
        f"{indent}  create: {format_typst_calver(post.create)},",
        f"{indent}  update: {update},",
        f"{indent}  description: {typst_string(post.description)},",
        f"{indent}  abstract: {abstract},",
        f"{indent}  og-image: {og_image},",
        f"{indent}  tags: {format_typst_json(post.tags)},",
        f"{indent}  draft: {'true' if post.draft else 'false'},",
        f"{indent}  extra: {format_typst_json(post.extra)},",
        f"{indent}  source_url_path: {typst_string(source_url_path)},",
        f"{indent}  outputs: {_format_generated_outputs(outputs or [])},",
        f"{indent}),",
    ]


def write_generated_site_data(
    context: BlogContext,
    posts: list[PostRecord],
    tag_slugs: dict[str, str],
    *,
    include_drafts: bool = False,
    post_outputs: dict[str, list[dict[str, str]]] | None = None,
    site_outputs: list[dict[str, str]] | None = None,
    pages: list[dict] | None = None,
) -> None:
    context.generated_site_data_file.parent.mkdir(parents=True, exist_ok=True)
    post_outputs = post_outputs or {}
    site_outputs = site_outputs or []
    pages = pages or []
    visible_posts = (
        posts if include_drafts else [post for post in posts if not post.draft]
    )
    lines: list[str] = []
    if visible_posts:
        lines.append("#let posts = (")
        for post in visible_posts:
            lines.extend(
                format_post_typst_record(
                    context,
                    post,
                    outputs=post_outputs.get(post.slug, []),
                    indent="  ",
                )
            )
        lines.append(")")
    else:
        lines.append("#let posts = (:)")
    lines.append("")
    visible_pages = pages if include_drafts else [page for page in pages if not page["draft"]]
    if visible_pages:
        lines.append("#let pages = (")
        for page in visible_pages:
            lines.extend(
                [
                    f"  {typst_string(page['slug'])}: (",
                    f"    url-slug: {typst_string(page['url_slug'])},",
                    f"    draft: {'true' if page['draft'] else 'false'},",
                    f"    index: {'true' if page['index'] else 'false'},",
                    f"    extra: {format_typst_json(page['extra'])},",
                    "  ),",
                ]
            )
        lines.append(")")
    else:
        lines.append("#let pages = (:)")
    lines.append("")
    if tag_slugs:
        lines.append("#let tag-slugs = (")
        for tag, slug in tag_slugs.items():
            lines.append(f"  {typst_string(tag)}: {typst_string(slug)},")
        lines.append(")")
    else:
        lines.append("#let tag-slugs = (:)")
    lines.append("")
    lines.append(f"#let site-outputs = {_format_generated_outputs(site_outputs)}")
    context.generated_site_data_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_generated_outputs(outputs: list[dict[str, str]]) -> str:
    if not outputs:
        return "()"
    entries = []
    for output in outputs:
        entries.append(
            "("
            f"id: {typst_string(output['id'])}, "
            f"label: {typst_string(output['label'])}, "
            f"media-type: {typst_string(output['media_type'])}, "
            f"path: {typst_string(output['path'])}"
            ")"
        )
    suffix = "," if len(entries) == 1 else ""
    return "(" + ", ".join(entries) + suffix + ")"
