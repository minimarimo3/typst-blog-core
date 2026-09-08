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
    write_generated_posts,
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


def _compile_theme_entry(
    context: BlogContext,
    name: str,
    source: str,
    output_file: Path,
) -> None:
    entries_dir = context.generated_posts_file.parent / "entries"
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
#import "/typst/generated/posts.typ": post-data
#render-home(home-page-data(posts: post-data))
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


def build(
    root_dir: Path | str | None = None,
    base_path: str | None = None,
    *,
    include_drafts: bool = False,
) -> None:
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

    if context.output_dir.exists():
        shutil.rmtree(context.output_dir)
    context.output_dir.mkdir(parents=True, exist_ok=True)
    write_generated_posts(context, posts, tag_slugs, include_drafts=include_drafts)
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
    print("Build complete.")
