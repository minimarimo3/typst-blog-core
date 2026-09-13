#import "../core/shared.typ": calver-iso-datetime
#import "i18n.typ": i18n
#import "components/head.typ": common-head
#import "components/page-layout.typ": page-layout
#import "content.typ": content-rules

#let article(data, main: none, sidebar: none) = context {
  let post = data.post
  let page = data.page
  let generated-og-image = post.outputs.find(output => output.id == "og-image")
  let authored-og-image = post.at("og-image", default: none)
  let use-generated-og-image = (
    (authored-og-image == none or authored-og-image == "")
      and generated-og-image != none
  )
  let generated-og-image-url = if generated-og-image == none {
    none
  } else {
    data.site.base_url.trim("/", at: end) + generated-og-image.path
  }
  let effective-og-image = if use-generated-og-image {
    generated-og-image-url
  } else {
    data.seo.image-url
  }
  let effective-json-ld = data.seo.json-ld
  if use-generated-og-image {
    effective-json-ld.insert("image", generated-og-image-url)
  }

  show: content-rules.with(data)

  let modified = if post.update == none { post.create } else { post.update }
  page-layout(
    head-content: {
      if post.draft {
        html.meta(name: "robots", content: "noindex, nofollow")
      }
      common-head(
        page.title,
        description: page.description,
        image: effective-og-image,
        url: page.url,
        og_type: "article",
        json_ld: effective-json-ld,
        article_published_time: calver-iso-datetime(post.create),
        article_modified_time: calver-iso-datetime(modified),
        article_authors: post.authors,
        article_tags: post.tags,
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
    main-content: main,
    sidebar-content: sidebar,
    sidebar-attrs: ("data-mobile-empty": "", "data-pagefind-ignore": "all", "data-nosnippet": ""),
  )
}

#let page(data, main: none, sidebar: none) = context {
  let page = data.page

  set document(title: page.title, author: page.authors)
  show: content-rules.with(data)

  let excluded-from-index = page.draft or not page.index
  page-layout(
    head-content: {
      if excluded-from-index {
        html.meta(name: "robots", content: "noindex, nofollow")
      }
      common-head(
        page.title,
        description: page.description,
        image: page.at("og-image", default: none),
        url: page.url,
      )
    },
    main-content: main,
    sidebar-content: sidebar,
    sidebar-attrs: ("data-pagefind-ignore": "all", "data-nosnippet": ""),
  )
}

#let home(data, main: none, sidebar: none) = context {
  let page-title = if data.pagination.current == 1 { data.page.title } else {
    data.page.title + " — " + i18n.page + " " + str(data.pagination.current)
  }
  set document(title: page-title, author: data.page.authors)
  set text(..data.site.language)

  page-layout(
    head-content: common-head(
      page-title,
      description: data.page.description,
      image: data.page.at("og-image", default: none),
      url: data.page.url,
    ),
    main-content: main,
    sidebar-content: sidebar,
  )
}

#let tag(data, main: none, sidebar: none) = context {
  let page-title = if data.pagination.current == 1 { data.page.title } else {
    data.page.title + " — " + i18n.page + " " + str(data.pagination.current)
  }
  set document(title: page-title, author: data.page.authors)
  set text(..data.site.language)

  page-layout(
    head-content: common-head(page-title, url: data.page.url),
    main-content: main,
    sidebar-content: sidebar,
  )
}

#let tags-index(data, main: none, sidebar: none) = context {
  let page-title = i18n.tag_index_title + " | " + data.site.title
  set document(title: page-title, author: data.page.authors)
  set text(..data.site.language)

  page-layout(
    head-content: common-head(page-title, url: data.page.url),
    main-content: main,
    sidebar-content: sidebar,
  )
}

#let not-found(data, main: none, sidebar: none) = context {
  let title = "404 Not Found"
  set document(title: title, author: data.page.authors)
  set text(..data.site.language)

  page-layout(
    head-content: common-head(title, description: i18n.not_found_desc),
    main-content: main,
    sidebar-content: sidebar,
  )
}
