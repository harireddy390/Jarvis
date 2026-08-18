import os
import subprocess


def read_code_file(path: str) -> str:
    """
    Reads the raw content of a code file (any extension: .py, .js, .html, etc.)
    so you can review, explain, or plan changes to it.
    """
    full_path = os.path.expanduser(path)
    if not os.path.exists(full_path):
        return f"'{path}' doesn't exist."
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return content[:8000]
    except Exception as e:
        return f"Couldn't read that file: {e}"


def write_code_file(path: str, content: str, confirmed: bool) -> str:
    """
    Creates or overwrites a code file with the given content. THIS OVERWRITES
    EXISTING FILES. confirmed must be True -- only set True if the user has
    explicitly confirmed this exact write after you described what would change.
    If not yet confirmed, call with confirmed=False first to get the warning.
    """
    full_path = os.path.expanduser(path)
    file_exists = os.path.exists(full_path)

    if not confirmed:
        action = "overwrite" if file_exists else "create"
        return f"CONFIRMATION NEEDED: Ask the user to confirm you should {action} '{path}'. Do not write yet."

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        if os.path.exists(full_path):
            return f"Wrote '{path}' -- confirmed on disk."
        return f"Wrote '{path}', sir, but I can't confirm it landed on disk. Please check."
    except Exception as e:
        return f"Couldn't write that file: {e}"


def run_python_file(path: str) -> str:
    """
    Runs a Python file and returns its real output, including any errors/traceback.
    Use this to test code or debug why something is failing.
    """
    full_path = os.path.expanduser(path)
    if not os.path.exists(full_path):
        return f"'{path}' doesn't exist."

    try:
        result = subprocess.run(
            ["python", full_path], capture_output=True, text=True, timeout=20
        )
        status = "SUCCESS" if result.returncode == 0 else f"FAILED (exit code {result.returncode})"
        output = result.stdout.strip()
        error = result.stderr.strip()
        combined = f"[{status}]\nOutput: {output or '(none)'}"
        if error:
            combined += f"\nError:\n{error[:1500]}"
        return combined
    except subprocess.TimeoutExpired:
        return "[FAILED] The script took too long and was stopped."
    except Exception as e:
        return f"[FAILED] Couldn't run that: {e}"