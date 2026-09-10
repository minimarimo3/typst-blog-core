/// サイト全体の設定を構築する。未知のキーはコンパイルエラー、制約違反は assert で即時検出される。
///
/// - title (str): サイトタイトル（空文字不可）
/// - description (str): サイト説明文（空文字不可）
/// - base_url (str): サイトのベース URL（例: `"https://example.com"`）。末尾スラッシュなし
/// - language (str, dictionary): `"ja"`、または Typst の `text` と同じ `lang` / `region` / `script` を持つ辞書
/// - theme (dictionary): template側themeが定義する設定。coreは内容を解釈しない
/// - pagination (dictionary): home / tag の一覧分割設定。各項目は enabled (bool) と per_page (int) を持つ
/// - posts_dir (str): 記事ディレクトリ。ブログルートからの相対パス（例: `"posts"`）
/// - update_policy (str): 更新日の決定方法。`"git"` は記事ディレクトリの Git 履歴、`"manual"` は記事の `update` を使う
/// - asset_extensions (array): 記事・固定ページのディレクトリから出力へコピーするファイル拡張子
/// - default_og_image (str, none): 記事やページに画像指定がないときに使う既定OGP画像 URL
/// - fonts (dictionary): フォント設定。`main` と `code` キーが必須で、各々 `pdf` フィールドが必要。```typst
///   fonts: (
///     main: (pdf: ("Noto Serif", "Noto Serif CJK JP"), web: ("Noto Serif", "Noto Serif JP"), weights: "400;700", fallback: "serif"),
///     code: (pdf: ("Fira Code", "Consolas"), web: ("Fira Code",), weights: "300..700", fallback: "monospace"),
///     // heading / math / 任意名のフォントも追加可
///   )
///   ```
/// - author (dictionary): 著者情報。`name`（必須）, `bio`（str）, `links`（`id` / `label` / `url` と省略可能な `icon` を持つ配列）を含む辞書
/// - github_repo (str, none): GitHub リポジトリの URL（例: `"https://github.com/user/repo"`）。設定すると記事ページに編集履歴リンクが表示される
/// -> dictionary
#let _site(
  title: none,
  description: none,
  base_url: none,
  language: none,
  theme: (:),
  pagination: (
    home: (enabled: false, per_page: 10),
    tag: (enabled: false, per_page: 10),
  ),
  posts_dir: ".",
  update_policy: "git",
  asset_extensions: none,
  default_og_image: none,
  fonts: none,
  author: none,
  github_repo: none,
) = {
  let _req = (v, f) => assert(
    type(v) == str and v != "",
    message: "site." + f + ": 空でない文字列が必要です",
  )
  let _url = (u, f) => assert(
    u == "" or u.starts-with("https://") or u.starts-with("http://"),
    message: "site." + f + ": URL は https:// または http:// で始まる必要があります",
  )
  let _ascii-letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
  let _language-code = (value, lengths) => (
    type(value) == str
      and value.len() in lengths
      and value.clusters().all(character => _ascii-letters.contains(character))
  )

  // 必須文字列
  _req(title,       "title")
  _req(description, "description")
  _req(base_url,    "base_url")
  assert(
    base_url.starts-with("https://") or base_url.starts-with("http://"),
    message: "site.base_url: https:// または http:// で始まる必要があります",
  )
  assert(not base_url.ends-with("/"), message: "site.base_url: 末尾にスラッシュは不要です")
  let language = if type(language) == str {
    (lang: language, region: none, script: auto)
  } else {
    assert(type(language) == dictionary, message: "site.language: 文字列か辞書が必要です")
    assert(
      language.keys().all(key => key in ("lang", "region", "script")),
      message: "site.language: lang, region, script 以外のキーは使用できません",
    )
    (
      lang: language.at("lang", default: none),
      region: language.at("region", default: none),
      script: language.at("script", default: auto),
    )
  }
  assert(
    _language-code(language.lang, (2, 3)),
    message: "site.language.lang: 2文字か3文字の ISO 639 言語コードが必要です",
  )
  assert(
    language.region == none or _language-code(language.region, (2,)),
    message: "site.language.region: none か2文字の ISO 3166-1 alpha-2 コードが必要です",
  )
  assert(
    language.script == auto or _language-code(language.script, (4,)),
    message: "site.language.script: auto か4文字の OpenType スクリプトタグが必要です",
  )
  language = (
    lang: lower(language.lang),
    region: if language.region == none { none } else { upper(language.region) },
    script: if language.script == auto { auto } else { lower(language.script) },
  )
  assert(default_og_image == none or type(default_og_image) == str, message: "site.default_og_image: none か文字列が必要です")
  _req(posts_dir, "posts_dir")
  assert(update_policy == "git" or update_policy == "manual", message: "site.update_policy: git または manual が必要です")
  assert(
    type(asset_extensions) == array and asset_extensions.len() > 0,
    message: "site.asset_extensions: 空でない配列が必要です",
  )
  let _asset-extension-characters = _ascii-letters + "0123456789"
  for (index, extension) in asset_extensions.enumerate() {
    assert(
      type(extension) == str
        and extension.len() > 1
        and extension.starts-with(".")
        and extension.slice(1).clusters().all(character => _asset-extension-characters.contains(character)),
      message: "site.asset_extensions.at(" + str(index) + "): ドットに続けて英数字の拡張子を指定してください",
    )
  }

  assert(type(theme) == dictionary, message: "site.theme: theme固有設定の辞書が必要です")
  assert(type(pagination) == dictionary, message: "site.pagination: 辞書が必要です")
  assert(
    pagination.keys().all(key => key in ("home", "tag")),
    message: "site.pagination: home, tag 以外のキーは使用できません",
  )
  let pagination = (
    home: pagination.at("home", default: (enabled: false, per_page: 10)),
    tag: pagination.at("tag", default: (enabled: false, per_page: 10)),
  )
  for (name, setting) in pagination {
    assert(type(setting) == dictionary, message: "site.pagination." + name + ": 辞書が必要です")
    assert(
      setting.keys().all(key => key in ("enabled", "per_page")),
      message: "site.pagination." + name + ": enabled, per_page 以外のキーは使用できません",
    )
    assert(type(setting.at("enabled", default: none)) == bool, message: "site.pagination." + name + ".enabled: true/false が必要です")
    assert(
      type(setting.at("per_page", default: none)) == int and setting.per_page > 0,
      message: "site.pagination." + name + ".per_page: 1以上の整数が必要です",
    )
  }

  // fonts（main・code は必須、それぞれ pdf フィールドが必要）
  assert(type(fonts) == dictionary, message: "site.fonts: 辞書が必要です")
  assert("main" in fonts, message: "site.fonts.main: 必須です")
  assert("code" in fonts, message: "site.fonts.code: 必須です")
  assert("pdf" in fonts.main, message: "site.fonts.main.pdf: 必須です")
  assert("pdf" in fonts.code, message: "site.fonts.code.pdf: 必須です")
  for (name, entry) in fonts {
    assert(type(entry) == dictionary, message: "site.fonts." + name + ": 辞書が必要です")
    let web = entry.at("web", default: none)
    assert(web == none or type(web) == array, message: "site.fonts." + name + ".web: フォント名の配列か none が必要です")
    if web != none {
      assert(web.len() > 0, message: "site.fonts." + name + ".web: 空でない配列が必要です")
      for (index, family) in web.enumerate() {
        assert(
          type(family) == str and family.trim() != "",
          message: "site.fonts." + name + ".web.at(" + str(index) + "): 空でないフォント名が必要です",
        )
      }
    }
    let weights = entry.at("weights", default: none)
    assert(
      weights == none or (type(weights) == str and weights.trim() != ""),
      message: "site.fonts." + name + ".weights: 空でない文字列か none が必要です",
    )
    let fallback = entry.at("fallback", default: "serif")
    assert(
      fallback == none or (type(fallback) == str and fallback.trim() != ""),
      message: "site.fonts." + name + ".fallback: 空でない文字列か none が必要です",
    )
  }

  // author
  assert(type(author) == dictionary, message: "site.author: 辞書が必要です")
  _req(author.at("name", default: none), "author.name")
  assert(type(author.at("bio", default: "")) == str, message: "site.author.bio: 文字列が必要です")
  let links = author.at("links", default: ())
  assert(type(links) == array, message: "site.author.links: 配列が必要です")
  for (index, link) in links.enumerate() {
    assert(type(link) == dictionary, message: "site.author.links.at(" + str(index) + "): 辞書が必要です")
    assert(
      link.keys().all(key => key in ("id", "label", "url", "icon")),
      message: "site.author.links.at(" + str(index) + "): id, label, url, icon 以外のキーは使用できません",
    )
    let id = link.at("id", default: none)
    _req(id, "author.links.at(" + str(index) + ").id")
    assert(
      id.clusters().all(character => "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-".contains(character)),
      message: "site.author.links.at(" + str(index) + ").id: 英数字・アンダースコア・ハイフンのみ使用可能です",
    )
    _req(link.at("label", default: none), "author.links.at(" + str(index) + ").label")
    let url = link.at("url", default: none)
    assert(type(url) == str and url != "", message: "site.author.links.at(" + str(index) + ").url: 空でないURLが必要です")
    _url(url, "author.links.at(" + str(index) + ").url")
    let icon = link.at("icon", default: none)
    assert(
      icon == none or (type(icon) == str and icon.trim() != ""),
      message: "site.author.links.at(" + str(index) + ").icon: 空でない文字列か none が必要です",
    )
    if icon != none {
      let segments = icon.split("/")
      assert(
        not icon.starts-with("/")
          and not icon.contains("\\")
          and not ("." in segments)
          and not (".." in segments)
          and not icon.contains("?")
          and not icon.contains("#"),
        message: "site.author.links.at(" + str(index) + ").icon: static/ からの安全な相対パスが必要です",
      )
    }
  }

  // github_repo（省略可・設定する場合は URL 文字列）
  assert(
    github_repo == none or (type(github_repo) == str and (github_repo.starts-with("https://") or github_repo.starts-with("http://"))),
    message: "site.github_repo: none か https:// / http:// で始まる URL 文字列が必要です",
  )

  (
    title: title, description: description, base_url: base_url, language: language,
    theme: theme, pagination: pagination, posts_dir: posts_dir, update_policy: update_policy, asset_extensions: asset_extensions, default_og_image: default_og_image, fonts: fonts, author: author,
    github_repo: github_repo,
  )
}
