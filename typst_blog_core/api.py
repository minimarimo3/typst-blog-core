"""Stable Python entry points for a blog template."""

from .cli import ConfigureNewPageParser, ConfigureNewPostParser, main
from .new_page import PageTemplate, PageTemplateContext, default_page_template
from .new_post import PostTemplate, PostTemplateContext, default_post_template

__all__ = [
    "ConfigureNewPageParser",
    "ConfigureNewPostParser",
    "PageTemplate",
    "PageTemplateContext",
    "PostTemplate",
    "PostTemplateContext",
    "default_page_template",
    "default_post_template",
    "main",
]
