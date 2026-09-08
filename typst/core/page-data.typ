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

/// ホームrendererへ渡す、表示方式に依存しないデータ。
#let home-page-data(
  posts: none,
  outputs: (),
  title: none,
  authors: none,
  description: none,
  og-image: none,
) = {
  let page-title = if title == none { site.title } else { title }
  let page-description = if description == none { site.description } else { description }
  let document-authors = if authors == none { (site.author.name,) } else { authors }
  (
    site: site,
    page: (
      title: page-title,
      description: page-description,
      url: "/",
      authors: document-authors,
      og-image: og-image,
    ),
    posts: _post-list(posts),
    outputs: _output-list(outputs),
  )
}

/// タグ別記事一覧rendererへ渡すデータ。
#let tag-page-data(tag: "", tag-slug: "", posts: (:)) = (
  site: site,
  page: (
    title: "#" + tag + " | " + site.title,
    url: "/tags/" + tag-slug + "/",
    authors: (site.author.name,),
  ),
  tag: (name: tag, slug: tag-slug),
  posts: _post-list(posts),
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
