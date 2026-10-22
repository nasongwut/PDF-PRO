"""Base class for modal dialogs."""

import tkinter as tk

import customtkinter as ctk

from pdfpro.ui.theme import PANEL


class Modal(ctk.CTkToplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=PANEL)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.bind("<Escape>", lambda e: self.destroy())

    def run(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + m.winfo_width() // 2 - self.winfo_reqwidth() // 2
        y = m.winfo_rooty() + max(80, m.winfo_height() // 2 - self.winfo_reqheight() // 2 - 60)
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        self.after(60, self._grab)
        self.wait_window()
        return self.result

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass
