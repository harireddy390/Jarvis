import json
import os

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "personal_memory.json")


def load_memory() -> list:
    """
    Loads all remembered facts from disk.
    """
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def remember(fact: str) -> str:
    """
    Saves a new fact about the user permanently, so JARVIS remembers it
    even after restarting. Use this whenever the user shares something
    worth remembering long-term, like their name, preferences, or projects.
    """
    facts = load_memory()
    facts.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2)
    return f"Got it, I'll remember that: {fact}"