"""Update notifications: ask the user once, check in the background, show a banner only when
a newer version exists, and install it when the user agrees."""

import logging
import queue
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from pdfpro import APP_NAME, REPO_URL, __version__
from pdfpro.config import SETTINGS, save_settings
from pdfpro.core import updater
from pdfpro.i18n import _, current_language
from pdfpro.ui.dialogs.about import AboutDialog, DonateDialog
from pdfpro.ui.dialogs.update_dialog import UpdateDialog
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, ACCENT_H, BORDER, HOVER, SOFT, TEXT, F

log = logging.getLogger(__name__)
STARTUP_DELAY_MS = 2500


class UpdatesMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def init_updates(self):
        self.manifest = None
        self.pending_update = None
        self._update_q = queue.Queue()
        self.after(STARTUP_DELAY_MS, self._startup_update_check)

    # ------------------------------------------------------------------ checking
    def _startup_update_check(self):
        if SETTINGS.get("update_check") is None:  # ask once
            allow = messagebox.askyesno(
                APP_NAME,
                _(
                    "อนุญาตให้ PDF PRO ตรวจหาเวอร์ชันใหม่อัตโนมัติเมื่อเปิดโปรแกรมหรือไม่?\n\n"
                    "• จะแจ้งเตือนเฉพาะเมื่อมีเวอร์ชันใหม่\n• จะติดตั้งก็ต่อเมื่อคุณกด “อัปเดตเลย” เท่านั้น\n"
                    "• เปลี่ยนได้ภายหลังที่เมนู ••• > เกี่ยวกับ PDF PRO"
                ),
            )
            SETTINGS["update_check"] = bool(allow)
            save_settings()
        if SETTINGS.get("update_check"):
            self.check_updates(manual=False)

    def check_updates(self, manual=True):
        """manual=True also reports 'up to date' and errors"""

        def work():
            try:
                manifest = updater.fetch_manifest()
                self._update_q.put((manifest, updater.parse_manifest(manifest), None, manual))
            except Exception as e:  # offline, server down…
                self._update_q.put((None, None, e, manual))

        threading.Thread(target=work, daemon=True).start()
        self.after(300, self._poll_update)
        if manual:
            self.set_status(_("กำลังตรวจหาอัปเดต…"))

    def _poll_update(self):
        try:
            manifest, info, error, manual = self._update_q.get_nowait()
        except queue.Empty:
            self.after(300, self._poll_update)
            return
        if manifest:
            self.manifest = manifest
        if error is not None:
            log.info("update check failed: %s", error)
            if manual:
                messagebox.showwarning(APP_NAME, _("ตรวจหาอัปเดตไม่ได้ (ตรวจสอบอินเทอร์เน็ต)") + "\n\n%s" % error)
            return
        if info is None:
            if manual:
                messagebox.showinfo(APP_NAME, _("คุณใช้เวอร์ชันล่าสุดแล้ว (%s)") % __version__)
            return
        if not manual and SETTINGS.get("skip_version") == info.version:
            return
        self.pending_update = info
        self.show_update_banner()

    # ------------------------------------------------------------------ banner
    def show_update_banner(self):
        info = self.pending_update
        holder = getattr(self, "banner_holder", None)
        if info is None or holder is None:
            return
        for w in holder.winfo_children():
            w.destroy()
        bar = ctk.CTkFrame(holder, fg_color=SOFT, corner_radius=0, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="", image=icon("refresh", 18, ACCENT)).pack(side="left", padx=(16, 8))
        note = info.notes_for(current_language()).strip().split("\n")[0]
        ctk.CTkLabel(
            bar,
            text=_("มี PDF PRO เวอร์ชันใหม่ %s") % info.version + ("  —  " + note[:90] if note else ""),
            font=F(13, "bold"),
            text_color=TEXT,
        ).pack(side="left")
        ctk.CTkButton(
            bar,
            text=_("ข้ามเวอร์ชันนี้"),
            width=10,
            height=28,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=TEXT,
            font=F(12),
            command=self._skip_update,
        ).pack(side="right", padx=(4, 12))
        ctk.CTkButton(
            bar,
            text=_("ไว้ทีหลัง"),
            width=10,
            height=28,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=TEXT,
            font=F(12),
            command=self.hide_update_banner,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            bar,
            text=_("อัปเดตเลย"),
            width=110,
            height=30,
            corner_radius=9,
            fg_color=ACCENT,
            hover_color=ACCENT_H,
            text_color="#ffffff",
            font=F(13, "bold"),
            command=self.start_update,
        ).pack(side="right", padx=4)
        ctk.CTkFrame(holder, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x")

    def hide_update_banner(self):
        for w in self.banner_holder.winfo_children():
            w.destroy()
        self.banner_holder.configure(height=1)

    def _skip_update(self):
        if self.pending_update:
            SETTINGS["skip_version"] = self.pending_update.version
            save_settings()
        self.hide_update_banner()

    # ------------------------------------------------------------------ installing
    def start_update(self):
        info = self.pending_update
        if info is None:
            return
        path = UpdateDialog(self, info).run()
        if not path:
            return
        for d in list(self.docs):  # never lose work
            if d.dirty:
                self.activate(d)
                if not self.confirm_discard():
                    return
        try:
            self.configure(cursor="watch")
            self.update()
            action = updater.install(path)
        except Exception as e:
            self.configure(cursor="")
            messagebox.showerror(APP_NAME, _("ติดตั้งอัปเดตไม่สำเร็จ") + "\n\n%s" % e)
            webbrowser.open(info.page or REPO_URL + "/releases/latest")
            return
        if action == "restart":
            updater.restart_source()
        self.destroy()

    # ------------------------------------------------------------------ about / donate
    def show_about(self):
        AboutDialog(self, self.manifest, on_check=lambda: self.check_updates(manual=True)).run()

    def show_donate(self):
        DonateDialog(self, self.manifest).run()
