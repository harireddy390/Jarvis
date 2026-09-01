import os
from pypdf import PdfReader
from docx import Document
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == ".docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        return ""


def read_document(path: str, question: str = "Summarize this document") -> str:
    """
    Reads a PDF, DOCX, or TXT file and answers a question about it or summarizes it.
    """
    full_path = os.path.expanduser(path)
    if not os.path.exists(full_path):
        return f"I couldn't find '{path}'."

    text = _extract_text(full_path)
    if not text.strip():
        return f"I couldn't extract any readable text from '{path}'."

    truncated = text[:15000]
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=f"Document content:\n{truncated}\n\nQuestion: {question}"
    )
    return response.text


def find_document(filename_hint: str) -> str:
    """
    Searches common folders for a file whose name contains the given hint.
    """
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/OneDrive/Desktop"),
        os.path.expanduser("~/OneDrive/Documents"),
        os.path.expanduser("~/OneDrive/Pictures/Documents"),
    ]

    matches = []
    hint_lower = filename_hint.lower()

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        for root, _, files in os.walk(directory):
            for f in files:
                if hint_lower in f.lower() and f.lower().endswith((".pdf", ".docx", ".txt")):
                    matches.append(os.path.join(root, f))

    if not matches:
        return f"I couldn't find any document matching '{filename_hint}' in your common folders."
    return "Found:\n" + "\n".join(matches[:10])