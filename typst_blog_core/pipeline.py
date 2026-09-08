from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import ModuleType
from typing import Callable, Iterable, Literal, Mapping, Sequence

from .context import BlogContext, run_typst


BuildMode = Literal["build", "preview"]
BUILD_MODES = frozenset({"build", "preview"})
HOOK_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")
WINDOWS_FORBIDDEN_FILENAME_CHARS = frozenset('<>:"/\\|?*')
PORTABLE_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class PostInfo:
    slug: str
    url_slug: str
    title: str
    create: object
    update: object
    description: str
    tags: tuple[str, ...]
    draft: bool
    source_file: Path
    source_dir: Path

    @classmethod
    def from_post(cls, post: Mapping[str, object]) -> "PostInfo":
        return cls(
            slug=str(post["slug"]),
            url_slug=str(post["url_slug"]),
            title=str(post["title"]),
            create=post["create"],
            update=post["update"],
            description=str(post["description"]),
            tags=tuple(post["tags"]),  # type: ignore[arg-type]
            draft=bool(post["draft"]),
            source_file=Path(post["source_file"]),
            source_dir=Path(post["source_dir"]),
        )


@dataclass(frozen=True)
class BuildTask:
    root_dir: Path
    build_dir: Path
    output_dir: Path
    mode: BuildMode
    site: Mapping[str, object]
    posts: tuple[PostInfo, ...]
    _context: BlogContext

    def relative(self, path: Path | str) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.root_dir).as_posix()
        except ValueError:
            return str(resolved)

    def run(
        self,
        command: Sequence[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(command),
            cwd=self.root_dir,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=capture_output,
        )

    def run_typst(
        self,
        *args: str,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return run_typst(self._context, *args, capture_output=capture_output)


@dataclass(frozen=True)
class OutputTask(BuildTask):
    id: str
    label: str
    media_type: str
    destination: Path
    post: PostInfo | None


@dataclass(frozen=True)
class HtmlTask(BuildTask):
    path: Path
    output_path: str


OutputCallback = Callable[[OutputTask], None]
HtmlCallback = Callable[[HtmlTask], None]
BuildCallback = Callable[[BuildTask], None]


@dataclass(frozen=True)
class _OutputSpec:
    id: str
    filename: str
    label: str
    media_type: str
    build: OutputCallback
    modes: frozenset[str]
    per_post: bool


@dataclass(frozen=True)
class _HookSpec:
    id: str
    run: HtmlCallback | BuildCallback
    modes: frozenset[str]


@dataclass(frozen=True)
class PlannedOutput:
    id: str
    label: str
    media_type: str
    output_path: str
    destination: Path
    build: OutputCallback
    post: PostInfo | None

    def as_theme_data(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "media_type": self.media_type,
            "path": self.output_path,
        }


class Pipeline:
    """User-configurable build stages loaded from the blog root's blog.py."""

    def __init__(self) -> None:
        self._outputs: list[_OutputSpec] = []
        self._after_html: list[_HookSpec] = []
        self._post_build: list[_HookSpec] = []
        self._ids: set[str] = set()

    def post_output(
        self,
        *,
        id: str,
        filename: str,
        label: str,
        media_type: str,
        build: OutputCallback,
        modes: Iterable[BuildMode] = ("build",),
    ) -> None:
        self._add_output(id, filename, label, media_type, build, modes, per_post=True)

    def site_output(
        self,
        *,
        id: str,
        filename: str,
        label: str,
        media_type: str,
        build: OutputCallback,
        modes: Iterable[BuildMode] = ("build",),
    ) -> None:
        self._add_output(id, filename, label, media_type, build, modes, per_post=False)

    def after_html(
        self,
        *,
        id: str,
        run: HtmlCallback,
        modes: Iterable[BuildMode] = ("build", "preview"),
    ) -> None:
        self._add_hook(self._after_html, id, run, modes)

    def post_build(
        self,
        *,
        id: str,
        run: BuildCallback,
        modes: Iterable[BuildMode] = ("build",),
    ) -> None:
        self._add_hook(self._post_build, id, run, modes)

    def _claim_id(self, id: str) -> None:
        if not isinstance(id, str) or not HOOK_ID_RE.fullmatch(id):
            raise ValueError(
                "pipeline id must contain only ASCII letters, digits, '.', '_', or '-'"
            )
        if id in self._ids:
            raise ValueError(f"duplicate pipeline id: {id}")
        self._ids.add(id)

    def _add_output(
        self,
        id: str,
        filename: str,
        label: str,
        media_type: str,
        build: OutputCallback,
        modes: Iterable[BuildMode],
        *,
        per_post: bool,
    ) -> None:
        self._claim_id(id)
        normalized_filename = validate_output_filename(filename)
        if (
            not isinstance(label, str)
            or not label
            or any(unicodedata.category(character).startswith("C") for character in label)
        ):
            raise ValueError(f"pipeline output '{id}' label must be a non-empty string")
        if (
            not isinstance(media_type, str)
            or not media_type
            or not media_type.isascii()
            or any(character.isspace() for character in media_type)
        ):
            raise ValueError(f"pipeline output '{id}' media_type must be a non-empty string")
        if not callable(build):
            raise TypeError(f"pipeline output '{id}' build must be callable")
        self._outputs.append(
            _OutputSpec(
                id=id,
                filename=normalized_filename,
                label=label,
                media_type=media_type,
                build=build,
                modes=normalize_modes(modes),
                per_post=per_post,
            )
        )

    def _add_hook(
        self,
        target: list[_HookSpec],
        id: str,
        run: HtmlCallback | BuildCallback,
        modes: Iterable[BuildMode],
    ) -> None:
        self._claim_id(id)
        if not callable(run):
            raise TypeError(f"pipeline hook '{id}' run must be callable")
        target.append(_HookSpec(id=id, run=run, modes=normalize_modes(modes)))

    def plan_outputs(
        self,
        context: BlogContext,
        posts: Sequence[Mapping[str, object]],
        mode: BuildMode,
        reserved_paths: Iterable[str],
    ) -> tuple[dict[str, list[PlannedOutput]], list[PlannedOutput]]:
        post_infos = tuple(PostInfo.from_post(post) for post in posts)
        post_outputs: dict[str, list[PlannedOutput]] = {
            post.slug: [] for post in post_infos
        }
        site_outputs: list[PlannedOutput] = []
        claimed = {portable_output_key(path) for path in reserved_paths}

        for spec in self._outputs:
            if mode not in spec.modes:
                continue
            owners: Sequence[PostInfo | None] = post_infos if spec.per_post else (None,)
            for post in owners:
                if post is not None:
                    destination = context.output_dir / post.slug / spec.filename
                    output_path = "/" + post.url_slug + "/" + url_quote_path(spec.filename)
                else:
                    destination = context.output_dir / spec.filename
                    output_path = "/" + url_quote_path(spec.filename)
                relative = destination.relative_to(context.output_dir).as_posix()
                key = portable_output_key(relative)
                conflict = next(
                    (
                        existing
                        for existing in claimed
                        if key == existing
                        or key.startswith(existing + "/")
                        or existing.startswith(key + "/")
                    ),
                    None,
                )
                if conflict is not None:
                    raise ValueError(
                        f"pipeline output '{spec.id}' conflicts with site output path: {relative}"
                    )
                claimed.add(key)
                planned = PlannedOutput(
                    id=spec.id,
                    label=spec.label,
                    media_type=spec.media_type,
                    output_path=output_path,
                    destination=destination,
                    build=spec.build,
                    post=post,
                )
                if post is None:
                    site_outputs.append(planned)
                else:
                    post_outputs[post.slug].append(planned)
        return post_outputs, site_outputs

    def active_after_html(self, mode: BuildMode) -> tuple[_HookSpec, ...]:
        return tuple(hook for hook in self._after_html if mode in hook.modes)

    def active_post_build(self, mode: BuildMode) -> tuple[_HookSpec, ...]:
        return tuple(hook for hook in self._post_build if mode in hook.modes)


def normalize_modes(modes: Iterable[BuildMode]) -> frozenset[str]:
    result = frozenset(modes)
    if not result or not result <= BUILD_MODES:
        raise ValueError("pipeline modes must contain only 'build' and/or 'preview'")
    return result


def validate_output_filename(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("pipeline output filename must be a non-empty relative path")
    if "\\" in value or "\0" in value or value.endswith("/"):
        raise ValueError("pipeline output filename must use a portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute() or ".." in path.parts:
        raise ValueError("pipeline output filename must stay inside its output directory")
    for part in path.parts:
        if part in {"", "."} or part != part.strip() or part.startswith(".") or part.endswith("."):
            raise ValueError("pipeline output filename contains a non-portable path component")
        if any(character in WINDOWS_FORBIDDEN_FILENAME_CHARS for character in part):
            raise ValueError("pipeline output filename contains a forbidden filename character")
        if any(unicodedata.category(character).startswith("C") for character in part):
            raise ValueError("pipeline output filename contains a control character")
        if unicodedata.normalize("NFC", part) != part:
            raise ValueError("pipeline output filename must use Unicode NFC normalization")
        if len(part.encode("utf-8")) > 255:
            raise ValueError("pipeline output filename contains a path component over 255 bytes")
        if part.split(".", 1)[0].casefold().rstrip(" ") in PORTABLE_RESERVED_NAMES:
            raise ValueError("pipeline output filename uses a reserved filename")
    return path.as_posix()


def portable_output_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def url_quote_path(value: str) -> str:
    from urllib.parse import quote

    return "/".join(quote(part, safe="-._~") for part in PurePosixPath(value).parts)


def load_pipeline(context: BlogContext) -> Pipeline:
    pipeline = Pipeline()
    config_file = context.root_dir / "blog.py"
    if not config_file.is_file():
        return pipeline

    module_name = "_typst_blog_user_pipeline"
    spec = importlib.util.spec_from_file_location(module_name, config_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load pipeline configuration: {config_file}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    inserted_path = False
    if str(context.root_dir) not in sys.path:
        sys.path.insert(0, str(context.root_dir))
        inserted_path = True
    try:
        spec.loader.exec_module(module)
        _configure_pipeline(module, pipeline)
    finally:
        if inserted_path:
            sys.path.remove(str(context.root_dir))
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    return pipeline


def _configure_pipeline(module: ModuleType, pipeline: Pipeline) -> None:
    configure = getattr(module, "configure", None)
    if configure is None or not callable(configure):
        raise ValueError("blog.py must define configure(pipeline)")
    configure(pipeline)
