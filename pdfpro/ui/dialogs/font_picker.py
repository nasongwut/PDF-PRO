"""Searchable font picker with live preview and 'add font from file'."""

import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pymupdf as fitz
from PIL import Image

from pdfpro import APP_NAME
from pdfpro.core.fonts import fontbook
from pdfpro.core.overlay import text_css, text_html
from pdfpro.i18n import _
from pdfpro.ui.constants import orig_prefix
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.theme import ACCENT, ACCENT_H, BORDER, CARD, MUTED, TEXT, F, tc
from pdfpro.ui.widgets import primary_btn, secondary_btn

log = logging.getLogger(__name__)


class FontPicker(Modal):
    """searchable list of every font on this computer, with live preview and 'add font' button"""

    SAMPLE = "กขค ภาษาไทย สวัสดีครับ  AaBbCc 123"

    def __init__(self, master, current=None, original=None):
        super().__init__(master, _("เลือกฟอนต์"))
        self.original = original
        self.result = None
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=20, pady=18, fill="both", expand=True)
        ctk.CTkLabel(body, text=_("เลือกฟอนต์"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("ฟอนต์ทั้งหมดที่ติดตั้งในเครื่องนี้ + ฟอนต์ที่เพิ่มเข้า PDF PRO"), font=F(12), text_color=MUTED).pack(
            anchor="w", pady=(0, 10)
        )
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        self.q = ctk.StringVar()
        e = ctk.CTkEntry(
            top,
            textvariable=self.q,
            placeholder_text=_("ค้นหาฟอนต์…"),
            height=32,
            width=300,
            corner_radius=8,
            border_color=BORDER,
            fg_color=CARD,
            font=F(13),
        )
        e.pack(side="left")
        self.thai = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            top,
            text=_("เฉพาะที่รองรับภาษาไทย"),
            variable=self.thai,
            command=self.fill,
            fg_color=ACCENT,
            hover_color=ACCENT_H,
            font=F(12),
            text_color=TEXT,
        ).pack(side="left", padx=12)
        self.q.trace_add("write", lambda *a: self.fill())
        mid = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10)
        mid.pack(fill="both", expand=True, pady=(10, 0))
        self.lb = tk.Listbox(
            mid,
            height=14,
            width=58,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            font=("Helvetica", 13),
            selectbackground=ACCENT,
            selectforeground="white",
            bg=tc(CARD),
            fg=tc(TEXT),
            exportselection=False,
        )
        sb = ctk.CTkScrollbar(mid, command=self.lb.yview, width=10)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=2, pady=4)
        self.lb.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.preview())
        self.lb.bind("<Double-Button-1>", lambda e: self.ok())
        self.prev = ctk.CTkLabel(body, text="", fg_color="#ffffff", corner_radius=10, height=74)
        self.prev.pack(fill="x", pady=(10, 0))
        self.info = ctk.CTkLabel(body, text="", font=F(11), text_color=MUTED, anchor="w")
        self.info.pack(fill="x", pady=(4, 0))
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 0))
        secondary_btn(btns, _("เพิ่มฟอนต์จากไฟล์…"), self.add_font, "plus", width=170).pack(side="left")
        primary_btn(btns, _("เลือก"), self.ok, width=90).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        self.items = []
        self.current = current
        self.fill(select=current)
        self.after(150, e.focus_set)

    def fill(self, select=None):
        q = self.q.get().strip().lower()
        allf = fontbook().choices(thai_only=self.thai.get())
        self.items = []
        if self.original:
            self.items.append((orig_prefix() + self.original, True, "orig"))
        self.items += [x for x in allf if not q or q in x[0].lower()]
        self.lb.delete(0, "end")
        tags = {"bundled": "  ★", "user": "  ＋", "orig": "  ↺"}
        for name, thai, kind in self.items:
            self.lb.insert(
                "end", "  %s%s%s" % (name, _("   ไทย") if thai and kind != "orig" else "", tags.get(kind, ""))
            )
        sel = select or self.current
        idx = next((i for i, x in enumerate(self.items) if x[0] == sel), 0 if self.items else None)
        if idx is not None:
            self.lb.selection_clear(0, "end")
            self.lb.selection_set(idx)
            self.lb.see(idx)
            self.preview()

    def chosen(self):
        s = self.lb.curselection()
        return self.items[s[0]] if s else None

    def preview(self):
        it = self.chosen()
        if not it:
            return
        name, thai, kind = it
        if kind == "orig":
            self.prev.configure(
                image=None, text=_("ใช้ฟอนต์เดิมของข้อความในไฟล์ (หรือฟอนต์ที่ใกล้เคียงที่สุด)"), text_color="#374151", font=F(13)
            )
            self.info.configure(text="")
            return
        try:
            fb = fontbook()
            key, _sb, _si = fb.family_key(name)
            d = fitz.open()
            pg = d.new_page(width=520, height=64)
            arch = fitz.Archive()
            arch.add((fb.reg[key]["buf"], fb.reg[key]["file"]))
            fbk = fb.family_key("Sarabun")[0]
            arch.add((fb.reg[fbk]["buf"], fb.reg[fbk]["file"]))
            o = dict(text=self.SAMPLE, size=24, color="#111827")
            pg.insert_htmlbox(
                fitz.Rect(10, 8, 510, 60),
                text_html(o, fb.fz(key)),
                css=text_css(o, key, fbk, False, False),
                archive=arch,
            )
            pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            self.prev.configure(text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=(520, 64)))
            kinds = {
                "bundled": _("มากับโปรแกรม"),
                "builtin": _("ฟอนต์มาตรฐาน PDF"),
                "user": _("ฟอนต์ที่เพิ่มเอง"),
                "system": _("ติดตั้งในเครื่อง"),
            }
            self.info.configure(
                text="%s · %s"
                % (
                    kinds.get(kind, ""),
                    _("รองรับภาษาไทย") if thai or kind == "bundled" else _("ไม่มีอักษรไทย (จะใช้ฟอนต์ไทยเสริมให้อัตโนมัติ)"),
                )
            )
        except Exception as e:
            self.prev.configure(image=None, text=_("แสดงตัวอย่างไม่ได้") + ": %s" % e, text_color="#b91c1c")

    def add_font(self):
        ps = filedialog.askopenfilenames(
            parent=self, title=_("เลือกไฟล์ฟอนต์"), filetypes=[(_("ฟอนต์"), "*.ttf *.otf *.ttc *.TTF *.OTF *.TTC")]
        )
        added = []
        for p in ps:
            try:
                fam = fontbook().system.install(p)
                if fam:
                    added.append(fam)
            except Exception as e:
                messagebox.showerror(APP_NAME, "%s\n%s" % (os.path.basename(p), e), parent=self)
        if added:
            self.q.set("")
            self.fill(select=added[0])
            messagebox.showinfo(APP_NAME, _("เพิ่มฟอนต์แล้ว") + ":\n" + "\n".join(sorted(set(added))), parent=self)

    def ok(self):
        it = self.chosen()
        if it:
            self.result = it[0]
        self.destroy()
