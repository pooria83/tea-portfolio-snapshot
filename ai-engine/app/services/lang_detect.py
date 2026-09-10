"""Script-based language detection + response-language hints for chat turns."""

import re

_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
_PERSIAN_SPECIFIC_RE = re.compile(r"[پچژگکی]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_RESPONSE_HINTS = {
    "ar": "Respond in Arabic.",
    "fa": "Respond in Farsi.",
    "en": "Respond in English.",
}

_FOLLOW_USER_LANGUAGE_HINT = "Respond in the same language as the user's most recent message."


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


def response_locale_hint(locale: str, user_text: str | None = None) -> str:
    """LLM instruction for the response language.

    The language detected from the user's message wins so replies follow the
    language the user is chatting in. The request locale is the fallback when
    detection is inconclusive; for unknown locales the model is asked to
    mirror the user's language.
    """
    detected = detect_locale(user_text or "")
    if detected is not None:
        return _RESPONSE_HINTS[detected]
    return _RESPONSE_HINTS.get(locale, _FOLLOW_USER_LANGUAGE_HINT)
