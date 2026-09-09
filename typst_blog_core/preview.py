from __future__ import annotations

import functools
import http.server
import shutil
import sys
import threading
import time
from pathlib import Path

from .builder import (
    PreparedBuild,
    build_page,
    build_post,
    build_prepared,
    prepare_build,
)
from .context import BlogContext, ROOT_STATIC_FILES
from .metadata import PostRecord, validate_extension_assets, validate_post_output_routes


PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 8000
PREVIEW_PORT_ATTEMPTS = 10
PREVIEW_VERSION_PATH = "/__typst_blog_preview_version"
PREVIEW_SCRIPT_PATH = "/__typst_blog_preview.js"
PREVIEW_SOURCE_SUFFIXES = frozenset({".css", ".typ", ".py"})
PREVIEW_IGNORED_DIRS = {".git", "__pycache__", ".build", "public"}


def _full_preview_build(root_dir: Path) -> PreparedBuild:
    print("Starting build...")
    prepared = prepare_build(
        root_dir=root_dir,
        base_path="",
        include_drafts=True,
        mode="preview",
    )
    return build_prepared(prepared)


class _PreviewState:
    def __init__(self) -> None:
        self._version = 1
        self._lock = threading.Lock()

    def version(self) -> int:
        with self._lock:
            return self._version

    def mark_rebuilt(self) -> None:
        with self._lock:
            self._version += 1


class _PreviewRequestHandler(http.server.SimpleHTTPRequestHandler):
    preview_state: _PreviewState

    def do_GET(self) -> None:
        path = self.path.partition("?")[0]
        if path == PREVIEW_VERSION_PATH:
            self._send_preview_content(
                str(self.preview_state.version()),
                "text/plain; charset=utf-8",
            )
            return
        if path == PREVIEW_SCRIPT_PATH:
            self._send_preview_content(_preview_reload_script(), "text/javascript; charset=utf-8")
            return
        super().do_GET()

    def _send_preview_content(self, content: str, content_type: str) -> None:
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        if self.path.partition("?")[0] != PREVIEW_VERSION_PATH:
            super().log_message(format, *args)


def _preview_reload_script() -> str:
    return f'''(() => {{
  let currentVersion;

  async function checkForUpdate() {{
    try {{
      const response = await fetch("{PREVIEW_VERSION_PATH}", {{ cache: "no-store" }});
      const nextVersion = await response.text();
      if (currentVersion === undefined) {{
        currentVersion = nextVersion;
      }} else if (nextVersion !== currentVersion) {{
        window.location.reload();
        return;
      }}
    }} catch (_) {{
      // The rebuild or preview server may be temporarily unavailable.
    }}
    window.setTimeout(checkForUpdate, 750);
  }}

  checkForUpdate();
}})();
'''


def _preview_snapshot(
    root_dir: Path,
    asset_extensions: frozenset[str],
) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root_dir.rglob("*"):
        try:
            if not path.is_file():
                continue
            relative = path.relative_to(root_dir)
            if any(part in PREVIEW_IGNORED_DIRS for part in relative.parts):
                continue
            if (
                path.suffix.lower() not in asset_extensions | PREVIEW_SOURCE_SUFFIXES
                and _static_output_path(relative) is None
            ):
                continue
            stat = path.stat()
        except OSError:
            continue
        snapshot[relative.as_posix()] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _changed_paths(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> set[Path]:
    return {
        Path(path)
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    }


def _static_output_path(relative: Path) -> Path | None:
    parts = relative.parts
    if parts[:2] == ("theme", "static"):
        return Path(*parts[2:])
    if parts[:1] == ("static",):
        return Path(*parts[1:])
    if len(parts) == 1 and parts[0] in ROOT_STATIC_FILES:
        return relative
    return None


def _preferred_static_source(context: BlogContext, output_path: Path) -> Path | None:
    candidates = []
    if len(output_path.parts) == 1 and output_path.name in ROOT_STATIC_FILES:
        candidates.append(context.root_dir / output_path)
    candidates.extend(
        (
            context.user_static_dir / output_path,
            context.theme_static_dir / output_path,
        )
    )
    return next((path for path in candidates if path.is_file()), None)


def _remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop:
        try:
            parent.rmdir()
        except OSError:
            return
        parent = parent.parent


def _sync_static_changes(prepared: PreparedBuild, changed: set[Path]) -> None:
    context = prepared.context
    validate_extension_assets(context)
    content = [*prepared.posts, *prepared.pages]
    validate_post_output_routes(content, context.user_static_dir)
    validate_post_output_routes(content, context.theme_static_dir)

    for relative in changed:
        output_path = _static_output_path(relative)
        if output_path is None:
            raise ValueError(f"not a static preview path: {relative.as_posix()}")
        destination = context.output_dir / output_path
        source = _preferred_static_source(context, output_path)
        if source is None:
            destination.unlink(missing_ok=True)
            _remove_empty_parents(destination, context.output_dir)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _content_source_file(content: PostRecord | dict) -> Path:
    return (
        content.source_file
        if isinstance(content, PostRecord)
        else content["source_file"]
    )


def _content_source_dir(content: PostRecord | dict) -> Path:
    return (
        content.source_dir
        if isinstance(content, PostRecord)
        else content["source_dir"]
    )


def _content_route_path(content: PostRecord | dict) -> str:
    return (
        content.route_path
        if isinstance(content, PostRecord)
        else content["route_path"]
    )


def _changed_content(
    prepared: PreparedBuild,
    changed: set[Path],
) -> PostRecord | dict | None:
    content = [*prepared.posts, *prepared.pages]
    owners: list[PostRecord | dict] = []
    for relative in changed:
        absolute = prepared.context.root_dir / relative
        candidates = [
            item
            for item in content
            if absolute.is_relative_to(_content_source_dir(item))
        ]
        if not candidates:
            return None
        owners.append(
            max(candidates, key=lambda item: len(_content_source_dir(item).parts))
        )
    source_files = {_content_source_file(item) for item in owners}
    return owners[0] if len(source_files) == 1 else None


def _same_incremental_inputs(before: PreparedBuild, after: PreparedBuild) -> bool:
    return (
        before.site == after.site
        and before.asset_extensions == after.asset_extensions
        and before.posts == after.posts
        and before.pages == after.pages
        and before.tag_slugs == after.tag_slugs
        and before.active_posts == after.active_posts
        and before.active_pages == after.active_pages
    )


def _sync_removed_content_assets(
    prepared: PreparedBuild,
    content: PostRecord | dict,
    changed: set[Path],
) -> None:
    source_dir = _content_source_dir(content)
    source_file = _content_source_file(content)
    output_dir = prepared.context.output_dir / _content_route_path(content)
    for relative in changed:
        source = prepared.context.root_dir / relative
        if source == source_file or source.exists():
            continue
        asset_relative = source.relative_to(source_dir)
        if source.suffix.lower() not in prepared.asset_extensions:
            continue
        destination = output_dir / asset_relative
        destination.unlink(missing_ok=True)
        _remove_empty_parents(destination, output_dir)


def _rebuild_preview_changes(
    root_dir: Path,
    previous: PreparedBuild,
    changed: set[Path],
) -> PreparedBuild:
    if (
        changed
        and all(_static_output_path(path) is not None for path in changed)
        and previous.supports_incremental_preview()
    ):
        _sync_static_changes(previous, changed)
        print(f"Updated {len(changed)} static file(s).")
        return previous

    content = _changed_content(previous, changed)
    if content is None or not previous.supports_incremental_preview():
        print("Change requires a full preview rebuild.")
        return _full_preview_build(root_dir)

    current = prepare_build(
        root_dir=root_dir,
        base_path="",
        include_drafts=True,
        mode="preview",
    )
    if not current.supports_incremental_preview() or not _same_incremental_inputs(
        previous, current
    ):
        print("Metadata, routes, or preview hooks changed; rebuilding all pages.")
        return build_prepared(current)

    source_file = _content_source_file(content)
    current_content = next(
        item
        for item in [*current.posts, *current.pages]
        if _content_source_file(item) == source_file
    )
    if isinstance(current_content, PostRecord):
        build_post(current.context, current_content, current.asset_extensions)
    else:
        build_page(current.context, current_content, current.asset_extensions)
    _sync_removed_content_assets(current, current_content, changed)
    print(f"Updated content: {source_file.relative_to(root_dir)}")
    return current


def _watch_preview(
    root_dir: Path,
    state: _PreviewState,
    prepared: PreparedBuild,
) -> None:
    asset_extensions = prepared.asset_extensions
    snapshot = _preview_snapshot(root_dir, asset_extensions)
    while True:
        time.sleep(0.5)
        next_snapshot = _preview_snapshot(root_dir, asset_extensions)
        if next_snapshot == snapshot:
            continue
        changed = _changed_paths(snapshot, next_snapshot)
        time.sleep(0.2)
        print("Change detected. Rebuilding preview...")
        try:
            prepared = _rebuild_preview_changes(root_dir, prepared, changed)
        except Exception as exc:
            print(f"Preview rebuild failed: {exc}", file=sys.stderr)
        else:
            asset_extensions = prepared.asset_extensions
            state.mark_rebuilt()
            print("Preview updated.")
        snapshot = _preview_snapshot(root_dir, asset_extensions)


def preview(root_dir: Path | str | None = None) -> None:
    context = BlogContext.create(root_dir, base_path="")
    prepared = _full_preview_build(context.root_dir)
    state = _PreviewState()
    _PreviewRequestHandler.preview_state = state
    handler = functools.partial(_PreviewRequestHandler, directory=str(context.output_dir))
    server = None
    last_error = None
    for port in range(PREVIEW_PORT, PREVIEW_PORT + PREVIEW_PORT_ATTEMPTS):
        try:
            server = http.server.ThreadingHTTPServer((PREVIEW_HOST, port), handler)
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise RuntimeError(
            f"Could not start preview server on ports {PREVIEW_PORT}-"
            f"{PREVIEW_PORT + PREVIEW_PORT_ATTEMPTS - 1}: {last_error}"
        ) from last_error

    watcher = threading.Thread(
        target=_watch_preview,
        args=(context.root_dir, state, prepared),
        daemon=True,
    )
    watcher.start()
    selected_port = server.server_address[1]
    if selected_port != PREVIEW_PORT:
        print(f"Port {PREVIEW_PORT} is in use; using {selected_port} instead.")
    print(f"Preview server: http://localhost:{selected_port}")
    print("Watching for changes. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.")
    finally:
        server.server_close()
