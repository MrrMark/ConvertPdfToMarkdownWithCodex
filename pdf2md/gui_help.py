from __future__ import annotations

from importlib import resources
from pathlib import Path


GUI_USER_GUIDE_FILENAME = "GUI_USER_GUIDE.md"
GUI_USER_GUIDE_RESOURCE_PACKAGE = "pdf2md.resources"


def source_gui_user_guide_path() -> Path:
    """Return the source-checkout GUI user guide path."""
    return Path(__file__).resolve().parents[1] / "docs" / GUI_USER_GUIDE_FILENAME


def packaged_gui_user_guide_path() -> Path | None:
    """Return the packaged GUI user guide resource path when available."""
    try:
        resource = resources.files(GUI_USER_GUIDE_RESOURCE_PACKAGE).joinpath(GUI_USER_GUIDE_FILENAME)
    except ModuleNotFoundError:
        return None
    if not resource.is_file():
        return None
    return Path(str(resource))


def gui_user_guide_path() -> Path:
    """Return the source help guide path, falling back to the packaged resource."""
    source_path = source_gui_user_guide_path()
    if source_path.exists():
        return source_path
    return packaged_gui_user_guide_path() or source_path
