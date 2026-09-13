#import "../core/shared.typ": base-path
#import "i18n.typ": i18n
#import "components/article-parts.typ": article-section-divider

#let sidebar(body) = html.div(class: "sidebar-inner", body)

#let reference-preview() = html.elem("div", attrs: (
  class: "reference-preview-slot", "data-reference-preview-slot": "",
))

#let back-home() = html.elem("nav", attrs: (
  class: "back-home-nav", "aria-label": i18n.back_to_top,
  "data-pagefind-ignore": "all", "data-nosnippet": "",
), html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home))

#let article-content(data, body) = {
  let attrs = if data.post.draft {
    ("data-pagefind-ignore": "all", "data-nosnippet": "")
  } else { ("data-pagefind-body": "") }
  html.elem("article", attrs: (
    ..attrs, "aria-labelledby": "article-title",
    "data-content-preview-close-label": i18n.close_preview,
    itemscope: "", itemtype: "https://schema.org/BlogPosting",
  ), body)
}

#let page-content(data, body) = {
  let attrs = if data.page.draft or not data.page.index {
    ("data-pagefind-ignore": "all", "data-nosnippet": "")
  } else { ("data-pagefind-body": "") }
  html.elem("article", attrs: (
    ..attrs, "aria-labelledby": "page-title",
    "data-content-preview-close-label": i18n.close_preview,
  ), body)
}

#let abstract(post) = {
  if type(post.abstract) != str or post.abstract != "" {
    html.elem("section", attrs: (class: "article-abstract", "aria-labelledby": "article-abstract-heading"), {
      html.elem("h2", attrs: (id: "article-abstract-heading", class: "abstract-title"), i18n.abstract)
      if type(post.abstract) == str {
        html.p(class: "abstract-content", post.abstract)
      } else {
        html.div(class: "abstract-content", post.abstract)
      }
    })
  }
}

#let article-end-divider(data) = {
  let actions = data.site.theme.article_actions
  if (actions.share.x or actions.share.misskey or actions.share.copy
    or (actions.feedback.google_form_url != none and actions.feedback.google_form_url != "")
    or data.navigation.previous != none or data.navigation.next != none) {
    article-section-divider(extra-class: "article-end-divider-desktop")
  }
  article-section-divider(extra-class: "article-end-divider-mobile")
}

#let page-header(page) = html.header(class: "article-header", {
  html.elem("h1", attrs: (id: "page-title", class: "article-title"), page.title)
  if page.draft { html.span(class: "draft-badge", i18n.draft) }
})

#let home-header(data) = html.header(class: "article-header", {
  html.h1(class: "article-title", data.page.title)
  if data.page.description != "" {
    html.p(class: "page-description", data.page.description)
  }
})

#let tag-header(data) = html.header(class: "article-header", {
  html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home)
  html.h1(class: "article-title", {
    html.span(class: "tag-page-prefix", i18n.tags + " / ")
    "#" + data.tag.name
  })
})

#let tags-index-header() = html.header(class: "article-header", {
  html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home)
  html.h1(class: "article-title", i18n.tag_index_title)
})

#let tag-list(tags) = html.div(class: "tag-index-list", {
  for tag in tags {
    html.a(class: "tag-index-item", href: tag.url, {
      html.span(class: "tag", "#" + tag.name)
      html.span(class: "tag-count", str(tag.count))
    })
  }
})

#let not-found-content() = html.article({
  html.header(class: "article-header", {
    html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home)
    html.h1(class: "article-title", "404 Not Found")
    html.p(class: "page-description", i18n.not_found_desc)
  })
  html.div(class: "article-body", {
    html.p(i18n.not_found_body)
    html.p(html.a(href: base-path + "/", i18n.back_to_top))
  })
})
