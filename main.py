"""
JARVIS - Main entry point.

Voice pipeline:
1. Continuous offline wake-word loop: listens for "Hey Jarvis" or F8.
2. After activation, enters a persistent conversational session.
3. Commands are processed immediately and JARVIS listens again.
4. Session ends on sleep/exit commands or two consecutive silent timeouts.
5. After a session ends, JARVIS returns to wake-word listening.
"""

import sys
import ctypes
import threading
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import pyautogui
import pyttsx3
import speech_recognition as sr
from PySide6.QtWidgets import QApplication

from core.brain import think
from core.logger import logger
from core.wake_word import wait_for_wake_word
from core.planner import needs_planning, execute_plan, continue_last_task
from core.event_bus import event_bus
from core import confirmations
from core.context_detector import get_current_working_context
from core.code_completer import (
    explain_code_in_active_context,
    complete_in_active_context,
)
from memory.reminder_manager import get_due_reminders
from ui.hud_window import JarvisHUD


# ---------------------------------------------------------------------------
# Speech recognition
# ---------------------------------------------------------------------------

recognizer = sr.Recognizer()
recognizer.energy_threshold = 100
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.12
recognizer.dynamic_energy_ratio = 1.1
recognizer.pause_threshold = 0.55
recognizer.non_speaking_duration = 0.35


# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------

speak_lock = threading.Lock()
_tts_engine = None


def _get_tts_engine():
    """Initialize and reuse a persistent TTS engine."""
    global _tts_engine

    if _tts_engine is None:
        try:
            _tts_engine = pyttsx3.init()
            _tts_engine.setProperty("rate", 195)
        except Exception:
            _tts_engine = None

    return _tts_engine


def _speak_fallback(text: str):
    """Emergency fallback TTS if the persistent engine fails."""
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 195)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception:
        pass


def speak(text: str):
    """Speak text through JARVIS TTS."""
    if not text:
        return

    with speak_lock:
        print(f"\nJARVIS: {text}")
        logger.info(f"JARVIS said: {text}")

        try:
            event_bus.emit_state("SUCCESS", text[:80])
        except Exception:
            pass

        try:
            engine = _get_tts_engine()

            if engine:
                engine.say(text)
                engine.runAndWait()
            else:
                _speak_fallback(text)

        except Exception as e:
            logger.error(f"TTS error: {e}")
            _speak_fallback(text)


# ---------------------------------------------------------------------------
# Microphone
# ---------------------------------------------------------------------------

def calibrate_microphone():
    """
    Perform one-time ambient-noise calibration.

    Keeps the threshold within a reasonable range so quiet voices
    are not accidentally treated as silence.
    """
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.6,
            )

            if recognizer.energy_threshold > 280:
                recognizer.energy_threshold = 180
            elif recognizer.energy_threshold < 55:
                recognizer.energy_threshold = 75

            logger.info(
                f"Mic calibrated. "
                f"Threshold: {recognizer.energy_threshold:.0f}"
            )

    except Exception as e:
        logger.warning(f"Mic calibration skipped: {e}")


def listen(timeout: int = 8, phrase_limit: int = 20) -> str:
    """
    Listen for one spoken command and return the recognized text.

    Returns an empty string on silence, unintelligible speech,
    microphone failure, or speech-recognition failure.
    """
    try:
        event_bus.emit_state(
            "LISTENING",
            "Listening... speak now",
        )
    except Exception:
        pass

    try:
        with sr.Microphone() as source:
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_limit,
            )

    except sr.WaitTimeoutError:
        return ""

    except OSError as e:
        logger.error(f"Microphone unavailable: {e}")
        return ""

    try:
        event_bus.emit_state(
            "THINKING",
            "Transcribing...",
        )
    except Exception:
        pass

    try:
        text = recognizer.recognize_google(
            audio,
            language="en-IN",
        )

        print(f"You: {text}")
        logger.info(f"User said: {text}")

        return text

    except sr.UnknownValueError:
        return ""

    except sr.RequestError as e:
        logger.error(f"Speech recognition error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Background reminder checker
# ---------------------------------------------------------------------------

def reminder_checker_loop():
    """Check reminders periodically in the background."""
    while True:
        try:
            due = get_due_reminders()

            for reminder in due:
                speak(f"Reminder, sir: {reminder['text']}")

        except Exception as e:
            logger.error(
                f"Reminder checker error: {e}"
            )

        time.sleep(20)


# ---------------------------------------------------------------------------
# Intent trigger banks
# ---------------------------------------------------------------------------

CODE_HELP_TRIGGERS = (
    "help me with code",
    "help me with the code",
    "help me with this code",
    "help with code",
    "help me solve this",
    "how do i solve this",
    "explain this problem",
    "explain the code",
    "explain this code",
    "give me logic",
    "give me the logic",
    "how to solve this",
    "what is the logic",
    "guide me with this",
    "what is the approach",
    "what approach should i use",
)

CODE_WRITE_TRIGGERS = (
    "write the code",
    "write this code",
    "write code in my tab",
    "write this in my tab",
    "write it in my tab",
    "write it here",
    "write the code here",
    "complete this",
    "complete this code",
    "complete my code",
    "complete the code",
    "solve this problem",
    "solve this",
    "code this for me",
    "code this",
    "fill the code",
    "fill in the code",
    "put the code in the editor",
    "yes write the code",
    "yes please write",
    "go ahead and write",
    "write it",
)

SLEEP_COMMANDS = (
    "go to sleep",
    "stop listening",
    "stand by",
    "standby",
    "that's all",
    "that is all",
    "thank you",
    "bye",
    "goodbye",
    "sleep",
    "stop",
    "pause",
)


# ---------------------------------------------------------------------------
# Active voice session
# ---------------------------------------------------------------------------

def run_session(conversation_history: list):
    """
    Run one active JARVIS session after wake-word detection.

    JARVIS continues listening after every command without requiring
    another wake phrase.

    The session ends when:
    - the user gives a sleep/standby command
    - the user gives an exit command
    - two consecutive listening timeouts occur
    """

    try:
        ctx = get_current_working_context()

        active_target = ctx.get(
            "primary_target",
            "desktop",
        )

        active_title = (
            ctx.get("browser", {}).get("title")
            or ctx.get("foreground", {}).get("title", "")
        )

        logger.info(
            f"Session started - target: {active_target}, "
            f"window: {active_title}"
        )

    except Exception as e:
        logger.warning(
            f"Could not determine working context: {e}"
        )

    speak("Ready, sir.")

    consecutive_silence = 0

    while True:

        try:
            event_bus.emit_state(
                "LISTENING",
                "Listening for your command...",
            )
        except Exception:
            pass

        user_input = listen(
            timeout=10,
            phrase_limit=20,
        )

        # ---------------------------------------------------------------
        # Silence
        # ---------------------------------------------------------------

        if not user_input:
            consecutive_silence += 1

            if consecutive_silence >= 2:
                speak("Standing by, sir.")

                event_bus.emit_state(
                    "IDLE",
                    "Say 'Hey Jarvis' or press F8",
                )

                return

            event_bus.emit_state(
                "LISTENING",
                "Still listening... speak your command",
            )

            continue

        consecutive_silence = 0
        lowered = user_input.lower().strip()

        # ---------------------------------------------------------------
        # Sleep / standby
        # ---------------------------------------------------------------

        if any(
            command in lowered
            for command in SLEEP_COMMANDS
        ):
            speak(
                "Going on standby, sir. "
                "Say 'Hey Jarvis' whenever you need me."
            )

            event_bus.emit_state(
                "IDLE",
                "Say 'Hey Jarvis' or press F8",
            )

            return

        # ---------------------------------------------------------------
        # Exit / shutdown
        # ---------------------------------------------------------------

        if (
            "exit" in lowered
            or "shut down" in lowered
            or "quit" in lowered
        ):
            speak("Shutting down. Goodbye, sir.")
            logger.info(
                "JARVIS shutting down - user request."
            )
            sys.exit(0)

        # ---------------------------------------------------------------
        # Pending confirmations
        # ---------------------------------------------------------------

        pending = confirmations.get_current()

        if pending:

            yes_words = (
                "yes",
                "yeah",
                "yep",
                "confirm",
                "sure",
                "go ahead",
                "do it",
            )

            no_words = (
                "no",
                "nope",
                "cancel",
                "don't",
                "stop",
            )

            if any(
                lowered.startswith(word)
                for word in yes_words
            ):
                speak(
                    confirmations.resolve_by_voice(True)
                )
                continue

            if any(
                lowered.startswith(word)
                for word in no_words
            ):
                speak(
                    confirmations.resolve_by_voice(False)
                )
                continue

        # ---------------------------------------------------------------
        # Explain code
        # ---------------------------------------------------------------

        if any(
            trigger in lowered
            for trigger in CODE_HELP_TRIGGERS
        ):
            event_bus.emit_state(
                "THINKING",
                "Analyzing problem...",
            )

            speak(
                "Analyzing the logic now, sir."
            )

            explanation = explain_code_in_active_context(
                user_input
            )

            event_bus.emit_state(
                "SUCCESS",
                "Logic explained",
            )

            speak(explanation)

            conversation_history.append(
                {
                    "role": "user",
                    "parts": [{"text": user_input}],
                }
            )

            conversation_history.append(
                {
                    "role": "model",
                    "parts": [{"text": explanation}],
                }
            )

            continue

        # ---------------------------------------------------------------
        # Write code into active editor
        # ---------------------------------------------------------------

        if any(
            trigger in lowered
            for trigger in CODE_WRITE_TRIGGERS
        ):
            event_bus.emit_state(
                "EXECUTING",
                "Writing code in your tab...",
            )

            speak(
                "On it, sir. "
                "Generating and inserting the code."
            )

            result = complete_in_active_context(
                user_input
            )

            event_bus.emit_state(
                "SUCCESS",
                "Code written!",
            )

            speak(result)

            conversation_history.append(
                {
                    "role": "user",
                    "parts": [{"text": user_input}],
                }
            )

            conversation_history.append(
                {
                    "role": "model",
                    "parts": [{"text": result}],
                }
            )

            continue

        # ---------------------------------------------------------------
        # Dictation
        # ---------------------------------------------------------------

        if (
            lowered.startswith("type this")
            or lowered.startswith("dictate ")
        ):
            dictated = (
                user_input.split(" ", 1)[1]
                if " " in user_input
                else ""
            )

            pyautogui.write(
                dictated,
                interval=0.015,
            )

            speak(f"Typed: {dictated}")
            continue

        # ---------------------------------------------------------------
        # Continue previous task
        # ---------------------------------------------------------------

        if (
            "continue the task" in lowered
            or "continue that task" in lowered
        ):
            event_bus.emit_state(
                "EXECUTING",
                "Continuing task...",
            )

            result = continue_last_task()

            speak(result)
            continue

        # ---------------------------------------------------------------
        # Multi-step planner
        # ---------------------------------------------------------------

        if needs_planning(user_input):
            event_bus.emit_state(
                "EXECUTING",
                "Planning your request...",
            )

            speak(
                "On it, sir. Breaking that down."
            )

            result = execute_plan(user_input)

            speak(result)

            conversation_history.append(
                {
                    "role": "user",
                    "parts": [{"text": user_input}],
                }
            )

            conversation_history.append(
                {
                    "role": "model",
                    "parts": [{"text": result}],
                }
            )

            continue

        # ---------------------------------------------------------------
        # General JARVIS reasoning
        # ---------------------------------------------------------------

        event_bus.emit_state(
            "THINKING",
            "Thinking...",
        )

        conversation_history.append(
            {
                "role": "user",
                "parts": [{"text": user_input}],
            }
        )

        response = think(
            conversation_history
        )

        conversation_history.append(
            {
                "role": "model",
                "parts": [{"text": response}],
            }
        )

        speak(response)


# ---------------------------------------------------------------------------
# Master voice loop
# ---------------------------------------------------------------------------

def voice_loop():
    """
    Main voice controller.

    JARVIS continuously waits for the wake word, enters a session,
    and automatically returns to wake-word detection afterward.
    """

    logger.info("JARVIS voice system starting up.")

    conversation_history = []

    calibrate_microphone()

    threading.Thread(
        target=reminder_checker_loop,
        daemon=True,
    ).start()

    while True:
        try:
            event_bus.emit_state(
                "IDLE",
                "Say 'Hey Jarvis' or press F8",
            )

            print("\n" + "-" * 55)
            print(
                "  JARVIS is listening... "
                "say 'Hey Jarvis' or press F8"
            )
            print("-" * 55)

            wait_for_wake_word()

            run_session(
                conversation_history
            )

        except SystemExit:
            raise

        except Exception as e:
            logger.error(
                f"Unexpected crash: {e}"
            )

            try:
                event_bus.emit_state(
                    "ERROR",
                    "Something went wrong, restarting...",
                )
            except Exception:
                pass

            time.sleep(1.0)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    app = QApplication(sys.argv)

    hud = JarvisHUD()

    voice_thread = threading.Thread(
        target=voice_loop,
        daemon=True,
    )

    voice_thread.start()

    sys.exit(app.exec())