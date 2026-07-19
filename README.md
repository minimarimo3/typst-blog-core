# Typst Blog Core

Reusable engine for `minimarimo3/typst-blog-template`.

This repository is intended to be consumed as a pinned Git submodule from a
user blog repository:

```sh
git submodule add https://github.com/minimarimo3/typst-blog-core.git vendor/typst-blog-core
```

The user repository owns `site.typ`, posts, custom assets, and deployment
workflow files. This core repository owns the reusable implementation:

- Typst templates under `typst/core/`
- Typst components under `typst/components/`
- default CSS, themes, JavaScript, and robots.txt under `static/`
- the build implementation in `build.py`
- RSS, sitemap, tag page, and generated post metadata logic
- Pagefind-compatible markup and frontend search integration
- validation helpers under `dev/`

## Use From A Blog Repository

The template repository provides a thin root-level `build.py`. It loads this
core build module and passes the blog repository root as the build root:

```sh
python3 build.py
```

Direct execution is also supported when the current working directory is the
blog repository root:

```sh
python3 vendor/typst-blog-core/build.py
```

Preview mode builds the site for `/`, starts a server at
`http://localhost:8000`, watches site sources, and reloads open browser pages
after successful rebuilds. Canonical URLs, RSS, and sitemap keep using the
public `base_url` from `site.typ`.

```sh
python3 vendor/typst-blog-core/build.py --preview
```

## Release Tags

Blog repositories should pin this submodule to a release tag instead of
tracking `main` directly. This keeps site builds reproducible and makes engine
updates explicit in the user repository history.

Suggested tag format:

```text
vYYYY.MM.DD
vYYYY.MM.DD.PATCH
```

## Import Contract

Core Typst files intentionally import user-owned configuration from the blog
repository root:

- `/site.typ`
- `/typst/generated/posts.typ`

User-authored posts should continue to import the root compatibility module:

```typst
#import "/template.typ": article, calver, post-meta
```

The root `template.typ` re-exports stable authoring helpers from this submodule.
