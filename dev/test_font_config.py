from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent


def run_typst(source: str, *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".typ",
        dir=DEV_DIR,
        encoding="utf-8",
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


def site_source(web: str) -> str:
    return f'''#import "../typst/core/site-impl.typ": _site
#let value = _site(
  title: "Test",
  description: "Test site",
  base_url: "https://example.com",
  language: "ja",
  fonts: (
    main: (pdf: "Noto Serif CJK JP", web: {web}, weights: "400;700", fallback: "serif"),
    code: (pdf: "Fira Code", web: ("Fira Code",), weights: none, fallback: none),
  ),
  author: (name: "Test", bio: "", socials: (:)),
  share: (x: true, misskey: true, copy: true),
)
#metadata(value) <result>
'''


class FontConfigTests(unittest.TestCase):
    def test_web_font_arrays_generate_google_families_and_css_stacks(self) -> None:
        source = '''#import "../typst/components/font-config.typ": google-font-families, font-css-lines
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
        run_typst(site_source("none"))

    def test_web_string_is_rejected(self) -> None:
        result = run_typst(site_source('"Noto Serif"'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web", result.stderr)
        self.assertIn("配列か none", result.stderr)

    def test_empty_web_array_is_rejected(self) -> None:
        result = run_typst(site_source("()"), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web", result.stderr)
        self.assertIn("空でない配列", result.stderr)

    def test_empty_web_family_is_rejected(self) -> None:
        result = run_typst(site_source('("　",)'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web.at(0)", result.stderr)

    def test_non_string_web_family_is_rejected(self) -> None:
        result = run_typst(site_source('(42,)'), expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("site.fonts.main.web.at(0)", result.stderr)


if __name__ == "__main__":
    unittest.main()
