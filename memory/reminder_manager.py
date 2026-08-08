import json
import os
from datetime import datetime, timedelta
from dateutil import parser as dateparser

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")


def _load() -> list:
    with open(REMINDERS_FILE, "r") as f:
        return json.load(f)


def _save(reminders: list):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def set_reminder(text: str, time_str: str) -> str:
    """
    Sets a reminder for the given time. text is what to remind the user about.
    time_str is a natural time like "5:00 PM", "17:30", or "in 10 minutes" --
    parse the user's request into a clear time string before calling this.
    If the time has already passed today, it will be scheduled for tomorrow.
    """
    now = datetime.now()
    try:
        when = dateparser.parse(time_str, fuzzy=True, default=now)
    except (ValueError, dateparser.ParserError):
        return f"I couldn't understand the time '{time_str}'. Try something like '5 PM' or '17:30'."

    if when < now:
        when += timedelta(days=1)

    reminders = _load()
    reminders.append({
        "text": text,
        "time": when.isoformat(),
        "done": False
    })
    _save(reminders)

    return f"Reminder set: '{text}' at {when.strftime('%I:%M %p')}."


def get_due_reminders() -> list:
    """
    Internal use: returns reminders whose time has passed and haven't been announced yet.
    """
    now = datetime.now()
    reminders = _load()
    due = [r for r in reminders if not r["done"] and dateparser.parse(r["time"]) <= now]

    if due:
        for r in reminders:
            if r in due:
                r["done"] = True
        _save(reminders)

    return due