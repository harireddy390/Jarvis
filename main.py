import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(1)

import pyautogui
import pyttsx3
import speech_recognition as sr
from core.brain import think
from core.logger import logger

recognizer = sr.Recognizer()


def speak(text: str):
    print(f"JARVIS: {text}")
    logger.info(f"JARVIS said: {text}")
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def listen() -> str:
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening...")
        audio = recognizer.listen(source)

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


def run():
    logger.info("JARVIS starting up.")
    print("JARVIS is online. Say 'exit' to quit.\n")
    conversation_history = []

    while True:
        try:
            user_input = listen()

            if not user_input:
                continue

            if "exit" in user_input.lower() or "shut down" in user_input.lower():
                speak("Shutting down. Goodbye.")
                logger.info("JARVIS shutting down (user request).")
                break

            # Verbatim dictation — bypasses the AI entirely so it types
            # exactly what you said, no paraphrasing risk
            if user_input.lower().startswith("type ") or user_input.lower().startswith("write "):
                dictated_text = user_input.split(" ", 1)[1]
                pyautogui.write(dictated_text, interval=0.02)
                speak(f"Typed: {dictated_text}")
                continue

            conversation_history.append({
                "role": "user",
                "parts": [{"text": user_input}]
            })

            response = think(conversation_history)

            conversation_history.append({
                "role": "model",
                "parts": [{"text": response}]
            })

            speak(response)

        except Exception as e:
            logger.error(f"Unexpected crash in main loop: {e}")
            print(f"Something went wrong: {e}")


if __name__ == "__main__":
    run()