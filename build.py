from __future__ import annotations

import argparse
import calendar
import datetime as dt
import functools
import http.server
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

CORE_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path.cwd().resolve()
OUTPUT_DIR = ROOT_DIR / "public"
GENERATED_POSTS_FILE = ROOT_DIR / "typst" / "generated" / "posts.typ"
CORE_STATIC_DIR = CORE_DIR / "static"
USER_STATIC_DIR = ROOT_DIR / "static"
SITE_METADATA_LABEL = "<site-meta>"
POST_METADATA_LABEL = "<post-meta>"
EXCLUDED_DIRS = {".git", ".github", "public", "typst", "vendor", "__pycache__"}
ROOT_STATIC_FILES = {
    "CNAME",
    "favicon.ico",
    "favicon.svg",
    "robots.txt",
    "site.webmanifest",
    "manifest.webmanifest",
}
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
CALVER_TEXT_RE = re.compile(r"(\d{2}|\d{4})\.(\d{1,2})\.(\d{1,2})(?:\.(\d+))?")
THEME_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
POST_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TAG_PLAIN_SLUG_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?")
GENERATED_ROUTE_NAMES = {"pagefind", "tags", "themes"}
PORTABLE_RESERVED_NAMES = {
    "aux", "con", "nul", "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
RESERVED_POST_SLUGS = GENERATED_ROUTE_NAMES | PORTABLE_RESERVED_NAMES
BASE_PATH_OVERRIDE: str | None = None
PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 8000
PREVIEW_PORT_ATTEMPTS = 10
PREVIEW_VERSION_PATH = "/__typst_blog_preview_version"
PREVIEW_SCRIPT_PATH = "/__typst_blog_preview.js"
PREVIEW_WATCH_SUFFIXES = STATIC_EXTENSIONS | {".css", ".typ"}
PREVIEW_IGNORED_DIRS = {".git", "__pycache__", "public"}


def configure(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
) -> None:
    global ROOT_DIR, OUTPUT_DIR, GENERATED_POSTS_FILE, USER_STATIC_DIR, BASE_PATH_OVERRIDE

    ROOT_DIR = Path(root_dir).resolve() if root_dir is not None else Path.cwd().resolve()
    OUTPUT_DIR = ROOT_DIR / "public"
    GENERATED_POSTS_FILE = ROOT_DIR / "typst" / "generated" / "posts.typ"
    USER_STATIC_DIR = ROOT_DIR / "static"
    BASE_PATH_OVERRIDE = base_path


@dataclass(frozen=True, order=True)
class CalVer:
    year: int
    month: int
    day: int
    patch: int = 0

    def as_datetime(self) -> dt.datetime:
        return dt.datetime(self.year, self.month, self.day, tzinfo=dt.timezone.utc)


"""
# 最新版を使いたい時に
TYPST_REPO = Path("~/Downloads/typst").expanduser()

def run_typst(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                "cargo",
                "run",
                "--manifest-path",
                str(TYPST_REPO / "Cargo.toml"),
                "--locked",
                "-p",
                "typst-cli",
                "--",
                *args,
            ],
            cwd=ROOT_DIR,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr, end="")
        raise
"""
def run_typst(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["typst", *args]
    if BASE_PATH_OVERRIDE is not None:
        command[2:2] = [
            "--input", f"base-path={BASE_PATH_OVERRIDE}",
            "--input", "preview=true",
        ]
    try:
        return subprocess.run(
            command,
            cwd=ROOT_DIR,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr, end="")
        raise


def load_site_config() -> dict:
    result = run_typst(
        "query",
        "--root",
        ".",
        "--features",
        "html",
        "--field",
        "value",
        "site.typ",
        SITE_METADATA_LABEL,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    if not data:
        raise ValueError("site.typ must include #metadata(site) <site-meta>")

    site = data[0]
    for field in ("title", "description", "base_url", "language"):
        if not site.get(field):
            raise ValueError(f"site.{field} is required")

    theme = site.get("theme", "dark")
    if not isinstance(theme, str) or not theme:
        raise ValueError("site.theme must be a non-empty string")
    if not THEME_NAME_RE.fullmatch(theme):
        raise ValueError("site.theme may only contain letters, numbers, underscores, and hyphens")
    theme_paths = (
        USER_STATIC_DIR / "themes" / f"{theme}.css",
        CORE_STATIC_DIR / "themes" / f"{theme}.css",
    )
    if not any(path.is_file() for path in theme_paths):
        raise ValueError(
            f"site.theme '{theme}' does not exist in static/themes "
            "or vendor/typst-blog-core/static/themes"
        )

    site["base_url"] = site["base_url"].rstrip("/")
    site["theme"] = theme
    return site


def parse_typst_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None

    match = re.search(r"year:\s*(\d+),\s*month:\s*(\d+),\s*day:\s*(\d+)", raw)
    if not match:
        return None

    return dt.datetime(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        tzinfo=dt.timezone.utc,
    )


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

    text = raw.strip()
    match = CALVER_TEXT_RE.fullmatch(text)
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


def format_typst_date(value: dt.datetime | None) -> str:
    if value is None:
        return "none"
    return f"datetime(year: {value.year}, month: {value.month}, day: {value.day})"


def format_typst_calver(value: CalVer) -> str:
    return f"(year: {value.year}, month: {value.month}, day: {value.day}, patch: {value.patch})"


def discover_post_files() -> list[Path]:
    post_files: list[Path] = []
    for path in ROOT_DIR.rglob("index.typ"):
        if path == ROOT_DIR / "index.typ":
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT_DIR).parts):
            continue
        post_files.append(path)
    return sorted(post_files)


def load_post_metadata(path: Path) -> dict | None:
    result = run_typst(
        "query",
        "--root",
        ".",
        "--features",
        "html",
        "--field",
        "value",
        str(path.relative_to(ROOT_DIR)),
        POST_METADATA_LABEL,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    if not data:
        return None
    return data[0]


def validate_post_slug(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("slug is required and must be a string")
    if not POST_SLUG_RE.fullmatch(value):
        raise ValueError(
            "slug must contain only lowercase ASCII letters, numbers, and single hyphens "
            "between words (example: my-first-post)"
        )
    if value in RESERVED_POST_SLUGS:
        raise ValueError(f"slug '{value}' is reserved for site output")
    return value


def validate_post_tags(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
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
    static_routes = {path.name.casefold(): path.name for path in static_dir.iterdir()}
    for post in posts:
        collision = static_routes.get(post["slug"].casefold())
        if collision is not None:
            raise ValueError(
                f"post slug {post['slug']!r} conflicts with static/{collision}"
            )


def collect_posts() -> list[dict]:
    posts: list[dict] = []
    seen_slugs: set[str] = set()

    for source_file in discover_post_files():
        meta = load_post_metadata(source_file)
        if meta is None:
            continue

        try:
            slug = validate_post_slug(meta.get("slug"))
        except ValueError as exc:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: {exc}") from exc
        title = meta.get("title")
        try:
            create = parse_calver(meta.get("create"))
        except ValueError as exc:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: create {exc}") from exc
        try:
            update = parse_calver(meta.get("update"))
        except ValueError as exc:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: update {exc}") from exc
        description = meta.get("description")
        try:
            tags = validate_post_tags(meta.get("tags", []))
        except ValueError as exc:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: {exc}") from exc
        draft_value = meta.get("draft", True)
        if not isinstance(draft_value, bool):
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: draft must be true or false")
        draft = draft_value

        if slug in seen_slugs:
            raise ValueError(f"duplicate slug: {slug}")
        seen_slugs.add(slug)

        if not title:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: title is required")
        if create is None:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: create is required")
        if not description:
            raise ValueError(f"{source_file.relative_to(ROOT_DIR)}: description is required")

        posts.append(
            {
                "slug": slug,
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


def write_generated_posts(posts: list[dict], tag_slugs: dict[str, str]) -> None:
    GENERATED_POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    published_posts = [post for post in posts if not post["draft"]]

    lines: list[str] = []
    if published_posts:
        lines.append("#let post-data = (")
        for post in published_posts:
            tag_value = (
                "(" + ", ".join(typst_string(tag) for tag in post["tags"]) + ("," if len(post["tags"]) == 1 else "") + ")"
                if post["tags"]
                else "()"
            )
            source_url_path = quote(
                post["source_file"].relative_to(ROOT_DIR).as_posix(),
                safe="/",
            )
            lines.extend(
                [
                    f"  {typst_string(post['slug'])}: (",
                    f"    title: {typst_string(post['title'])},",
                    f"    create: {format_typst_calver(post['create'])},",
                    f"    update: {format_typst_date(post['update'].as_datetime() if post['update'] else None)},",
                    f"    description: {typst_string(post['description'])},",
                    f"    tags: {tag_value},",
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
    GENERATED_POSTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_post_assets(post: dict, output_dir: Path) -> None:
    for asset in post["source_dir"].rglob("*"):
        if not asset.is_file():
            continue
        if asset == post["source_file"]:
            continue
        if asset.suffix.lower() not in STATIC_EXTENSIONS:
            continue

        relative_path = asset.relative_to(post["source_dir"])
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def build_post(post: dict) -> None:
    output_dir = OUTPUT_DIR / post["slug"]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"

    print(f"Compiling: {post['title']}")
    run_typst(
        "compile",
        "--features",
        "html",
        "--format",
        "html",
        "--root",
        ".",
        str(post["source_file"].relative_to(ROOT_DIR)),
        str(output_file.relative_to(ROOT_DIR)),
    )
    copy_post_assets(post, output_dir)


def copy_static_dir(source_dir: Path) -> None:
    if not source_dir.exists():
        return

    for asset in source_dir.rglob("*"):
        if not asset.is_file():
            continue

        destination = OUTPUT_DIR / asset.relative_to(source_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def copy_root_static_files() -> None:
    for filename in ROOT_STATIC_FILES:
        source = ROOT_DIR / filename
        if not source.is_file():
            continue

        shutil.copy2(source, OUTPUT_DIR / filename)


def copy_static_assets() -> None:
    copy_static_dir(CORE_STATIC_DIR)
    copy_static_dir(USER_STATIC_DIR)
    copy_root_static_files()


def _tag_page_content(tag: str, tag_slug: str, tag_posts: list[dict]) -> str:
    lines = [
        '#import "/vendor/typst-blog-core/typst/core/tag.typ": tag-page',
        "#show: tag-page.with(",
        f"  tag: {typst_string(tag)},",
        f"  tag-slug: {typst_string(tag_slug)},",
        "  posts: (",
    ]
    for post in tag_posts:
        tag_value = (
            "("
            + ", ".join(typst_string(t) for t in post["tags"])
            + ("," if len(post["tags"]) == 1 else "")
            + ")"
            if post["tags"]
            else "()"
        )
        lines += [
            f"    {typst_string(post['slug'])}: (",
            f"      title: {typst_string(post['title'])},",
            f"      create: {format_typst_calver(post['create'])},",
            f"      description: {typst_string(post['description'])},",
            f"      tags: {tag_value},",
            "    ),",
        ]
    lines += ["  )", ")"]
    return "\n".join(lines) + "\n"


def _tags_index_content(tags_with_counts: list[tuple[str, str, int]]) -> str:
    lines = [
        '#import "/vendor/typst-blog-core/typst/core/tags-index.typ": tags-index-page',
        "#show: tags-index-page.with(",
        "  tags: (",
    ]
    for tag, slug, count in tags_with_counts:
        lines.append(
            f"    {typst_string(tag)}: (slug: {typst_string(slug)}, count: {count}),"
        )
    lines += ["  )", ")"]
    return "\n".join(lines) + "\n"


def build_tag_pages(posts: list[dict], tag_slugs: dict[str, str]) -> None:
    published = [p for p in posts if not p["draft"]]

    tag_posts: dict[str, list[dict]] = {}
    for post in published:
        for tag in post["tags"]:
            tag_posts.setdefault(tag, []).append(post)

    if not tag_posts:
        return

    tags_dir = OUTPUT_DIR / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)

    for i, (tag, tposts) in enumerate(tag_posts.items()):
        slug = tag_slugs[tag]
        tag_output_dir = tags_dir / slug
        tag_output_dir.mkdir(parents=True, exist_ok=True)

        temp_file = ROOT_DIR / f"_tag_build_{i}.typ"
        temp_file.write_text(_tag_page_content(tag, slug, tposts), encoding="utf-8")

        print(f"Building tag page: #{tag}")
        try:
            run_typst(
                "compile",
                "--features", "html",
                "--format", "html",
                "--root", ".",
                str(temp_file.relative_to(ROOT_DIR)),
                str((tag_output_dir / "index.html").relative_to(ROOT_DIR)),
            )
        finally:
            temp_file.unlink(missing_ok=True)

    tags_with_counts = sorted(
        [(tag, tag_slugs[tag], len(tposts)) for tag, tposts in tag_posts.items()],
        key=lambda x: x[0].lower(),
    )
    temp_file = ROOT_DIR / "_tags_index_build.typ"
    temp_file.write_text(_tags_index_content(tags_with_counts), encoding="utf-8")

    print("Building tags index page...")
    try:
        run_typst(
            "compile",
            "--features", "html",
            "--format", "html",
            "--root", ".",
            str(temp_file.relative_to(ROOT_DIR)),
            str((tags_dir / "index.html").relative_to(ROOT_DIR)),
        )
    finally:
        temp_file.unlink(missing_ok=True)

    print(f"Built {len(tag_posts)} tag page(s).")


def build_static_pages() -> None:
    run_typst(
        "compile",
        "--features",
        "html",
        "--format",
        "html",
        "--root",
        ".",
        "index.typ",
        str((OUTPUT_DIR / "index.html").relative_to(ROOT_DIR)),
    )

    if (ROOT_DIR / "404.typ").exists():
        run_typst(
            "compile",
            "--features",
            "html",
            "--format",
            "html",
            "--root",
            ".",
            "404.typ",
            str((OUTPUT_DIR / "404.html").relative_to(ROOT_DIR)),
        )

    copy_static_assets()


def generate_rss(site: dict, posts: list[dict]) -> None:
    published_posts = [post for post in posts if not post["draft"]]
    rss_path = OUTPUT_DIR / "feed.xml"
    now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    base_url = site["base_url"]

    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>{escape(site["title"])}</title>
  <link>{escape(base_url)}</link>
  <description>{escape(site["description"])}</description>
  <lastBuildDate>{now}</lastBuildDate>
"""
    for post in published_posts:
        link = f"{base_url}/{post['slug']}/"
        pub_date = post["create"].as_datetime().strftime("%a, %d %b %Y 00:00:00 GMT")
        xml += f"""  <item>
    <title>{escape(post['title'])}</title>
    <link>{escape(link)}</link>
    <guid isPermaLink="true">{escape(link)}</guid>
    <description>{escape(post['description'])}</description>
    <pubDate>{pub_date}</pubDate>
  </item>
"""

    xml += "</channel>\n</rss>"
    rss_path.write_text(xml, encoding="utf-8")


def generate_sitemap(site: dict, posts: list[dict]) -> None:
    published_posts = [post for post in posts if not post["draft"]]
    sitemap_path = OUTPUT_DIR / "sitemap.xml"
    base_url = site["base_url"]

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{escape(base_url)}/</loc>
    <priority>1.0</priority>
  </url>
"""
    for post in published_posts:
        link = f"{base_url}/{post['slug']}/"
        last_mod_value = post["update"].as_datetime() if post["update"] else post["create"].as_datetime()
        last_mod = last_mod_value.strftime("%Y-%m-%d")
        xml += f"""  <url>
    <loc>{escape(link)}</loc>
    <lastmod>{last_mod}</lastmod>
    <priority>0.8</priority>
  </url>
"""

    xml += "</urlset>"
    sitemap_path.write_text(xml, encoding="utf-8")


def build(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
) -> None:
    configure(root_dir, base_path)
    print("Starting build...")

    site = load_site_config()
    posts = collect_posts()
    tag_slugs = build_tag_slug_map(posts)
    validate_post_output_routes(posts, USER_STATIC_DIR)
    published_count = sum(1 for post in posts if not post["draft"])
    print(f"Found {len(posts)} posts ({published_count} published).")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_generated_posts(posts, tag_slugs)

    for post in posts:
        if post["draft"]:
            print(f"Draft skip: {post['title']}")
            continue
        build_post(post)

    print("Building static pages...")
    build_static_pages()

    print("Building tag pages...")
    build_tag_pages(posts, tag_slugs)

    print("Generating RSS and sitemap...")
    generate_rss(site, posts)
    generate_sitemap(site, posts)

    print("Build complete.")


class _PreviewState:
    def __init__(self) -> None:
        self._version = 1
        self._lock = threading.Lock()

    def version(self) -> int:
        with self._lock:
            return self._version

    def mark_rebuilt(self) -> None:
        with self._lock:
            self._version += 1


class _PreviewRequestHandler(http.server.SimpleHTTPRequestHandler):
    preview_state: _PreviewState

    def do_GET(self) -> None:
        path = self.path.partition("?")[0]
        if path == PREVIEW_VERSION_PATH:
            self._send_preview_content(str(self.preview_state.version()), "text/plain; charset=utf-8")
            return
        if path == PREVIEW_SCRIPT_PATH:
            self._send_preview_content(_preview_reload_script(), "text/javascript; charset=utf-8")
            return
        super().do_GET()

    def _send_preview_content(self, content: str, content_type: str) -> None:
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        if self.path.partition("?")[0] != PREVIEW_VERSION_PATH:
            super().log_message(format, *args)


def _preview_reload_script() -> str:
    return f"""(() => {{
  let currentVersion;

  async function checkForUpdate() {{
    try {{
      const response = await fetch(\"{PREVIEW_VERSION_PATH}\", {{ cache: \"no-store\" }});
      const nextVersion = await response.text();
      if (currentVersion === undefined) {{
        currentVersion = nextVersion;
      }} else if (nextVersion !== currentVersion) {{
        window.location.reload();
        return;
      }}
    }} catch (_) {{
      // The rebuild or preview server may be temporarily unavailable.
    }}
    window.setTimeout(checkForUpdate, 750);
  }}

  checkForUpdate();
}})();
"""


def _preview_snapshot() -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in ROOT_DIR.rglob("*"):
        try:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT_DIR)
            if any(part in PREVIEW_IGNORED_DIRS for part in relative.parts):
                continue
            if relative.parts[:2] == ("typst", "generated"):
                continue
            if (
                path.suffix.lower() not in PREVIEW_WATCH_SUFFIXES
                and relative.name != "build.py"
                and relative.parts[:1] != ("static",)
            ):
                continue
            stat = path.stat()
        except OSError:
            # Editors may replace files atomically while a snapshot is running.
            continue
        snapshot[relative.as_posix()] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _watch_preview(state: _PreviewState) -> None:
    snapshot = _preview_snapshot()
    while True:
        time.sleep(0.5)
        next_snapshot = _preview_snapshot()
        if next_snapshot == snapshot:
            continue

        # Give editors that save through multiple file operations a moment to settle.
        time.sleep(0.2)
        snapshot = _preview_snapshot()
        print("Change detected. Rebuilding preview...")
        try:
            build(root_dir=ROOT_DIR, base_path="")
        except Exception as exc:
            print(f"Preview rebuild failed: {exc}", file=sys.stderr)
        else:
            state.mark_rebuilt()
            print("Preview updated.")


def preview(root_dir: Path | str | None = None) -> None:
    build(root_dir=root_dir, base_path="")

    state = _PreviewState()
    _PreviewRequestHandler.preview_state = state
    handler = functools.partial(_PreviewRequestHandler, directory=str(OUTPUT_DIR))
    server = None
    last_error = None
    for port in range(PREVIEW_PORT, PREVIEW_PORT + PREVIEW_PORT_ATTEMPTS):
        try:
            server = http.server.ThreadingHTTPServer((PREVIEW_HOST, port), handler)
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise RuntimeError(
            f"Could not start preview server on ports {PREVIEW_PORT}-"
            f"{PREVIEW_PORT + PREVIEW_PORT_ATTEMPTS - 1}: {last_error}"
        ) from last_error

    watcher = threading.Thread(target=_watch_preview, args=(state,), daemon=True)
    watcher.start()
    selected_port = server.server_address[1]
    if selected_port != PREVIEW_PORT:
        print(f"Port {PREVIEW_PORT} is in use; using {selected_port} instead.")
    print(f"Preview server: http://localhost:{selected_port}")
    print("Watching for changes. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.")
    finally:
        server.server_close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Typst blog.")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="build, serve, watch, and live-reload the site locally",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parse_args()
        if args.preview:
            preview()
        else:
            build()
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        sys.exit(1)
