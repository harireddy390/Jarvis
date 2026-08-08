from ddgs import DDGS


def web_search(query: str) -> str:
    """
    Searches the web for current, real information -- general facts, prices, how-to info.
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    if not results:
        return f"No search results found for '{query}'."
    return "\n\n".join(f"{r['title']}: {r['body']}" for r in results)


def news_search(query: str) -> str:
    """
    Searches for recent news headlines specifically.
    """
    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=5))
    if not results:
        return f"No recent news found for '{query}'."
    return "\n\n".join(
        f"{r['title']} ({r.get('date', 'unknown date')}): {r['body']}" for r in results
    )