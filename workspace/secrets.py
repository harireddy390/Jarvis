"""
Secret protection: redacts credential-looking content from any text that
JARVIS tools return to the LLM, and blocks reads of secret files.

Two layers:
1. Path layer (workspace/scanner.is_secret_path) - files never opened.
2. Content layer (this module) - even if a secret leaks into a scanned file
   (hardcoded API key in source code), it is redacted before reaching the LLM
   or being persisted to memory.
"""

import re

# Patterns that look like live credentials.
_SECRET_PATTERNS = [
    (re.compile(r"(sk-[A-Za-z0-9_\-]{16,})"), "sk-***REDACTED***"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "AKIA***REDACTED***"),
    (re.compile(r"(ghp_[A-Za-z0-9]{20,})"), "ghp_***REDACTED***"),
    (re.compile(r"(gho_[A-Za-z0-9]{20,})"), "gho_***REDACTED***"),
    (re.compile(r"(github_pat_[A-Za-z0-9_]{20,})"), "github_pat_***REDACTED***"),
    (re.compile(r"(xox[baprs]-[A-Za-z0-9\-]{10,})"), "xox-***REDACTED***"),
    (re.compile(r"(AIza[0-9A-Za-z_\-]{30,})"), "AIza***REDACTED***"),
    (re.compile(r"(eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,})"), "***JWT-REDACTED***"),
    (re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)"), "***PRIVATE-KEY-REDACTED***"),
    # key = value style assignments for obvious secret names
    (re.compile(
        r"((?:api[_-]?key|apikey|secret|password|passwd|pwd|token|auth)"
        r"\s*[=:]\s*)(['\"]?)[^\s'\"]{6,}\2",
        re.IGNORECASE,
    ), r"\1\2***REDACTED***\2"),
]


def redact_secrets(text: str) -> str:
    """
    Returns text with credential-looking strings replaced by redacted markers.
    Applied to every file excerpt, search hit, and command output that leaves
    the workspace layer.
    """
    if not text:
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text