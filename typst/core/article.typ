#import "/site.typ": site
#import "shared.typ": calver-iso-datetime, export-target, main-font, heading-font, math-font, base-path
#import "i18n.typ": i18n
#import "/typst/generated/posts.typ" as generated-posts
#let post-data = generated-posts.post-data
#import "article-seo.typ": article-seo-data
#import "../components/article-parts.typ": article-header, article-actions, post-navigation
#import "../components/head.typ": common-head
#import "../components/page-layout.typ": page-layout
#import "../components/widgets.typ": widget-author, widget-search

#let env(..items) = context {
  heading(outlined: false, numbering: none, i18n.writing_env)

  table(
    columns: (auto, auto, 1fr),
    inset: 8pt,
    align: horizon,
    stroke: (x, y) => if y == 0 { (bottom: 1pt + black) } else { (bottom: 0.5pt + gray) },
    table.header(i18n.env_software, i18n.env_version, i18n.env_notes),
    ..items
      .pos()
      .map(item => (
        item.at(0),
        item.at(1),
        item.at(2, default: [---]),
      ))
      .flatten(),
  )
}

/// 記事のメタデータを構築する。
///
/// - slug (str, none): URLスラッグ（例: `"my-first-post"`）。`none` の記事は build コマンドでエラーになる
/// - title (str): 記事タイトル
/// - authors (array, none): 著者名のリスト（例: `("Alice", "Bob")`）。`none` のとき `site.author.name` が使われる
/// - create (datetime, none): 初回公開日（例: `datetime(year: 2024, month: 1, day: 1)`）
/// - update (datetime, none): 最終更新日。`none` のとき作成日と同じ扱い
/// - tags (array): タグのリスト（例: `("Typst", "Web")`）
/// - description (str, none): メタディスクリプション（SEO・OGP用）
/// - abstract (content, none): 記事要約。`none` のとき `description` がフォールバックとして使われる
/// - og-image (str, none): OGP画像の URL（例: `"https://example.com/og.png"`）
/// - draft (bool): `true` のとき下書き。preview では表示し、build では公開対象から除外する
/// -> dictionary
#let post-meta(
  slug: none,
  title: "記事タイトル",
  authors: none,
  create: none,
  update: none,
  tags: (),
  description: none,
  abstract: none,
  og-image: none,
  draft: true,
) = (
  slug: slug,
  title: title,
  authors: authors,
  create: create,
  update: update,
  tags: tags,
  description: description,
  abstract: abstract,
  og-image: og-image,
  draft: draft,
)

#let article(
  slug: none,
  title: "記事タイトル",
  authors: none,
  create: none,
  update: none,
  tags: (),
  description: none,
  abstract: none,
  og-image: none,
  draft: false,
  ..args,
  body,
) = context {
  let document-authors = if authors == none { (site.author.name,) } else { authors }
  set document(title: title, author: document-authors)
  set heading(numbering: "1.")
  set text(lang: site.language, font: main-font)
  show heading: set text(font: heading-font)
  show figure.where(kind: table): set figure.caption(position: top)
  show figure.where(kind: raw): set figure(supplement: i18n.code)
  set quote(block: true)

  if export-target() == "paged" {
    set text(font: main-font, size: 12pt)
    show heading: set text(font: heading-font)
    if math-font != none {
      show math.equation: set text(font: math-font)
    }
    body
    return
  }

  assert(slug != none, message: "slug is required")
  assert(create != none, message: "create is required")
  assert(description != none, message: "description is required")
  let generated-update = post-data.at(slug, default: (:)).at("update", default: none)
  let url-slug = post-data.at(slug).at("url-slug")
  let effective-update = if site.update_policy == "git" { generated-update } else { update }
  let abstract-content = if abstract != none { abstract } else { description }
  let seo-data = article-seo-data(
    title: title,
    description: description,
    authors: document-authors,
    create: create,
    update: effective-update,
    slug: slug,
    url-slug: url-slug,
    image: og-image,
  )
  let article-image-url = seo-data.image-url
  let article-json-ld = seo-data.json-ld
  let modified = if effective-update == none { create } else { effective-update }

  let note-counter = counter("my-footnote")
  let footnotes = state("article-footnotes-" + slug, ())
  show footnote: it => {
    context {
      note-counter.step()
      let num = note-counter.get().first() + 1
      let note-id = "footnote-" + str(num)
      let reference-id = "footnote-reference-" + str(num)
      footnotes.update(notes => notes + ((number: num, body: it.body),))
      html.elem("sup", attrs: (class: "footnote-wrapper"), {
        html.elem(
          "a",
          attrs: (
            id: reference-id,
            class: "footnote-marker",
            href: "#" + note-id,
            role: "doc-noteref",
          ),
          "※" + str(num),
        )
      })
    }
  }

  if sys.version < version(0, 15, 0) {
    show math.equation.where(block: false): it => {
      html.elem("span", attrs: (role: "math"), html.frame(it))
    }
    show math.equation.where(block: true): it => {
      html.elem("figure", attrs: (role: "math"), html.frame(it))
    }
  }

  let article-indexing-attrs = if draft {
    ("data-pagefind-ignore": "all", "data-nosnippet": "")
  } else {
    ("data-pagefind-body": "")
  }

  page-layout(
    head-content: {
      if draft {
        html.meta(name: "robots", content: "noindex, nofollow")
      }
      common-head(
        title,
        description: description,
        image: article-image-url,
        url: "/" + url-slug + "/",
        og_type: "article",
        json_ld: article-json-ld,
        article_published_time: calver-iso-datetime(create),
        article_modified_time: calver-iso-datetime(modified),
        article_authors: document-authors,
        article_tags: tags,
      )
    },
    before-content: {
      html.elem(
        "div",
        attrs: (
          id: "copy-toast",
          role: "status",
          "aria-live": "polite",
          "aria-atomic": "true",
          "data-copied-label": i18n.copied,
          "data-pagefind-ignore": "all",
          "data-nosnippet": "",
        ),
      )
    },
    main-content: {
      html.elem("div", attrs: (class: "mobile-search", "data-pagefind-ignore": "all", "data-nosnippet": ""), {
        widget-search()
      })

      html.elem("nav", attrs: (class: "back-home-nav", "aria-label": i18n.back_to_top, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
        html.elem(
          "a",
          attrs: (class: "back-home-btn", href: base-path + "/", "data-pagefind-ignore": "all", "data-nosnippet": ""),
          i18n.back_home,
        )
      })

      html.elem("article", attrs: (
        ..article-indexing-attrs,
        "aria-labelledby": "article-title",
        "data-content-preview-close-label": i18n.close_preview,
        itemscope: "",
        itemtype: "https://schema.org/BlogPosting",
      ), {
        article-header(
          title: title,
          draft: draft,
          create: create,
          update: effective-update,
          tags: tags,
          slug: slug,
        )

        html.elem("nav", attrs: (class: "mobile-toc", "aria-label": i18n.toc, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
          html.details({
            html.summary(i18n.toc_open)
            outline(title: none)
          })
        })

        if type(abstract-content) != str or abstract-content != "" {
          html.elem(
            "section",
            attrs: (class: "article-abstract", "aria-labelledby": "article-abstract-heading"),
            {
              html.elem("h2", attrs: (id: "article-abstract-heading", class: "abstract-title"), i18n.abstract)
              if type(abstract-content) == str {
                html.p(class: "abstract-content", abstract-content)
              } else {
                html.div(class: "abstract-content", abstract-content)
              }
            },
          )
        }

        html.elem("div", attrs: (class: "article-body", itemprop: "articleBody"), {
          body

          context {
            let notes = footnotes.final()
            if notes.len() > 0 {
              html.elem(
                "section",
                attrs: (
                  class: "footnotes",
                  role: "doc-endnotes",
                  "aria-labelledby": "footnotes-heading",
                ),
                {
                  html.elem("h2", attrs: (id: "footnotes-heading", class: "footnotes-heading"), i18n.footnotes)
                  html.elem("ol", attrs: (class: "footnotes-list"), {
                    for note in notes {
                      let note-id = "footnote-" + str(note.number)
                      let reference-id = "footnote-reference-" + str(note.number)
                      html.elem(
                        "li",
                        attrs: (id: note-id, role: "doc-endnote"),
                        {
                          html.div(class: "footnote-body", note.body)
                          [ ]
                          html.elem(
                            "a",
                            attrs: (
                              class: "footnote-backlink",
                              href: "#" + reference-id,
                              role: "doc-backlink",
                              "aria-label": i18n.back_to_footnote_reference,
                            ),
                            "↩",
                          )
                        },
                      )
                    }
                  })
                },
              )
            }
          }
        })
      })

      article-actions()
      post-navigation(slug)
    },
    sidebar-content: {
      html.div(class: "sidebar-inner", {
        widget-search(extra-class: "desktop-search")
        html.elem("nav", attrs: (class: "sidebar-widget toc-widget", "aria-label": i18n.toc, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
          html.div(class: "widget-title", i18n.toc)
          outline(title: none)
        })
        widget-author()
      })
    },
    sidebar-attrs: ("data-pagefind-ignore": "all", "data-nosnippet": ""),
  )
}
