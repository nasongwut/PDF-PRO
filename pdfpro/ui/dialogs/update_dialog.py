"""Download-and-install progress dialog for application updates."""

import threading

import customtkinter as ctk

from pdfpro import __version__
from pdfpro.core import updater
from pdfpro.i18n import _, current_language
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.theme import ACCENT, CARD, MUTED, TEXT, F
from pdfpro.ui.widgets import primary_btn, secondary_btn


class UpdateDialog(Modal):
    """Shows release notes, then downloads the update with a progress bar.

    ``result`` is the path of the verified download, or ``None`` when cancelled / failed.
    """

    def __init__(self, master, info: updater.UpdateInfo):
        super().__init__(master, _("อัปเดต PDF PRO"))
        self.info = info
        self.progress = (0, 0)
        self.error = None
        self.path = None
        self._cancel = False
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=26, pady=22, fill="both")
        ctk.CTkLabel(body, text=_("มีเวอร์ชันใหม่ %s") % info.version, font=F(18, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            body,
            text=_("เวอร์ชันที่ใช้อยู่ %s") % __version__ + (" · " + info.released if info.released else ""),
            font=F(12),
            text_color=MUTED,
        ).pack(anchor="w", pady=(0, 10))
        notes = info.notes_for(current_language()) or _("ปรับปรุงและแก้ไขข้อผิดพลาด")
        box = ctk.CTkTextbox(
            body, width=440, height=140, corner_radius=10, fg_color=CARD, text_color=TEXT, font=F(13), wrap="word"
        )
        box.insert("1.0", notes)
        box.configure(state="disabled")
        box.pack(fill="x")
        self.bar = ctk.CTkProgressBar(body, progress_color=ACCENT, height=10)
        self.bar.set(0)
        self.status = ctk.CTkLabel(
            body, text=_("โปรแกรมจะดาวน์โหลด ตรวจสอบไฟล์ แล้วติดตั้งให้อัตโนมัติ"), font=F(12), text_color=MUTED
        )
        self.status.pack(anchor="w", pady=(12, 4))
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(12, 0))
        self.b_go = primary_btn(btns, _("ดาวน์โหลดและติดตั้ง"), self.start, "save", width=190)
        self.b_go.pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.cancel, width=90).pack(side="right", padx=8)

    def start(self):
        self.b_go.configure(state="disabled")
        self.bar.pack(fill="x", before=self.status)
        self.status.configure(text=_("กำลังดาวน์โหลด…"))
        threading.Thread(target=self._work, daemon=True).start()
        self.after(150, self._poll)

    def _work(self):
        try:
            self.path = updater.download(
                self.info.url,
                sha256=self.info.sha256,
                progress=lambda d, t: setattr(self, "progress", (d, t)),
                cancelled=lambda: self._cancel,
            )
        except Exception as e:
            self.error = e

    def _poll(self):
        if not self.winfo_exists():
            return
        done, total = self.progress
        if total:
            self.bar.set(done / total)
            self.status.configure(text=_("กำลังดาวน์โหลด… %.1f / %.1f MB") % (done / 1e6, total / 1e6))
        if self.error is not None:
            self.status.configure(text=_("ดาวน์โหลดไม่สำเร็จ") + ": %s" % self.error, text_color=ACCENT)
            self.b_go.configure(state="normal", text=_("ลองอีกครั้ง"))
            self.error = None
            return
        if self.path:
            self.result = self.path
            self.destroy()
            return
        self.after(150, self._poll)

    def cancel(self):
        self._cancel = True
        self.destroy()
