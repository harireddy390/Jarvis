import sys
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(1)

import threading
import time
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
from memory.reminder_manager import set_reminder, get_due_reminders
from ui.hud_window import JarvisHUD

recognizer = sr.Recognizer()
speak_lock = threading.Lock()


def speak(text: str):
    with speak_lock:
        print(f"JARVIS: {text}")
        logger.info(f"JARVIS said: {text}")
        event_bus.emit_state("SUCCESS", text[:60])
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()


def listen() -> str:
    event_bus.emit_state("LISTENING", "Listening...")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
    except OSError as e:
        logger.error(f"Microphone unavailable: {e}")
        return ""

    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            return ""

    event_bus.emit_state("THINKING", "Transcribing...")
    try:
        text = recognizer.recognize_google(audio)
        print(f"You: {text}")
        logger.info(f"User said: {text}")
        return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        logger.error(f"Speech recognition error: {e}")
        return ""


def reminder_checker_loop():
    while True:
        try:
            due = get_due_reminders()
            for r in due:
                speak(f"Reminder: {r['text']}")
        except Exception as e:
            logger.error(f"Reminder checker error: {e}")
        time.sleep(20)


def voice_loop():
    logger.info("JARVIS starting up.")
    conversation_history = []
    threading.Thread(target=reminder_checker_loop, daemon=True).start()

    while True:
        try:
            wait_for_wake_word()
            speak("Yes?")
            user_input = listen()

            if not user_input:
                continue
            pending = confirmations.get_current()
            if pending:
                lowered = user_input.lower().strip()
                yes_words = ("yes", "yeah", "yep", "confirm", "sure", "go ahead")
                no_words = ("no", "nope", "cancel", "don't", "stop")
                if lowered.startswith(yes_words):
                    speak(confirmations.resolve_by_voice(True))
                    continue
                if lowered.startswith(no_words):
                    speak(confirmations.resolve_by_voice(False))
                    continue

            if "exit" in user_input.lower() or "shut down" in user_input.lower():
                speak("Shutting down. Goodbye.")
                logger.info("JARVIS shutting down (user request).")
                break

            if user_input.lower().startswith("type this") or user_input.lower().startswith("dictate "):
                dictated_text = user_input.split(" ", 1)[1] if " " in user_input else ""
                pyautogui.write(dictated_text, interval=0.02)
                speak(f"Typed: {dictated_text}")
                continue

            if "continue the task" in user_input.lower() or "continue that task" in user_input.lower():
                event_bus.emit_state("EXECUTING", "Continuing task...")
                result = continue_last_task()
                speak(result)
                continue

            if needs_planning(user_input):
                event_bus.emit_state("EXECUTING", "Planning...")
                speak("Understood, sir. Breaking that down and getting started.")
                result = execute_plan(user_input)
                speak(result)
                conversation_history.append({"role": "user", "parts": [{"text": user_input}]})
                conversation_history.append({"role": "model", "parts": [{"text": result}]})
                continue

            event_bus.emit_state("THINKING", "Thinking...")
            conversation_history.append({"role": "user", "parts": [{"text": user_input}]})
            response = think(conversation_history)
            conversation_history.append({"role": "model", "parts": [{"text": response}]})
            speak(response)

        except Exception as e:
            logger.error(f"Unexpected crash in main loop: {e}")
            event_bus.emit_state("ERROR", "Something went wrong")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = JarvisHUD()

    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()

    sys.exit(app.exec())