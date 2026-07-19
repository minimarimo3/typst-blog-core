#import "/site.typ": site
#import "shared.typ": export-target, main-font, heading-font, base-path
#import "i18n.typ": i18n
#import "../components/head.typ": common-head
#import "../components/widgets.typ": widget-author, widget-about, widget-search

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

  html.html(lang: site.language, {
    html.head({
      common-head(page-title, url: "/tags/")
    })
    html.body({
      html.div(class: "site-container", {
        html.main(class: "main-content", {
          html.header(class: "article-header", {
            html.a(class: "back-home-btn", href: base-path + "/", i18n.back_home)
            html.h1(class: "article-title", i18n.tag_index_title)
          })

          html.div(class: "mobile-search", {
            widget-search()
          })

          html.div(class: "tag-index-list", {
            for (tag, tag-data) in tags.pairs() {
              html.a(class: "tag-index-item", href: base-path + "/tags/" + tag-data.slug + "/", {
                html.span(class: "tag", "#" + tag)
                html.span(class: "tag-count", str(tag-data.count))
              })
            }
          })
        })

        html.aside(class: "sidebar", {
          html.div(class: "sidebar-inner", {
            widget-search(extra-class: "desktop-search")
            widget-author()
            widget-about()
          })
        })
      })
    })
  })
}
