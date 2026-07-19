#import "/site.typ": site
#import "shared.typ": calver-iso-datetime

#let _article-url(url-slug) = {
  site.base_url + "/" + url-slug + "/"
}

#let _absolute-site-url(value) = {
  let cleaned = if value.starts-with("./") { value.slice(2) } else { value }
  if cleaned.starts-with("https://") or cleaned.starts-with("http://") {
    cleaned
  } else if cleaned.starts-with("//") {
    "https:" + cleaned
  } else if cleaned.starts-with("/") {
    site.base_url + cleaned
  } else {
    site.base_url + "/" + cleaned
  }
}

#let _absolute-article-url(value, page-url) = {
  let cleaned = if value.starts-with("./") { value.slice(2) } else { value }
  if cleaned.starts-with("https://") or cleaned.starts-with("http://") {
    cleaned
  } else if cleaned.starts-with("//") {
    "https:" + cleaned
  } else if cleaned.starts-with("/") {
    site.base_url + cleaned
  } else {
    page-url + cleaned
  }
}

#let _article-image-url(image, page-url) = {
  let default-image = site.at("default_og_image", default: none)
  if image != none and image != "" {
    _absolute-article-url(image, page-url)
  } else if default-image != none and default-image != "" {
    _absolute-site-url(default-image)
  } else {
    none
  }
}

#let _site-author-same-as() = {
  let socials = site.author.at("socials", default: (:))
  let urls = ()
  for key in ("x", "misskey", "github") {
    let url = socials.at(key, default: "")
    if url != "" {
      urls.push(url)
    }
  }
  urls
}

#let _person-json-ld(name) = {
  let data = (
    "@type": "Person",
    name: name,
  )
  if name == site.author.name {
    let same-as = _site-author-same-as()
    if same-as.len() > 0 {
      data.insert("sameAs", same-as)
    }
  }
  data
}

#let _article-json-ld(title, description, authors, create, update, url-slug, image-url) = {
  let page-url = _article-url(url-slug)
  let modified = if update == none { create } else { update }
  let author-data = authors.map(name => _person-json-ld(name))
  let data = (
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: title,
    description: description,
    datePublished: calver-iso-datetime(create),
    dateModified: calver-iso-datetime(modified),
    author: if author-data.len() == 1 { author-data.first() } else { author-data },
    mainEntityOfPage: (
      "@type": "WebPage",
      "@id": page-url,
    ),
    url: page-url,
    inLanguage: site.language,
  )

  if image-url != none and image-url != "" {
    data.insert("image", image-url)
  }
  data
}

#let article-seo-data(
  title: none,
  description: none,
  authors: (),
  create: none,
  update: none,
  slug: none,
  url-slug: none,
  image: none,
) = {
  assert(title != none, message: "article-seo-data: title is required")
  assert(description != none, message: "article-seo-data: description is required")
  assert(create != none, message: "article-seo-data: create is required")
  assert(slug != none, message: "article-seo-data: slug is required")
  assert(url-slug != none, message: "article-seo-data: url-slug is required")

  let page-url = _article-url(url-slug)
  let image-url = _article-image-url(image, page-url)
  (
    image-url: image-url,
    json-ld: _article-json-ld(
      title,
      description,
      authors,
      create,
      update,
      url-slug,
      image-url,
    ),
  )
}
