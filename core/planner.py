import os
from dotenv import load_dotenv
from google import genai
from memory.task_manager import create_task, update_task, get_latest_incomplete_task
from core.brain import think

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def needs_planning(user_input: str) -> bool:
    """
    Heuristic: does this request look like it needs multiple sequential steps?
    """
    lowered = user_input.lower()
    multi_step_signals = [" and then ", " then ", " after that "]
    and_count = lowered.count(" and ")
    return any(signal in lowered for signal in multi_step_signals) or and_count >= 2


def create_plan(user_input: str) -> list:
    """
    Asks Gemini to break a complex request into a short ordered list of concrete steps.
    """
    prompt = (
        "Break the following request into a short numbered list of concrete, sequential "
        "steps that an AI assistant with tools (file operations, web search, browser control, "
        "etc.) could execute one at a time. Keep it to the minimum steps needed -- 2 to 6 steps. "
        "Reply with ONLY the numbered list, one step per line, no extra text.\n\n"
        f"Request: {user_input}"
    )
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )
    lines = [line.strip() for line in response.text.strip().split("\n") if line.strip()]
    steps = []
    for line in lines:
        cleaned = line.lstrip("0123456789.-) ").strip()
        if cleaned:
            steps.append(cleaned)
    return steps


def execute_plan(user_input: str) -> str:
    """
    Creates a plan, executes each step using the existing tool-enabled think(), verifies
    each step, saves progress after every step, and returns a final summary.
    """
    steps = create_plan(user_input)
    if not steps:
        return "I couldn't break that request into clear steps -- could you rephrase it?"

    task = create_task(user_input, steps)

    for i, step in enumerate(task["steps"]):
        step_conversation = [{
            "role": "user",
            "parts": [{"text": f"(Part of a larger task: '{user_input}') Now do this specific step: {step['description']}"}]
        }]
        result = think(step_conversation)

        step["result"] = result
        step["status"] = "done"
        update_task(task["id"], task)

    task["status"] = "completed"
    update_task(task["id"], task)

    summary_lines = [f"Step {i+1}: {s['description']} -> {s['result']}" for i, s in enumerate(task["steps"])]
    return "Task complete, sir. Here's what happened:\n" + "\n".join(summary_lines)


def continue_last_task() -> str:
    """
    Resumes the most recent incomplete task from where it left off.
    """
    task = get_latest_incomplete_task()
    if not task:
        return "There's no incomplete task to continue, sir."

    for i, step in enumerate(task["steps"]):
        if step["status"] == "done":
            continue

        step_conversation = [{
            "role": "user",
            "parts": [{"text": f"(Continuing a task: '{task['request']}') Now do this specific step: {step['description']}"}]
        }]
        result = think(step_conversation)
        step["result"] = result
        step["status"] = "done"
        update_task(task["id"], task)

    task["status"] = "completed"
    update_task(task["id"], task)
    return "Resumed and completed the task, sir."