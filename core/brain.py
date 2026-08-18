import os
import time
import io
import pyautogui
from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools.browser_tool import open_website
from tools.youtube_tool import play_youtube_video
from tools.screen_tool import click_on_screen_text, scroll_screen, close_current_tab, press_key, type_text, click_skip_ad
from tools.search_tool import web_search, news_search
from memory.memory_manager import load_memory, remember
from memory.reminder_manager import set_reminder

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TIME_SENSITIVE_KEYWORDS = [
    "latest", "news", "current", "currently", "today", "recent",
    "score", "price", "weather", "now", "update"
]

def needs_search(user_input: str) -> bool:
    return any(word in user_input.lower() for word in TIME_SENSITIVE_KEYWORDS)

def build_system_prompt() -> str:
    facts = load_memory()
    facts_text = "\n".join(f"- {fact}" for fact in facts) if facts else "Nothing yet."
    return (
        "You are JARVIS, a personal AI assistant running locally on the user's PC. "
        "You are NOT a text-only chatbot -- you have a full voice interface: the user "
        "speaks their request, and you respond out loud via text-to-speech. You also "
        "have tools to open websites, search/play YouTube videos, click things on screen, "
        "scroll, close tabs, press keys, type text, search the web, search news, and set "
        "reminders. Never claim you're limited to text chat or suggest the user needs to "
        "'set up' voice features -- they are already active.\n\n"
        f"Here is what you currently know about the user:\n{facts_text}\n\n"
        "If the user tells you something worth remembering long-term "
        "(their name, preferences, ongoing projects, etc.), use the remember tool to save it.\n\n"
        "IMPORTANT: Only claim you performed an action (clicking, scrolling, closing a tab, "
        "opening something) if you actually called the matching tool and it returned success. "
        "Never say you did something you didn't actually call a tool for.\n\n"
        "MANDATORY: For ANY question about current events, recent news, today's date, "
        "prices, scores, or anything that could have changed recently, you MUST call "
        "news_search or web_search BEFORE answering -- never answer such questions from "
        "memory alone, even if you think you know the answer. Your training data has a "
        "cutoff and cannot be trusted for anything time-sensitive. If you're unsure whether "
        "something counts as time-sensitive, search anyway."
    )

def think(conversation_history: list) -> str:
    """
    Takes the full conversation so far and returns JARVIS's next response.
    Forces a real search first for time-sensitive questions, then retries
    a couple of times if the server is temporarily overloaded.
    """
    last_user_message = conversation_history[-1]["parts"][0]["text"]
    
    # 1. Proactive Search Check
    if needs_search(last_user_message):
        search_results = news_search(last_user_message)
        conversation_history.insert(-1, {
            "role": "user",
            "parts": [{"text": f"[Real search results for context, use these to answer: {search_results}]"}]
        })
        
    # 2. Take a live screenshot of whatever you are currently looking at
    current_screen = pyautogui.screenshot()
    
    # Compress the screenshot into a JPEG byte array so the Gemini API can read it natively
    img_byte_arr = io.BytesIO()
    current_screen.save(img_byte_arr, format='JPEG', quality=80)
    image_bytes = img_byte_arr.getvalue()
    
    # Format the payload exactly how the API expects inline visual data
    image_part = {
        "inline_data": {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
    }
    
    # 3. Make a temporary copy of the history so we don't save the image 
    # permanently (which would waste memory/tokens on future turns)
    vision_history = conversation_history.copy()
    last_msg = dict(vision_history[-1]) 
    
    # 4. Inject the binary screenshot alongside your text command
    last_msg["parts"] = [image_part, last_msg["parts"][0]]
    vision_history[-1] = last_msg

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=vision_history,
                config=types.GenerateContentConfig(
                    system_instruction=build_system_prompt(),
                    tools=[
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
                        set_reminder
                    ]
                )
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"(JARVIS hit a hiccup, retrying... {e})")
                time.sleep(2)
            else:
                return "I'm having trouble reaching my brain right now. Please try again in a moment."