"""
Code & project tools for JARVIS.

Extends the original three functions (read_code_file, write_code_file,
run_python_file) with a full project-understanding toolset backed by the
workspace package: structure discovery, symbol search, relevance-based
reading, and safe writes with automatic backups.

All functions are LLM-callable (registered in core/brain.py) and follow the
existing tool convention: plain functions, precise docstrings (which serve as
the tool spec for Gemini), human-readable string results, never raising.
"""

import os
import subprocess
from pathlib import Path

from workspace.context import get_or_default, set_workspace, get_active
from workspace.backups import list_backups, restore_backup
from workspace.secrets import redact_secrets
from core import confirmations


# ---------------------------------------------------------------------------
# Workspace activation & overview
# ---------------------------------------------------------------------------

def set_workspace(path: str) -> str:
    """
    Sets the project folder JARVIS should work with (the "workspace") and
    builds its code index. Use this when the user asks to work on, inspect,
    or modify a project and no workspace is active yet. path can be absolute
    or relative to JARVIS's own directory.
    """
    root = Path(os.path.expanduser(path))
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / root
    if not root.is_dir():
        return f"'{path}' isn't a folder I can find."
    mgr = set_workspace(str(root))
    stats = mgr.index.project_summary()
    langs = ", ".join(f"{k}: {v}" for k, v in stats["languages"].items())
    return (f"Workspace set to '{mgr.root}'. Indexed {stats['files']} files "
            f"({stats['symbols']} symbols). Languages: {langs}. "
            f"Project tools are now active.")


def get_project_summary() -> str:
    """
    Returns a compact overview of the active workspace: root, file count,
    languages, top-level structure, and internal module relationships.
    Call this first when asked about a project's architecture.
    """
    mgr = get_or_default()
    stats = mgr.index.project_summary()
    langs = ", ".join(f"{k}: {v}" for k, v in stats["languages"].items())

    top_dirs = sorted({rel.split("/")[0] for rel in mgr.index.file_list()
                       if "/" in rel})[:15]

    edges = mgr.index.import_graph(limit_files=30)
    edge_lines = [f"  {e['from']} -> {e['to']}" for e in edges[:20]]

    lines = [
        f"Workspace: {mgr.root}",
        f"Files indexed: {stats['files']} | Symbols: {stats['symbols']}",
        f"Languages: {langs}",
    ]
    if top_dirs:
        lines.append("Top-level dirs: " + ", ".join(top_dirs))
    if edge_lines:
        lines.append("Internal imports (sample):")
        lines.extend(edge_lines)
    return "\n".join(lines)


def list_project_tree(subpath: str = "", max_entries: int = 120) -> str:
    """
    Lists the project's file structure (relative paths), skipping caches,
    builds, virtual environments and secret files. Optionally limited to a
    subfolder via subpath (e.g. 'core' or 'tools').
    """
    mgr = get_or_default()
    files = mgr.index.file_list()
    if subpath:
        prefix = subpath.strip("/").lower()
        files = [f for f in files if f.lower().startswith(prefix)]
    if not files:
        return f"No files found under '{subpath}'."
    shown = files[:max(1, min(int(max_entries), 400))]
    out = "\n".join(shown)
    if len(files) > len(shown):
        out += f"\n... and {len(files) - len(shown)} more files."
    return f"Project structure ({len(files)} files):\n{out}"


# ---------------------------------------------------------------------------
# Search & reading
# ---------------------------------------------------------------------------

def search_in_files(query: str, file_pattern: str = "") -> str:
    """
    Searches file contents across the workspace for a literal text query
    (not regex). Returns matching file, line number and excerpt for each hit.
    Optionally filter files with a glob pattern like '*.py' or 'core/*'.
    """
    mgr = get_or_default()
    import fnmatch
    hits = mgr.index.search_text(query, limit=30)
    if file_pattern:
        hits = [h for h in hits
                if fnmatch.fnmatch(h["file"].lower(), file_pattern.lower())]
    if not hits:
        return f"No matches for '{query}' in the workspace."
    lines = [f"{h['file']}:{h['line']}: {redact_secrets(h['excerpt'])}"
             for h in hits]
    return f"Found {len(hits)} matches for '{query}':\n" + "\n".join(lines)


def find_symbol(symbol_name: str) -> str:
    """
    Finds where a class, function, or route is defined in the workspace
    (e.g. 'think', 'JarvisHUD', 'voice_loop'). Returns file, line, kind and
    signature info for each match.
    """
    mgr = get_or_default()
    hits = mgr.index.search_symbols(symbol_name, limit=25)
    if not hits:
        return f"No symbol matching '{symbol_name}' found in the workspace."
    lines = []
    for h in hits:
        sig = ""
        if h.get("args"):
            sig = f"({', '.join(h['args'])})"
        if h.get("bases"):
            sig = f"({', '.join(h['bases'])})"
        lines.append(f"{h['file']}:{h['line']}  {h['kind']} {h['name']}{sig}")
    return "Found:\n" + "\n".join(lines)


def read_file_excerpt(path: str, start_line: int = 0, num_lines: int = 120) -> str:
    """
    Reads a specific line range of a workspace file (with line numbers),
    with secrets redacted. Use after search_in_files/find_symbol to read the
    exact code around a hit. start_line is 0-based; num_lines max 400.
    """
    mgr = get_or_default()
    resolved = mgr.resolve_in_workspace(path)
    if resolved is None:
        return f"Refused: '{path}' is outside the active workspace."
    text = mgr.safe_read(path, max_chars=400000)
    if text.startswith("Refused") or text.startswith("Couldn't"):
        return text
    lines = text.splitlines()
    start = max(0, int(start_line))
    count = max(1, min(int(num_lines), 400))
    chunk = lines[start:start + count]
    if not chunk:
        return f"'{path}' has {len(lines)} lines; range {start + 1}+" \
               f"{start + count} is past the end."
    body = "\n".join(f"{start + i + 1}: {l}" for i, l in enumerate(chunk))
    header = f"'{path}' lines {start + 1}-{start + len(chunk)} of {len(lines)}:"
    return f"{header}\n{body}"


def read_relevant_files(query: str, max_files: int = 4) -> str:
    """
    THE main context tool: given a task or question in natural language
    (e.g. 'wake word detection', 'login bug', 'reminder scheduling'), finds
    the most relevant project files and returns compact excerpts of each.
    Use this FIRST for any code question -- it keeps context small instead
    of loading whole files or the whole project.
    """
    mgr = get_or_default()
    context = mgr.build_task_context(query, max_files=max(1, min(int(max_files), 8)),
                                     chars_per_file=3000)
    return context


def read_code_file(path: str) -> str:
    """
    Reads the full content of a workspace file (redacted, size-capped).
    Prefer read_relevant_files or read_file_excerpt for large files.
    """
    mgr = get_or_default()
    return mgr.safe_read(path, max_chars=12000)


# ---------------------------------------------------------------------------
# Safe writing
# ---------------------------------------------------------------------------

def write_code_file(path: str, content: str, confirmed: bool = False,
                    conf_id: str = "") -> str:
    """
    Creates a new file or overwrites an existing one inside the workspace.

    SAFETY PROTOCOL:
    - Overwriting an EXISTING file always requires explicit human approval:
      call with confirmed=False first; you'll receive a confirmation id.
      Tell the user exactly what will change, then after they clearly say
      yes, call again with confirmed=True and the same conf_id.
    - Creating a NEW file does not need confirmation.
    - The previous version of any overwritten file is backed up automatically
      (recoverable via restore_backup).
    - Secrets files (.env, keys, credentials) are refused.
    """
    mgr = get_or_default()

    def _request(tool: str, summary: str) -> str:
        return confirmations.request_confirmation(tool, summary)

    return mgr.safe_write(path, content, confirmed=confirmed,
                          conf_id=conf_id or None, request_confirmation=_request)


def list_backups_tool() -> str:
    """
    Lists recent automatic backups in the workspace (newest first).
    Each entry can be used with restore_backup to undo changes.
    """
    mgr = get_or_default()
    entries = list_backups(mgr.root)
    if not entries:
        return "No backups yet (backups are created automatically before overwrites)."
    lines = [f"{e['folder']}  ({e['files']} files)" for e in entries]
    return "Recent backups:\n" + "\n".join(lines)


def restore_backup_tool(backup_folder: str, target: str = "") -> str:
    """
    Restores file(s) from a backup folder (undoing a previous write).
    backup_folder is a name from list_backups. Optionally restore only one
    file by passing its relative path as target.
    """
    mgr = get_or_default()
    return restore_backup(mgr.root, backup_folder, target or None)


# ---------------------------------------------------------------------------
# Execution (kept from the original module; hardened in a later phase)
# ---------------------------------------------------------------------------

def run_python_file(path: str) -> str:
    """
    Runs a Python file and returns its real output, including any
    errors/traceback. Only use when the user explicitly asks to run code.
    """
    mgr = get_or_default()
    resolved = mgr.resolve_in_workspace(path)
    if resolved is None:
        return f"Refused: '{path}' is outside the active workspace."
    if not resolved.is_file():
        return f"'{path}' doesn't exist."

    try:
        result = subprocess.run(
            ["python", str(resolved)], capture_output=True, text=True, timeout=20
        )
        status = "SUCCESS" if result.returncode == 0 else \
            f"FAILED (exit code {result.returncode})"
        output = result.stdout.strip()
        error = result.stderr.strip()
        combined = f"[{status}]\nOutput: {output or '(none)'}"
        if error:
            combined += f"\nError:\n{redact_secrets(error[:1500])}"
        return combined
    except subprocess.TimeoutExpired:
        return "[FAILED] The script took too long and was stopped."
    except Exception as e:
        return f"[FAILED] Couldn't run that: {e}"