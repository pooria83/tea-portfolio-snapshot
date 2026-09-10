"""Script-based language detection for chat messages.

Fast and deterministic: the user's message language decides the locale used
for the engine call instead of the conversation's creation-time locale.
"""

import re

_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
_PERSIAN_SPECIFIC_RE = re.compile(r"[پچژگکی]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_locale(text: str) -> str | None:
    """Detect the language of a message from its script.

    Returns "fa" (Persian-specific characters present), "ar" (other Arabic
    script), "en" (Latin only), or None when the script is inconclusive
    (empty, whitespace, numbers/emoji only).
    """
    stripped = text.strip()
    if not stripped:
        return None
    if _PERSIAN_SPECIFIC_RE.search(stripped):
        return "fa"
    if _ARABIC_SCRIPT_RE.search(stripped):
        return "ar"
    if _LATIN_RE.search(stripped):
        return "en"
    return None
