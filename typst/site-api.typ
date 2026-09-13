// site.typ向けの安定した公開API。
// site設定自身を読む通常のAPIとは分離し、循環importを避ける。
#import "core/site-impl.typ": _site as core-site

#let site = core-site
