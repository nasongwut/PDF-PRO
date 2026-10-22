"""Home screen with recently opened files."""

import os
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

import customtkinter as ctk
import pymupdf as fitz
from PIL import Image

from pdfpro import APP_NAME, REPO_URL, __version__
from pdfpro.config import SETTINGS, THUMB_DIR, save_settings
from pdfpro.i18n import _
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, BG, BORDER, CARD, HOVER, MUTED, PANEL, SOFT, TEXT, F
from pdfpro.ui.widgets import Tooltip
from pdfpro.utils import reveal


class HomeMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def build_home(self):
        for w in self.home.winfo_children():
            w.destroy()
        wrap = ctk.CTkScrollableFrame(
            self.home, fg_color=BG, corner_radius=0, scrollbar_button_color=BG, scrollbar_button_hover_color=BORDER
        )
        wrap.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(wrap, fg_color="transparent")
        inner.pack(fill="x", padx=48, pady=(36, 30))
        ctk.CTkLabel(inner, text=_("ยินดีต้อนรับสู่ PDF PRO"), font=F(26, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            inner, text=_("เปิด แก้ไข และพิมพ์ไฟล์ PDF — ทุกอย่างทำงานในเครื่องของคุณ"), font=F(14), text_color=MUTED
        ).pack(anchor="w", pady=(2, 10))
        badges = ctk.CTkFrame(inner, fg_color="transparent")
        badges.pack(anchor="w", pady=(0, 22))
        ctk.CTkLabel(
            badges,
            text=_("✓ ฟรี 100% · ไม่มีโฆษณา"),
            font=F(12, "bold"),
            text_color=ACCENT,
            fg_color=SOFT,
            corner_radius=12,
            height=26,
        ).pack(side="left", ipadx=10)
        ctk.CTkButton(
            badges,
            text="github.com/nasongwut/PDF-PRO",
            image=icon("star", 14),
            width=10,
            height=26,
            corner_radius=12,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            font=F(12),
            command=lambda: webbrowser.open(REPO_URL),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            badges,
            text=_("สนับสนุนผู้พัฒนา"),
            image=icon("heart", 14, ACCENT),
            width=10,
            height=26,
            corner_radius=12,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            font=F(12),
            command=self.show_donate,
        ).pack(side="left")
        ctk.CTkLabel(badges, text="v" + __version__, font=F(11), text_color=MUTED).pack(side="left", padx=10)
        acts = ctk.CTkFrame(inner, fg_color="transparent")
        acts.pack(fill="x")
        for ic, title, sub, cmd, accent in (
            ("open", _("เปิดไฟล์ PDF"), _("เลือกไฟล์จากเครื่อง"), self.open_dialog, True),
            ("blank", _("สร้างเอกสารเปล่า"), _("เริ่มจากหน้าว่าง A4"), self.new_blank, False),
            ("merge", _("รวมไฟล์ PDF"), _("รวมหลายไฟล์เป็นไฟล์เดียว"), self.merge_new, False),
        ):
            card = ctk.CTkFrame(
                acts,
                fg_color=PANEL,
                corner_radius=16,
                border_width=1,
                border_color=BORDER,
                width=250,
                height=92,
                cursor="hand2",
            )
            card.pack(side="left", padx=(0, 14))
            card.pack_propagate(False)
            badge = ctk.CTkFrame(card, fg_color=ACCENT if accent else SOFT, corner_radius=12, width=48, height=48)
            badge.pack(side="left", padx=(18, 12))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text="", image=icon(ic, 22, "#ffffff" if accent else ACCENT)).pack(expand=True)
            tx = ctk.CTkFrame(card, fg_color="transparent")
            tx.pack(side="left")
            a = ctk.CTkLabel(tx, text=_(title), font=F(15, "bold"), text_color=TEXT, anchor="w")
            a.pack(anchor="w")
            b = ctk.CTkLabel(tx, text=_(sub), font=F(12), text_color=MUTED, anchor="w")
            b.pack(anchor="w")
            for w in (card, badge, tx, a, b):
                w.bind("<Button-1>", lambda e, c=cmd: c())
            for w in badge.winfo_children():
                w.bind("<Button-1>", lambda e, c=cmd: c())

        rec = [r for r in SETTINGS.get("recent", []) if isinstance(r, dict) and r.get("path")]
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(34, 12))
        ctk.CTkLabel(row, text=_("ไฟล์ล่าสุด"), font=F(18, "bold"), text_color=TEXT).pack(side="left")
        if rec:
            ctk.CTkButton(
                row,
                text=_("ล้างรายการ"),
                width=90,
                height=28,
                corner_radius=8,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED,
                font=F(12),
                command=self.clear_recent,
            ).pack(side="right")
        if not rec:
            empty = ctk.CTkFrame(inner, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
            empty.pack(fill="x")
            ctk.CTkLabel(empty, text="", image=icon("file", 34, MUTED)).pack(pady=(30, 6))
            ctk.CTkLabel(empty, text=_("ยังไม่มีไฟล์ที่เปิดล่าสุด"), font=F(14, "bold"), text_color=TEXT).pack()
            ctk.CTkLabel(empty, text=_("ไฟล์ที่คุณเปิดจะแสดงที่นี่ เพื่อเปิดซ้ำได้ในคลิกเดียว"), font=F(12), text_color=MUTED).pack(
                pady=(2, 30)
            )
            return
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        cols = max(2, min(6, (self.center.winfo_width() - 96) // 196 or 4))
        for i, r in enumerate(rec[:18]):
            self._recent_card(grid, r).grid(row=i // cols, column=i % cols, padx=(0, 16), pady=(0, 16), sticky="n")

    def _recent_card(self, master, r):
        path = r["path"]
        exists = os.path.exists(path)
        card = ctk.CTkFrame(
            master,
            fg_color=PANEL,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
            width=180,
            height=262,
            cursor="hand2" if exists else "",
        )
        card.pack_propagate(False)
        holder = ctk.CTkFrame(card, fg_color=CARD, corner_radius=10, width=156, height=170)
        holder.pack(pady=(12, 8))
        holder.pack_propagate(False)
        img = self._recent_thumb(path) if exists else None
        if img is not None:
            lab = ctk.CTkLabel(holder, text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=img.size))
        else:
            lab = ctk.CTkLabel(
                holder,
                text=_("ไม่พบไฟล์") if not exists else "",
                image=icon("file", 34, MUTED),
                compound="top",
                font=F(11),
                text_color=MUTED,
            )
        lab.pack(expand=True)
        name = os.path.basename(path)
        n = ctk.CTkLabel(
            card,
            text=name if len(name) <= 24 else name[:22] + "…",
            font=F(13, "bold"),
            text_color=TEXT if exists else MUTED,
            anchor="w",
        )
        n.pack(fill="x", padx=12)
        folder = os.path.basename(os.path.dirname(path)) or os.path.dirname(path)
        when = time.strftime("%d/%m/%Y %H:%M", time.localtime(r.get("t", 0))) if r.get("t") else ""
        m = ctk.CTkLabel(
            card, text="📁 %s\n%s" % (folder[:22], when), font=F(11), text_color=MUTED, anchor="w", justify="left"
        )
        m.pack(fill="x", padx=12, pady=(2, 0))
        Tooltip(card, path)

        def openit(e=None):
            if exists:
                self.open_path(path)
            else:
                self.remove_recent(path)

        def menu(e):
            mm = tk.Menu(self, tearoff=0)
            if exists:
                mm.add_command(label=_("เปิด"), command=openit)
                mm.add_command(label=_("แสดงในโฟลเดอร์"), command=lambda: reveal(path))
            mm.add_command(label=_("ลบออกจากรายการ"), command=lambda: self.remove_recent(path))
            mm.tk_popup(e.x_root, e.y_root)

        for w in (card, holder, lab, n, m):
            w.bind("<Button-1>", openit)
            w.bind("<Button-3>", menu)
            w.bind("<Button-2>", menu)
        return card

    def _thumb_path(self, path):
        try:
            st = os.stat(path)
        except OSError:
            return None
        import hashlib

        h = hashlib.md5(("%s|%s|%s" % (path, st.st_mtime, st.st_size)).encode("utf-8")).hexdigest()
        return os.path.join(THUMB_DIR, h + ".png")

    def _recent_thumb(self, path):
        tp = self._thumb_path(path)
        if not tp:
            return None
        try:
            if not os.path.exists(tp):
                d = fitz.open(path)
                if d.needs_pass:
                    return None
                pg = d[0]
                s = min(150 / pg.rect.width, 164 / pg.rect.height)
                pg.get_pixmap(matrix=fitz.Matrix(s * 2, s * 2), alpha=False).save(tp)
            img = Image.open(tp)
            img.load()
            w, h = img.size
            sc = min(150 / w, 164 / h)
            img = img.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS) if sc < 1 else img
            return img
        except Exception:
            return None

    def add_recent(self, path):
        if not path:
            return
        path = os.path.abspath(path)
        rec = [r for r in SETTINGS.get("recent", []) if isinstance(r, dict) and r.get("path") != path]
        rec.insert(0, {"path": path, "t": time.time()})
        SETTINGS["recent"] = rec[:30]
        save_settings()

    def remove_recent(self, path):
        SETTINGS["recent"] = [r for r in SETTINGS.get("recent", []) if r.get("path") != path]
        save_settings()
        self.build_home()

    def clear_recent(self):
        if messagebox.askyesno(APP_NAME, _("ล้างรายการไฟล์ล่าสุดทั้งหมดหรือไม่?")):
            SETTINGS["recent"] = []
            save_settings()
            self.build_home()

    def go_home(self):
        """show the home screen; open tabs stay open"""
        if self.active is not None and not self.multi:
            self.active.scroll = (self.cv.yview()[0], self.cv.xview()[0])
        self.show_home = True
        self.multi = False
        self._layout()
        self.update_state()
