#import "/site.typ": site
#import "shared.typ": base-path, calver-key

#let _output-list(outputs) = outputs.map(output => (
  ..output,
  url: base-path + output.path,
))

#let _post-list(posts) = if posts == none {
  ()
} else {
  posts
    .pairs()
    .map(pair => {
      let (slug, value) = pair
      value + (
        slug: slug,
        url: base-path + "/" + value.at("url-slug") + "/",
      )
    })
    .sorted(key: post => calver-key(post.create))
    .rev()
}

#let _pagination(current, total, root-path) = {
  let route = page => if page == 1 { root-path } else { root-path + "page/" + str(page) + "/" }
  (
    current: current,
    total: total,
    previous: if current > 1 { base-path + route(current - 1) } else { none },
    next: if current < total { base-path + route(current + 1) } else { none },
    pages: range(1, total + 1).map(page => (number: page, url: base-path + route(page))),
  )
}

/// ホームrendererへ渡す、表示方式に依存しないデータ。
#let home-page-data(
  posts: none,
  outputs: (),
  title: none,
  authors: none,
  description: none,
  og-image: none,
  page-number: 1,
  total-pages: 1,
  per-page: none,
) = {
  let page-title = if title == none { site.title } else { title }
  let page-description = if description == none { site.description } else { description }
  let document-authors = if authors == none { (site.author.name,) } else { authors }
  let all-posts = _post-list(posts)
  let visible-posts = if per-page == none { all-posts } else {
    all-posts.slice((page-number - 1) * per-page, calc.min(page-number * per-page, all-posts.len()))
  }
  let page-url = if page-number == 1 { "/" } else { "/page/" + str(page-number) + "/" }
  (
    site: site,
    page: (
      title: page-title,
      description: page-description,
      url: page-url,
      authors: document-authors,
      og-image: og-image,
    ),
    posts: visible-posts,
    pagination: _pagination(page-number, total-pages, "/"),
    outputs: _output-list(outputs),
  )
}

/// タグ別記事一覧rendererへ渡すデータ。
#let tag-page-data(tag: "", tag-slug: "", posts: (:), page-number: 1, total-pages: 1) = (
  site: site,
  page: (
    title: "#" + tag + " | " + site.title,
    url: "/tags/" + tag-slug + "/" + if page-number == 1 { "" } else { "page/" + str(page-number) + "/" },
    authors: (site.author.name,),
  ),
  tag: (name: tag, slug: tag-slug),
  posts: _post-list(posts),
  pagination: _pagination(page-number, total-pages, "/tags/" + tag-slug + "/"),
)

/// タグ一覧rendererへ渡すデータ。
#let tags-index-page-data(tags: (:)) = (
  site: site,
  page: (
    url: "/tags/",
    authors: (site.author.name,),
  ),
  tags: tags.pairs().map(pair => {
    let (name, value) = pair
    (
      name: name,
      slug: value.slug,
      count: value.count,
      url: base-path + "/tags/" + value.slug + "/",
    )
  }),
)

/// 404 rendererへ渡す共通データ。表示タイトルと文言はthemeが所有する。
#let not-found-page-data() = (
  site: site,
  page: (url: none, authors: (site.author.name,)),
)
