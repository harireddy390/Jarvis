import os
import shutil


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


def delete_file_or_folder(path: str, confirmed: bool) -> str:
    """
    Deletes a file or folder. THIS IS DESTRUCTIVE AND CANNOT BE UNDONE.
    confirmed must be True -- only set it True if the user has ALREADY explicitly
    confirmed "yes" to a direct question you asked them about deleting this exact
    item. If you have not yet asked for confirmation, call this with confirmed=False
    first to get the exact warning message, then ask the user, then only call again
    with confirmed=True if they say yes.
    """
    full_path = os.path.expanduser(path)

    if not os.path.exists(full_path):
        return f"'{path}' doesn't exist."

    if not confirmed:
        kind = "folder" if os.path.isdir(full_path) else "file"
        return f"CONFIRMATION NEEDED: Ask the user to confirm deleting the {kind} '{path}'. Do not delete yet."

    try:
        if os.path.isdir(full_path):
            os.rmdir(full_path)
        else:
            os.remove(full_path)
        return f"Deleted '{path}'."
    except OSError as e:
        return f"Couldn't delete that: {e} (folder might not be empty)."


def move_file(source: str, destination: str) -> str:
    """
    Moves or renames a file/folder from source to destination, verifying the
    destination actually exists afterward before confirming success.
    """
    src = os.path.expanduser(source)
    dst = os.path.expanduser(destination)
    if not os.path.exists(src):
        return f"'{source}' doesn't exist."
    try:
        shutil.move(src, dst)
        if os.path.exists(dst):
            return f"Moved '{source}' to '{destination}' -- confirmed."
        return f"Ran the move, sir, but I don't see it at the destination -- please check manually."
    except Exception as e:
        return f"Couldn't move that: {e}"


def copy_file(source: str, destination: str) -> str:
    """
    Copies a file/folder from source to destination, verifying the destination
    actually exists afterward before confirming success.
    """
    src = os.path.expanduser(source)
    dst = os.path.expanduser(destination)
    if not os.path.exists(src):
        return f"'{source}' doesn't exist."
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        if os.path.exists(dst):
            return f"Copied '{source}' to '{destination}' -- confirmed."
        return f"Ran the copy, sir, but I don't see it at the destination -- please check manually."
    except Exception as e:
        return f"Couldn't copy that: {e}"