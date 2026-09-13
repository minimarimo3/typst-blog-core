from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

from ui_fixture import CORE_DIR, create_ui_blog

sys.path.insert(0, str(CORE_DIR))
from typst_blog_core.builder import copy_static_assets  # noqa: E402
from typst_blog_core.context import BlogContext  # noqa: E402
from typst_blog_core.metadata import validate_permalink  # noqa: E402
from typst_blog_core.preview import _static_output_path, _sync_static_changes  # noqa: E402


class Elements(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.elements: list[tuple[str, dict]] = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def matching(self, *, tag=None, cls=None, attr=None):
        return [
            attrs for element_tag, attrs in self.elements
            if (tag is None or element_tag == tag)
            and (cls is None or cls in attrs.get("class", "").split())
            and (attr is None or attr in attrs)
        ]


class ComponentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        create_ui_blog(self.root)

    def build(self):
        result = subprocess.run(
            [sys.executable, str(CORE_DIR / "command.py"), "build"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def read(self, path):
        return (self.root / "public" / path).read_text(encoding="utf-8")

    def test_components_render_all_page_types_with_shared_content_and_assets(self):
        self.build()
        for path, note in (("demo/index.html", "Article note"), ("about/index.html", "Fixed page note")):
            with self.subTest(path=path):
                source = self.read(path)
                dom = Elements(source)
                self.assertIn(note, source)
                refs = dom.matching(cls="footnote-marker")
                self.assertEqual(len(refs), 1)
                self.assertEqual(refs[0]["href"], "#footnote-1")
                self.assertEqual(len(dom.matching(attr="data-pagefind-body")), 1)
                self.assertTrue(dom.matching(tag="math"))
                self.assertTrue(dom.matching(cls="responsive-toc"))
                styles = [a["href"] for a in dom.matching(tag="link") if a.get("rel") == "stylesheet"]
                self.assertLess(styles.index("/blog/_core/styles/components.css"), styles.index("/blog/styles/theme.css"))
                self.assertIn("/blog/color-schemes/test.css", styles)
                self.assertTrue(any(a.get("src") == "/blog/_core/scripts/main.js" for a in dom.matching(tag="script")))
                self.assertTrue(all(not a.get("src", "").startswith("/blog/scripts/") for a in dom.matching(tag="script")))
                self.assertIn('href="https://example.com/blog/' + path.removesuffix("index.html") + '"', source)
        for path in ("index.html", "tags/Test/index.html", "tags/index.html", "404.html"):
            self.assertTrue(Elements(self.read(path)).matching(tag="main"))
        self.assertTrue((self.root / "public/_core/scripts/search.js").is_file())
        self.assertIn("19px", self.read("styles/theme.css"))
        license_notice = self.read("third-party-licenses.txt")
        self.assertIn("CC BY-SA 4.0", license_notice)
        self.assertIn("misskey-hub.net/ja/brand-assets", license_notice)
        home = self.read("index.html")
        self.assertIn('class="widget-meta-link"', home)
        self.assertIn('href="/blog/third-party-licenses.txt"', home)
        self.assertNotIn('class="site-footer"', home)

    def test_composition_order_and_direct_html_extension_are_preserved(self):
        composition = self.root / "theme/composition.typ"
        original = composition.read_text()
        self.build()
        source = self.read("demo/index.html")
        self.assertLess(source.index('class="toc-desktop-slot"'), source.index('class="sidebar-widget search-widget'))
        composition.write_text(original.replace('  ui.toc()\n  ui.search()', '  ui.search()\n  html.aside(class: "custom-component", [Custom content])\n  ui.toc()'))
        self.build()
        source = self.read("demo/index.html")
        self.assertLess(source.index('class="sidebar-widget search-widget'), source.index('class="toc-desktop-slot"'))
        self.assertIn('class="custom-component"', source)
        self.assertIn("Custom content", source)

    def test_frozen_theme_survives_internal_core_relocation(self):
        frozen = {p.relative_to(self.root): p.read_bytes() for p in (self.root / "theme").rglob("*") if p.is_file()}
        vendored = self.root / "vendor/typst-blog-core"
        vendored.unlink()
        shutil.copytree(CORE_DIR / "typst", vendored / "typst")
        component = vendored / "typst/ui/components/widgets.typ"
        component.rename(component.with_name("widgets-next.typ"))
        api = vendored / "typst/ui.typ"
        api.write_text(api.read_text().replace('components/widgets.typ', 'components/widgets-next.typ'))
        self.build()
        self.assertTrue(Elements(self.read("demo/index.html")).matching(cls="search-input"))
        for path, content in frozen.items():
            self.assertEqual((self.root / path).read_bytes(), content)

    def test_non_indexed_page_keeps_robots_and_search_exclusion(self):
        page = self.root / "pages/about/index.typ"
        page.write_text(page.read_text().replace('draft: false)', 'draft: false, index: false)'))
        self.build()
        dom = Elements(self.read("about/index.html"))
        self.assertFalse(dom.matching(attr="data-pagefind-body"))
        self.assertTrue(any(a.get("name") == "robots" and a.get("content") == "noindex, nofollow" for a in dom.matching(tag="meta")))


class CoreAssetTests(unittest.TestCase):
    def test_namespace_cannot_be_replaced_by_site_assets_or_content(self):
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            for root in (context.user_static_dir, context.theme_static_dir):
                with self.subTest(root=root):
                    collision = root / "_CORE"
                    collision.mkdir(parents=True)
                    with self.assertRaisesRegex(ValueError, "reserved for core assets"):
                        copy_static_assets(context)
                    collision.rmdir()
            with self.assertRaisesRegex(ValueError, "reserved for site output"):
                validate_permalink("/_core/styles/")

    def test_core_assets_are_copied_and_updated_in_preview(self):
        self.assertEqual(_static_output_path(Path("vendor/typst-blog-core/static/_core/scripts/main.js")), Path("_core/scripts/main.js"))
        with tempfile.TemporaryDirectory() as directory:
            context = BlogContext.create(directory)
            context.output_dir.mkdir()
            copy_static_assets(context)
            output = context.output_dir / "_core/scripts/search.js"
            expected = (CORE_DIR / "static/_core/scripts/search.js").read_bytes()
            self.assertEqual(output.read_bytes(), expected)
            notice = context.output_dir / "third-party-licenses.txt"
            self.assertIn("CC BY-SA 4.0", notice.read_text(encoding="utf-8"))
            output.write_text("stale")
            prepared = SimpleNamespace(context=context, posts=[], pages=[])
            (context.root_dir / "extensions.typ").write_text("#metadata(()) <extensions-meta>\n")
            _sync_static_changes(prepared, {Path("vendor/typst-blog-core/static/_core/scripts/search.js")})
            self.assertEqual(output.read_bytes(), expected)
