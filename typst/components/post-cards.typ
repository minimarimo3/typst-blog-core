#import "../core/shared.typ": calver-display, calver-iso, calver-key, base-path
#import "../core/i18n.typ": i18n

#let post-card-grid(posts) = {
  let posts-list = if posts != none {
    posts
      .pairs()
      .map(pair => {
        let (key, val) = pair
        val + (url: base-path + "/" + key + "/")
      })
      .sorted(key: post => calver-key(post.create))
      .rev()
  } else {
    ()
  }

  html.div(class: "card-grid home-card-grid", {
    for post in posts-list {
      html.a(class: "post-card", href: post.url, {
        html.div(class: "card-content", {
          if "create" in post {
            html.elem(
              "time",
              attrs: (class: "card-date", datetime: calver-iso(post.create)),
              calver-display(post.create),
            )
          }
          if post.at("draft", default: false) {
            html.span(class: "draft-badge", i18n.draft)
          }
          html.h2(class: "card-title", post.title)
          if "description" in post {
            html.p(class: "card-desc", post.description)
          }
        })
      })
    }
  })
}
