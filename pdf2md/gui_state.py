from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pdf2md.gui_i18n import DEFAULT_GUI_LANGUAGE, GuiLanguage, normalize_language
from pdf2md.gui_presets import DEFAULT_GUI_OPTION_PRESET, GuiOptionPreset, normalize_preset

GUI_STATE_SCHEMA_VERSION = 2
SUPPORTED_GUI_STATE_SCHEMA_VERSIONS = {1, 2}
DEFAULT_RECENT_LIMIT = 5

RecentPathKind = Literal["input_file", "input_folder", "output_dir"]
ResultOpenTarget = Literal["markdown", "report", "manifest", "assets", "output_dir"]


class GuiDocumentLike(Protocol):
    output_dir: Path
    markdown_path: Path | None
    manifest_path: Path | None
    report_path: Path | None
    assets_dir: Path | None


@dataclass(frozen=True)
class GuiRecentState:
    recent_input_files: tuple[Path, ...] = ()
    recent_input_folders: tuple[Path, ...] = ()
    recent_output_dirs: tuple[Path, ...] = ()
    language: GuiLanguage = DEFAULT_GUI_LANGUAGE
    option_preset: GuiOptionPreset = DEFAULT_GUI_OPTION_PRESET

    def is_empty(self) -> bool:
        """Return whether no recent GUI path is available."""
        return not (self.recent_input_files or self.recent_input_folders or self.recent_output_dirs)


@dataclass(frozen=True)
class GuiProgressSnapshot:
    current: int
    total: int
    percent: int
    label: str


def default_gui_state_path() -> Path:
    """Return the local-only GUI state path for the current user profile."""
    override = os.environ.get("PDF2MD_GUI_STATE_PATH")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "pdf2md" / "gui_state.json"


def load_gui_recent_state(path: Path | None = None) -> GuiRecentState:
    """Load GUI recent-path state, falling back to empty state on missing or invalid files."""
    state_path = path or default_gui_state_path()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GuiRecentState()
    if not isinstance(payload, dict) or payload.get("schema_version") not in SUPPORTED_GUI_STATE_SCHEMA_VERSIONS:
        return GuiRecentState()
    return GuiRecentState(
        recent_input_files=_coerce_recent_paths(payload.get("recent_input_files")),
        recent_input_folders=_coerce_recent_paths(payload.get("recent_input_folders")),
        recent_output_dirs=_coerce_recent_paths(payload.get("recent_output_dirs")),
        language=normalize_language(payload.get("language") if isinstance(payload.get("language"), str) else None),
        option_preset=normalize_preset(
            payload.get("option_preset") if isinstance(payload.get("option_preset"), str) else None
        ),
    )


def save_gui_recent_state(
    state: GuiRecentState,
    path: Path | None = None,
    *,
    max_items: int = DEFAULT_RECENT_LIMIT,
) -> None:
    """Persist GUI recent-path state without storing PDF content or conversion warnings."""
    state_path = path or default_gui_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": GUI_STATE_SCHEMA_VERSION,
        "recent_input_files": _serialize_paths(state.recent_input_files, max_items=max_items),
        "recent_input_folders": _serialize_paths(state.recent_input_folders, max_items=max_items),
        "recent_output_dirs": _serialize_paths(state.recent_output_dirs, max_items=max_items),
        "language": state.language,
        "option_preset": state.option_preset,
    }
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clear_gui_recent_state(path: Path | None = None) -> GuiRecentState:
    """Remove persisted GUI recent-path state if it exists and return empty state."""
    state_path = path or default_gui_state_path()
    try:
        state_path.unlink()
    except FileNotFoundError:
        pass
    return GuiRecentState()


def remember_gui_path(
    state: GuiRecentState,
    kind: RecentPathKind,
    path: Path,
    *,
    max_items: int = DEFAULT_RECENT_LIMIT,
) -> GuiRecentState:
    """Return updated recent state with the given path promoted to the front."""
    if kind == "input_file":
        return GuiRecentState(
            recent_input_files=_promote_path(state.recent_input_files, path, max_items=max_items),
            recent_input_folders=state.recent_input_folders,
            recent_output_dirs=state.recent_output_dirs,
            language=state.language,
            option_preset=state.option_preset,
        )
    if kind == "input_folder":
        return GuiRecentState(
            recent_input_files=state.recent_input_files,
            recent_input_folders=_promote_path(state.recent_input_folders, path, max_items=max_items),
            recent_output_dirs=state.recent_output_dirs,
            language=state.language,
            option_preset=state.option_preset,
        )
    return GuiRecentState(
        recent_input_files=state.recent_input_files,
        recent_input_folders=state.recent_input_folders,
        recent_output_dirs=_promote_path(state.recent_output_dirs, path, max_items=max_items),
        language=state.language,
        option_preset=state.option_preset,
    )


def remember_gui_preferences(
    state: GuiRecentState,
    *,
    language: str | None = None,
    option_preset: str | None = None,
) -> GuiRecentState:
    """Return updated recent state with GUI-only preference values."""
    return GuiRecentState(
        recent_input_files=state.recent_input_files,
        recent_input_folders=state.recent_input_folders,
        recent_output_dirs=state.recent_output_dirs,
        language=normalize_language(language or state.language),
        option_preset=normalize_preset(option_preset or state.option_preset),
    )


class GuiStateStore:
    def __init__(self, path: Path | None = None, *, max_items: int = DEFAULT_RECENT_LIMIT) -> None:
        self.path = path or default_gui_state_path()
        self.max_items = max_items

    def load(self) -> GuiRecentState:
        """Load recent GUI paths from this store."""
        return load_gui_recent_state(self.path)

    def save(self, state: GuiRecentState) -> None:
        """Save recent GUI paths to this store."""
        save_gui_recent_state(state, self.path, max_items=self.max_items)

    def clear(self) -> GuiRecentState:
        """Clear recent GUI paths in this store."""
        return clear_gui_recent_state(self.path)


def first_existing_path(paths: tuple[Path, ...]) -> Path | None:
    """Return the first path that still exists."""
    for path in paths:
        if path.exists():
            return path
    return None


def gui_document_open_target(document: GuiDocumentLike, target: ResultOpenTarget) -> Path | None:
    """Return the filesystem path opened by a GUI result action."""
    if target == "markdown":
        return document.markdown_path
    if target == "report":
        return document.report_path
    if target == "manifest":
        return document.manifest_path
    if target == "assets":
        return document.assets_dir
    return document.output_dir


def gui_batch_progress_snapshot(*, current: int, total: int, input_pdf: Path, status: str) -> GuiProgressSnapshot:
    """Return a clamped progress snapshot for document-level batch progress."""
    safe_total = max(total, 0)
    safe_current = max(current, 0)
    if safe_total:
        safe_current = min(safe_current, safe_total)
        percent = round((safe_current / safe_total) * 100)
    else:
        percent = 0
    return GuiProgressSnapshot(
        current=safe_current,
        total=safe_total,
        percent=percent,
        label=f"Batch {safe_current}/{safe_total} ({percent}%) {input_pdf.name}: {status}",
    )


def _coerce_recent_paths(value: object, *, max_items: int = DEFAULT_RECENT_LIMIT) -> tuple[Path, ...]:
    if not isinstance(value, list):
        return ()
    paths: list[Path] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        path = Path(item)
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
        if len(paths) >= max_items:
            break
    return tuple(paths)


def _promote_path(paths: tuple[Path, ...], path: Path, *, max_items: int) -> tuple[Path, ...]:
    promoted = Path(path)
    seen = {_path_key(promoted)}
    ordered = [promoted]
    for existing in paths:
        key = _path_key(existing)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(existing)
        if len(ordered) >= max_items:
            break
    return tuple(ordered)


def _serialize_paths(paths: tuple[Path, ...], *, max_items: int) -> list[str]:
    return [str(path) for path in _coerce_recent_paths([str(path) for path in paths], max_items=max_items)]


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path))
