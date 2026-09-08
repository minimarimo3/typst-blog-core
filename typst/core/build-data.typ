/// Python builderが生成した中間データを、core内部で読み出す。
/// importを関数内に置くことで、paged出力は.buildなしでもコンパイルできる。
#let load-build-data() = {
  import "/.build/typst/site-data.typ" as generated
  let values = dictionary(generated)
  (
    posts: values.at("posts", default: (:)),
    tag-slugs: values.at("tag-slugs", default: (:)),
    site-outputs: values.at("site-outputs", default: ()),
  )
}
