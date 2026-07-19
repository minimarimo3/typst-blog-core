#import "/site.typ": site
#import "shared.typ": calver-display, calver-iso, calver-iso-datetime, calver-key, export-target, main-font, heading-font, math-font, base-path
#import "i18n.typ": i18n
#import "/typst/generated/posts.typ" as generated-posts
#let post-data = generated-posts.post-data
#let tag-slugs = dictionary(generated-posts).at("tag-slugs", default: (:))
#import "../components/head.typ": common-head
#import "../components/widgets.typ": widget-author, widget-search
#import "@preview/suiji:0.5.0": *

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
/// - draft (bool): `true` のとき下書き。build コマンドが公開対象から除外する
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

#let _article-url(slug) = {
  site.base_url + "/" + slug.trim("/", at: start).trim("/", at: end) + "/"
}

#let _absolute-site-url(value) = {
  let cleaned = if value.starts-with("./") { value.slice(2) } else { value }
  if cleaned.starts-with("https://") or cleaned.starts-with("http://") {
    cleaned
  } else if cleaned.starts-with("//") {
    "https:" + cleaned
  } else if cleaned.starts-with("/") {
    site.base_url + cleaned
  } else {
    site.base_url + "/" + cleaned
  }
}

#let _absolute-article-url(value, page-url) = {
  let cleaned = if value.starts-with("./") { value.slice(2) } else { value }
  if cleaned.starts-with("https://") or cleaned.starts-with("http://") {
    cleaned
  } else if cleaned.starts-with("//") {
    "https:" + cleaned
  } else if cleaned.starts-with("/") {
    site.base_url + cleaned
  } else {
    page-url + cleaned
  }
}

#let _article-image-url(image, page-url) = {
  let default-image = site.at("default_og_image", default: none)
  if image != none and image != "" {
    _absolute-article-url(image, page-url)
  } else if default-image != none and default-image != "" {
    _absolute-site-url(default-image)
  } else {
    none
  }
}

#let _site-author-same-as() = {
  let socials = site.author.at("socials", default: (:))
  let urls = ()
  for key in ("x", "misskey", "github") {
    let url = socials.at(key, default: "")
    if url != "" {
      urls.push(url)
    }
  }
  urls
}

#let _person-json-ld(name) = {
  let data = (
    "@type": "Person",
    name: name,
  )
  if name == site.author.name {
    let same-as = _site-author-same-as()
    if same-as.len() > 0 {
      data.insert("sameAs", same-as)
    }
  }
  data
}

#let _article-json-ld(title, description, authors, create, update, slug, image-url) = {
  let page-url = _article-url(slug)
  let modified = if update == none { create } else { update }
  let author-data = authors.map(name => _person-json-ld(name))
  let data = (
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: title,
    description: description,
    datePublished: calver-iso-datetime(create),
    dateModified: calver-iso-datetime(modified),
    author: if author-data.len() == 1 { author-data.first() } else { author-data },
    mainEntityOfPage: (
      "@type": "WebPage",
      "@id": page-url,
    ),
    url: page-url,
    inLanguage: site.language,
  )

  if image-url != none and image-url != "" {
    data.insert("image", image-url)
  }
  data
}

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
  let abstract-content = if abstract != none { abstract } else { description }
  let article-page-url = _article-url(slug)
  let article-image-url = _article-image-url(og-image, article-page-url)
  let modified = if update == none { create } else { update }
  let article-json-ld = _article-json-ld(title, description, document-authors, create, update, slug, article-image-url)

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
  
  let share-enabled = site.share.x or site.share.misskey or site.share.copy
  let feedback-enabled = site.feedback.google_form_url != none and site.feedback.google_form_url != ""

  html.html(lang: site.language, {
    html.head({
      common-head(
        title,
        description: description,
        image: article-image-url,
        url: "/" + slug + "/",
        og_type: "article",
        json_ld: article-json-ld,
        article_published_time: calver-iso-datetime(create),
        article_modified_time: calver-iso-datetime(modified),
        article_authors: document-authors,
        article_tags: tags,
      )
    })
    html.body({
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
      html.div(class: "site-container", {
        html.main(class: "main-content", {
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

          html.elem("article", attrs: ("data-pagefind-body": "", "aria-labelledby": "article-title", itemscope: "", itemtype: "https://schema.org/BlogPosting"), {
            html.header(class: "article-header", {
              html.elem("h1", attrs: (id: "article-title", class: "article-title", itemprop: "headline"), title)
              html.div(class: "article-meta", {
                html.div(class: "meta-dates", {
                  if create != none {
                    html.span(class: "meta-date", {
                      i18n.created
                      html.elem(
                        "time",
                        attrs: (
                          datetime: calver-iso(create),
                          itemprop: if update == none { "datePublished dateModified" } else { "datePublished" },
                        ),
                        calver-display(create),
                      )
                    })
                  }
                  if update != none {
                    html.span(class: "meta-date", {
                      i18n.updated
                      html.elem("time", attrs: (datetime: calver-iso(update), itemprop: "dateModified"), calver-display(update))
                    })
                  }
                })
                if tags.len() > 0 {
                  html.div(class: "meta-tags", {
                    for tag in tags {
                      html.a(class: "tag", href: base-path + "/tags/" + tag-slugs.at(tag) + "/", "#" + tag)
                    }
                  })
                }
                let github-repo = site.at("github_repo", default: none)
                if github-repo != none and github-repo != "" {
                  let source-path = post-data.at(slug, default: (:)).at("source_url_path", default: none)
                  if source-path != none {
                    html.elem("div", attrs: (class: "meta-edit-history", "data-pagefind-ignore": "all", "data-nosnippet": ""), {
                      html.elem(
                        "a",
                        attrs: (
                          class: "edit-history-link",
                          href: github-repo.trim("/", at: end) + "/commits/main/" + source-path,
                          target: "_blank",
                          rel: "noopener noreferrer",
                        ),
                        i18n.edit_history,
                      )
                    })
                  }
                }
              })
            })

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

          if share-enabled or feedback-enabled {
            html.elem("aside", attrs: (class: "share-feedback-section", "aria-label": i18n.article_actions, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
              html.hr(class: "section-divider")
              if share-enabled {
                html.elem("section", attrs: (class: "share-area", "aria-labelledby": "share-heading"), {
                  html.elem("h3", attrs: (id: "share-heading"), i18n.share)
                  html.div(class: "share-buttons", {
                    if site.share.x {
                      html.elem("button", attrs: (class: "share-btn btn-x", onclick: "shareX()"), i18n.post_on_x)
                    }
                    if site.share.misskey {
                      html.elem("button", attrs: (class: "share-btn btn-misskey", onclick: "shareMisskey()"), i18n.note_on_misskey)
                    }
                    if site.share.copy {
                      html.elem("button", attrs: (class: "share-btn btn-copy", onclick: "copyInfo()"), i18n.copy_info)
                    }
                  })
                })
              }

              if feedback-enabled {
                let feedback-entry-id = if site.feedback.entry_id == none { "" } else { site.feedback.entry_id }
                html.elem("section", attrs: (class: "feedback-area", "aria-labelledby": "feedback-heading"), {
                  html.elem("h3", attrs: (id: "feedback-heading"), i18n.feedback_title)
                  html.p(i18n.feedback_body)
                  html.elem(
                    "button",
                    attrs: (
                      class: "feedback-link",
                      onclick: "openFeedback('" + site.feedback.google_form_url + "', '" + feedback-entry-id + "')",
                    ),
                    i18n.feedback_send,
                  )
                })
              }
            })
          }

          let other-posts = post-data
            .pairs()
            .filter(p => p.first() != slug)
          if other-posts.len() > 0 {
            html.hr(class: "section-divider")

            html.elem("aside", attrs: (class: "related-posts", "aria-labelledby": "related-posts-heading", "data-pagefind-ignore": "all", "data-nosnippet": ""), {
              html.elem("h2", attrs: (id: "related-posts-heading", class: "section-title"), i18n.other_articles)
              let seed-src = slug + title
              let seed = int(seed-src.clusters().map(str.to-unicode).map(str).join().slice(0, calc.min(14, seed-src.clusters().len())))
              let rng = gen-rng(seed)
              let (_, indices) = shuffle-f(rng, range(other-posts.len()))
              let picks = indices.slice(0, calc.min(3, indices.len())).map(i => other-posts.at(i))

              html.div(class: "card-grid", {
                for pair in picks {
                  let (other-slug, post) = pair
                  let url = base-path + "/" + other-slug + "/"
                  html.a(class: "post-card", href: url, {
                    html.div(class: "card-content", {
                      if "create" in post {
                        html.elem("time", attrs: (class: "card-date", datetime: calver-iso(post.create)), calver-display(post.create))
                      }
                      html.h3(class: "card-title", post.title)
                      if "description" in post {
                        html.p(class: "card-desc", post.description)
                      }
                    })
                  })
                }
              })
            })
          }

          let sorted-posts = post-data
            .pairs()
            .map(pair => {
              let (key, val) = pair
              val + (slug: key)
            })
            .sorted(key: p => calver-key(p.create))
            .rev()
          let current-idx = sorted-posts.position(p => p.slug == slug)
          if current-idx != none {
            let prev-post = if current-idx + 1 < sorted-posts.len() { sorted-posts.at(current-idx + 1) } else { none }
            let next-post = if current-idx > 0 { sorted-posts.at(current-idx - 1) } else { none }
            if prev-post != none or next-post != none {
              html.hr(class: "section-divider")
              html.elem("nav", attrs: (class: "post-nav", "aria-label": i18n.adjacent_articles, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
                if prev-post != none {
                  html.a(class: "post-nav-link post-nav-prev", href: base-path + "/" + prev-post.slug + "/", {
                    html.span(class: "post-nav-label", i18n.prev_article)
                    html.span(class: "post-nav-title", prev-post.title)
                  })
                }
                if next-post != none {
                  html.a(class: "post-nav-link post-nav-next", href: base-path + "/" + next-post.slug + "/", {
                    html.span(class: "post-nav-label", i18n.next_article)
                    html.span(class: "post-nav-title", next-post.title)
                  })
                }
              })
            }
          }
        })

        html.elem("aside", attrs: (class: "sidebar", "data-pagefind-ignore": "all", "data-nosnippet": ""), {
          html.div(class: "sidebar-inner", {
            widget-search(extra-class: "desktop-search")
            html.elem("nav", attrs: (class: "sidebar-widget toc-widget", "aria-label": i18n.toc, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
              html.div(class: "widget-title", i18n.toc)
              outline(title: none)
            })
            widget-author()
          })
        })
      })
    })
  })
}
