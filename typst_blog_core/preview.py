from __future__ import annotations

import functools
import http.server
import sys
import threading
import time
from pathlib import Path

from .builder import build
from .context import BlogContext, STATIC_EXTENSIONS


PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 8000
PREVIEW_PORT_ATTEMPTS = 10
PREVIEW_VERSION_PATH = "/__typst_blog_preview_version"
PREVIEW_SCRIPT_PATH = "/__typst_blog_preview.js"
PREVIEW_WATCH_SUFFIXES = STATIC_EXTENSIONS | {".css", ".typ", ".py"}
PREVIEW_IGNORED_DIRS = {".git", "__pycache__", "public"}


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


def _preview_snapshot(root_dir: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root_dir.rglob("*"):
        try:
            if not path.is_file():
                continue
            relative = path.relative_to(root_dir)
            if any(part in PREVIEW_IGNORED_DIRS for part in relative.parts):
                continue
            if relative.parts[:2] == ("typst", "generated"):
                continue
            if (
                path.suffix.lower() not in PREVIEW_WATCH_SUFFIXES
                and relative.parts[:1] != ("static",)
            ):
                continue
            stat = path.stat()
        except OSError:
            continue
        snapshot[relative.as_posix()] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _watch_preview(root_dir: Path, state: _PreviewState) -> None:
    snapshot = _preview_snapshot(root_dir)
    while True:
        time.sleep(0.5)
        next_snapshot = _preview_snapshot(root_dir)
        if next_snapshot == snapshot:
            continue
        time.sleep(0.2)
        snapshot = _preview_snapshot(root_dir)
        print("Change detected. Rebuilding preview...")
        try:
            build(root_dir=root_dir, base_path="")
        except Exception as exc:
            print(f"Preview rebuild failed: {exc}", file=sys.stderr)
        else:
            state.mark_rebuilt()
            print("Preview updated.")


def preview(root_dir: Path | str | None = None) -> None:
    context = BlogContext.create(root_dir, base_path="")
    build(root_dir=context.root_dir, base_path="")
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

    watcher = threading.Thread(target=_watch_preview, args=(context.root_dir, state), daemon=True)
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
