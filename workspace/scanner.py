"""
Project scanner: discovers project structure while skipping noise.

Provides:
- IGNORED_DIRS: directories never scanned (caches, builds, venvs, VCS)
- SECRET_FILE_PATTERNS: files never read/indexed (env, keys, credentials)
- is_ignored_dir / is_secret_path: predicates used by every other module
- scan_tree(root): filtered recursive listing with sizes
- classify_file(path): language/kind detection for common project files
"""

import os
from pathlib import Path

# Directories that never contain useful source and are expensive to walk.
IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "bower_components",
    "venv", ".venv", "env", ".env_dir", "virtualenv",
    "build", "dist", "out", "target", "bin", "obj",
    ".idea", ".vscode", ".vs",
    ".jarvis_backups", ".jarvis_viz",
    "site-packages", ".tox", ".eggs", "egg-info",
    "coverage", ".nyc_output", "vendor",
}

# Files that must never be read, indexed, or returned to the LLM.
SECRET_FILE_PATTERNS = (
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials.json", "client_secret.json", "service-account*.json",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore",
    ".npmrc", ".netrc", ".pgpass", "known_hosts",
    "*.kdbx", "*.kwallet",
)

# Extensions treated as text/source (everything else is binary-ish).
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
    ".md", ".rst", ".txt", ".csv", ".sql", ".sh", ".bat", ".ps1",
    ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rb", ".php",
    ".swift", ".kt", ".rs", ".vue", ".svelte", ".gitignore", ".dockerfile",
}

LANGUAGE_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "css",
    ".json": "json", ".md": "markdown", ".sql": "sql",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".java": "java", ".c": "c", ".cpp": "cpp", ".cs": "csharp",
    ".go": "go", ".rb": "ruby", ".php": "php", ".rs": "rust",
    ".sh": "shell", ".bat": "batch", ".ps1": "powershell",
}

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # refuse to read files larger than 2 MB


def is_ignored_dir(name: str) -> bool:
    """True if a directory name should never be scanned."""
    return name in IGNORED_DIRS or name.endswith(".egg-info")


def is_secret_path(path: str | Path) -> bool:
    """
    True if this path looks like a secrets/credential file.
    Uses fnmatch-style matching against SECRET_FILE_PATTERNS on the file name.
    """
    import fnmatch
    name = os.path.basename(str(path)).lower()
    for pattern in SECRET_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def classify_file(path: str | Path) -> dict:
    """
    Returns {"language": str|None, "is_text": bool, "size": int} for a file.
    """
    p = Path(path)
    ext = p.suffix.lower()
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return {
        "language": LANGUAGE_BY_EXT.get(ext),
        "is_text": ext in TEXT_EXTENSIONS or ext == "",
        "size": size,
    }


def scan_tree(root: str, max_entries: int = 2000) -> list[dict]:
    """
    Walks the project root, skipping ignored/secret paths.
    Returns a list of {"path": relative_path, "size": int, "language": str|None}
    sorted by path. Capped at max_entries to protect huge projects.
    """
    root_path = Path(root).resolve()
    results = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune ignored directories in-place so os.walk never descends.
        dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
        dirnames.sort()
        for fname in sorted(filenames):
            if is_secret_path(fname):
                continue
            full = Path(dirpath) / fname
            rel = full.relative_to(root_path).as_posix()
            info = classify_file(full)
            results.append(
                {"path": rel, "size": info["size"], "language": info["language"]}
            )
            if len(results) >= max_entries:
                return results
    return results