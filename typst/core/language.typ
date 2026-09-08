/// 正規化済みのサイト言語設定を BCP 47 言語タグへ変換する。
/// Typst の script は小文字の OpenType スクリプトタグだが、BCP 47 では Title Case にする。
#let html-language(language) = {
  let tag = language.lang
  if language.script != auto {
    let script = language.script
    tag += "-" + upper(script.slice(0, 1)) + lower(script.slice(1))
  }
  if language.region != none {
    tag += "-" + upper(language.region)
  }
  tag
}

/// UI 翻訳は、完全な BCP 47 タグ、言語+地域、言語+script、言語の順で探す。
/// これにより `zh-Hani-TW` でも既存の `zh-TW` 翻訳を利用できる。
#let translation-language(language, translations) = {
  let candidates = (html-language(language),)
  if language.region != none {
    candidates.push(language.lang + "-" + upper(language.region))
  }
  if language.script != auto {
    let script = language.script
    candidates.push(language.lang + "-" + upper(script.slice(0, 1)) + lower(script.slice(1)))
  }
  candidates.push(language.lang)
  let match = candidates.find(key => key in translations)
  if match == none { "ja" } else { match }
}
