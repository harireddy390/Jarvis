from playwright.sync_api import sync_playwright

_playwright = None
_browser = None
_page = None


def _get_active_page():
    global _page
    if _browser is None or not _browser.is_connected():
        return None
    for context in _browser.contexts:
        for page in reversed(context.pages):
            url = page.url
            if url and url not in ("about:blank", "chrome://newtab/") and not url.startswith("chrome://"):
                _page = page
                return _page
    return None


def _ensure_browser():
    global _playwright, _browser, _page

    if _browser is None or not _browser.is_connected():
        if _playwright is None:
            _playwright = sync_playwright().start()
        try:
            _browser = _playwright.chromium.connect_over_cdp("http://localhost:9222")
        except Exception:
            _browser = _playwright.chromium.launch(headless=False)
            _page = _browser.new_page()
            return _page

    active = _get_active_page()
    if active:
        return active

    if _browser.contexts:
        _page = _browser.contexts[0].new_page()
    else:
        _page = _browser.new_page()
    return _page

def browser_open(url: str) -> str:
    """
    Opens a URL in JARVIS's dedicated browser window. If the URL doesn't start with
    http, treats it as a search query on Google. Use this instead of open_website
    for anything you'll need to click on or verify afterward, since this browser
    is directly controllable, unlike the user's regular browser.
    """
    page = _ensure_browser()
    if not url.startswith("http"):
        url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return f"Opened {url} in JARVIS's browser."


def browser_click_text(text: str) -> str:
    """
    Clicks a button or link containing the given visible text, using real page
    elements (not screenshots) -- so if this succeeds, the click genuinely happened.
    Works for any labeled button: subscribe, like, dislike, download, anything --
    EXCEPT submit/run/execute buttons on coding platforms, which are permanently
    blocked for safety and require the user to click manually.
    """
    blocked_words = ["submit", "run code", "execute"]
    if any(word in text.lower() for word in blocked_words):
        return f"I won't click '{text}', sir -- submitting or running code is something you should do yourself. I've left it for you."

    page = _ensure_browser()
    try:
        locator = page.get_by_text(text, exact=False).first
        locator.click(timeout=5000)
        return f"Clicked '{text}' -- confirmed, sir (real element, not a guess)."
    except Exception as e:
        return f"Couldn't find or click '{text}' on the current page, sir. ({str(e)[:100]})"
def browser_search_youtube(query: str) -> str:
    """
    Searches YouTube and opens the first video result directly, so it starts playing.
    """
    page = _ensure_browser()
    page.goto(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}", timeout=15000)
    try:
        first_video = page.locator("a#video-title").first
        first_video.click(timeout=8000)
        return f"Playing the top YouTube result for '{query}', sir."
    except Exception:
        return f"Opened YouTube search results for '{query}', but couldn't auto-click the first video, sir."


def browser_close_tab() -> str:
    """
    Closes the current tab in JARVIS's browser. If it was the only tab, the
    browser stays open with a blank page ready for the next command.
    """
    global _page, _browser

    if _page is None or _browser is None or not _browser.is_connected():
        return "There's no browser tab open right now, sir."

    _page.close()
    remaining = _browser.pages

    if remaining:
        _page = remaining[-1]
        return "Closed the tab, sir."
    else:
        _page = _browser.new_page()
        return "Closed the last tab -- opened a fresh blank page, ready for the next command."


def browser_go_back() -> str:
    """
    Navigates back to the previous page in JARVIS's browser.
    """
    page = _ensure_browser()
    page.go_back(timeout=5000)
    return "Went back, sir."


def browser_extract_problem_text() -> str:
    """
    Extracts the visible text of the current page -- use this to read a coding
    problem statement (LeetCode, CodeChef, HackerRank, etc.) before writing a
    solution.
    """
    print("[DEBUG] browser_extract_problem_text called")
    page = _ensure_browser()
    try:
        text = page.inner_text("body")[:6000]
        print(f"[DEBUG] extracted {len(text)} chars, page url: {page.url}")
        return text
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
    selectors = [".monaco-editor", ".CodeMirror", ".ace_editor", "[contenteditable='true']", "textarea"]
    for selector in selectors:
        try:
            editor = page.locator(selector).first
            editor.click(timeout=3000)
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.keyboard.type(code, delay=5)
            typed_check = page.locator(selector).first.inner_text() if selector != "textarea" else None
            return f"Wrote the code into the editor using selector '{selector}' -- please review before submitting, sir."
        except Exception:
            continue
    return "I couldn't find a code editor on this page, sir -- the platform may use an editor type I don't recognize yet."