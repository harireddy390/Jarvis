import subprocess
import time
import psutil


def open_application(app_name: str) -> str:
    """
    Opens a desktop application by name and verifies a matching process actually
    started before confirming success.
    """
    processes_before = {p.name().lower() for p in psutil.process_iter(['name'])}

    try:
        subprocess.Popen(app_name, shell=True)
    except Exception as e:
        return f"Couldn't open {app_name}: {e}"

    time.sleep(1.5)
    processes_after = {p.name().lower() for p in psutil.process_iter(['name'])}
    new_processes = processes_after - processes_before

    if new_processes:
        return f"Opened {app_name} (confirmed: new process {list(new_processes)[0]} started)."
    else:
        return f"I ran the command to open {app_name}, sir, but I don't see a new process -- it may not have actually launched. Please check."


def run_terminal_command(command: str) -> str:
    """
    Runs a command-line command and returns its output along with whether it
    actually succeeded (exit code 0) or failed.
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip() or result.stderr.strip()
        status = "SUCCESS" if result.returncode == 0 else f"FAILED (exit code {result.returncode})"
        return f"[{status}] {output[:900] if output else 'No output.'}"
    except subprocess.TimeoutExpired:
        return "[FAILED] That command took too long and was stopped."
    except Exception as e:
        return f"[FAILED] Couldn't run that command: {e}"