from ddgs import DDGS


def web_search(query: str) -> str:
    """
    Searches the web for current, real information -- general facts, prices, how-to info.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception:
        return f"No search results found for '{query}'."

    if not results:
        return f"No search results found for '{query}'."
    return "\n\n".join(f"{r['title']}: {r['body']}" for r in results)


def news_search(query: str) -> str:
    """
    Searches for recent news headlines specifically.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=5))
    except Exception:
        return f"No recent news found for '{query}'."

    if not results:
        return f"No recent news found for '{query}'."
    return "\n\n".join(
        f"{r['title']} ({r.get('date', 'unknown date')}): {r['body']}" for r in results
    )