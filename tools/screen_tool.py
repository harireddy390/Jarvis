import pyautogui
import pytesseract
from pytesseract import Output

# Point to the Tesseract OCR engine we installed earlier
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def click_skip_ad() -> str:
    """
    Looks specifically for a YouTube 'Skip Ad' button on screen and clicks it.
    """
    try:
        location = pyautogui.locateCenterOnScreen("templates/skip_ad.png", confidence=0.7)
        if location:
            pyautogui.click(location)
            return "Skipped the ad."
        return "I don't see a Skip Ad button on screen right now."
    except pyautogui.ImageNotFoundException:
        return "I don't see a Skip Ad button on screen right now."

def click_on_screen_text(text_to_find: str) -> str:
    """
    Looks for the given text or phrase anywhere on screen and clicks it.
    """
    screenshot = pyautogui.screenshot()
    data = pytesseract.image_to_data(screenshot, output_type=Output.DICT)
    n = len(data["text"])
    target_words = text_to_find.lower().split()
    
    for i in range(n):
        if not data["text"][i].strip():
            continue
            
        joined = ""
        boxes = []
        for j in range(i, min(i + len(target_words) + 2, n)):
            word = data["text"][j].strip()
            if not word:
                break
            joined = (joined + " " + word).strip()
            boxes.append((data["left"][j], data["top"][j], data["width"][j], data["height"][j]))
            
            if text_to_find.lower() in joined.lower():
                left = min(b[0] for b in boxes)
                top = min(b[1] for b in boxes)
                right = max(b[0] + b[2] for b in boxes)
                bottom = max(b[1] + b[3] for b in boxes)
                x = (left + right) // 2
                y = (top + bottom) // 2
                pyautogui.click(x, y)
                return f"Clicked '{joined}' on screen."
                
    return f"I couldn't find anything saying '{text_to_find}' on screen right now."

def scroll_screen(direction: str) -> str:
    """
    Scrolls the current window up or down. direction must be either "up" or "down".
    """
    amount = 500 if direction == "down" else -500
    pyautogui.scroll(-amount)
    return f"Scrolled {direction}."

def close_current_tab() -> str:
    """
    Closes the current browser tab. Only works reliably if the browser window
    currently has focus.
    """
    pyautogui.hotkey("ctrl", "w")
    return "Closed the current tab."

def press_key(key: str) -> str:
    """
    Presses a single key or key combination on the keyboard.
    """
    keys = key.lower().split("+")
    pyautogui.hotkey(*keys)
    return f"Pressed {key}."

def type_text(text: str) -> str:
    """
    Types the given text wherever the cursor currently is.
    """
    pyautogui.write(text, interval=0.02)
    return f"Typed: {text}"