#import "/site.typ": site
#import "shared.typ": export-target, main-font, heading-font, math-font, base-path, calver-key
#import "/typst/generated/posts.typ" as generated-posts
#import "article-seo.typ": article-seo-data

#let post-data = generated-posts.post-data
#let tag-slugs = dictionary(generated-posts).at("tag-slugs", default: (:))

/// 記事のメタデータを構築する。
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

#let _post-link(post) = if post == none {
  none
} else {
  (
    slug: post.slug,
    title: post.title,
    url: base-path + "/" + post.at("url-slug") + "/",
  )
}

#let _post-navigation(slug) = {
  let sorted-posts = post-data
    .pairs()
    .map(pair => {
      let (key, value) = pair
      value + (slug: key)
    })
    .sorted(key: post => calver-key(post.create))
    .rev()
  let current-index = sorted-posts.position(post => post.slug == slug)

  if current-index == none {
    (previous: none, next: none)
  } else {
    let previous = if current-index + 1 < sorted-posts.len() {
      sorted-posts.at(current-index + 1)
    } else {
      none
    }
    let next = if current-index > 0 {
      sorted-posts.at(current-index - 1)
    } else {
      none
    }
    (previous: _post-link(previous), next: _post-link(next))
  }
}

#let _article-data(
  slug,
  title,
  authors,
  create,
  update,
  tags,
  description,
  abstract,
  og-image,
  draft,
  body,
) = {
  assert(slug != none, message: "slug is required")
  assert(create != none, message: "create is required")
  assert(description != none, message: "description is required")

  let generated = post-data.at(slug)
  let generated-update = generated.at("update", default: none)
  let url-slug = generated.at("url-slug")
  let effective-update = if site.update_policy == "git" { generated-update } else { update }
  let document-authors = if authors == none { (site.author.name,) } else { authors }
  let abstract-content = if abstract != none { abstract } else { description }
  let seo = article-seo-data(
    title: title,
    description: description,
    authors: document-authors,
    create: create,
    update: effective-update,
    slug: slug,
    url-slug: url-slug,
    image: og-image,
  )
  let source-path = generated.at("source_url_path", default: none)
  let source-url = if source-path == none or site.github_repo == none or site.github_repo == "" {
    none
  } else {
    site.github_repo.trim("/", at: end) + "/commits/main/" + source-path
  }

  (
    site: site,
    page: (
      title: title,
      description: description,
      url: "/" + url-slug + "/",
      authors: document-authors,
    ),
    post: (
      slug: slug,
      url-slug: url-slug,
      title: title,
      authors: document-authors,
      create: create,
      update: effective-update,
      tags: tags,
      tag-links: tags.map(tag => (
        name: tag,
        url: base-path + "/tags/" + tag-slugs.at(tag) + "/",
      )),
      description: description,
      abstract: abstract-content,
      og-image: og-image,
      draft: draft,
      source-url: source-url,
    ),
    navigation: _post-navigation(slug),
    seo: seo,
    body: body,
  )
}

/// 記事メタデータを解決し、完成 HTML の構築を template 側の renderer に委譲する。
#let article(
  renderer: none,
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

  if export-target() == "paged" {
    set text(font: main-font, size: 12pt, ..site.language)
    show heading: set text(font: heading-font)
    if math-font != none {
      show math.equation: set text(font: math-font)
    }
    body
    return
  }

  assert(renderer != none, message: "article renderer is required; bind it from /template.typ")
  renderer(_article-data(
    slug,
    title,
    document-authors,
    create,
    update,
    tags,
    description,
    abstract,
    og-image,
    draft,
    body,
  ))
}

/// 記事メタデータ登録と renderer 呼び出しをまとめる。
#let post(
  renderer: none,
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
  body,
) = {
  let meta = post-meta(
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
  let render = article.with(renderer: renderer, ..meta)

  [
    #metadata(meta) <post-meta>
    #render(body)
  ]
}
