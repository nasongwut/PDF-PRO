"""Draw-your-signature dialog; returns a transparent PNG."""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import pymupdf as fitz

from pdfpro import APP_NAME
from pdfpro.i18n import _
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.theme import BORDER, MUTED, TEXT, F
from pdfpro.ui.widgets import ColorRow, primary_btn, secondary_btn
from pdfpro.utils import hex2rgb


class SignatureDialog(Modal):
    def __init__(self, master):
        super().__init__(master, _("ลายเซ็น"))
        self.strokes = []
        self.color = "#1e3a8a"
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=20, pady=18)
        ctk.CTkLabel(body, text=_("วาดลายเซ็นของคุณ"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("ใช้เมาส์หรือแทร็กแพดเซ็นชื่อในกรอบด้านล่าง"), font=F(12), text_color=MUTED).pack(
            anchor="w", pady=(0, 10)
        )
        holder = ctk.CTkFrame(body, fg_color="#ffffff", corner_radius=12, border_width=1, border_color=BORDER)
        holder.pack()
        self.cv = tk.Canvas(holder, width=560, height=220, bg="#ffffff", highlightthickness=0, cursor="crosshair")
        self.cv.pack(padx=6, pady=6)
        self.cv.create_line(30, 170, 530, 170, fill="#e5e7eb", dash=(4, 4))
        self.cv.create_text(36, 186, text="✕", fill="#cbd5e1", anchor="w")
        self.cv.bind("<ButtonPress-1>", self.down)
        self.cv.bind("<B1-Motion>", self.move)
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(14, 0))
        ColorRow(row, ["#111827", "#1e3a8a", "#2563eb", "#e03c43"], self.color, self.setc).pack(side="left")
        primary_btn(row, _("ใช้ลายเซ็นนี้"), self.ok, width=120).pack(side="right")
        secondary_btn(row, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        secondary_btn(row, _("ล้าง"), self.clear, width=70).pack(side="right")

    def setc(self, c):
        if c:
            self.color = c
            self.cv.itemconfigure("ink", fill=c)

    def down(self, e):
        self.strokes.append([(e.x, e.y)])

    def move(self, e):
        if not self.strokes:
            return
        s = self.strokes[-1]
        x0, y0 = s[-1]
        if abs(e.x - x0) + abs(e.y - y0) < 1:
            return
        s.append((e.x, e.y))
        self.cv.create_line(x0, y0, e.x, e.y, fill=self.color, width=2.6, capstyle="round", smooth=True, tags="ink")

    def clear(self):
        self.strokes = []
        self.cv.delete("ink")

    def ok(self):
        pts = [p for s in self.strokes for p in s]
        if not pts:
            messagebox.showinfo(APP_NAME, _("กรุณาเซ็นชื่อก่อน"), parent=self)
            return
        x0 = min(p[0] for p in pts) - 6
        y0 = min(p[1] for p in pts) - 6
        x1 = max(p[0] for p in pts) + 6
        y1 = max(p[1] for p in pts) + 6
        d = fitz.open()
        pg = d.new_page(width=x1 - x0, height=y1 - y0)
        col = hex2rgb(self.color)
        for s in self.strokes:
            pp = [(x - x0, y - y0) for x, y in s]
            if len(pp) == 1:
                pp.append((pp[0][0] + 0.1, pp[0][1]))
            pg.draw_polyline(pp, color=col, width=2.6, lineCap=1, lineJoin=1)
        pix = pg.get_pixmap(matrix=fitz.Matrix(4, 4), alpha=True)
        self.result = (pix.tobytes("png"), x1 - x0, y1 - y0)
        self.destroy()
