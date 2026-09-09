"""Stable Python entry points for a blog template."""

from .cli import ConfigureNewPostParser, main
from .new_post import PostTemplate, PostTemplateContext, default_post_template

__all__ = [
    "ConfigureNewPostParser",
    "PostTemplate",
    "PostTemplateContext",
    "default_post_template",
    "main",
]
