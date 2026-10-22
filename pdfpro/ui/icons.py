"""Line icons rendered from inline SVG with MuPDF (sharp on Retina / HiDPI, no image files needed)."""

import customtkinter as ctk
import pymupdf as fitz
from PIL import Image

ICONS = {
    "select": '<path d="M5 3l6 17 2.5-7 7-2.5z"/>',
    "text": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "edittext": '<path d="M3 7V5h11v2M8.5 5v12M6.5 17h4"/><path d="M13.5 21l.8-3.3 5.7-5.7 2.5 2.5-5.7 5.7z"/>',
    "whiteout": '<path d="M7 20h12"/><path d="M5.2 14.8l8.6-8.6a1.8 1.8 0 012.5 0l2.5 2.5a1.8 1.8 0 010 2.5L11 19H8.4l-3.2-3.2a.9.9 0 010-1z"/>',
    "ink": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
    "highlight": '<path d="M9 11l-5 5v3h3l5-5"/><path d="M9 11l6-6 4 4-6 6z"/><path d="M14 21h7"/>',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="2"/>',
    "line": '<path d="M5 19L19 5"/>',
    "arrow": '<path d="M5 19L19 5M9 5h10v10"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5L6 20"/>',
    "sign": '<path d="M3 17c3 0 4-9 6-9s1 8 3 8 2-4 4-4 1 3 5 3"/><path d="M3 21h18"/>',
    "open": '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    "save": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 000 12h3"/>',
    "minus": '<path d="M6 12h12"/>',
    "plus": '<path d="M12 6v12M6 12h12"/>',
    "fit": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "left": '<path d="M15 6l-6 6 6 6"/>',
    "right": '<path d="M9 6l6 6-6 6"/>',
    "moon": '<path d="M20.5 13.2A8.5 8.5 0 1110.8 3.5a6.6 6.6 0 009.7 9.7z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M2.5 12h2M19.5 12h2M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "more": '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
    "rotl": '<path d="M3 4v5h5"/><path d="M3.6 9a8.5 8.5 0 112 8.6"/>',
    "rotr": '<path d="M21 4v5h-5"/><path d="M20.4 9a8.5 8.5 0 10-2 8.6"/>',
    "up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "blank": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>',
    "extract": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M12 10v7M9 14l3 3 3-3"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "merge": '<path d="M14 3H8a2 2 0 00-2 2v11a2 2 0 002 2h9a2 2 0 002-2V8z"/><path d="M14 3v5h5"/><path d="M3 8v11a2 2 0 002 2h9"/>',
    "file": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "front": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 012-2h10"/>',
    "back": '<rect x="4" y="4" width="12" height="12" rx="2"/><path d="M20 8v10a2 2 0 01-2 2H8"/>',
    "columns": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "heart": '<path d="M12 20s-7-4.4-9.2-8.6C1.2 8.3 3 5 6.3 5c2 0 3.2 1.1 3.7 2 .5-.9 1.7-2 3.7-2C17 5 18.8 8.3 17.2 11.4 15 15.6 12 20 12 20z" transform="translate(1.5 0)"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "refresh": '<path d="M20 11a8 8 0 00-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0014.3 4.9L20 16M20 20v-4h-4"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "print": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "export": '<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 14v5a2 2 0 002 2h10a2 2 0 002-2v-5"/>',
    "replace": '<path d="M4 7h11l-3-3M20 17H9l3 3"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
}

_svg_cache = {}


def _svg(name, color, px):
    key = (name, color, px)
    if key not in _svg_cache:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
            'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
        ) % (color, ICONS[name])
        pix = fitz.open("svg", svg.encode())[0].get_pixmap(matrix=fitz.Matrix(px / 24, px / 24), alpha=True)
        _svg_cache[key] = Image.frombytes("RGBa", (pix.width, pix.height), pix.samples).convert("RGBA")
    return _svg_cache[key]


def icon(name, size=20, color=None):
    """CTkImage for both themes (rendered at 3x for sharp Retina display)"""
    if color is None:
        light, dark = "#374151", "#d4d7dd"
    elif isinstance(color, tuple):
        light, dark = color
    else:
        light = dark = color
    return ctk.CTkImage(
        light_image=_svg(name, light, size * 3), dark_image=_svg(name, dark, size * 3), size=(size, size)
    )


def clear_icon_cache():
    """drop rendered icons (e.g. after switching theme or language)"""
    _svg_cache.clear()
