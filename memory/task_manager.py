import json
import os
from datetime import datetime

TASKS_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")


def _load() -> list:
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r") as f:
        return json.load(f)


def _save(tasks: list):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def create_task(request: str, steps: list) -> dict:
    tasks = _load()
    task = {
        "id": f"JARVIS-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "request": request,
        "steps": [{"description": s, "status": "pending", "result": None} for s in steps],
        "status": "in_progress",
        "created": datetime.now().isoformat()
    }
    tasks.append(task)
    _save(tasks)
    return task


def update_task(task_id: str, task: dict):
    tasks = _load()
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            tasks[i] = task
            break
    _save(tasks)


def get_latest_incomplete_task():
    tasks = _load()
    incomplete = [t for t in tasks if t["status"] == "in_progress"]
    return incomplete[-1] if incomplete else None