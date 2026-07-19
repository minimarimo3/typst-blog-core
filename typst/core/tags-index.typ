#import "/site.typ": site
#import "shared.typ": export-target, main-font, heading-font, base-path
#import "i18n.typ": i18n
#import "../components/head.typ": common-head
#import "../components/page-layout.typ": page-layout
#import "../components/widgets.typ": widget-mobile-search, widget-site-sidebar

#let tags-index-page(
  tags: (:),
  body,
) = context {
  let page-title = i18n.tag_index_title + " | " + site.title
  set document(title: page-title, author: site.author.name)
  set text(lang: site.language)

  if export-target() == "paged" {
    set text(font: main-font, size: 12pt)
    show heading: set text(font: heading-font)
    body
    return
  }

  page-layout(
    head-content: {
      common-head(page-title, url: "/tags/")
    },
    main-content: {
      html.header(class: "article-header", {
        html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home)
        html.h1(class: "article-title", i18n.tag_index_title)
      })

      widget-mobile-search()

      html.div(class: "tag-index-list", {
        for (tag, tag-data) in tags.pairs() {
          html.a(class: "tag-index-item", href: base-path + "/tags/" + tag-data.slug + "/", {
            html.span(class: "tag", "#" + tag)
            html.span(class: "tag-count", str(tag-data.count))
          })
        }
      })
    },
    sidebar-content: widget-site-sidebar(),
  )
}
