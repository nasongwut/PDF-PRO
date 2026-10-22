"""Design tokens (colors, fonts) shared by every widget. Tuples are (light, dark)."""

import sys

import customtkinter as ctk


def init_appearance(mode: str = "system") -> None:
    """call once before creating the main window"""
    ctk.set_appearance_mode(mode if mode in ("light", "dark", "system") else "system")
    ctk.set_default_color_theme("blue")


ACCENT = "#e03c43"
ACCENT_H = "#c4323a"
BG = ("#f3f4f6", "#0f1115")
PANEL = ("#ffffff", "#181b21")
BORDER = ("#e6e8ec", "#272b33")
TEXT = ("#111827", "#e7e9ec")
MUTED = ("#6b7280", "#9aa1ad")
HOVER = ("#f1f2f5", "#23272e")
SOFT = ("#fdecec", "#3a1e22")
CANVAS = ("#e7e9ee", "#0b0d10")
SHADOW = ("#d3d6dc", "#050607")
CARD = ("#f6f7f9", "#20242b")
SEL = "#3b82f6"
MOD = "⌘" if sys.platform == "darwin" else "Ctrl+"
SWATCHES = ["#111827", "#e03c43", "#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#ffffff"]
HL_SWATCHES = ["#fde047", "#86efac", "#7dd3fc", "#f9a8d4", "#fdba74"]


def tc(pair):
    if isinstance(pair, str):
        return pair
    return pair[0] if ctk.get_appearance_mode() == "Light" else pair[1]


def F(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)
