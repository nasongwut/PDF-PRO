"""About / Donate dialogs: free-software notice, credit to the project and donation links."""

import webbrowser

import customtkinter as ctk

from pdfpro import APP_NAME, DONATE_URL, LICENSE_NAME, REPO_URL, __version__
from pdfpro.config import SETTINGS, save_settings
from pdfpro.core.updater import donate_links
from pdfpro.i18n import _
from pdfpro.ui.dialogs.base import Modal
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, ACCENT_H, CARD, MUTED, SOFT, TEXT, F
from pdfpro.ui.widgets import primary_btn, secondary_btn

LINK = ("#2563eb", "#7aa7ff")


def _link(master, text, url):
    b = ctk.CTkButton(
        master,
        text=text,
        command=lambda: webbrowser.open(url),
        fg_color="transparent",
        hover=False,
        text_color=LINK,
        font=F(13, "bold"),
        height=22,
        width=10,
        anchor="w",
    )
    return b


class AboutDialog(Modal):
    """version, 'free' notice, credit, update preference"""

    def __init__(self, master, manifest=None, on_check=None):
        super().__init__(master, _("เกี่ยวกับ PDF PRO"))
        self.manifest, self.on_check = manifest, on_check
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=28, pady=24)
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(
            top,
            text="PDF",
            fg_color=ACCENT,
            text_color="#ffffff",
            corner_radius=9,
            width=56,
            height=38,
            font=F(17, "bold"),
        ).pack(side="left")
        tt = ctk.CTkFrame(top, fg_color="transparent")
        tt.pack(side="left", padx=12)
        ctk.CTkLabel(tt, text=APP_NAME, font=F(22, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(tt, text=_("เวอร์ชัน") + " " + __version__, font=F(12), text_color=MUTED).pack(anchor="w")

        free = ctk.CTkFrame(body, fg_color=SOFT, corner_radius=12)
        free.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(free, text=_("✓ โปรแกรมฟรี 100%"), font=F(16, "bold"), text_color=ACCENT).pack(
            anchor="w", padx=16, pady=(12, 2)
        )
        ctk.CTkLabel(
            free,
            text=_(
                "ใช้งานได้ฟรีทั้งส่วนตัว หน่วยงาน และองค์กร ไม่มีค่าใช้จ่าย ไม่มีโฆษณา\nไม่มีการเก็บข้อมูล — ไฟล์ทั้งหมดประมวลผลในเครื่องของคุณ"
            ),
            font=F(12),
            text_color=TEXT,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        cr = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12)
        cr.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(cr, text=_("เครดิต / ซอร์สโค้ด"), font=F(12), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(10, 0)
        )
        _link(cr, REPO_URL, REPO_URL).pack(anchor="w", padx=12)
        ctk.CTkLabel(
            cr,
            text=_("สัญญาอนุญาต") + ": " + LICENSE_NAME + "\n" + _("สร้างด้วย Python · CustomTkinter · PyMuPDF"),
            font=F(11),
            text_color=MUTED,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(2, 10))

        upd = ctk.CTkFrame(body, fg_color="transparent")
        upd.pack(fill="x", pady=(14, 0))
        self.auto = ctk.BooleanVar(value=bool(SETTINGS.get("update_check")))
        ctk.CTkSwitch(
            upd,
            text=_("ตรวจหาเวอร์ชันใหม่อัตโนมัติเมื่อเปิดโปรแกรม"),
            variable=self.auto,
            command=self._toggle,
            progress_color=ACCENT,
            font=F(12),
            text_color=TEXT,
        ).pack(side="left")
        if on_check:
            secondary_btn(upd, _("ตรวจหาอัปเดต"), self._check, "refresh", height=30, width=130).pack(side="right")

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(20, 0))
        primary_btn(btns, _("สนับสนุนผู้พัฒนา"), self._donate, "heart", width=170).pack(side="left")
        secondary_btn(btns, _("ปิด"), self.destroy, width=80).pack(side="right")

    def _toggle(self):
        SETTINGS["update_check"] = bool(self.auto.get())
        save_settings()

    def _check(self):
        self.destroy()
        self.on_check()

    def _donate(self):
        self.destroy()
        DonateDialog(self.master, self.manifest).run()


class DonateDialog(Modal):
    """thank-you message with the donation links from the update manifest"""

    def __init__(self, master, manifest=None):
        super().__init__(master, _("สนับสนุนผู้พัฒนา"))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=28, pady=24)
        badge = ctk.CTkFrame(body, fg_color=SOFT, corner_radius=20, width=64, height=64)
        badge.pack()
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon("heart", 30, ACCENT)).pack(expand=True)
        ctk.CTkLabel(body, text=_("ขอบคุณที่ใช้ PDF PRO ❤"), font=F(18, "bold"), text_color=TEXT).pack(pady=(12, 4))
        ctk.CTkLabel(
            body,
            text=_(
                "PDF PRO เป็นโปรแกรมฟรีและจะฟรีตลอดไป\nถ้าโปรแกรมมีประโยชน์ คุณช่วยสนับสนุนได้ตามกำลัง หรือกดดาว ⭐ ให้โปรเจกต์บน GitHub"
            ),
            font=F(12),
            text_color=MUTED,
            justify="center",
        ).pack()
        links = ctk.CTkFrame(body, fg_color="transparent")
        links.pack(fill="x", pady=(18, 0))
        for d in donate_links(manifest, DONATE_URL):
            ctk.CTkButton(
                links,
                text=d.get("label") or "Donate",
                image=icon("heart", 16, "#ffffff"),
                command=lambda u=d["url"]: webbrowser.open(u),
                fg_color=ACCENT,
                hover_color=ACCENT_H,
                text_color="#ffffff",
                corner_radius=10,
                height=38,
                font=F(14, "bold"),
            ).pack(fill="x", pady=3)
        secondary_btn(links, _("ให้ดาว ⭐ บน GitHub"), lambda: webbrowser.open(REPO_URL), "star", height=36).pack(
            fill="x", pady=3
        )
        secondary_btn(body, _("ปิด"), self.destroy, width=80).pack(pady=(16, 0))
