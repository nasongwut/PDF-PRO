"""Print options dialog (printer, page range, copies)."""

from tkinter import messagebox

import customtkinter as ctk

from pdfpro import APP_NAME
from pdfpro.core.printing import list_printers
from pdfpro.i18n import _
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.theme import ACCENT, BORDER, CARD, HOVER, MUTED, PANEL, TEXT, F
from pdfpro.ui.widgets import primary_btn, secondary_btn


class PrintDialog(Modal):
    def __init__(self, master, n_pages, cur):
        super().__init__(master, _("พิมพ์"))
        self.n = n_pages
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=22, pady=18, fill="both")
        ctk.CTkLabel(body, text=_("พิมพ์เอกสาร"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("งานที่แก้ไขไว้ทั้งหมดจะถูกพิมพ์ด้วย"), font=F(12), text_color=MUTED).pack(
            anchor="w", pady=(0, 14)
        )
        self.printers, default = list_printers()
        self.printer = ctk.StringVar(value=default or (self.printers[0] if self.printers else _("เครื่องพิมพ์เริ่มต้น")))
        r1 = ctk.CTkFrame(body, fg_color="transparent")
        r1.pack(fill="x", pady=4)
        ctk.CTkLabel(r1, text=_("เครื่องพิมพ์"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(side="left")
        ctk.CTkOptionMenu(
            r1,
            values=self.printers or [_("เครื่องพิมพ์เริ่มต้น")],
            variable=self.printer,
            width=300,
            height=32,
            corner_radius=8,
            fg_color=CARD,
            button_color=CARD,
            button_hover_color=HOVER,
            text_color=TEXT,
            dropdown_fg_color=PANEL,
            dropdown_text_color=TEXT,
            dropdown_hover_color=HOVER,
            font=F(13),
        ).pack(side="left")
        r2 = ctk.CTkFrame(body, fg_color="transparent")
        r2.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(r2, text=_("หน้า"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(
            side="left", anchor="n"
        )
        opts = ctk.CTkFrame(r2, fg_color="transparent")
        opts.pack(side="left")
        self.which = ctk.StringVar(value="all")
        ctk.CTkRadioButton(
            opts,
            text=_("ทั้งหมด") + " (%d)" % n_pages,
            variable=self.which,
            value="all",
            fg_color=ACCENT,
            font=F(13),
            text_color=TEXT,
        ).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(
            opts,
            text=_("หน้าปัจจุบัน") + " (%d)" % (cur + 1),
            variable=self.which,
            value="cur",
            fg_color=ACCENT,
            font=F(13),
            text_color=TEXT,
        ).pack(anchor="w", pady=2)
        rr = ctk.CTkFrame(opts, fg_color="transparent")
        rr.pack(anchor="w", pady=2)
        ctk.CTkRadioButton(
            rr, text=_("กำหนดเอง"), variable=self.which, value="range", fg_color=ACCENT, font=F(13), text_color=TEXT
        ).pack(side="left")
        self.range = ctk.StringVar(value="1-%d" % n_pages)
        re_ = ctk.CTkEntry(
            rr,
            textvariable=self.range,
            width=130,
            height=28,
            corner_radius=7,
            border_color=BORDER,
            fg_color=CARD,
            placeholder_text="1-3, 5",
        )
        re_.pack(side="left", padx=6)
        re_.bind("<FocusIn>", lambda e: self.which.set("range"))
        self.cur = cur
        r3 = ctk.CTkFrame(body, fg_color="transparent")
        r3.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(r3, text=_("จำนวนชุด"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(side="left")
        self.copies = ctk.StringVar(value="1")
        ctk.CTkEntry(
            r3,
            textvariable=self.copies,
            width=60,
            height=28,
            corner_radius=7,
            justify="center",
            border_color=BORDER,
            fg_color=CARD,
        ).pack(side="left")
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(20, 0))
        primary_btn(btns, _("พิมพ์"), lambda: self.done(False), "print", width=100).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        ctk.CTkButton(
            btns,
            text=_("ใช้หน้าต่างพิมพ์ของระบบ…"),
            command=lambda: self.done(True),
            fg_color="transparent",
            hover_color=HOVER,
            text_color=("#2563eb", "#7aa7ff"),
            font=F(12),
            width=10,
        ).pack(side="left")
        if not self.printers:
            ctk.CTkLabel(body, text=_("ไม่พบรายชื่อเครื่องพิมพ์ — จะใช้หน้าต่างพิมพ์ของระบบ"), font=F(11), text_color=MUTED).pack(
                anchor="w", pady=(8, 0)
            )

    def pages(self):
        w = self.which.get()
        if w == "all":
            return list(range(self.n))
        if w == "cur":
            return [self.cur]
        out = []
        for part in self.range.get().replace(" ", "").split(","):
            if not part:
                continue
            try:
                if "-" in part:
                    a, b = part.split("-", 1)
                    a = int(a) if a else 1
                    b = int(b) if b else self.n
                    out += list(range(max(1, a), min(self.n, b) + 1))
                else:
                    out.append(int(part))
            except ValueError:
                return None
        out = [p - 1 for p in out if 1 <= p <= self.n]
        return out or None

    def done(self, system):
        pages = self.pages()
        if not pages:
            messagebox.showerror(APP_NAME, _("ช่วงหน้าไม่ถูกต้อง"), parent=self)
            return
        try:
            copies = max(1, min(99, int(self.copies.get())))
        except ValueError:
            copies = 1
        self.result = dict(
            pages=pages,
            copies=copies,
            system=system or not self.printers,
            printer=self.printer.get() if self.printers else None,
        )
        self.destroy()
