import yt_dlp
import webbrowser


def play_youtube_video(query: str) -> str:
    """
    Searches YouTube for the given query and opens the top matching video directly,
    so it starts playing rather than just showing search results.
    """
    ydl_opts = {"quiet": True, "noplaylist": True, "default_search": "ytsearch1"}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

    if not info.get("entries"):
        return f"Couldn't find any video for '{query}'."

    video = info["entries"][0]
    video_url = video["webpage_url"]
    title = video["title"]

    webbrowser.open(video_url)
    return f"Playing '{title}' on YouTube."