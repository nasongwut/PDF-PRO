"""Small helpers shared by core and UI (colors, names, OS integration)."""

import os
import re
import subprocess
import sys


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def int2hex(c):
    return "#%06x" % (c & 0xFFFFFF)


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def reveal(path):
    """show a file in Finder / Explorer"""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass


def open_folder(path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass
