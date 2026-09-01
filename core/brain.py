import os
import time
from dotenv import load_dotenv
from google import genai
from tools.file_tool import open_file_or_folder, list_folder, create_folder, delete_file_or_folder
from google.genai import types
from tools.browser_tool import open_website
from tools.youtube_tool import play_youtube_video
from tools.screen_tool import click_on_screen_text, scroll_screen, close_current_tab, press_key, type_text, click_skip_ad
from tools.search_tool import web_search, news_search
from tools.vision_tool import see_camera
from memory.memory_manager import load_memory, remember
from memory.reminder_manager import set_reminder
from tools.coding_tool import (
    set_workspace, get_project_summary, list_project_tree, search_in_files,
    find_symbol, read_relevant_files, read_file_excerpt, read_code_file,
    write_code_file, run_python_file, list_backups_tool, restore_backup_tool,
)
from tools.browser_control import (
    browser_status, browser_open, browser_go_back, browser_go_forward,
    browser_refresh, browser_current_url, browser_page_title,
    browser_list_tabs, browser_switch_tab, browser_new_tab, browser_close_tab,
    browser_click_text, browser_fill_field, browser_press_key, browser_scroll,
    browser_wait_for_text, browser_screenshot, browser_search_youtube,
    browser_extract_problem_text, browser_write_code_in_editor,
)
from tools.document_tool import read_document, find_document
from tools.app_tool import open_application, run_terminal_command
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TIME_SENSITIVE_KEYWORDS = [
    "latest news", "recent news", "today's news", "breaking news",
    "latest", "news", "score", "weather"
]

VISION_KEYWORDS = [
    "see", "look", "camera", "vision", "how many", "who is",
    "what am i", "what do i have", "picture", "photo"
]


def needs_search(user_input: str) -> bool:
    return any(word in user_input.lower() for word in TIME_SENSITIVE_KEYWORDS)


def needs_vision(user_input: str) -> bool:
    return any(word in user_input.lower() for word in VISION_KEYWORDS)


def build_system_prompt() -> str:
    facts = load_memory()
    facts_text = "\n".join(f"- {fact}" for fact in facts) if facts else "Nothing yet."
    return (
                "You are NOT a text-only chatbot -- you have a full voice interface: the user "
        "speaks their request, and you respond out loud via text-to-speech. You also "
        "have tools to open websites, search/play YouTube videos, click things on screen, "
        "scroll, close tabs, press keys, type text, search the web, search news, see "
        "through the webcam, and set reminders. Never claim you're limited to text chat "
        "or suggest the user needs to 'set up' voice features -- they are already active.\n\n"
        "You ALSO have three larger toolsets, use them proactively when relevant:\n"
        "1. CODING/PROJECT tools: set_workspace, get_project_summary, list_project_tree, "
        "search_in_files, find_symbol, read_relevant_files, read_file_excerpt, read_code_file, "
        "write_code_file, run_python_file, list_backups_tool, restore_backup_tool -- use these "
        "when the user asks you to inspect, explain, modify, or run code in a project folder. "
        "Always call set_workspace first if no workspace is active yet.\n"
        "2. REAL BROWSER tools (browser_status, browser_open, browser_go_back, "
        "browser_go_forward, browser_refresh, browser_current_url, browser_page_title, "
        "browser_list_tabs, browser_switch_tab, browser_new_tab, browser_close_tab, "
        "browser_click_text, browser_fill_field, browser_press_key, browser_scroll, "
        "browser_wait_for_text, browser_screenshot, browser_search_youtube, "
        "browser_extract_problem_text, browser_write_code_in_editor) -- these give you real "
        "control of an actual browser tab (clicking real elements, filling real forms), unlike "
        "open_website which just opens the default browser with no further control. Prefer the "
        "browser_ tools whenever the user needs you to interact with a page, not just open one.\n"
        "3. DOCUMENT and SYSTEM tools: read_document, find_document (PDF/DOCX/TXT), "
        "open_application, run_terminal_command -- use for reading files or running "
        "programs/commands on the user's machine.\n\n"
        f"Here is what you currently know about the user:\n{facts_text}\n\n"
        "If the user tells you something worth remembering long-term "
        "(their name, preferences, ongoing projects, etc.), use the remember tool to save it.\n\n"
        "IMPORTANT: Only claim you performed an action (clicking, scrolling, closing a tab, "
        "opening something) if you actually called the matching tool and it returned success. "
        "Never say you did something you didn't actually call a tool for. If a tool's result "
        "doesn't fully match what the user asked (e.g. they asked for 'all tabs' but the tool "
        "only closed one), say so honestly rather than reporting full success.\n\n"
        "PRIVACY: The user's stored facts may include emails, IDs, or other personal details. "
        "Never volunteer or read out emails, ID numbers, or similarly sensitive stored facts "
        "unless the user specifically asks for that exact piece of information (e.g. 'what's my "
        "email'). When asked broadly 'what do you know about me', summarize non-sensitive facts "
        "(name, field of study, preferences, projects) and simply say you also have some contact "
        "details on file if they want them, rather than reciting everything.\n\n"
        "Only use the camera when the user explicitly asks you to look, see, or check "
        "something visually -- never activate it on your own inference.\n\n"
        "FILE SAFETY: Deleting files/folders is irreversible. Always confirm with the user "
        "by name before calling delete_file_or_folder with confirmed=True -- read back exactly "
        "what will be deleted and wait for explicit yes. Never delete system folders, Windows "
        "folders, or anything outside the user's own personal files. The same applies to "
        "write_code_file when overwriting an EXISTING file -- read back what will change and "
        "wait for explicit yes before calling it with confirmed=True.\n\n"
        "SYSTEM COMMAND SAFETY: run_terminal_command executes immediately with no confirmation "
        "step -- there is no undo. Never run a command that deletes, formats, moves system "
        "files, changes permissions, or could affect anything outside the user's own project "
        "folder, even if asked casually. For anything destructive or irreversible, tell the "
        "user you won't run it via voice and that they should run it themselves."
    )

def think(conversation_history: list) -> str:
    """
    Takes the full conversation so far and returns JARVIS's next response.
    Forces a real search or a fresh camera capture first when the question calls
    for it, then retries a couple of times if the server is temporarily overloaded.
    """
    last_user_message = conversation_history[-1]["parts"][0]["text"]

    if needs_search(last_user_message):
        search_results = news_search(last_user_message)
        conversation_history.append({
            "role": "user",
            "parts": [{"text": f"[Real search results for context, use these to answer accurately]:\n{search_results}"}]
        })

    if needs_vision(last_user_message):
        fresh_description = see_camera(last_user_message)
        conversation_history.append({
            "role": "user",
            "parts": [{"text": f"[Fresh camera capture just now, use this not older camera info]:\n{fresh_description}"}]
        })

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=conversation_history,
                config=types.GenerateContentConfig(
                    system_instruction=build_system_prompt(),
                                        tools=[
                        # original tool set
                        open_website,
                        play_youtube_video,
                        remember,
                        click_on_screen_text,
                        scroll_screen,
                        close_current_tab,
                        press_key,
                        type_text,
                        click_skip_ad,
                        web_search,
                        news_search,
                        set_reminder,
                        see_camera, open_file_or_folder, list_folder, create_folder, delete_file_or_folder,
                        # coding / project tools
                        set_workspace, get_project_summary, list_project_tree, search_in_files,
                        find_symbol, read_relevant_files, read_file_excerpt, read_code_file,
                        write_code_file, run_python_file, list_backups_tool, restore_backup_tool,
                        # real browser control (Playwright-backed)
                        browser_status, browser_open, browser_go_back, browser_go_forward,
                        browser_refresh, browser_current_url, browser_page_title,
                        browser_list_tabs, browser_switch_tab, browser_new_tab, browser_close_tab,
                        browser_click_text, browser_fill_field, browser_press_key, browser_scroll,
                        browser_wait_for_text, browser_screenshot, browser_search_youtube,
                        browser_extract_problem_text, browser_write_code_in_editor,
                        # documents
                        read_document, find_document,
                        # system / apps
                        open_application, run_terminal_command,
                    ]
                )
            )
            return response.text or "I'm not sure how to respond to that, sir — could you rephrase?"
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"(JARVIS hit a hiccup, retrying... {e})")
                time.sleep(2)
            else:
                return "I'm having trouble reaching my brain right now. Please try again in a moment."