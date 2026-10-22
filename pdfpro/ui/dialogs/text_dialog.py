"""Dialog for adding / editing a text object."""

import tkinter as tk

import customtkinter as ctk

from pdfpro.i18n import _
from pdfpro.ui.constants import orig_prefix
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.theme import ACCENT, BORDER, CARD, HOVER, MUTED, SWATCHES, TEXT, F
from pdfpro.ui.widgets import ColorRow, font_button, primary_btn, secondary_btn


class TextDialog(Modal):
    """spec: text,size,color,bold,italic,family ; fonts: list of family names ; original: label of the PDF font"""

    def __init__(self, master, title, spec, fonts=None, original=None):
        super().__init__(master, title)
        self.color = spec.get("color", "#111827")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=20, pady=18, fill="both")
        ctk.CTkLabel(body, text=title, font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            body, text=_("กด Enter เพื่อขึ้นบรรทัดใหม่ · ⌘/Ctrl + Enter เพื่อบันทึก"), font=F(12), text_color=MUTED
        ).pack(anchor="w", pady=(0, 10))
        self.txt = ctk.CTkTextbox(
            body,
            width=480,
            height=140,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            fg_color=CARD,
            text_color=TEXT,
            font=F(16),
            wrap="word",
        )
        self.txt.pack(fill="both")
        self.txt.insert("1.0", spec.get("text", ""))

        frow = ctk.CTkFrame(body, fg_color="transparent")
        frow.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(frow, text=_("ฟอนต์"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        cur = (
            orig_prefix() + original if original and spec.get("from_orig", True) else (spec.get("family") or "Sarabun")
        )
        self.font = ctk.StringVar(value=cur)
        font_button(frow, self.font, original=original).pack(side="left")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text=_("ขนาด"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        self.size = ctk.StringVar(value=("%g" % round(spec.get("size", 16), 1)))
        ctk.CTkButton(
            row,
            text="−",
            width=28,
            height=28,
            corner_radius=8,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            command=lambda: self._step(-1),
        ).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(
            row,
            textvariable=self.size,
            width=56,
            height=28,
            corner_radius=8,
            justify="center",
            border_color=BORDER,
            fg_color=CARD,
        ).pack(side="left")
        ctk.CTkButton(
            row,
            text="+",
            width=28,
            height=28,
            corner_radius=8,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            command=lambda: self._step(1),
        ).pack(side="left", padx=(2, 18))
        self.bold = ctk.BooleanVar(value=bool(spec.get("bold")))
        self.italic = ctk.BooleanVar(value=bool(spec.get("italic")))
        ctk.CTkSwitch(
            row, text=_("ตัวหนา"), variable=self.bold, progress_color=ACCENT, font=F(13), text_color=TEXT, width=90
        ).pack(side="left")
        ctk.CTkSwitch(
            row, text=_("ตัวเอียง"), variable=self.italic, progress_color=ACCENT, font=F(13), text_color=TEXT, width=90
        ).pack(side="left", padx=(8, 0))
        crow = ctk.CTkFrame(body, fg_color="transparent")
        crow.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(crow, text=_("สี"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        ColorRow(crow, SWATCHES[:6], self.color, self._setc).pack(side="left")
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(20, 0))
        primary_btn(btns, _("ตกลง"), self.ok, width=96).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=90).pack(side="right", padx=8)
        for k in ("<Command-Return>", "<Control-Return>"):
            self.bind(k, lambda e: (self.ok(), "break")[1])
        self.after(120, self._focus)

    def _focus(self):
        try:
            self.txt.focus_set()
            self.txt.tag_add("sel", "1.0", "end-1c")
        except tk.TclError:
            pass

    def _setc(self, c):
        if c:
            self.color = c

    def _step(self, d):
        try:
            v = float(self.size.get())
        except ValueError:
            v = 16
        self.size.set("%g" % max(4, min(300, v + d)))

    def ok(self):
        try:
            size = max(4.0, min(300.0, float(self.size.get())))
        except ValueError:
            size = 16.0
        f = self.font.get()
        self.result = dict(
            text=self.txt.get("1.0", "end-1c").rstrip("\n"),
            size=size,
            color=self.color,
            bold=self.bold.get(),
            italic=self.italic.get(),
            original=f.startswith(orig_prefix()),
            family=None if f.startswith(orig_prefix()) else f,
        )
        self.destroy()
