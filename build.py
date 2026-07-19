"""Compatibility entry point for blog repositories using the former wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from typst_blog_core.builder import build  # noqa: E402
from typst_blog_core.preview import preview  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Typst blog (compatibility entry point)."
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="build, serve, watch, and live-reload the site locally",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parse_args()
        if args.preview:
            preview()
        else:
            build()
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
