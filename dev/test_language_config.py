from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent


def evaluate_typst(
    language: str, body: str, *, expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    source = f'''#import "../typst/core/site-impl.typ": _site
#import "../typst/core/language.typ": html-language, translation-language
#let site = _site(
  title: "Test",
  description: "Test site",
  base_url: "https://example.com",
  language: {language},
  fonts: (
    main: (pdf: "Noto Serif CJK JP", web: none),
    code: (pdf: "Fira Code", web: none),
  ),
  author: (name: "Test", bio: "", links: ()),
)
{body}
'''
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".typ", dir=DEV_DIR, encoding="utf-8"
    ) as source_file:
        source_file.write(source)
        source_file.flush()
        result = subprocess.run(
            [
                "typst",
                "eval",
                "query(<result>).map(it => it.value)",
                "--in",
                source_file.name,
                "--root",
                str(CORE_DIR),
            ],
            check=False,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def run_typst(language: str, body: str) -> list[dict]:
    return json.loads(evaluate_typst(language, body).stdout)


class LanguageConfigTests(unittest.TestCase):
    def test_string_shorthand_uses_typst_defaults(self) -> None:
        values = run_typst(
            '"ja"',
            '#metadata((language: site.language, html: html-language(site.language))) <result>',
        )
        self.assertEqual(
            values[0],
            {
                "language": {"lang": "ja", "region": None, "script": "auto"},
                "html": "ja",
            },
        )

    def test_structured_language_drives_typst_and_bcp47(self) -> None:
        values = run_typst(
            '(lang: "ZH", region: "tw", script: "HANI")',
            '''#set text(..site.language)
#metadata((
  language: site.language,
  html: html-language(site.language),
  translation: translation-language(site.language, (ja: (:), "zh-TW": (:))),
)) <result>''',
        )
        self.assertEqual(values[0]["language"], {"lang": "zh", "region": "TW", "script": "hani"})
        self.assertEqual(values[0]["html"], "zh-Hani-TW")
        self.assertEqual(values[0]["translation"], "zh-TW")

    def test_structured_language_defaults_region_and_script(self) -> None:
        values = run_typst(
            '(lang: "en")',
            '#metadata((language: site.language, html: html-language(site.language))) <result>',
        )
        self.assertEqual(
            values[0],
            {
                "language": {"lang": "en", "region": None, "script": "auto"},
                "html": "en",
            },
        )

    def test_invalid_region_is_rejected(self) -> None:
        result = evaluate_typst(
            '(lang: "zh", region: "Taiwan")',
            '#metadata(site) <result>',
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.language.region", result.stderr)

    def test_unknown_language_key_is_rejected(self) -> None:
        result = evaluate_typst(
            '(lang: "zh", locale: "TW")',
            '#metadata(site) <result>',
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lang, region, script", result.stderr)


if __name__ == "__main__":
    unittest.main()
