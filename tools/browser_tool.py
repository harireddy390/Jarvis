import webbrowser

def browser_extract_problem_text() -> str:
    """
    Extracts the visible text of the current page -- use this to read a coding
    problem statement (LeetCode, CodeChef, HackerRank, etc.) before writing a
    solution.
    """
    page = _ensure_browser()
    try:
        return page.inner_text("body")[:6000]
    except Exception as e:
        return f"Couldn't read the page text: {e}"


def browser_write_code_in_editor(code: str) -> str:
    """
    Writes code into the visible code editor on the current page (LeetCode,
    CodeChef, HackerRank, etc.). Clicks into the editor, selects all existing
    content, and replaces it with the given code. Does NOT submit -- the user
    reviews and submits manually.
    """
    page = _ensure_browser()
    selectors = [".monaco-editor", ".CodeMirror", "textarea"]
    for selector in selectors:
        try:
            editor = page.locator(selector).first
            editor.click(timeout=3000)
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.keyboard.type(code, delay=5)
            return f"Wrote the code into the editor, sir -- please review before submitting."
        except Exception:
            continue
    return "I couldn't find a code editor on this page, sir."
def open_website(url: str) -> str:
    """
    Opens a website in the default browser.
    """
    webbrowser.open(url)
    return f"Opened {url}"