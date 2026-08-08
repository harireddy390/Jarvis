import webbrowser


def open_website(url: str) -> str:
    """
    Opens a website in the default browser.
    """
    webbrowser.open(url)
    return f"Opened {url}"