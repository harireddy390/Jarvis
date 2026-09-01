"""
Workspace manager and relevance-based context selection.

Holds the single "active workspace" (the project JARVIS is currently working
with), owns its ProjectIndex, and provides token-efficient file selection:
given a task/query, rank files by relevance and return only small excerpts
of the most relevant ones -- never whole projects.

Also provides safe_read (secret/binary/size guarded, redacted) used by every
file-reading tool.
"""

import os
import threading
from pathlib import Path

from workspace.scanner import (
    scan_tree, is_secret_path, classify_file, MAX_FILE_SIZE_BYTES,
)
from workspace.indexer import ProjectIndex
from workspace.secrets import redact_secrets
from workspace import backups

_lock = threading.Lock()

_active = None  # WorkspaceManager instance


class WorkspaceManager:
    """Owns the index and read/write helpers for one project root."""

    def __init__(self, root: str):
        self.root = str(Path(root).resolve())
        self.index = ProjectIndex(self.root)

    # -- safety --------------------------------------------------------------

    def resolve_in_workspace(self, path: str) -> Path | None:
        """
        Resolves a user/LLM-supplied path and returns it only if it lies
        inside the workspace. Returns None otherwise (path escape attempt).
        """
        p = Path(os.path.expanduser(path))
        if not p.is_absolute():
            p = Path(self.root) / p
        try:
            resolved = p.resolve()
            resolved.relative_to(self.root)
        except (ValueError, OSError):
            return None
        return resolved

    def safe_read(self, path: str, max_chars: int = 12000) -> str:
        """
        Reads a file with all guards: must be inside workspace, not a secret,
        not binary, not oversized. Content is secret-redacted and truncated.
        Returns a human-readable string (never raises).
        """
        resolved = self.resolve_in_workspace(path)
        if resolved is None:
            return f"Refused: '{path}' is outside the active workspace."

        if is_secret_path(resolved.name):
            return f"Refused: '{path}' looks like a secrets/credential file."

        info = classify_file(resolved)
        if not resolved.is_file():
            return f"'{path}' doesn't exist in the workspace."
        if info["size"] > MAX_FILE_SIZE_BYTES:
            return (f"Refused: '{path}' is {info['size'] // 1024} KB "
                    f"(over the {MAX_FILE_SIZE_BYTES // 1024} KB read limit).")

        try:
            raw = resolved.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return f"Refused: '{path}' appears to be binary."
        except OSError as e:
            return f"Couldn't read '{path}': {e}"

        text = redact_secrets(raw)
        if len(text) > max_chars:
            note = (f"\n\n[... truncated: showing {max_chars} of "
                    f"{len(text)} characters. Use read_file_excerpt with a "
                    f"search term to target specific parts.]")
            return text[:max_chars] + note
        return text

    # -- relevance selection ---------------------------------------------------

    def select_relevant_files(self, query: str, max_files: int = 6) -> list[dict]:
        """
        Ranks indexed files against a natural-language query and returns the
        top candidates: [{"path", "score", "reason"}].
        Scoring: filename hits, symbol-name hits, text hits, recency of match.
        Cheap (uses the in-memory index; no LLM involved).
        """
        q = query.lower().strip()
        if not q:
            return []
        terms = [t for t in q.replace("?", " ").split() if len(t) > 2][:8]

        scores: dict[str, dict] = {}

        def bump(rel: str, points: float, reason: str):
            entry = scores.setdefault(rel, {"path": rel, "score": 0.0, "reasons": []})
            entry["score"] += points
            if len(entry["reasons"]) < 3:
                entry["reasons"].append(reason)

        for rel in self.index.file_list():
            base = os.path.basename(rel).lower()
            stem = Path(rel).stem.lower()
            for term in terms:
                if term in stem:
                    bump(rel, 5.0, f"filename contains '{term}'")
                elif term in base:
                    bump(rel, 3.0, f"path contains '{term}'")

        for hit in self.index.search_symbols(q, limit=40):
            bump(hit["file"], 4.0, f"symbol '{hit['name']}'")

        for term in terms:
            for hit in self.index.search_text(term, limit=10):
                bump(hit["file"], 1.5, f"contains '{term}' (line {hit['line']})")

        ranked = sorted(scores.values(), key=lambda e: -e["score"])
        results = []
        for entry in ranked[:max_files]:
            results.append({
                "path": entry["path"],
                "score": round(entry["score"], 1),
                "reason": "; ".join(entry["reasons"]),
            })
        return results

    def build_task_context(self, query: str, max_files: int = 4,
                           chars_per_file: int = 3000) -> str:
        """
        Builds a compact context block for the LLM: the most relevant files
        with targeted excerpts. This is what keeps token usage proportional
        to the task, not the project size.
        """
        relevant = self.select_relevant_files(query, max_files=max_files)
        if not relevant:
            return "No obviously relevant files found for this request."

        blocks = []
        for entry in relevant:
            content = self.safe_read(entry["path"], max_chars=chars_per_file)
            blocks.append(
                f"### {entry['path']} (relevance: {entry['reason']})\n"
                f"```\n{content}\n```"
            )
        return "\n\n".join(blocks)

    # -- writes ----------------------------------------------------------------

    def safe_write(self, path: str, content: str, confirmed: bool,
                   conf_id: str | None, request_confirmation) -> str:
        """
        Writes a file with full safeguards:
        - path containment + secret-file refusal
        - hard confirmation gate (human-approved) when overwriting existing files
        - automatic backup before any overwrite
        Returns a human-readable result string (never raises).
        """
        resolved = self.resolve_in_workspace(path)
        if resolved is None:
            return f"Refused: '{path}' is outside the active workspace."
        if is_secret_path(resolved.name):
            return f"Refused: '{path}' looks like a secrets/credential file."

        exists = resolved.is_file()
        summary = f"{'overwrite' if exists else 'create'} file '{path}'"

        if exists:
            # Overwriting an existing file requires HUMAN approval.
            if not confirmed:
                cid = request_confirmation("write_code_file", summary)
                return (f"CONFIRMATION NEEDED (id {cid}): I need your approval "
                        f"to {summary}. Say 'yes' to allow it, or 'no' to cancel.")
            if not conf_id or not _check_approved(conf_id):
                return ("Refused: that operation was never approved by you. "
                        "Ask me to propose it again and confirm with yes/no.")

        # backup before overwrite
        if exists:
            backups.backup_file(self.root, str(resolved), label="pre_write")

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"Couldn't write '{path}': {e}"

        action = "overwrote" if exists else "created"
        msg = f"{action.capitalize()} '{path}' ({len(content)} chars)."
        if exists:
            msg += " Previous version saved to .jarvis_backups."
        return msg


def _check_approved(conf_id: str) -> bool:
    # imported lazily to avoid a circular import at module load
    from core.confirmations import is_approved
    return is_approved(conf_id)


def set_workspace(root: str) -> WorkspaceManager:
    """Activates a workspace (global). Refreshes its index."""
    global _active
    with _lock:
        mgr = WorkspaceManager(root)
        mgr.index.refresh()
        _active = mgr
    return _active


def get_active() -> WorkspaceManager | None:
    """Returns the active workspace manager, or None if none was set."""
    return _active


def get_or_default() -> WorkspaceManager:
    """
    Returns the active workspace; if none was set explicitly, defaults to
    JARVIS's own project directory so code tools work out of the box.
    """
    global _active
    if _active is None:
        with _lock:
            if _active is None:  # double-checked
                default_root = str(Path(__file__).resolve().parent.parent)
                mgr = WorkspaceManager(default_root)
                mgr.index.refresh()
                _active = mgr
    return _active