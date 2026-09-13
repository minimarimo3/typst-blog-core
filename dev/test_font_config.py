from __future__ import annotations

import json
import unittest

from typst_fixture import run_typst, site_source


def font_source(web: str) -> str:
    return site_source(fonts=f'(main: (pdf: "serif", web: {web}), code: (pdf: "monospace", web: none))')


class FontConfigTests(unittest.TestCase):
    def test_web_font_arrays_generate_google_families_and_css_stacks(self) -> None:
        source = '''#import "/vendor/typst-blog-core/typst/api.typ": google-font-families, font-css-lines
#let fonts = (
  main: (web: ("Noto Serif", "Noto Serif JP"), weights: "400;700", fallback: "serif"),
  code: (web: ("Fira Code",), weights: "300..700", fallback: none),
  local: (web: ("Local Font",), weights: none, fallback: "sans-serif"),
  math: (web: none, weights: none, fallback: none),
)
#metadata((google: google-font-families(fonts), css: font-css-lines(fonts))) <result>
'''
        result = run_typst(source)
        value = json.loads(result.stdout)[0]

        self.assertEqual(
            value["google"],
            ["Noto+Serif:wght@400;700", "Noto+Serif+JP:wght@400;700", "Fira+Code:wght@300..700"],
        )
        self.assertEqual(
            value["css"],
            [
                '  --font-main: "Noto Serif", "Noto Serif JP", serif;',
                '  --font-code: "Fira Code";',
                '  --font-local: "Local Font", sans-serif;',
            ],
        )

    def test_web_none_is_valid(self) -> None:
        run_typst(font_source("none"))

    def test_web_string_is_rejected(self) -> None:
        result = run_typst(font_source('"Noto Serif"'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web", result.stderr)
        self.assertIn("配列か none", result.stderr)

    def test_empty_web_array_is_rejected(self) -> None:
        result = run_typst(font_source("()"), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web", result.stderr)
        self.assertIn("空でない配列", result.stderr)

    def test_empty_web_family_is_rejected(self) -> None:
        result = run_typst(font_source('("　",)'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web.at(0)", result.stderr)

    def test_non_string_web_family_is_rejected(self) -> None:
        result = run_typst(font_source('(42,)'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web.at(0)", result.stderr)


if __name__ == "__main__":
    unittest.main()
