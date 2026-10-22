"""Translation helper.

UI strings are written in Thai in the source code and wrapped with ``_()``.
When the language is English they are looked up in :data:`pdfpro.locales.en.EN`;
missing entries fall back to the Thai text.
"""

from .config import SETTINGS
from .locales.en import EN

__all__ = ["_", "current_language", "set_language", "LANGUAGES"]

LANGUAGES = ("th", "en")


def current_language() -> str:
    return SETTINGS.get("lang", "th")


def set_language(lang: str) -> None:
    if lang in LANGUAGES:
        SETTINGS["lang"] = lang


def _(text: str) -> str:
    """Translate a Thai UI string to the current language."""
    if SETTINGS.get("lang") == "en":
        return EN.get(text, text)
    return text
