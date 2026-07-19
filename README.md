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
- the Python command implementation in `typst_blog_core/`
- thin direct-entry wrapper in `command.py`
- compatibility facade in `build.py` for blog repositories using the former wrapper
- RSS, sitemap, tag page, and generated post metadata logic
- Pagefind-compatible markup and frontend search integration
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

```sh
python3 vendor/typst-blog-core/command.py preview
```

Create a minimal post directory and `index.typ` with validated metadata using
the `new` command. New posts are drafts unless `--publish` is supplied.

```sh
python3 command.py new my-first-post \
  --title "My First Post" \
  --description "A short description." \
  --tag Typst
```

The Python package is split by responsibility: `cli.py` dispatches commands,
`new_post.py` creates posts, `metadata.py` validates and collects metadata,
`builder.py` produces the site, and `preview.py` owns the local server and
watcher. Updating the pinned submodule therefore updates all command behavior
without copying Python implementation into the blog repository.

The former core-level `build.py` API remains as a compatibility facade so an
older blog wrapper can still load `build()` and `preview()` after updating only
the submodule. New blog repositories should use `command.py`.

Set `posts_dir` in the user-owned `site.typ` when posts should live below a
dedicated directory. It defaults to `"."`; for example, `posts_dir: "posts"`
makes both `new` and `build` use the `posts/` tree. Only safe relative paths
inside the blog root are accepted.

Post update dates use `update_policy: "git"` by default. The build follows the
history of each post's `index.typ` across renames and combines it with commits
touching other files in the same post directory. The initial post commit does
not produce an update date. Set `update_policy: "manual"` to use the `update`
value authored in each post instead. GitHub Actions checkouts must use full
history (`fetch-depth: 0`); unavailable or shallow history produces a warning
and preserves authored update values as a fallback.

## URL Route Rules

Post slugs are validated as lowercase ASCII words separated by single hyphens.
Generated route names and names that are unsafe on common filesystems are
rejected before anything is written outside the expected post directory.

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
