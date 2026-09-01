import os
import subprocess

from core import confirmations
from workspace.context import get_or_default
from workspace.backups import backup_file


def open_file_or_folder(path: str) -> str:
    """
    Opens a file or folder in its default application (e.g. opens a folder in
    File Explorer, opens a document in Word, opens an image in the default viewer).
    path can be a full path or a relative one from the user's home directory.
    """
    full_path = os.path.expanduser(path)
    if not os.path.exists(full_path):
        return f"I couldn't find '{path}'."
    os.startfile(full_path)
    return f"Opened '{path}'."


def list_folder(path: str) -> str:
    """
    Lists the files and folders inside the given directory.
    """
    full_path = os.path.expanduser(path)
    if not os.path.isdir(full_path):
        return f"'{path}' isn't a folder I can find."

    items = os.listdir(full_path)
    if not items:
        return f"'{path}' is empty."

    return f"Contents of '{path}':\n" + "\n".join(items[:30])


def create_folder(path: str) -> str:
    """
    Creates a new folder at the given path.
    """
    full_path = os.path.expanduser(path)
    try:
        os.makedirs(full_path, exist_ok=True)
        return f"Created folder '{path}'."
    except Exception as e:
        return f"Couldn't create that folder: {e}"


def delete_file_or_folder(path: str, confirmed: bool = False, conf_id: str = "") -> str:
    """
    Deletes a file or folder from the workspace. DELETION IS RECOVERABLE:
    the item is moved into .jarvis_backups (restore with restore_backup_tool).

    SAFETY PROTOCOL (hard-enforced, not just polite):
    - Call with confirmed=False first: you'll receive a confirmation id.
      Tell the user exactly what will be deleted, then only after they
      clearly say yes, call again with confirmed=True and the same conf_id.
    - If the user says no, do NOT retry.
    - System locations (Windows, Program Files) are always refused.
    """
    mgr = get_or_default()
    resolved = mgr.resolve_in_workspace(path)
    if resolved is None:
        return f"Refused: '{path}' is outside the active workspace."
    if not resolved.exists():
        return f"'{path}' doesn't exist in the workspace."

    lowered = str(resolved).lower()
    if lowered.startswith(("c:\\windows", "c:\\program files", "c:\\programdata")):
        return f"I won't delete '{path}' -- system locations are off-limits."

    kind = "folder" if resolved.is_dir() else "file"
    summary = f"delete {kind} '{path}'"

    if not confirmed:
        cid = confirmations.request_confirmation("delete_file_or_folder", summary)
        return (f"CONFIRMATION NEEDED (id {cid}): I need your approval to "
                f"{summary}. Say 'yes' to allow it, or 'no' to cancel.")

    if not conf_id or not confirmations.is_approved(conf_id):
        cid = confirmations.request_confirmation("delete_file_or_folder", summary)
        return (f"Refused: that deletion was never approved by you. "
                f"(New request id {cid}.) Ask the user to confirm with yes/no.")

    # Soft delete: move into the backup area so it stays recoverable.
    backup_dest = backup_file(mgr.root, str(resolved), label="pre_delete")
    if backup_dest:
        try:
            import shutil
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        except OSError as e:
            return f"Couldn't delete '{path}': {e}"
        return (f"Deleted '{path}' (previous copy saved in .jarvis_backups -- "
                f"recoverable with restore_backup_tool).")
    else:
        return f"Couldn't back up '{path}' first, so I stopped -- safer to abort."
