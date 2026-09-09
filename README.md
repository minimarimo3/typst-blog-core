# Typst Blog Core

Reusable engine for `minimarimo3/typst-blog-template`.

This repository is intended to be consumed as a pinned Git submodule from a
user blog repository:

```sh
git submodule add https://github.com/minimarimo3/typst-blog-core.git vendor/typst-blog-core
```

The user repository owns `site.typ`, posts, the complete page theme,
template-provided authoring extensions, custom assets, and deployment workflow
files. This core repository owns the reusable implementation:

- metadata, URL, SEO-data, page-data, language, and extension contracts under
  `typst/core/`
- renderer-independent Typst helpers
- the Python command implementation in `typst_blog_core/`
- thin direct-entry wrapper in `command.py`
- compatibility facade in `build.py` for blog repositories using the former wrapper
- RSS, sitemap, generated page-entry, tag-route, and post metadata logic
- user-owned Python build-pipeline loading and validated output routing
- validation helpers under `dev/`

## Use From A Blog Repository

The template repository provides a thin root-level `command.py`. It imports the
command implementation from this submodule and passes the blog repository root:

```sh
python3 command.py build
```

Direct execution is also supported when the current working directory is the
blog repository root:

```sh
python3 vendor/typst-blog-core/command.py build
```

Preview mode builds the site for `/`, starts a server at
`http://localhost:8000`, watches site sources, and reloads open browser pages
after successful rebuilds. Canonical URLs, RSS, and sitemap keep using the
public `base_url` from `site.typ`.

Preview builds include drafts and label them on post cards and article pages.
Draft pages use `noindex` and are excluded from Pagefind. Regular builds keep
excluding drafts from pages, tag routes, RSS, and sitemap output.

```sh
python3 vendor/typst-blog-core/command.py preview
```

Create a minimal post directory and `index.typ` with validated metadata using
the `new post` command. New posts are drafts unless `--publish` is supplied.

```sh
python3 command.py new post my-first-post \
  --title "My First Post" \
  --description "A short description." \
  --tag Typst
```

### Customize `new post` From The Blog

The blog-owned `command.py` can add arguments to `new post` without modifying
the core submodule. Pass a parser callback to `core_api.main()`:

```python
from __future__ import annotations

import argparse


core_api = _load_core_api()


def configure_new_post(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--course", required=True)
    parser.add_argument("--lesson", required=True, type=int)


def main() -> int:
    return core_api.main(
        root_dir=ROOT_DIR,
        configure_new_post=configure_new_post,
    )
```

The added values are written to the standard template's `extra` dictionary,
so this command produces `extra: (course: ..., lesson: ...)` metadata after
Typst decodes it:

```sh
python3 command.py new post lesson-one \
  --title "Lesson one" \
  --description "The first lesson." \
  --course typst-basics \
  --lesson 1
```

Argument values must be JSON-compatible. Options with a value of `None` are
omitted; this lets an optional argument stay absent from `extra` unless it is
used.

For a completely custom source template, also pass a function as
`new_post_template`. It receives a validated `PostTemplateContext`. Calling
`default_post_template()` is the easiest way to keep the core metadata header
and replace only the starter body:

```python
def course_post_template(post: core_api.PostTemplateContext) -> str:
    source = core_api.default_post_template(post)
    return source.replace(
        "// Write the post body below.",
        "= Goals\n\n= Lesson\n\n= Exercises",
    )


def main() -> int:
    return core_api.main(
        root_dir=ROOT_DIR,
        configure_new_post=configure_new_post,
        new_post_template=course_post_template,
    )
```

If neither customization argument is passed, core continues to use its own
standard arguments and standard post template.

Create non-post content such as About, FAQ, or policy pages with `new page`.
General pages live below `pages/`, stay out of post lists, tags, adjacent-post
navigation, and RSS, and use their own theme renderer.

```sh
python3 command.py new page about \
  --title "About" \
  --description "About this site."
```

General pages are drafts by default. `--publish` publishes immediately, while
`--no-index` excludes a published utility page from search engines, Pagefind,
and the sitemap.

The Python package is split by responsibility: `cli.py` dispatches commands,
`new_post.py` and `new_page.py` create content, `metadata.py` validates and collects metadata,
`pipeline.py` loads site-owned build extensions, `builder.py` produces the site,
and `preview.py` owns the local server and watcher. Updating the pinned
submodule therefore updates all command behavior without copying Python
implementation into the blog repository.

The former core-level `build.py` API remains as a compatibility facade so an
older blog wrapper can still load `build()` and `preview()` after updating only
the submodule. New blog repositories should use `command.py`.

Set `posts_dir` in the user-owned `site.typ` when posts should live below a
dedicated directory. It defaults to `"."`; for example, `posts_dir: "posts"`
makes both `new` and `build` use the `posts/` tree. Only safe relative paths
inside the blog root are accepted.

The required `asset_extensions` array in the user-owned `site.typ` controls
which files beside a post or page are copied to its output directory. Core does
not keep its own extension allowlist; templates can include the image, video,
audio, font, and download formats their content needs.

Post update dates use `update_policy: "git"` by default. The build follows the
history of each post's `index.typ` across renames and combines it with commits
touching other files in the same post directory. The initial post commit does
not produce an update date. Set `update_policy: "manual"` to use the `update`
value authored in each post instead. GitHub Actions checkouts must use full
history (`fetch-depth: 0`); unavailable or shallow history produces a warning
and preserves authored update values as a fallback.

## URL Route Rules

Post slugs may use human-readable Unicode text, including spaces, uppercase
letters, punctuation, and symbols. They must use NFC normalization. Generated
URLs percent-encode each post path segment once. Only values that are unsafe as
a single portable filename, generated route names, and common filesystem
reservations are rejected before anything is written.

Tag display names may contain Unicode, whitespace, and symbols. The build owns
their URL-segment encoding and passes the resulting mapping to every Typst page,
so tag output directories, links, and canonical URLs cannot drift apart. It also
rejects duplicate tags and collisions on case-insensitive filesystems.

## Release Tags

Blog repositories should pin this submodule to a release tag instead of
tracking `main` directly. This keeps site builds reproducible and makes engine
updates explicit in the user repository history.

Suggested tag format:

```text
vYYYY.MM.DD
vYYYY.MM.DD.PATCH
```

## Theme Boundary

The core does not own completed HTML pages, page layout, CSS, or browser-side
JavaScript. Those live in the user repository under `theme/`. The build creates
short-lived Typst entry documents and calls the renderers exported by
`/theme/theme.typ`:

- `render-article(data)`
- `render-page(data)`
- `render-home(data)`
- `render-tag(data)`
- `render-tags-index(data)`
- `render-not-found(data)`

Those generated entry documents import only `/theme/theme.typ`; they do not
import files from `vendor/typst-blog-core` directly. The theme facade re-exports
the core public module as the `core` namespace. New public core APIs therefore
become available without adding another re-export to an already customized
template, while the builder-to-theme boundary remains stable.

The core resolves dates, encoded URLs, adjacent-post links, source links, and
SEO data before calling these renderers. A theme controls the final document
structure without duplicating the Python builder or the metadata contract.

The `site.theme` dictionary is also opaque to core. The template's
`theme/config.typ` defines and validates settings used by its own renderers, so
a replacement theme does not inherit assumptions such as a particular color
scheme.

`theme/static/` contains the theme's CSS and JavaScript. Site-specific files
such as favicons and extension assets remain in root `static/`; the builder
copies the theme assets first and site assets second.

## Import Contract

The stable template-facing entry points owned by core are:

- `typst/api.typ`, exposed by the template as a module namespace
- `typst/site-api.typ`, used only while constructing `/site.typ` to avoid a
  circular import through APIs that consume the completed site configuration
- `typst_blog_core.api`, the Python command entry point

Files below `typst/core/`, `typst/components/`, and the other Python modules are
implementation details. A core update may reorganize them without requiring
changes to an existing user-owned template, provided these public entry points
and the renderer contract remain compatible.

Core Typst files intentionally import user-owned configuration from the blog
repository root:

- `/site.typ`
- `/extensions.typ`
- `/theme/theme.typ`

The Python builder also writes private intermediate data to
`/.build/typst/site-data.typ`. Core reads it lazily through
`typst/core/build-data.typ` and passes normalized values to theme renderers.
Themes should consume `data.posts`, `data.post.extra`, `data.post.outputs`, and
`data.outputs` instead of importing the private generated file. Core validates
but does not interpret the JSON-compatible dictionary in `extra`; the same
value is available on post entries in lists and as `PostRecord.extra` in Python
pipeline callbacks.

User-authored posts should continue to import the root compatibility module:

```typst
#import "/template.typ": post, calver

#show: post.with(
  slug: "my-first-post",
  title: "My First Post",
  create: calver(2026, 1, 1),
  description: "A short description of the post.",
  tags: ("Typst",),
  extra: (course: "typst-basics", lesson: 1),
  draft: true,
)
```

The `post` show rule registers metadata and asks the renderer bound by the root
`template.typ` to render the remaining document. This root module is the
composition boundary between core and theme and also re-exports stable
authoring helpers.

## Build Pipeline Contract

If the blog root contains `blog.py`, core loads it for every build and preview
rebuild and calls `configure(pipeline)`. A site can register:

- `post_output` for a declared file generated once per included post
- `site_output` for a declared site-wide file
- `after_html` for each HTML file below `public/`
- `post_build` after the completed local artifact is available

Outputs run before HTML so their validated metadata can be included in renderer
data. Output callbacks must create exactly their declared file; route conflicts,
unsafe paths, callback exceptions, and non-zero subprocess exits fail the build.
`after_html` and `post_build` hooks run in registration order.

Extra outputs and `post_build` default to production builds only. `after_html`
defaults to both production and preview. Each registration can set `modes` to
an explicit subset of `{"build", "preview"}`. Core never installs hook
dependencies automatically and does not treat local `post_build` completion as
successful deployment.

## Extension Contract

The core only owns the generic extension registry and loads the CSS and
JavaScript declared by `/extensions.typ`. Built-in conveniences such as alerts
and YouTube embeds belong to the template repository and use that same public
contract. A blog owner can therefore add or replace an authoring feature using
only template-side Typst modules and files under `static/`, without editing or
forking the core.
