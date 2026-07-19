#import "/site.typ": site
#import "/typst/generated/posts.typ" as generated-posts
#import "../core/shared.typ": calver-display, calver-iso, calver-key, base-path
#import "../core/i18n.typ": i18n

#let post-data = generated-posts.post-data
#let tag-slugs = dictionary(generated-posts).at("tag-slugs", default: (:))

#let article-header(
  title: none,
  draft: false,
  create: none,
  update: none,
  tags: (),
  slug: none,
) = {
  assert(title != none, message: "article-header: title is required")
  assert(slug != none, message: "article-header: slug is required")

  html.header(class: "article-header", {
    html.elem("h1", attrs: (id: "article-title", class: "article-title", itemprop: "headline"), title)
    if draft {
      html.span(class: "draft-badge", i18n.draft)
    }
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
            html.elem(
              "time",
              attrs: (datetime: calver-iso(update), itemprop: "dateModified"),
              calver-display(update),
            )
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
}

#let article-actions() = {
  let share-enabled = site.share.x or site.share.misskey or site.share.copy
  let feedback-enabled = site.feedback.google_form_url != none and site.feedback.google_form_url != ""

  if share-enabled or feedback-enabled {
    html.elem("aside", attrs: (class: "share-feedback-section", "aria-label": i18n.article_actions, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
      html.hr(class: "section-divider")
      if share-enabled {
        html.elem("section", attrs: (class: "share-area", "aria-labelledby": "share-heading"), {
          html.elem("h3", attrs: (id: "share-heading"), i18n.share)
          html.div(class: "share-buttons", {
            if site.share.x {
              html.elem(
                "button",
                attrs: (class: "share-btn btn-x", type: "button", "data-article-action": "share-x"),
                i18n.post_on_x,
              )
            }
            if site.share.misskey {
              html.elem(
                "button",
                attrs: (class: "share-btn btn-misskey", type: "button", "data-article-action": "share-misskey"),
                i18n.note_on_misskey,
              )
            }
            if site.share.copy {
              html.elem(
                "button",
                attrs: (class: "share-btn btn-copy", type: "button", "data-article-action": "copy-info"),
                i18n.copy_info,
              )
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
              type: "button",
              "data-article-action": "open-feedback",
              "data-feedback-url": site.feedback.google_form_url,
              "data-feedback-entry-id": feedback-entry-id,
            ),
            i18n.feedback_send,
          )
        })
      }
    })
  }
}

#let post-navigation(slug) = {
  let sorted-posts = post-data
    .pairs()
    .map(pair => {
      let (key, val) = pair
      val + (slug: key)
    })
    .sorted(key: post => calver-key(post.create))
    .rev()
  let current-index = sorted-posts.position(post => post.slug == slug)

  if current-index != none {
    let previous-post = if current-index + 1 < sorted-posts.len() { sorted-posts.at(current-index + 1) } else { none }
    let next-post = if current-index > 0 { sorted-posts.at(current-index - 1) } else { none }
    if previous-post != none or next-post != none {
      html.hr(class: "section-divider")
      html.elem("nav", attrs: (class: "post-nav", "aria-label": i18n.adjacent_articles, "data-pagefind-ignore": "all", "data-nosnippet": ""), {
        if previous-post != none {
          html.a(class: "post-nav-link post-nav-prev", href: base-path + "/" + previous-post.slug + "/", {
            html.span(class: "post-nav-label", i18n.prev_article)
            html.span(class: "post-nav-title", previous-post.title)
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
}
