#import "/site.typ": site

#let page-layout(
  head-content: none,
  main-content: none,
  sidebar-content: none,
  before-content: none,
  sidebar-attrs: (:),
) = {
  assert(head-content != none, message: "page-layout: head-content is required")
  assert(main-content != none, message: "page-layout: main-content is required")
  assert(sidebar-content != none, message: "page-layout: sidebar-content is required")

  html.html(lang: site.language, {
    html.head(head-content)
    html.body({
      if before-content != none {
        before-content
      }
      html.div(class: "site-container", {
        html.main(class: "main-content", main-content)
        html.elem(
          "aside",
          attrs: (class: "sidebar", ..sidebar-attrs),
          sidebar-content,
        )
      })
    })
  })
}
