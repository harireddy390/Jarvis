"""
JARVIS's real browser automation, backed by Playwright.

This is the SINGLE source of truth for browser control -- tools/browser_tool.py
only offers a plain webbrowser.open() fallback with no live page access.
Everything that needs to see, click, type into, or read the actual page goes
through the shared _page/_browser handles here so there is only ever one
Playwright session, not two competing ones.

Connection strategy: first tries to attach to an already-running Chrome with
--remote-debugging-port=9222 (see run_jarvis.bat), which lets JARVIS control
the user's real browser/session/cookies. Falls back to launching a fresh
Chromium instance if nothing is listening on that port.
"""

from playwright.sync_api import sync_playwright

_playwright = None
_browser = None
_page = None

BLOCKED_CLICK_WORDS = ["submit", "run code", "execute"]


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

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


def browser_status() -> str:
    """
    Reports whether JARVIS's browser is connected, and to how many tabs/pages,
    without opening or touching anything. Useful before deciding to act.
    """
    if _browser is None or not _browser.is_connected():
        return "Not connected to a browser yet, sir -- the next browser command will connect automatically."
    total_pages = sum(len(ctx.pages) for ctx in _browser.contexts)
    current = _page.url if _page else "(none active)"
    return f"Connected. {total_pages} page(s) open across {len(_browser.contexts)} context(s). Current page: {current}"


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def browser_open(url: str) -> str:
    """
    Opens a URL in JARVIS's browser. If the URL doesn't start with http, treats
    it as a Google search.
    """
    page = _ensure_browser()
    if not url.startswith("http"):
        url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return f"Opened {url} in JARVIS's browser."


def browser_go_back() -> str:
    """
    Navigates back to the previous page in JARVIS's browser.
    """
    page = _ensure_browser()
    page.go_back(timeout=5000)
    return "Went back, sir."


def browser_go_forward() -> str:
    """
    Navigates forward to the next page in JARVIS's browser history.
    """
    page = _ensure_browser()
    page.go_forward(timeout=5000)
    return "Went forward, sir."


def browser_refresh() -> str:
    """
    Reloads the current page.
    """
    page = _ensure_browser()
    page.reload(timeout=15000)
    return "Refreshed the page, sir."


def browser_current_url() -> str:
    """
    Returns the URL of the page JARVIS is currently looking at.
    """
    page = _ensure_browser()
    return page.url


def browser_page_title() -> str:
    """
    Returns the title of the current page.
    """
    page = _ensure_browser()
    return page.title() or "(page has no title)"


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

def browser_list_tabs() -> str:
    """
    Lists every open tab across all browser contexts, with an index you can
    use with browser_switch_tab.
    """
    if _browser is None or not _browser.is_connected():
        return "There's no browser connected right now, sir."
    lines = []
    idx = 0
    for context in _browser.contexts:
        for page in context.pages:
            marker = " (active)" if page == _page else ""
            lines.append(f"[{idx}] {page.title() or '(untitled)'} -- {page.url}{marker}")
            idx += 1
    if not lines:
        return "No tabs are currently open, sir."
    return "\n".join(lines)


def browser_switch_tab(index: int) -> str:
    """
    Switches JARVIS's active tab to the one at the given index (see
    browser_list_tabs for indices).
    """
    global _page
    if _browser is None or not _browser.is_connected():
        return "There's no browser connected right now, sir."
    all_pages = [p for ctx in _browser.contexts for p in ctx.pages]
    if not (0 <= index < len(all_pages)):
        return f"There's no tab at index {index}, sir -- I only see {len(all_pages)} tab(s)."
    _page = all_pages[index]
    _page.bring_to_front()
    return f"Switched to tab {index}: {_page.title() or _page.url}"


def browser_new_tab(url: str = "") -> str:
    """
    Opens a brand-new tab, optionally navigating it straight to a URL.
    """
    global _page
    page = _ensure_browser()
    context = page.context
    _page = context.new_page()
    if url:
        if not url.startswith("http"):
            url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
        _page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"Opened a new tab at {url}, sir."
    return "Opened a new blank tab, sir."


def browser_close_tab() -> str:
    """
    Closes the current tab in JARVIS's browser.
    """
    global _page, _browser
    if _page is None or _browser is None or not _browser.is_connected():
        return "There's no browser tab open right now, sir."

    _page.close()
    remaining = [p for ctx in _browser.contexts for p in ctx.pages]

    if remaining:
        _page = remaining[-1]
        return "Closed the tab, sir."
    else:
        _page = _browser.new_page()
        return "Closed the last tab -- opened a fresh blank page, ready for the next command."


# ---------------------------------------------------------------------------
# Page interaction
# ---------------------------------------------------------------------------

def browser_click_text(text: str) -> str:
    """
    Clicks a button or link containing the given visible text, using real page
    elements -- so if this succeeds, the click genuinely happened. EXCEPT
    submit/run/execute buttons on coding platforms, which are permanently
    blocked for safety.
    """
    if any(word in text.lower() for word in BLOCKED_CLICK_WORDS):
        return f"I won't click '{text}', sir -- submitting or running code is something you should do yourself."

    page = _ensure_browser()
    try:
        locator = page.get_by_text(text, exact=False).first
        locator.click(timeout=5000)
        return f"Clicked '{text}' -- confirmed, sir (real element, not a guess)."
    except Exception as e:
        return f"Couldn't find or click '{text}' on the current page, sir. ({str(e)[:100]})"


def browser_fill_field(label_or_placeholder: str, value: str) -> str:
    """
    Fills a form field (input/textarea) identified by its visible label or
    placeholder text with the given value. Tries label first, then
    placeholder, then a matching name/id attribute.
    """
    page = _ensure_browser()
    attempts = [
        lambda: page.get_by_label(label_or_placeholder, exact=False).first,
        lambda: page.get_by_placeholder(label_or_placeholder, exact=False).first,
        lambda: page.locator(f"[name='{label_or_placeholder}'], #{label_or_placeholder}").first,
    ]
    for get_locator in attempts:
        try:
            field = get_locator()
            field.click(timeout=3000)
            field.fill(value, timeout=3000)
            return f"Filled '{label_or_placeholder}' with '{value}', sir."
        except Exception:
            continue
    return f"I couldn't find a field matching '{label_or_placeholder}' on this page, sir."


def browser_press_key(key: str) -> str:
    """
    Presses a keyboard key or combination (e.g. 'Enter', 'Control+A') inside
    the current browser page.
    """
    page = _ensure_browser()
    try:
        page.keyboard.press(key)
        return f"Pressed {key} in the browser, sir."
    except Exception as e:
        return f"Couldn't press {key}: {e}"


def browser_scroll(direction: str = "down", amount: int = 600) -> str:
    """
    Scrolls the current page up or down by the given pixel amount, using
    real page scrolling (more reliable than OS-level scrolling since it
    doesn't depend on window focus).
    """
    page = _ensure_browser()
    delta = amount if direction.lower() == "down" else -amount
    try:
        page.mouse.wheel(0, delta)
        return f"Scrolled {direction} on the page, sir."
    except Exception as e:
        return f"Couldn't scroll: {e}"


def browser_wait_for_text(text: str, timeout_seconds: int = 10) -> str:
    """
    Waits until the given text appears anywhere on the current page, up to
    timeout_seconds. Use this before clicking/reading something that loads
    asynchronously (e.g. after a search or form submission).
    """
    page = _ensure_browser()
    try:
        page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout_seconds * 1000
        )
        return f"'{text}' appeared on the page, sir."
    except Exception:
        return f"'{text}' didn't appear within {timeout_seconds} seconds, sir."


def browser_screenshot(path: str = "browser_screenshot.png") -> str:
    """
    Takes a screenshot of the current page and saves it to the given path
    (relative to JARVIS's project folder unless absolute). Useful for the
    user to review what JARVIS is currently looking at.
    """
    page = _ensure_browser()
    try:
        page.screenshot(path=path, full_page=False)
        return f"Saved a screenshot of the current page to '{path}', sir."
    except Exception as e:
        return f"Couldn't take a screenshot: {e}"


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

def browser_search_youtube(query: str) -> str:
    """
    Searches YouTube and opens the first video result directly.
    """
    page = _ensure_browser()
    page.goto(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}", timeout=15000)
    try:
        first_video = page.locator("a#video-title").first
        first_video.click(timeout=8000)
        return f"Playing the top YouTube result for '{query}', sir."
    except Exception:
        return f"Opened YouTube search results for '{query}', but couldn't auto-click the first video, sir."


# ---------------------------------------------------------------------------
# Coding-platform helpers
# ---------------------------------------------------------------------------

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
    selectors = [".monaco-editor", ".CodeMirror", ".ace_editor", "[contenteditable='true']", "textarea"]
    for selector in selectors:
        try:
            editor = page.locator(selector).first
            editor.click(timeout=3000)
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.keyboard.type(code, delay=5)
            return f"Wrote the code into the editor using selector '{selector}' -- please review before submitting, sir."
        except Exception:
            continue
    return "I couldn't find a code editor on this page, sir."