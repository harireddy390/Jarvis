"""
High-speed context-aware code completion and explanation engine for JARVIS.

Inspects the user's active browser tab or desktop editor, provides verbal logic/guidance
when asked for help, and writes clean solution code directly into the active editor
when instructed to write or complete the code.

Seamlessly supports both:
1. Live Playwright CDP session (if Chrome is running on port 9222).
2. Live active desktop Chrome window via instant screen vision + atomic clipboard paste
   (no remote debugging flags required).
"""

import re
import time
import io
import pyautogui
import pyperclip
from core.gemini_client import get_client, get_model_name
from core.context_detector import get_current_working_context
from tools.browser_control import browser_write_code_in_editor, browser_extract_problem_text
from core.logger import logger

# Cache last extracted context to speed up multi-turn "help with code" -> "write the code"
_cached_context = {
    "title": "",
    "url": "",
    "body_text": "",
    "timestamp": 0.0,
}


def _strip_markdown_code_fences(text: str) -> str:
    """Removes ```lang and ``` fences if the model included them."""
    cleaned = text.strip()
    match = re.match(r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$", cleaned)
    if match:
        return match.group(1).strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        lines = cleaned.split("\n")
        if lines and lines[0].strip().isalnum():
            cleaned = "\n".join(lines[1:]).strip()
    return cleaned


def _capture_screen_jpeg() -> bytes | None:
    """Captures a quick compressed JPEG screenshot for multimodal vision inspection."""
    try:
        screen = pyautogui.screenshot()
        buf = io.BytesIO()
        screen.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Failed to capture screen: {e}")
        return None


def _get_or_refresh_context(force_refresh: bool = False) -> dict:
    """
    Returns existing cached context if fresh (under 120 seconds),
    otherwise queries context detector for active tab or window.
    """
    global _cached_context
    now = time.time()

    if not force_refresh and (now - _cached_context.get("timestamp", 0) < 120) and _cached_context.get("body_text"):
        return _cached_context

    ctx = get_current_working_context()
    browser_info = ctx.get("browser", {})
    fg_info = ctx.get("foreground", {})

    title = browser_info.get("title") or fg_info.get("title", "")
    url = browser_info.get("url", "")
    body_text = browser_info.get("body_text", "")

    if not body_text and browser_info.get("connected"):
        body_text = browser_extract_problem_text()

    _cached_context = {
        "title": title,
        "url": url,
        "body_text": body_text,
        "is_browser": browser_info.get("connected", False) or fg_info.get("is_browser", False),
        "is_ide": fg_info.get("is_ide", False),
        "has_editor": browser_info.get("has_editor", False),
        "timestamp": now,
    }
    return _cached_context


def explain_code_in_active_context(user_instruction: str = "help me with this code") -> str:
    """
    Stage 1: Analyzes the active tab/editor problem and gives a concise, conversational
    verbal explanation of the logic, algorithmic strategy, and time complexity.
    """
    logger.info(f"Code explanation requested: {user_instruction}")
    ctx = _get_or_refresh_context(force_refresh=True)

    title = ctx.get("title", "")
    url = ctx.get("url", "")
    body_text = ctx.get("body_text", "")

    client = get_client()
    model = get_model_name()

    prompt = (
        "You are JARVIS, Tony Stark's personal AI assistant speaking out loud to the user.\n"
        f"The user is viewing a problem or coding page in their active workspace:\n"
        f"- Tab / Window Title: {title}\n"
        f"- URL: {url}\n\n"
        f"User request: '{user_instruction}'\n\n"
    )

    if body_text:
        prompt += f"Here is the problem description / page content:\n'''\n{body_text[:4000]}\n'''\n\n"
    else:
        prompt += "The problem or code is visible in the attached screenshot of the user's active window.\n\n"

    prompt += (
        "INSTRUCTIONS FOR YOUR SPOKEN RESPONSE:\n"
        "1. Give a crisp, concise, high-level explanation in 3 to 4 spoken sentences maximum.\n"
        "2. State what the core challenge requires.\n"
        "3. Explain the optimal algorithm, data structure, or formula (e.g. hash map for O(n), two pointers, BFS/DFS).\n"
        "4. Mention the time and space complexity.\n"
        "5. Conclude with: 'Would you like me to write the code into your editor, sir?'\n"
        "6. Do NOT recite raw code blocks -- this is for spoken audio."
    )

    contents_payload = []
    # If DOM text was not extractable via CDP, pass live screenshot so Gemini can see the problem directly
    if not body_text:
        screen_bytes = _capture_screen_jpeg()
        if screen_bytes:
            contents_payload.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": screen_bytes
                }
            })
    contents_payload.append(prompt)

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents_payload
        )
        return response.text or "I've analyzed the problem. An optimal approach is ready -- would you like me to write the code into your editor, sir?"
    except Exception as e:
        logger.error(f"Error generating code explanation: {e}")
        return f"I had trouble analyzing the problem logic: {e}"


def complete_in_active_context(user_instruction: str = "write the code and complete this") -> str:
    """
    Stage 2: Generates clean, production-ready code for the active problem
    and automatically writes/pastes it directly into the open editor on the tab or desktop.
    """
    logger.info(f"Code write/completion requested: {user_instruction}")
    ctx = _get_or_refresh_context(force_refresh=False)

    title = ctx.get("title", "")
    url = ctx.get("url", "")
    body_text = ctx.get("body_text", "")

    # Fallback to desktop clipboard if no text
    clipboard_content = ""
    if not body_text:
        try:
            clipboard_content = pyperclip.paste()
        except Exception:
            pass

    client = get_client()
    model = get_model_name()

    prompt = (
        "You are JARVIS's ultra-fast autonomous code generator.\n"
        f"The user is working in their active workspace:\n"
        f"- Title: {title}\n"
        f"- URL: {url}\n\n"
        f"User command: '{user_instruction}'\n\n"
    )

    if body_text or clipboard_content:
        prompt += f"Context / problem description / code stubs:\n'''\n{(body_text or clipboard_content)[:5000]}\n'''\n\n"
    else:
        prompt += "The problem or code stub is visible in the attached screenshot of the user's active window.\n\n"

    prompt += (
        "INSTRUCTIONS:\n"
        "1. Write the complete, optimal, and correct code that solves this task or completes the editor.\n"
        "2. Output ONLY the raw executable code ready to be pasted directly into the code editor.\n"
        "3. Do NOT include markdown code fences (no ```python or ```), no conversational comments, no greetings.\n"
        "4. Match the language requested or implied by the problem/signature (default to Python if unspecified).\n"
        "5. Ensure proper indentation and syntax."
    )

    contents_payload = []
    # If no DOM text, pass live screenshot so Gemini can see the problem statement and editor on screen
    if not body_text and not (clipboard_content and len(clipboard_content.strip()) > 30):
        screen_bytes = _capture_screen_jpeg()
        if screen_bytes:
            contents_payload.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": screen_bytes
                }
            })
    contents_payload.append(prompt)

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents_payload
        )
        raw_code = response.text or ""
        code_to_insert = _strip_markdown_code_fences(raw_code)

        if not code_to_insert:
            return "I couldn't generate the solution code, sir."

        # Insert directly into active editor (supports CDP or active desktop window)
        write_result = browser_write_code_in_editor(code_to_insert)
        logger.info(f"Code write result: {write_result}")
        return "I've written the solution directly into your editor, sir. Please review it before submitting."

    except Exception as e:
        logger.error(f"Error generating or inserting code: {e}")
        return f"I encountered an error while writing the code: {e}"
