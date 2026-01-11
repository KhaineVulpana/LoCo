"""
Workspace path resolution helpers.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import os

from app.core.config import settings


def paths_equal(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _expand_path(value: str) -> Path:
    expanded = os.path.expandvars(value)
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve(strict=False)
    return path


def _split_search_roots(value: str) -> List[str]:
    if not value:
        return []
    cleaned = value.replace(";", ",")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def _get_search_roots() -> List[Path]:
    roots: List[Path] = []
    for root_str in _split_search_roots(settings.WORKSPACE_SEARCH_ROOTS):
        root = _expand_path(root_str)
        if root.is_dir():
            roots.append(root)
    return roots


def _swap_home(path: Path) -> Optional[Path]:
    home = Path.home()
    if not path.is_absolute():
        return None
    path_parts = path.parts
    home_parts = home.parts
    if len(path_parts) < 3 or len(home_parts) < 3:
        return None
    if path_parts[1] not in ("Users", "home") or home_parts[1] != path_parts[1]:
        return None
    if path_parts[0] != home_parts[0]:
        return None
    if path_parts[2] == home_parts[2]:
        return None
    return Path(*home_parts[:3], *path_parts[3:])


def _find_cwd_parent(names: List[str]) -> Optional[Path]:
    if not names:
        return None
    cwd = Path.cwd().resolve(strict=False)
    for parent in [cwd, *cwd.parents]:
        if parent.name in names and parent.is_dir():
            return parent
    return None


def resolve_workspace_path(stored_path: str, workspace_name: Optional[str] = None) -> Tuple[str, str]:
    expanded = _expand_path(stored_path)
    if expanded.is_dir():
        source = "stored" if paths_equal(stored_path, str(expanded)) else "expanded"
        return str(expanded), source

    swapped = _swap_home(expanded)
    if swapped and swapped.is_dir():
        return str(swapped), "home_swap"

    names: List[str] = []
    if workspace_name:
        names.append(workspace_name)
    if expanded.name and expanded.name not in names:
        names.append(expanded.name)

    cwd_match = _find_cwd_parent(names)
    if cwd_match:
        return str(cwd_match), "cwd_parent"

    roots = _get_search_roots()
    if roots and names:
        suffixes: List[Path] = []
        seen = set()
        for name in names:
            if name and name not in seen:
                seen.add(name)
                suffixes.append(Path(name))
        if len(expanded.parts) >= 2:
            tail = Path(*expanded.parts[-2:])
            tail_str = str(tail)
            if tail_str not in seen:
                seen.add(tail_str)
                suffixes.append(tail)

        for root in roots:
            for suffix in suffixes:
                candidate = root / suffix
                if candidate.is_dir():
                    return str(candidate), "search_root"

    return str(expanded), "missing"
