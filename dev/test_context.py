from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.context import BlogContext  # noqa: E402


class ContextTests(unittest.TestCase):
    def test_build_artifacts_live_under_dot_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            context = BlogContext.create(root)

            self.assertEqual(context.build_dir, root / ".build")
            self.assertEqual(
                context.generated_site_data_file,
                root / ".build" / "typst" / "site-data.typ",
            )


if __name__ == "__main__":
    unittest.main()
