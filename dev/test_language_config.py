from __future__ import annotations

import json
import unittest

from typst_fixture import run_typst, site_source


def evaluate_typst(language: str, body: str, *, expect_success: bool = True):
    return run_typst(
        site_source(
            '#import "/vendor/typst-blog-core/typst/api.typ": html-language, translation-language\n' + body,
            language=language,
        ),
        expect_success=expect_success,
    )


def language_values(language: str, body: str) -> list[dict]:
    return json.loads(evaluate_typst(language, body).stdout)


class LanguageConfigTests(unittest.TestCase):
    def test_string_shorthand_uses_typst_defaults(self) -> None:
        values = language_values(
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
        values = language_values(
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
        values = language_values(
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
