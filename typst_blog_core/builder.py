from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

from .context import BlogContext, ROOT_STATIC_FILES, STATIC_EXTENSIONS, run_typst
from .git_dates import apply_update_policy
from .metadata import (
    build_tag_slug_map,
    collect_posts,
    format_typst_calver,
    load_site_config,
    resolve_posts_dir,
    typst_string,
    validate_post_output_routes,
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
    PostInfo,
    load_pipeline,
)


def copy_post_assets(post: dict, output_dir: Path) -> None:
    for asset in post["source_dir"].rglob("*"):
        if not asset.is_file() or asset == post["source_file"]:
            continue
        if asset.suffix.lower() not in STATIC_EXTENSIONS:
            continue
        destination = output_dir / asset.relative_to(post["source_dir"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def build_post(context: BlogContext, post: dict) -> None:
    output_dir = context.output_dir / post["slug"]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    print(f"Compiling: {post['title']}")
    run_typst(
        context,
        "compile",
        "--features",
        "html",
        "--format",
        "html",
        "--root",
        ".",
        str(post["source_file"].relative_to(context.root_dir)),
        str(output_file.relative_to(context.root_dir)),
    )
    copy_post_assets(post, output_dir)


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
    copy_static_dir(context, context.theme_static_dir)
    copy_static_dir(context, context.user_static_dir)
    for filename in ROOT_STATIC_FILES:
        source = context.root_dir / filename
        if source.is_file():
            shutil.copy2(source, context.output_dir / filename)


def reserved_output_paths(
    context: BlogContext,
    posts: list[dict],
    tag_slugs: dict[str, str],
) -> set[str]:
    paths = {"index.html", "404.html", "feed.xml", "sitemap.xml", "tags/index.html"}
    for post in posts:
        paths.add(f"{post['slug']}/index.html")
        for asset in post["source_dir"].rglob("*"):
            if (
                asset.is_file()
                and asset != post["source_file"]
                and asset.suffix.lower() in STATIC_EXTENSIONS
            ):
                relative = asset.relative_to(post["source_dir"]).as_posix()
                paths.add(f"{post['slug']}/{relative}")
        for tag in post["tags"]:
            paths.add(f"tags/{tag_slugs[tag]}/index.html")
    for source_dir in (context.theme_static_dir, context.user_static_dir):
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
    return paths


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


def _tag_page_content(tag: str, tag_slug: str, tag_posts: list[dict]) -> str:
    lines = [
        '#import "/theme/theme.typ": render-tag',
        '#import "/vendor/typst-blog-core/typst/core/page-data.typ": tag-page-data',
        "#render-tag(tag-page-data(",
        f"  tag: {typst_string(tag)},",
        f"  tag-slug: {typst_string(tag_slug)},",
        "  posts: (",
    ]
    for post in tag_posts:
        tags = post["tags"]
        update = post["update"]
        tag_value = (
            "("
            + ", ".join(typst_string(value) for value in tags)
            + ("," if len(tags) == 1 else "")
            + ")"
            if tags
            else "()"
        )
        lines.extend(
            [
                f"    {typst_string(post['slug'])}: (",
                f"      url-slug: {typst_string(post['url_slug'])},",
                f"      title: {typst_string(post['title'])},",
                f"      create: {format_typst_calver(post['create'])},",
                f"      update: {format_typst_calver(update) if update else 'none'},",
                f"      description: {typst_string(post['description'])},",
                f"      tags: {tag_value},",
                f"      draft: {'true' if post['draft'] else 'false'},",
                "    ),",
            ]
        )
    lines.extend(["  )", "))"])
    return "\n".join(lines) + "\n"


def _tags_index_content(tags_with_counts: list[tuple[str, str, int]]) -> str:
    lines = [
        '#import "/theme/theme.typ": render-tags-index',
        '#import "/vendor/typst-blog-core/typst/core/page-data.typ": tags-index-page-data',
        "#render-tags-index(tags-index-page-data(",
        "  tags: (",
    ]
    for tag, slug, count in tags_with_counts:
        lines.append(f"    {typst_string(tag)}: (slug: {typst_string(slug)}, count: {count}),")
    lines.extend(["  )", "))"])
    return "\n".join(lines) + "\n"


def build_tag_pages(
    context: BlogContext,
    posts: list[dict],
    tag_slugs: dict[str, str],
    *,
    include_drafts: bool = False,
) -> None:
    tag_posts: dict[str, list[dict]] = {}
    visible_posts = (
        posts if include_drafts else (post for post in posts if not post["draft"])
    )
    for post in visible_posts:
        for tag in post["tags"]:
            tag_posts.setdefault(tag, []).append(post)
    if not tag_posts:
        return

    tags_dir = context.output_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    for index, (tag, posts_for_tag) in enumerate(tag_posts.items()):
        slug = tag_slugs[tag]
        tag_output_dir = tags_dir / slug
        tag_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Building tag page: #{tag}")
        _compile_theme_entry(
            context,
            f"tag-{index}",
            _tag_page_content(tag, slug, posts_for_tag),
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


def build_static_pages(context: BlogContext) -> None:
    _compile_theme_entry(
        context,
        "home",
        '''#import "/theme/theme.typ": render-home
#import "/vendor/typst-blog-core/typst/core/page-data.typ": home-page-data
#import "/vendor/typst-blog-core/typst/core/build-data.typ": load-build-data
#let build-data = load-build-data()
#render-home(home-page-data(posts: build-data.posts, outputs: build-data.site-outputs))
''',
        context.output_dir / "index.html",
    )
    _compile_theme_entry(
        context,
        "not-found",
        '''#import "/theme/theme.typ": render-not-found
#import "/vendor/typst-blog-core/typst/core/page-data.typ": not-found-page-data
#render-not-found(not-found-page-data())
''',
        context.output_dir / "404.html",
    )
    copy_static_assets(context)


def generate_rss(context: BlogContext, site: dict, posts: list[dict]) -> None:
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
    for post in (post for post in posts if not post["draft"]):
        link = f"{base_url}/{post['url_slug']}/"
        pub_date = post["create"].as_datetime().strftime("%a, %d %b %Y 00:00:00 GMT")
        xml += f"""  <item>
    <title>{escape(post["title"])}</title>
    <link>{escape(link)}</link>
    <guid isPermaLink="true">{escape(link)}</guid>
    <description>{escape(post["description"])}</description>
    <pubDate>{pub_date}</pubDate>
  </item>
"""
    xml += "</channel>\n</rss>"
    (context.output_dir / "feed.xml").write_text(xml, encoding="utf-8")


def generate_sitemap(context: BlogContext, site: dict, posts: list[dict]) -> None:
    base_url = site["base_url"]
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{escape(base_url)}/</loc>
    <priority>1.0</priority>
  </url>
"""
    for post in (post for post in posts if not post["draft"]):
        link = f"{base_url}/{post['url_slug']}/"
        last_mod_value = (
            post["update"].as_datetime()
            if post["update"]
            else post["create"].as_datetime()
        )
        last_mod = last_mod_value.strftime("%Y-%m-%d")
        xml += f"""  <url>
    <loc>{escape(link)}</loc>
    <lastmod>{last_mod}</lastmod>
    <priority>0.8</priority>
  </url>
"""
    xml += "</urlset>"
    (context.output_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _build_task(
    context: BlogContext,
    mode: BuildMode,
    site: dict,
    posts: list[dict],
) -> BuildTask:
    return BuildTask(
        root_dir=context.root_dir,
        build_dir=context.build_dir,
        output_dir=context.output_dir,
        mode=mode,
        site=site,
        posts=tuple(PostInfo.from_post(post) for post in posts),
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


def build(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
    *,
    include_drafts: bool = False,
    mode: BuildMode = "build",
) -> None:
    if mode not in {"build", "preview"}:
        raise ValueError("build mode must be 'build' or 'preview'")
    context = BlogContext.create(root_dir, base_path)
    print("Starting build...")
    site = load_site_config(context)
    validate_extension_assets(context)
    posts_dir = resolve_posts_dir(context, site)
    posts = collect_posts(context, posts_dir)
    apply_update_policy(context, site, posts)
    tag_slugs = build_tag_slug_map(posts)
    validate_post_output_routes(posts, context.user_static_dir)
    validate_post_output_routes(posts, context.theme_static_dir)
    published_count = sum(1 for post in posts if not post["draft"])
    print(f"Found {len(posts)} posts ({published_count} published).")
    active_posts = posts if include_drafts else [post for post in posts if not post["draft"]]
    pipeline = load_pipeline(context)
    post_outputs, site_outputs = pipeline.plan_outputs(
        context,
        active_posts,
        mode,
        reserved_output_paths(context, active_posts, tag_slugs),
    )

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
    )
    for post in posts:
        if post["draft"] and not include_drafts:
            print(f"Draft skip: {post['title']}")
        else:
            build_post(context, post)
    print("Building static pages...")
    build_static_pages(context)
    print("Building tag pages...")
    build_tag_pages(context, posts, tag_slugs, include_drafts=include_drafts)
    print("Generating RSS and sitemap...")
    generate_rss(context, site, posts)
    generate_sitemap(context, site, posts)
    _run_after_html(pipeline, task)
    _run_post_build(pipeline, task)
    print("Build complete.")
