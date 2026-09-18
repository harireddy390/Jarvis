"""
Context detector: identifies what application, window, and browser tab the user is actively working on.
"""

import psutil
try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def get_foreground_window_info() -> dict:
    """
    Returns information about the user's currently focused foreground window.
    """
    if not HAS_WIN32:
        return {"title": "", "process": "", "is_browser": False, "is_ide": False}

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"title": "", "process": "", "is_browser": False, "is_ide": False}

        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = ""
        try:
            process_name = psutil.Process(pid).name().lower()
        except Exception:
            pass

        title_lower = title.lower()
        is_browser = any(b in process_name for b in ("chrome", "msedge", "brave", "firefox")) or \
                     any(b in title_lower for b in ("google chrome", "microsoft edge", "brave"))

        is_ide = any(i in process_name for i in ("code", "cursor", "pycharm", "sublime", "notepad", "devenv", "windowsterminal", "powershell", "cmd")) or \
                 any(i in title_lower for i in ("visual studio code", "cursor", "pycharm", "sublime text", "notepad"))

        return {
            "hwnd": hwnd,
            "title": title,
            "process": process_name,
            "is_browser": is_browser,
            "is_ide": is_ide,
        }
    except Exception as e:
        return {"title": "", "process": "", "is_browser": False, "is_ide": False, "error": str(e)}


def get_active_browser_tab_info() -> dict:
    """
    Queries the live Chrome session (via tools.browser_control) to extract details
    about the active browser tab (URL, title, editor availability, and problem text excerpt).
    """
    try:
        from tools.browser_control import _ensure_browser, _get_active_page
        page = _ensure_browser()
        if not page:
            return {"connected": False}

        url = page.url or ""
        title = page.title() or ""

        # Check if page has an active code editor
        has_editor = False
        editor_selector = ""
        selectors = [
            ".monaco-editor .view-lines",
            ".monaco-editor",
            ".CodeMirror-code",
            ".CodeMirror",
            ".ace_editor",
            "[contenteditable='true']",
            "textarea:visible",
            "textarea",
        ]
        for s in selectors:
            try:
                count = page.locator(s).count()
                if count > 0:
                    has_editor = True
                    editor_selector = s
                    break
            except Exception:
                continue

        # Extract problem text / main body content
        body_text = ""
        try:
            body_text = page.inner_text("body")[:5000]
        except Exception:
            pass

        return {
            "connected": True,
            "title": title,
            "url": url,
            "has_editor": has_editor,
            "editor_selector": editor_selector,
            "body_text": body_text,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def get_current_working_context() -> dict:
    """
    Combines foreground OS window info and live browser tab info
    to produce a complete picture of what the user is working on right now.
    """
    fg = get_foreground_window_info()
    browser_info = get_active_browser_tab_info()

    # Prioritize browser if foreground is browser or Chrome has active non-blank tab
    is_active_browser = (
        fg.get("is_browser") or
        (browser_info.get("connected") and browser_info.get("url") and not browser_info.get("url", "").startswith("chrome://"))
    )

    context = {
        "foreground": fg,
        "browser": browser_info,
        "primary_target": "browser" if is_active_browser else ("ide" if fg.get("is_ide") else "desktop"),
    }
    return context
