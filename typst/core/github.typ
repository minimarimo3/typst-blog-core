/// 記事ソースの GitHub コミット履歴 URL を構築する。
#let github-commits-url(repository, branch, source-path) = {
  if source-path == none or repository == none or repository == "" {
    none
  } else {
    repository.trim("/", at: end) + "/commits/" + branch + "/" + source-path
  }
}
