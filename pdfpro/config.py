"""Application paths and persistent user settings (language, theme, mode, recent files)."""

import json
import logging
import os
import sys

log = logging.getLogger(__name__)

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(PACKAGE_DIR, "assets", "fonts")


def _config_dir() -> str:
    """Per-user folder for settings, thumbnails and fonts added by the user."""
    if sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/PDF PRO")
    elif os.name == "nt":
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "PDF PRO")
    else:
        d = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "pdfpro")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.join(os.path.dirname(PACKAGE_DIR), ".pdfpro")
        os.makedirs(d, exist_ok=True)
    return d


CONFIG_DIR = _config_dir()
USER_FONT_DIR = os.path.join(CONFIG_DIR, "fonts")
THUMB_DIR = os.path.join(CONFIG_DIR, "thumbs")
LOG_PATH = os.path.join(CONFIG_DIR, "pdfpro.log")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
for _d in (USER_FONT_DIR, THUMB_DIR):
    os.makedirs(_d, exist_ok=True)

DEFAULT_SETTINGS = {"lang": "th", "theme": "system", "recent": [], "mode": "edit"}
MAX_RECENT = 30

#: live settings dictionary shared by the whole application
SETTINGS = dict(DEFAULT_SETTINGS)


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            SETTINGS.update(data)
    except FileNotFoundError:
        pass
    except Exception as e:  # corrupt file: keep defaults
        log.warning("cannot read settings: %s", e)
    return SETTINGS


def save_settings() -> None:
    """Write settings atomically."""
    try:
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=1)
        os.replace(tmp, SETTINGS_PATH)
    except Exception as e:
        log.warning("cannot save settings: %s", e)


load_settings()
