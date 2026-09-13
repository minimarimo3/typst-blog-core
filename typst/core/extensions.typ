/// ブログ拡張を宣言する。
///
/// `styles` と `scripts` には、`static/` からの相対パスか HTTPS URL を指定する。
/// ローカルの JavaScript は ES module として読み込まれる。
#let extension(name, styles: (), scripts: ()) = {
  assert(
    type(name) == str and name.trim() != "",
    message: "extension.name: 空でない文字列が必要です",
  )
  assert(type(styles) == array, message: "extension.styles: 文字列の配列が必要です")
  assert(type(scripts) == array, message: "extension.scripts: 文字列の配列が必要です")

  let validate-asset = (asset, field, index) => {
    assert(
      type(asset) == str and asset.trim() != "",
      message: "extension." + name + "." + field + ".at(" + str(index) + "): 空でない文字列が必要です",
    )
    let external = asset.starts-with("https://")
    let segments = asset.split("/")
    assert(
      external or (
        not asset.starts-with("/")
          and not asset.contains("\\")
          and not ("." in segments)
          and not (".." in segments)
          and not asset.contains("?")
          and not asset.contains("#")
      ),
      message: "extension." + name + "." + field + ".at(" + str(index) + "): static/ からの安全な相対パスか HTTPS URL が必要です",
    )
  }

  for (index, asset) in styles.enumerate() {
    validate-asset(asset, "styles", index)
  }
  for (index, asset) in scripts.enumerate() {
    validate-asset(asset, "scripts", index)
  }

  (name: name, styles: styles, scripts: scripts)
}

/// 登録された拡張を検証し、head に読み込むアセットをまとめる。
#let extension-assets(extensions) = {
  assert(type(extensions) == array, message: "extensions: 拡張の配列が必要です")
  let names = ()
  let styles = ()
  let scripts = ()

  for item in extensions {
    assert(type(item) == dictionary, message: "extensions: extension(...) で作った拡張が必要です")
    assert("name" in item and "styles" in item and "scripts" in item, message: "extensions: extension(...) で作った拡張が必要です")
    assert(not (item.name in names), message: "extensions: 拡張名 " + item.name + " が重複しています")
    names.push(item.name)
    styles += item.styles
    scripts += item.scripts
  }

  (styles: styles, scripts: scripts)
}

/// 拡張アセットの公開 URL を返す。HTTPS URL はそのまま、ローカルパスには base path を付ける。
#let extension-asset-url(asset, base-path) = if asset.starts-with("https://") {
  asset
} else {
  base-path + "/" + asset
}
