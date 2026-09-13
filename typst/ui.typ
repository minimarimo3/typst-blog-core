// Public component API. Theme composition depends only on this module.
#import "ui/pages.typ": article, page, home, tag, tags-index, not-found
#import "ui/content.typ": content-body
#import "ui/parts.typ": (
  sidebar, reference-preview, back-home, article-content, page-content, abstract,
  article-end-divider, page-header, home-header, tag-header,
  tags-index-header, tag-list, not-found-content,
)
#import "ui/components/article-parts.typ": (
  article-header, article-actions, post-navigation,
  article-section-divider as divider,
)
#import "ui/components/widgets.typ": (
  widget-author as author,
  widget-search as search,
  widget-about as about,
  widget-mobile-search as mobile-search,
  widget-responsive-toc as toc,
  widget-toc-inline-slot as toc-inline-slot,
)
#import "ui/components/post-cards.typ": post-card-grid as post-cards, pagination-nav
#import "ui/components/navigation.typ": site-navigation
#import "ui/components/page-layout.typ": page-layout
#import "ui/components/head.typ": common-head
#import "ui/i18n.typ": i18n, i18n-coverage

#let pagination(data) = pagination-nav(
  data, i18n.pagination, i18n.previous_page, i18n.next_page,
)
