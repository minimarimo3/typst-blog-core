// Template向けの安定した公開API。
// core内部のファイル構成は、このmoduleの背後で自由に変更できる。
#let api-version = 1

#import "core/shared.typ": (
  calver as core-calver,
  calver-display as core-calver-display,
  calver-iso as core-calver-iso,
  calver-iso-datetime as core-calver-iso-datetime,
  export-target as core-export-target,
  base-path as core-base-path,
  main-font as core-main-font,
  heading-font as core-heading-font,
  math-font as core-math-font,
)
#import "core/article.typ": (
  post-meta as core-post-meta,
  article as core-article,
  post as core-post,
)
#import "core/page.typ": (
  page-meta as core-page-meta,
  render-page as core-render-page,
  site-page as core-site-page,
)
#import "core/page-data.typ": (
  home-page-data as core-home-page-data,
  tag-page-data as core-tag-page-data,
  tags-index-page-data as core-tags-index-page-data,
  not-found-page-data as core-not-found-page-data,
)
#import "core/build-data.typ": load-build-data as core-load-build-data
#import "core/language.typ": (
  html-language as core-html-language,
  translation-language as core-translation-language,
)
#import "core/extensions.typ": (
  extension as core-extension,
  extension-assets as core-extension-assets,
  extension-asset-url as core-extension-asset-url,
)
#import "components/font-config.typ": (
  google-font-families as core-google-font-families,
  font-css-lines as core-font-css-lines,
)

#let calver = core-calver
#let calver-display = core-calver-display
#let calver-iso = core-calver-iso
#let calver-iso-datetime = core-calver-iso-datetime
#let export-target = core-export-target
#let base-path = core-base-path
#let main-font = core-main-font
#let heading-font = core-heading-font
#let math-font = core-math-font

#let post-meta = core-post-meta
#let article = core-article
#let post = core-post
#let page-meta = core-page-meta
#let render-page = core-render-page
#let site-page = core-site-page
#let home-page-data = core-home-page-data
#let tag-page-data = core-tag-page-data
#let tags-index-page-data = core-tags-index-page-data
#let not-found-page-data = core-not-found-page-data
#let load-build-data = core-load-build-data

#let html-language = core-html-language
#let translation-language = core-translation-language
#let extension = core-extension
#let extension-assets = core-extension-assets
#let extension-asset-url = core-extension-asset-url
#let google-font-families = core-google-font-families
#let font-css-lines = core-font-css-lines
