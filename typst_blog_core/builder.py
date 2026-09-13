from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape
from urllib.parse import urlsplit

from .context import BlogContext, ROOT_STATIC_FILES, run_typst
from .git_dates import apply_update_policy
from .metadata import (
    build_tag_slug_map,
    collect_pages,
    collect_posts,
    format_post_typst_record,
    load_site_config,
    PostRecord,
    resolve_posts_dir,
    typst_string,
    validate_post_output_routes,
    validate_content_route_collisions,
    validate_extension_assets,
    write_generated_site_data,
)
from .pipeline import (
    BuildMode,
    BuildTask,
    HtmlTask,
    OutputTask,
    Pipeline,
    PlannedOutput,
    load_pipeline,
)


@dataclass(frozen=True)
class PreparedBuild:
    """Validated inputs and planned outputs for one site build."""

    context: BlogContext
    mode: BuildMode
    include_drafts: bool
    site: dict
    asset_extensions: frozenset[str]
    posts: list[PostRecord]
    pages: list[dict]
    active_posts: list[PostRecord]
    active_pages: list[dict]
    tag_slugs: dict[str, str]
    pipeline: Pipeline
    post_outputs: dict[str, list[PlannedOutput]]
    site_outputs: list[PlannedOutput]

    def supports_incremental_preview(self) -> bool:
        return (
            self.mode == "preview"
            and not any(self.post_outputs.values())
            and not self.site_outputs
            and not self.pipeline.active_after_html("preview")
            and not self.pipeline.active_post_build("preview")
        )


def copy_content_assets(
    content: dict | PostRecord,
    output_dir: Path,
    asset_extensions: frozenset[str],
) -> None:
    validate_content_asset_output_paths([content], asset_extensions)
    source_dir = (
        content.source_dir if isinstance(content, PostRecord) else content["source_dir"]
    )
    source_file = (
        content.source_file if isinstance(content, PostRecord) else content["source_file"]
    )
    for asset in source_dir.rglob("*"):
        if not asset.is_file() or asset == source_file:
            continue
        if asset.suffix.lower() not in asset_extensions:
            continue
        destination = output_dir / asset.relative_to(source_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def validate_content_asset_output_paths(
    content: list[dict | PostRecord],
    asset_extensions: frozenset[str],
) -> None:
    """Reject source assets that would overwrite generated content HTML."""
    for item in content:
        source_dir = (
            item.source_dir if isinstance(item, PostRecord) else item["source_dir"]
        )
        source_file = (
            item.source_file if isinstance(item, PostRecord) else item["source_file"]
        )
        for asset in source_dir.rglob("*"):
            if (
                asset.is_file()
                and asset != source_file
                and asset.suffix.lower() in asset_extensions
                and asset.relative_to(source_dir).as_posix().casefold() == "index.html"
            ):
                raise ValueError(
                    f"content asset {asset} conflicts with generated index.html"
                )


def build_post(
    context: BlogContext,
    post: PostRecord,
    asset_extensions: frozenset[str],
) -> None:
    output_dir = context.output_dir / post.route_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    print(f"Compiling: {post.title}")
    run_typst(
        context,
        "compile",
        "--input",
        f"content-id={post.slug}",
        "--features",
        "html",
        "--format",
        "html",
        "--root",
        ".",
        str(post.source_file.relative_to(context.root_dir)),
        str(output_file.relative_to(context.root_dir)),
    )
    copy_content_assets(post, output_dir, asset_extensions)


def build_page(
    context: BlogContext,
    page: dict,
    asset_extensions: frozenset[str],
) -> None:
    output_dir = context.output_dir / page["route_path"]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    print(f"Compiling page: {page['title']}")
    run_typst(
        context,
        "compile",
        "--input",
        f"content-id={page['slug']}",
        "--features",
        "html",
        "--format",
        "html",
        "--root",
        ".",
        str(page["source_file"].relative_to(context.root_dir)),
        str(output_file.relative_to(context.root_dir)),
    )
    copy_content_assets(page, output_dir, asset_extensions)


def copy_static_dir(context: BlogContext, source_dir: Path) -> None:
    if not source_dir.exists():
        return
    for asset in source_dir.rglob("*"):
        if not asset.is_file():
            continue
        destination = context.output_dir / asset.relative_to(source_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def copy_static_assets(context: BlogContext) -> None:
    validate_core_asset_namespace(context)
    copy_static_dir(context, context.core_dir / "static")
    copy_static_dir(context, context.theme_static_dir)
    copy_static_dir(context, context.user_static_dir)
    for filename in ROOT_STATIC_FILES:
        source = context.root_dir / filename
        if source.is_file():
            shutil.copy2(source, context.output_dir / filename)


def validate_core_asset_namespace(context: BlogContext) -> None:
    for source_dir in (context.theme_static_dir, context.user_static_dir):
        if source_dir.is_dir() and any(
            child.name.casefold() == "_core" for child in source_dir.iterdir()
        ):
            raise ValueError(f"{source_dir}/_core is reserved for core assets")


def generate_alias_redirects(
    context: BlogContext,
    site: dict,
    content: list[PostRecord | dict],
) -> None:
    published_base_path = urlsplit(site["base_url"]).path.rstrip("/")
    base_path = (
        context.base_path if context.base_path is not None else published_base_path
    )
    language = site["language"]
    html_language = language if isinstance(language, str) else language["lang"]
    for item in content:
        if isinstance(item, PostRecord):
            aliases = item.aliases
            url_slug = item.url_slug
        else:
            aliases = item["aliases"]
            url_slug = item["url_slug"]
        target = f"{base_path}/{url_slug}/"
        escaped_target = escape(target, {'"': "&quot;"})
        script_target = json.dumps(target, ensure_ascii=False).replace("<", "\\u003c")
        html = f'''<!doctype html>
<html lang="{escape(html_language)}">
<head>
  <meta charset="utf-8">
  <meta name="robots" content="noindex">
  <link rel="canonical" href="{escape(site['base_url'])}/{url_slug}/">
  <meta http-equiv="refresh" content="0; url={escaped_target}">
  <title>Moved</title>
</head>
<body>
  <p>This page has moved to <a href="{escaped_target}">{escaped_target}</a>.</p>
  <script>location.replace({script_target} + location.search + location.hash)</script>
</body>
</html>
'''
        for alias in aliases:
            destination = context.output_dir / alias / "index.html"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(html, encoding="utf-8")


def reserved_output_paths(
    context: BlogContext,
    posts: list[PostRecord],
    pages: list[dict],
    tag_slugs: dict[str, str],
    asset_extensions: frozenset[str],
    site: dict,
) -> set[str]:
    paths = {"index.html", "404.html", "feed.xml", "sitemap.xml", "tags/index.html"}
    for post in posts:
        paths.add(f"{post.route_path}/index.html")
        paths.update(f"{alias}/index.html" for alias in post.aliases)
        for asset in post.source_dir.rglob("*"):
            if (
                asset.is_file()
                and asset != post.source_file
                and asset.suffix.lower() in asset_extensions
            ):
                relative = asset.relative_to(post.source_dir).as_posix()
                paths.add(f"{post.route_path}/{relative}")
        for tag in post.tags:
            paths.add(f"tags/{tag_slugs[tag]}/index.html")
    for page in pages:
        paths.add(f"{page['route_path']}/index.html")
        paths.update(f"{alias}/index.html" for alias in page["aliases"])
        for asset in page["source_dir"].rglob("*"):
            if (
                asset.is_file()
                and asset != page["source_file"]
                and asset.suffix.lower() in asset_extensions
            ):
                relative = asset.relative_to(page["source_dir"]).as_posix()
                paths.add(f"{page['route_path']}/{relative}")
    for source_dir in (
        context.core_dir / "static",
        context.theme_static_dir,
        context.user_static_dir,
    ):
        if source_dir.is_dir():
            paths.update(
                asset.relative_to(source_dir).as_posix()
                for asset in source_dir.rglob("*")
                if asset.is_file()
            )
    paths.update(
        filename
        for filename in ROOT_STATIC_FILES
        if (context.root_dir / filename).is_file()
    )
    home_pages = _pagination_page_count(len(posts), site["pagination"]["home"])
    paths.update(f"page/{page}/index.html" for page in range(2, home_pages + 1))
    tag_counts: dict[str, int] = {}
    for post in posts:
        for tag in post.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    for tag, count in tag_counts.items():
        total = _pagination_page_count(count, site["pagination"]["tag"])
        paths.update(
            f"tags/{tag_slugs[tag]}/page/{page}/index.html"
            for page in range(2, total + 1)
        )
    return paths


def _pagination_page_count(item_count: int, setting: dict) -> int:
    if not setting["enabled"] or item_count == 0:
        return 1
    return (item_count + setting["per_page"] - 1) // setting["per_page"]


def _pagination_slice(items: list, setting: dict, page: int) -> list:
    if not setting["enabled"]:
        return items
    start = (page - 1) * setting["per_page"]
    return items[start : start + setting["per_page"]]


def _compile_theme_entry(
    context: BlogContext,
    name: str,
    source: str,
    output_file: Path,
) -> None:
    entries_dir = context.build_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    entry_file = entries_dir / f"{name}.typ"
    entry_file.write_text(source, encoding="utf-8")
    try:
        run_typst(
            context,
            "compile",
            "--features",
            "html",
            "--format",
            "html",
            "--root",
            ".",
            str(entry_file.relative_to(context.root_dir)),
            str(output_file.relative_to(context.root_dir)),
        )
    finally:
        entry_file.unlink(missing_ok=True)
        try:
            entries_dir.rmdir()
        except OSError:
            pass


def _tag_page_content(
    context: BlogContext,
    tag: str,
    tag_slug: str,
    tag_posts: list[PostRecord],
    page_number: int = 1,
    total_pages: int = 1,
) -> str:
    lines = [
        '#import "/theme/theme.typ": render-tag, core',
        "#render-tag(core.tag-page-data(",
        f"  tag: {typst_string(tag)},",
        f"  tag-slug: {typst_string(tag_slug)},",
        f"  page-number: {page_number},",
        f"  total-pages: {total_pages},",
        "  posts: (",
    ]
    for post in tag_posts:
        lines.extend(format_post_typst_record(context, post, indent="    "))
    lines.extend(["  )", "))"])
    return "\n".join(lines) + "\n"


def _tags_index_content(tags_with_counts: list[tuple[str, str, int]]) -> str:
    lines = [
        '#import "/theme/theme.typ": render-tags-index, core',
        "#render-tags-index(core.tags-index-page-data(",
        "  tags: (",
    ]
    for tag, slug, count in tags_with_counts:
        lines.append(f"    {typst_string(tag)}: (slug: {typst_string(slug)}, count: {count}),")
    lines.extend(["  )", "))"])
    return "\n".join(lines) + "\n"


def build_tag_pages(
    context: BlogContext,
    posts: list[PostRecord],
    tag_slugs: dict[str, str],
    site: dict,
    *,
    include_drafts: bool = False,
) -> None:
    tag_posts: dict[str, list[PostRecord]] = {}
    visible_posts = (
        posts if include_drafts else (post for post in posts if not post.draft)
    )
    for post in visible_posts:
        for tag in post.tags:
            tag_posts.setdefault(tag, []).append(post)
    if not tag_posts:
        return

    tags_dir = context.output_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    for index, (tag, posts_for_tag) in enumerate(tag_posts.items()):
        slug = tag_slugs[tag]
        setting = site["pagination"]["tag"]
        total_pages = _pagination_page_count(len(posts_for_tag), setting)
        for page_number in range(1, total_pages + 1):
            tag_output_dir = tags_dir / slug
            if page_number > 1:
                tag_output_dir = tag_output_dir / "page" / str(page_number)
            tag_output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Building tag page: #{tag} ({page_number}/{total_pages})")
            _compile_theme_entry(
                context,
                f"tag-{index}-{page_number}",
                _tag_page_content(
                    context,
                    tag,
                    slug,
                    _pagination_slice(posts_for_tag, setting, page_number),
                    page_number,
                    total_pages,
                ),
                tag_output_dir / "index.html",
            )

    tags_with_counts = sorted(
        [(tag, tag_slugs[tag], len(posts_for_tag)) for tag, posts_for_tag in tag_posts.items()],
        key=lambda value: value[0].lower(),
    )
    print("Building tags index page...")
    _compile_theme_entry(
        context,
        "tags-index",
        _tags_index_content(tags_with_counts),
        tags_dir / "index.html",
    )
    print(f"Built {len(tag_posts)} tag page(s).")


def _home_page_content(page_number: int = 1, total_pages: int = 1, per_page: int | None = None) -> str:
    per_page_value = "none" if per_page is None else str(per_page)
    return f'''#import "/theme/theme.typ": render-home, core
#let build-data = core.load-build-data()
#render-home(core.home-page-data(
  posts: build-data.posts,
  outputs: build-data.site-outputs,
  page-number: {page_number},
  total-pages: {total_pages},
  per-page: {per_page_value},
))
'''


def _not_found_page_content() -> str:
    return '''#import "/theme/theme.typ": render-not-found, core
#render-not-found(core.not-found-page-data())
'''


def build_static_pages(context: BlogContext, site: dict, post_count: int) -> None:
    setting = site["pagination"]["home"]
    total_pages = _pagination_page_count(post_count, setting)
    per_page = setting["per_page"] if setting["enabled"] else None
    for page_number in range(1, total_pages + 1):
        output_dir = context.output_dir
        if page_number > 1:
            output_dir = output_dir / "page" / str(page_number)
        output_dir.mkdir(parents=True, exist_ok=True)
        _compile_theme_entry(
            context,
            f"home-{page_number}",
            _home_page_content(page_number, total_pages, per_page),
            output_dir / "index.html",
        )
    _compile_theme_entry(
        context,
        "not-found",
        _not_found_page_content(),
        context.output_dir / "404.html",
    )
    copy_static_assets(context)


def generate_rss(context: BlogContext, site: dict, posts: list[PostRecord]) -> None:
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
    for post in (post for post in posts if not post.draft):
        link = f"{base_url}/{post.url_slug}/"
        pub_date = post.create.as_datetime().strftime("%a, %d %b %Y 00:00:00 GMT")
        xml += f"""  <item>
    <title>{escape(post.title)}</title>
    <link>{escape(link)}</link>
    <guid isPermaLink="true">{escape(link)}</guid>
    <description>{escape(post.description)}</description>
    <pubDate>{pub_date}</pubDate>
  </item>
"""
    xml += "</channel>\n</rss>"
    (context.output_dir / "feed.xml").write_text(xml, encoding="utf-8")


def generate_sitemap(
    context: BlogContext,
    site: dict,
    posts: list[PostRecord],
    pages: list[dict],
) -> None:
    base_url = site["base_url"]
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{escape(base_url)}/</loc>
    <priority>1.0</priority>
  </url>
"""
    for post in (post for post in posts if not post.draft):
        link = f"{base_url}/{post.url_slug}/"
        last_mod_value = (
            post.update.as_datetime()
            if post.update
            else post.create.as_datetime()
        )
        last_mod = last_mod_value.strftime("%Y-%m-%d")
        xml += f"""  <url>
    <loc>{escape(link)}</loc>
    <lastmod>{last_mod}</lastmod>
    <priority>0.8</priority>
  </url>
"""
    for page in (
        page for page in pages if not page["draft"] and page["index"]
    ):
        link = f"{base_url}/{page['url_slug']}/"
        xml += f"""  <url>
    <loc>{escape(link)}</loc>
    <priority>0.6</priority>
  </url>
"""
    xml += "</urlset>"
    (context.output_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _build_task(
    context: BlogContext,
    mode: BuildMode,
    site: dict,
    posts: list[PostRecord],
) -> BuildTask:
    return BuildTask(
        root_dir=context.root_dir,
        build_dir=context.build_dir,
        output_dir=context.output_dir,
        mode=mode,
        site=site,
        posts=tuple(posts),
        _context=context,
    )


def _run_outputs(
    task: BuildTask,
    outputs: list[PlannedOutput],
) -> None:
    for output in outputs:
        print(f"Building extra output: {output.label}")
        output.destination.parent.mkdir(parents=True, exist_ok=True)
        output.build(
            OutputTask(
                **task.__dict__,
                id=output.id,
                label=output.label,
                media_type=output.media_type,
                destination=output.destination,
                post=output.post,
            )
        )
        if not output.destination.is_file():
            relative = output.destination.relative_to(task.root_dir)
            raise RuntimeError(
                f"pipeline output '{output.id}' did not create its declared file: {relative}"
            )


def _run_after_html(pipeline: Pipeline, task: BuildTask) -> None:
    hooks = pipeline.active_after_html(task.mode)
    if not hooks:
        return
    for path in sorted(task.output_dir.rglob("*.html")):
        relative = path.relative_to(task.output_dir).as_posix()
        output_path = "/" if relative == "index.html" else "/" + relative
        for hook in hooks:
            print(f"Running after_html '{hook.id}': {relative}")
            hook.run(HtmlTask(**task.__dict__, path=path, output_path=output_path))
            if not path.is_file():
                raise RuntimeError(f"after_html '{hook.id}' removed its input: {relative}")


def _run_post_build(pipeline: Pipeline, task: BuildTask) -> None:
    for hook in pipeline.active_post_build(task.mode):
        print(f"Running post_build: {hook.id}")
        hook.run(task)


def run_preview_start(prepared: PreparedBuild) -> None:
    task = _build_task(
        prepared.context,
        "preview",
        prepared.site,
        prepared.active_posts,
    )
    for hook in prepared.pipeline.active_preview_start():
        print(f"Running preview_start: {hook.id}")
        hook.run(task)


def prepare_build(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
    *,
    include_drafts: bool = False,
    mode: BuildMode = "build",
) -> PreparedBuild:
    if mode not in {"build", "preview"}:
        raise ValueError("build mode must be 'build' or 'preview'")
    context = BlogContext.create(root_dir, base_path)
    site = load_site_config(context)
    asset_extensions = frozenset(site["asset_extensions"])
    validate_core_asset_namespace(context)
    validate_extension_assets(context)
    posts_dir = resolve_posts_dir(context, site)
    posts = collect_posts(context, posts_dir)
    pages = collect_pages(context)
    apply_update_policy(context, site, posts)
    tag_slugs = build_tag_slug_map(posts)
    validate_content_route_collisions(posts, pages)
    content = posts + pages
    validate_post_output_routes(content, context.user_static_dir)
    validate_post_output_routes(content, context.theme_static_dir)
    published_count = sum(1 for post in posts if not post.draft)
    print(f"Found {len(posts)} posts ({published_count} published).")
    active_posts = posts if include_drafts else [post for post in posts if not post.draft]
    active_pages = pages if include_drafts else [page for page in pages if not page["draft"]]
    validate_content_asset_output_paths(
        [*active_posts, *active_pages],
        asset_extensions,
    )
    pipeline = load_pipeline(context)
    post_outputs, site_outputs = pipeline.plan_outputs(
        context,
        active_posts,
        mode,
        reserved_output_paths(
            context,
            active_posts,
            active_pages,
            tag_slugs,
            asset_extensions,
            site,
        ),
    )

    return PreparedBuild(
        context=context,
        mode=mode,
        include_drafts=include_drafts,
        site=site,
        asset_extensions=asset_extensions,
        posts=posts,
        pages=pages,
        active_posts=active_posts,
        active_pages=active_pages,
        tag_slugs=tag_slugs,
        pipeline=pipeline,
        post_outputs=post_outputs,
        site_outputs=site_outputs,
    )


def build_prepared(prepared: PreparedBuild) -> PreparedBuild:
    context = prepared.context
    mode = prepared.mode
    include_drafts = prepared.include_drafts
    site = prepared.site
    asset_extensions = prepared.asset_extensions
    posts = prepared.posts
    pages = prepared.pages
    active_posts = prepared.active_posts
    active_pages = prepared.active_pages
    tag_slugs = prepared.tag_slugs
    pipeline = prepared.pipeline
    post_outputs = prepared.post_outputs
    site_outputs = prepared.site_outputs

    if context.build_dir.exists():
        shutil.rmtree(context.build_dir)
    context.build_dir.mkdir(parents=True, exist_ok=True)

    if context.output_dir.exists():
        shutil.rmtree(context.output_dir)
    context.output_dir.mkdir(parents=True, exist_ok=True)
    task = _build_task(context, mode, site, active_posts)
    all_outputs = [
        output
        for outputs in post_outputs.values()
        for output in outputs
    ] + site_outputs
    _run_outputs(task, all_outputs)
    write_generated_site_data(
        context,
        posts,
        tag_slugs,
        include_drafts=include_drafts,
        post_outputs={
            slug: [output.as_theme_data() for output in outputs]
            for slug, outputs in post_outputs.items()
        },
        site_outputs=[output.as_theme_data() for output in site_outputs],
        pages=pages,
    )
    for post in posts:
        if post.draft and not include_drafts:
            print(f"Draft skip: {post.title}")
        else:
            build_post(context, post, asset_extensions)
    for page in pages:
        if page["draft"] and not include_drafts:
            print(f"Draft page skip: {page['title']}")
        else:
            build_page(context, page, asset_extensions)
    print("Building static pages...")
    build_static_pages(context, site, len(active_posts))
    print("Building tag pages...")
    build_tag_pages(context, posts, tag_slugs, site, include_drafts=include_drafts)
    print("Generating RSS and sitemap...")
    generate_rss(context, site, posts)
    generate_sitemap(context, site, posts, pages)
    generate_alias_redirects(context, site, active_posts + active_pages)
    _run_after_html(pipeline, task)
    _run_post_build(pipeline, task)
    print("Build complete.")
    return prepared


def build(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
    *,
    include_drafts: bool = False,
    mode: BuildMode = "build",
) -> None:
    print("Starting build...")
    prepared = prepare_build(
        root_dir=root_dir,
        base_path=base_path,
        include_drafts=include_drafts,
        mode=mode,
    )
    build_prepared(prepared)
