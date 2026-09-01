"""
Shared Gemini client factory.

Previously brain.py, planner.py, vision_tool.py and document_tool.py each
constructed their own genai.Client. This module gives the whole project one
client and one place to configure the model name.
"""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

_client = None


def get_client():
    """
    Returns the process-wide Gemini client, creating it on first use.
    Fails fast with a clear message if GEMINI_API_KEY is missing.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(see .env.example in the project root)."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def get_model_name() -> str:
    """
    Model used for conversation and planning. Override with JARVIS_MODEL
    in .env (e.g. gemini-flash-latest for stronger reasoning on code tasks).
    """
    return os.getenv("JARVIS_MODEL", "gemini-flash-lite-latest")