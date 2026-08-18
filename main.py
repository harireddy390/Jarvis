import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(1)

import threading
import time
import pyautogui
import pyttsx3
import speech_recognition as sr
from core.brain import think
from core.logger import logger
from memory.reminder_manager import get_due_reminders
from core.wake_word import wait_for_wake_word

recognizer = sr.Recognizer()
speak_lock = threading.Lock()

def speak(text: str):
    with speak_lock:
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

def reminder_checker_loop():
    while True:
        try:
            due = get_due_reminders()
            for r in due:
                speak(f"Reminder: {r['text']}")
        except Exception as e:
            logger.error(f"Reminder checker error: {e}")
        time.sleep(20)

def run():
    logger.info("JARVIS starting up.")
    print("JARVIS is online. Say 'exit' to quit.\n")
    conversation_history = []
    
    threading.Thread(target=reminder_checker_loop, daemon=True).start()
    
    # State tracker for continuous conversation
    is_awake = False 
    
    while True:
        try:
            # Only wait for the wake word if JARVIS is currently asleep
            if not is_awake:
                wait_for_wake_word() 
                speak("Yes?")
                is_awake = True
            
            # Listen for your command
            user_input = listen() 
            
            # If JARVIS hears silence, go back to sleep automatically
            if not user_input:
                print("Going back to sleep...")
                is_awake = False
                continue
                
            if "exit" in user_input.lower() or "shut down" in user_input.lower():
                speak("Shutting down. Goodbye.")
                logger.info("JARVIS shutting down (user request).")
                break
                
            # Manual command to put JARVIS back to sleep
            if "go to sleep" in user_input.lower() or "stop listening" in user_input.lower():
                speak("Standing by.")
                is_awake = False
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
            is_awake = False # Reset state on crash

if __name__ == "__main__":
    run()