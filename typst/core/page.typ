#import "/site.typ": site
#import "shared.typ": export-target, main-font, heading-font, math-font
#import "build-data.typ": load-build-data

/// 汎用ページのメタデータを構築する。
#let page-meta(
  permalink: none,
  aliases: (),
  title: "ページタイトル",
  description: none,
  authors: none,
  og-image: none,
  draft: true,
  index: true,
  extra: (:),
) = {
  assert(type(extra) == dictionary, message: "extra must be a dictionary")
  (
    permalink: permalink,
    aliases: aliases,
    title: title,
    description: description,
    authors: authors,
    og-image: og-image,
    draft: draft,
    index: index,
    extra: extra,
  )
}

#let _page-data(
  permalink,
  aliases,
  title,
  description,
  authors,
  og-image,
  draft,
  index,
  extra,
  body,
) = {
  assert(description != none, message: "description is required")
  assert(type(extra) == dictionary, message: "extra must be a dictionary")

  let content-id = sys.inputs.at("content-id")
  let generated = load-build-data().pages.at(content-id)
  let document-authors = if authors == none { (site.author.name,) } else { authors }
  (
    site: site,
    page: (
      slug: content-id,
      url-slug: generated.at("url-slug"),
      title: title,
      description: description,
      url: "/" + generated.at("url-slug") + "/",
      authors: document-authors,
      og-image: og-image,
      draft: generated.at("draft", default: draft),
      index: generated.at("index", default: index),
      extra: generated.at("extra", default: extra),
    ),
    body: body,
  )
}

/// 汎用ページを完成HTMLへ変換する。paged出力では本文だけを描画する。
#let render-page(
  renderer: none,
  permalink: none,
  aliases: (),
  title: "ページタイトル",
  description: none,
  authors: none,
  og-image: none,
  draft: false,
  index: true,
  extra: (:),
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

  assert(renderer != none, message: "page renderer is required; bind it from /template.typ")
  renderer(_page-data(
    permalink,
    aliases,
    title,
    description,
    document-authors,
    og-image,
    draft,
    index,
    extra,
    body,
  ))
}

/// 汎用ページのメタデータ登録とrenderer呼び出しをまとめる。
#let site-page(
  renderer: none,
  permalink: none,
  aliases: (),
  title: "ページタイトル",
  description: none,
  authors: none,
  og-image: none,
  draft: true,
  index: true,
  extra: (:),
  body,
) = {
  let meta = page-meta(
    permalink: permalink,
    aliases: aliases,
    title: title,
    description: description,
    authors: authors,
    og-image: og-image,
    draft: draft,
    index: index,
    extra: extra,
  )
  let render = render-page.with(renderer: renderer, ..meta)

  [
    #metadata(meta) <page-meta>
    #render(body)
  ]
}
