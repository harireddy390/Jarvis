"""
Backup system: every file modification or deletion performed by JARVIS
creates a timestamped backup first, enabling restore.

Backups live in <workspace>/.jarvis_backups/<timestamp>_<label>/<relative path>
and are excluded from scanning (see scanner.IGNORED_DIRS).
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

BACKUP_DIR_NAME = ".jarvis_backups"


def _backup_root(workspace: str) -> Path:
    return Path(workspace) / BACKUP_DIR_NAME


def backup_file(workspace: str, file_path: str, label: str = "edit") -> str | None:
    """
    Copies a single file into a new timestamped backup folder.
    Returns the backup copy's path, or None if the source doesn't exist.
    """
    src = Path(file_path)
    if not src.is_file():
        return None
    ws = Path(workspace).resolve()
    try:
        rel = src.resolve().relative_to(ws)
    except ValueError:
        rel = Path(src.name)  # outside workspace: keep name only

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest_dir = _backup_root(workspace) / f"{stamp}_{label}"
    dest = dest_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return str(dest)


def list_backups(workspace: str, limit: int = 20) -> list[dict]:
    """
    Returns recent backup folders: [{"folder": name, "time": iso, "files": n}]
    newest first.
    """
    root = _backup_root(workspace)
    if not root.is_dir():
        return []
    out = []
    for entry in sorted(root.iterdir(), reverse=True)[:limit]:
        if not entry.is_dir():
            continue
        n_files = sum(1 for _ in entry.rglob("*") if _.is_file())
        out.append({"folder": entry.name, "files": n_files})
    return out


def restore_backup(workspace: str, backup_folder: str, target: str | None = None) -> str:
    """
    Restores files from a backup folder (by folder name) back into the
    workspace. If target is given, only that relative path is restored;
    otherwise every file in the backup is restored.
    """
    root = _backup_root(workspace) / backup_folder
    if not root.is_dir():
        return f"No backup folder named '{backup_folder}'."

    ws = Path(workspace).resolve()
    candidates = [Path(target)] if target else [
        p for p in root.rglob("*") if p.is_file()
    ]
    restored = []
    for src in candidates:
        rel_src = src if src.is_absolute() else root / src
        if not rel_src.is_file():
            continue
        rel = rel_src.relative_to(root)
        dest = ws / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rel_src, dest)
        restored.append(rel.as_posix())

    if not restored:
        return "Nothing was restored (no matching files in that backup)."
    return "Restored: " + ", ".join(restored[:10]) + ("..." if len(restored) > 10 else "")