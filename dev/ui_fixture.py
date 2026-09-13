from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1]


def create_ui_blog(root: Path) -> None:
    files = {
        "site.typ": '''#import "/vendor/typst-blog-core/typst/site-api.typ" as site-api
#import "/vendor/typst-blog-core/typst/ui-config.typ": theme-config
#let site = site-api.site(
  title: "Component fixture", description: "Test blog", base_url: "https://example.com/blog",
  language: "en", update_policy: "manual", posts_dir: "posts",
  fonts: (main: (pdf: "serif", web: none), code: (pdf: "monospace", web: none)),
  author: (name: "Ada", bio: "Author biography", links: ()),
  theme: theme-config(color_scheme: "test"),
)
#metadata(site) <site-meta>
''',
        "extensions.typ": "#let extensions = ()\n#metadata(extensions) <extensions-meta>\n",
        "blog.py": "def configure(pipeline):\n    pass\n",
        "template.typ": '''#import "/theme/theme.typ": core, render-article, render-page
#let post = core.post.with(renderer: render-article)
#let site-page = core.site-page.with(renderer: render-page)
#let calver = core.calver
''',
        "theme/theme.typ": '''#import "/vendor/typst-blog-core/typst/api.typ" as core
#assert(core.api-version == 1, message: "Fixture requires renderer contract v1")
#import "composition.typ": sidebar
#let ui = core.ui
#let render-article(data) = ui.article(data,
  main: ui.article-content(data, {
    ui.article-header(data.post)
    ui.toc-inline-slot()
    ui.abstract(data.post)
    ui.content-body(data)
  }),
  sidebar: sidebar(),
)
#let render-page(data) = ui.page(data,
  main: ui.page-content(data, {
    ui.page-header(data.page)
    ui.toc-inline-slot()
    ui.content-body(data)
  }),
  sidebar: sidebar(),
)
#let render-home(data) = ui.home(data, main: {
  ui.home-header(data)
  ui.post-cards(data.posts)
  ui.pagination(data.pagination)
})
#let render-tag(data) = ui.tag(data, main: {
  ui.tag-header(data)
  ui.post-cards(data.posts)
  ui.pagination(data.pagination)
})
#let render-tags-index(data) = ui.tags-index(data, main: {
  ui.tags-index-header()
  ui.tag-list(data.tags)
})
#let render-not-found(data) = ui.not-found(data, main: ui.not-found-content())
''',
        "theme/composition.typ": '''#import "/vendor/typst-blog-core/typst/api.typ": ui
#let sidebar() = ui.sidebar({
  ui.reference-preview()
  ui.toc()
  ui.search()
  ui.author()
  ui.about()
})
''',
        "theme/static/color-schemes/test.css": ":root { --accent-color: rgb(12, 34, 56); }\n",
        "theme/static/styles/theme.css": ".search-input { border-radius: 19px; }\n",
        "posts/demo/index.typ": '''#import "/template.typ": post, calver
#show: post.with(title: "Public components", description: "Searchable component fixture", create: calver(2026, 9, 13), tags: ("Test",), draft: false)
= First section
A footnote#footnote[Article note].

Inline math $x^2$ and display math:
$ x^2 + y^2 = z^2 $

#table(columns: 2, [A], [B], [1], [2])

```python
print("hello")
```
''',
        "pages/about/index.typ": '''#import "/template.typ": site-page
#show: site-page.with(title: "About", description: "Fixed page", draft: false)
= About section
A footnote#footnote[Fixed page note] and math $a+b$.
''',
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "vendor").mkdir()
    (root / "vendor/typst-blog-core").symlink_to(CORE_DIR, target_is_directory=True)
