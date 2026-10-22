"""Reusable widgets: tooltip, styled buttons, color swatches, font button."""

import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk

from pdfpro.i18n import _
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, ACCENT_H, BORDER, CARD, HOVER, MUTED, PANEL, SEL, TEXT, F


class Tooltip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, e=None):
        self.job = self.w.after(450, self._show)

    def _leave(self, e=None):
        if self.job:
            self.w.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def _show(self):
        if self.tip:
            return
        x = self.w.winfo_rootx() + self.w.winfo_width() // 2
        y = self.w.winfo_rooty() + self.w.winfo_height() + 6
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.configure(bg="#111827")
        tk.Label(self.tip, text=self.text, bg="#111827", fg="#ffffff", padx=8, pady=4, font=("Helvetica", 12)).pack()
        self.tip.update_idletasks()
        self.tip.geometry("+%d+%d" % (x - self.tip.winfo_width() // 2, y))


def ghost_btn(master, ico, cmd, tip=None, size=34, isz=19):
    b = ctk.CTkButton(
        master,
        text="",
        image=icon(ico, isz),
        width=size,
        height=size,
        corner_radius=9,
        fg_color="transparent",
        hover_color=HOVER,
        command=cmd,
    )
    if tip:
        Tooltip(b, tip)
    return b


def primary_btn(master, text, cmd, ico=None, **kw):
    return ctk.CTkButton(
        master,
        text=text,
        image=icon(ico, 18, "#ffffff") if ico else None,
        command=cmd,
        fg_color=ACCENT,
        hover_color=ACCENT_H,
        text_color="#ffffff",
        corner_radius=10,
        height=kw.pop("height", 36),
        font=F(14, "bold"),
        **kw,
    )


def secondary_btn(master, text, cmd, ico=None, **kw):
    return ctk.CTkButton(
        master,
        text=text,
        image=icon(ico, 18) if ico else None,
        command=cmd,
        fg_color=PANEL,
        hover_color=HOVER,
        text_color=TEXT,
        border_width=1,
        border_color=BORDER,
        corner_radius=10,
        height=kw.pop("height", 36),
        font=F(13),
        **kw,
    )


class ColorRow(ctk.CTkFrame):
    def __init__(self, master, colors, current, on_pick, allow_none=False):
        super().__init__(master, fg_color="transparent")
        self.on_pick = on_pick
        self.current = current
        self.btns = {}
        if allow_none:
            b = ctk.CTkButton(
                self,
                text="⌀",
                width=24,
                height=24,
                corner_radius=12,
                fg_color=PANEL,
                hover_color=HOVER,
                text_color=MUTED,
                border_width=2,
                font=F(13),
                border_color=ACCENT if current is None else BORDER,
                command=lambda: self.pick(None),
            )
            b.pack(side="left", padx=(0, 5))
            self.btns[None] = b
        for c in colors:
            b = ctk.CTkButton(
                self,
                text="",
                width=24,
                height=24,
                corner_radius=12,
                fg_color=c,
                hover_color=c,
                border_width=2,
                command=lambda c=c: self.pick(c),
            )
            b.pack(side="left", padx=(0, 5))
            self.btns[c] = b
        more = ctk.CTkButton(
            self,
            text="",
            image=icon("plus", 13),
            width=24,
            height=24,
            corner_radius=12,
            fg_color=CARD,
            hover_color=HOVER,
            command=self.custom,
        )
        more.pack(side="left")
        Tooltip(more, _("เลือกสีอื่น"))
        self.refresh()

    def refresh(self):
        for c, b in self.btns.items():
            on = (c or "").lower() == (self.current or "").lower() if c is not None else self.current is None
            if c is None:
                b.configure(border_color=ACCENT if on else BORDER)
            else:
                b.configure(border_color=SEL if on else BORDER)

    def pick(self, c):
        self.current = c
        self.refresh()
        self.on_pick(c)

    def custom(self):
        c = colorchooser.askcolor(self.current or "#000000", parent=self)[1]
        if c:
            self.pick(c)


def font_button(master, value_var, original=None, on_change=None, width=300):
    """a button that shows the current font and opens the FontPicker"""

    def pick():
        from pdfpro.ui.dialogs.font_picker import FontPicker  # local import: dialogs depend on widgets

        cur = value_var.get()
        r = FontPicker(master.winfo_toplevel(), current=cur, original=original).run()
        if r:
            value_var.set(r)
            btn.configure(text=_short(r))
            if on_change:
                on_change(r)

    def _short(v):
        return v if len(v) <= 34 else v[:32] + "…"

    btn = ctk.CTkButton(
        master,
        text=_short(value_var.get()),
        command=pick,
        width=width,
        height=32,
        corner_radius=8,
        fg_color=CARD,
        hover_color=HOVER,
        text_color=TEXT,
        font=F(13),
        anchor="w",
        image=icon("text", 15),
        compound="left",
        border_width=1,
        border_color=BORDER,
    )
    return btn
