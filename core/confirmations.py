"""
Hard confirmation gate for destructive operations.

Problem this solves: previously, destructive tools (delete_file_or_folder,
write_code_file) trusted the LLM to follow a two-step confirmation protocol
described in prompts/docstrings. A confused or prompt-injected model could
pass confirmed=True in a single call and destroy data.

How it works now:
1. A tool called with confirmed=False returns a warning and registers a
   PENDING confirmation with a unique id.
2. A HUMAN approves it (voice "yes" / "no" through main.py, or later a HUD
   button). Only human action moves a pending item to APPROVED.
3. The tool called again with confirmed=True only executes if the pending
   record exists AND is approved. Otherwise it is refused.

The LLM can create pending requests and see their status, but can never
approve them itself. One pending confirmation at a time keeps voice
resolution unambiguous.
"""

import threading
import time
import uuid

_lock = threading.Lock()

# id -> {"summary": str, "tool": str, "status": "pending"|"approved"|"denied",
#        "created": float, "resolved": float|None}
_pending = {}
_current_id = None  # the single active pending confirmation


def request_confirmation(tool: str, summary: str) -> str:
    """
    Registers a pending confirmation and returns its id.
    Called by tools when they run with confirmed=False.
    """
    global _current_id
    with _lock:
        conf_id = f"C-{uuid.uuid4().hex[:8]}"
        _pending[conf_id] = {
            "summary": summary,
            "tool": tool,
            "status": "pending",
            "created": time.time(),
            "resolved": None,
        }
        _current_id = conf_id
    return conf_id


def approve(conf_id: str) -> bool:
    """Human approval. Returns True if a pending confirmation was approved."""
    global _current_id
    with _lock:
        rec = _pending.get(conf_id)
        if rec and rec["status"] == "pending":
            rec["status"] = "approved"
            rec["resolved"] = time.time()
            return True
    return False


def deny(conf_id: str) -> bool:
    """Human denial. Returns True if a pending confirmation was denied."""
    global _current_id
    with _lock:
        rec = _pending.get(conf_id)
        if rec and rec["status"] == "pending":
            rec["status"] = "denied"
            rec["resolved"] = time.time()
            if _current_id == conf_id:
                _current_id = None
            return True
    return False


def is_approved(conf_id: str) -> bool:
    """Tool-side check before executing a destructive operation."""
    with _lock:
        rec = _pending.get(conf_id)
        return bool(rec and rec["status"] == "approved")


def get_current() -> dict | None:
    """Returns the active pending confirmation (for voice/UI resolution)."""
    with _lock:
        if _current_id and _current_id in _pending:
            rec = _pending[_current_id]
            if rec["status"] == "pending":
                return {"id": _current_id, **rec}
    return None


def resolve_by_voice(answer_yes: bool) -> str:
    """
    Resolves the current pending confirmation from a spoken yes/no.
    Returns a human-readable result string.
    """
    with _lock:
        current = None
        if _current_id and _current_id in _pending:
            rec = _pending[_current_id]
            if rec["status"] == "pending":
                current = {"id": _current_id, **rec}
    if not current:
        return "There's nothing awaiting my confirmation right now, sir."

    if answer_yes:
        approve(current["id"])
        return f"Confirmed. You may proceed with: {current['summary']}"
    deny(current["id"])
    return "Understood, I've cancelled that operation."