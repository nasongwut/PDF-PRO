"""Main window: header, panels, layout, view/edit modes, theme and language."""

import logging
import os
import sys
import tkinter as tk

import customtkinter as ctk

from pdfpro import APP_NAME
from pdfpro.config import LOG_PATH, PACKAGE_DIR, SETTINGS, save_settings
from pdfpro.i18n import _
from pdfpro.ui.constants import HINTS, MARGIN, TOOLS
from pdfpro.ui.icons import clear_icon_cache, icon
from pdfpro.ui.mixins.editing import EditingMixin
from pdfpro.ui.mixins.files import FilesMixin
from pdfpro.ui.mixins.history import HistoryMixin
from pdfpro.ui.mixins.home import HomeMixin
from pdfpro.ui.mixins.images import ImagesMixin
from pdfpro.ui.mixins.pages import PagesMixin
from pdfpro.ui.mixins.properties import PropertiesMixin
from pdfpro.ui.mixins.tabs import TabsMixin
from pdfpro.ui.mixins.text import TextMixin
from pdfpro.ui.mixins.updates import UpdatesMixin
from pdfpro.ui.mixins.viewer import ViewerMixin
from pdfpro.ui.theme import (
    ACCENT,
    ACCENT_H,
    BG,
    BORDER,
    CANVAS,
    CARD,
    HOVER,
    MOD,
    MUTED,
    PANEL,
    TEXT,
    F,
    init_appearance,
    tc,
)
from pdfpro.ui.widgets import Tooltip, ghost_btn, primary_btn, secondary_btn
from pdfpro.ui.workspace import MultiView


class PDFProApp(
    TabsMixin,
    HomeMixin,
    HistoryMixin,
    FilesMixin,
    ViewerMixin,
    PagesMixin,
    EditingMixin,
    TextMixin,
    PropertiesMixin,
    ImagesMixin,
    UpdatesMixin,
    ctk.CTk,
):
    """The PDF PRO main window (behaviour is split over the mixins)."""

    def __init__(self, path=None):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1360x880")
        self.minsize(1040, 700)
        self.configure(fg_color=BG)
        self.docs = []  # open documents (tabs)
        self.active = None  # Document shown in the editor
        self.show_home = True
        self.multi = False  # multi-file view
        self._rebuilding = False
        self.images = {}  # image bytes used by overlay objects (shared by all tabs)
        self.drag = None
        self.thumb_imgs = {}
        self._thumb_pos = []
        self._thumb_job = None
        self.page_img = None
        self.ox = self.oy = MARGIN

        self.tool = "select"
        self.color = "#e03c43"
        self.text_color = "#111827"
        self.hl_color = "#fde047"
        self.stroke = 2.0
        self.fsize = 16.0
        self.ffamily = "TH Sarabun New"
        self.fill = None
        self._prop_armed = False
        self._prop_job = None
        self.mode = SETTINGS.get("mode", "edit") if SETTINGS.get("mode") in ("edit", "view") else "edit"
        if SETTINGS.get("theme") in ("light", "dark"):
            ctk.set_appearance_mode(SETTINGS["theme"])

        self._build_ui()
        self._layout()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        try:  # window / taskbar icon
            self._icon = tk.PhotoImage(file=os.path.join(PACKAGE_DIR, "assets", "icon.png"))
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        if sys.platform == "darwin":  # files dropped on the Dock icon / "Open with PDF PRO"
            self.createcommand("::tk::mac::OpenDocument", lambda *paths: [self.open_path(p) for p in paths])
        self.set_tool("select")
        self.update_state()
        self.init_updates()
        if path:
            self.after(150, lambda: self.open_path(path))

    def _build_ui(self):
        """create all widgets (called again after switching language)"""
        self._build_header()
        self.build_tabbar(self)
        self.tabbar.pack(fill="x")
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x")
        self.banner_holder = ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BG)
        self.banner_holder.pack(fill="x")
        if getattr(self, "pending_update", None):
            self.after(50, self.show_update_banner)

        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        self.body = body
        self.leftbox = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0, width=1)
        self.leftbox.pack(side="left", fill="y")
        self.rightbox = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0, width=1)
        self.rightbox.pack(side="right", fill="y")
        self._build_tool_rail()
        self._build_pages_panel()
        self._build_properties_panel()
        self._build_canvas()
        self._build_statusbar()
        self.apply_theme(rerender=False)

    def _build_header(self):
        """logo, file name, mode switch, zoom, page navigation and main actions"""
        hdr = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=PANEL)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x")
        hdr.grid_columnconfigure(1, weight=1)
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(16, 0), pady=12)
        logo = ctk.CTkFrame(left, fg_color="transparent", cursor="hand2")
        logo.pack(side="left")
        l1 = ctk.CTkLabel(
            logo,
            text="PDF",
            fg_color=ACCENT,
            text_color="#ffffff",
            corner_radius=7,
            width=42,
            height=28,
            font=F(13, "bold"),
        )
        l1.pack(side="left")
        l2 = ctk.CTkLabel(logo, text="PRO", text_color=TEXT, font=F(18, "bold"))
        l2.pack(side="left", padx=(7, 10))
        for w in (logo, l1, l2):
            w.bind("<Button-1>", lambda e: self.go_home())
        self.b_home = ghost_btn(left, "home", self.go_home, _("หน้าแรก"))
        self.b_home.pack(side="left", padx=(0, 8))
        self.fname = ctk.CTkLabel(left, text="", text_color=MUTED, font=F(13), anchor="w")
        self.fname.pack(side="left")

        self.mid = mid = ctk.CTkFrame(hdr, fg_color="transparent")
        mid.grid(row=0, column=1, pady=12)
        self.mode_seg = ctk.CTkSegmentedButton(
            mid,
            values=[_("ดู"), _("แก้ไข")],
            command=self._on_mode_seg,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_H,
            unselected_color=CARD,
            unselected_hover_color=HOVER,
            fg_color=CARD,
            text_color=TEXT,
            font=F(13, "bold"),
            height=32,
            width=150,
            dynamic_resizing=False,
        )
        self.mode_seg.pack(side="left", padx=(0, 14))
        self.b_undo = ghost_btn(mid, "undo", self.undo, _("เลิกทำ") + "  " + MOD + "Z")
        self.b_undo.pack(side="left")
        self.b_redo = ghost_btn(mid, "redo", self.redo, _("ทำซ้ำ") + "  ⇧" + MOD + "Z")
        self.b_redo.pack(side="left", padx=(2, 12))
        zp = ctk.CTkFrame(mid, fg_color=CARD, corner_radius=10)
        zp.pack(side="left", padx=4)
        ghost_btn(zp, "minus", lambda: self.set_zoom(self.zoom / 1.2), _("ย่อ"), 30, 16).pack(
            side="left", padx=2, pady=2
        )
        self.zoom_lbl = ctk.CTkLabel(zp, text="100%", width=52, font=F(13), text_color=TEXT)
        self.zoom_lbl.pack(side="left")
        ghost_btn(zp, "plus", lambda: self.set_zoom(self.zoom * 1.2), _("ขยาย"), 30, 16).pack(side="left", padx=2)
        ghost_btn(zp, "fit", lambda: self.fit_width(), _("พอดีความกว้าง"), 30, 16).pack(side="left", padx=(0, 2))
        pp = ctk.CTkFrame(mid, fg_color=CARD, corner_radius=10)
        pp.pack(side="left", padx=8)
        ghost_btn(pp, "left", lambda: self.goto(self.cur - 1), _("หน้าก่อนหน้า"), 30, 16).pack(side="left", padx=2, pady=2)
        self.page_var = ctk.StringVar(value="–")
        ent = ctk.CTkEntry(
            pp,
            textvariable=self.page_var,
            width=44,
            height=26,
            corner_radius=7,
            justify="center",
            border_width=0,
            fg_color=PANEL,
            font=F(13),
        )
        ent.pack(side="left")
        ent.bind("<Return>", lambda e: self._goto_entry())
        self.page_total = ctk.CTkLabel(pp, text="/ –", font=F(13), text_color=MUTED, width=40)
        self.page_total.pack(side="left", padx=(4, 0))
        ghost_btn(pp, "right", lambda: self.goto(self.cur + 1), _("หน้าถัดไป"), 30, 16).pack(side="left", padx=2)

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=12)
        self.b_lang = ctk.CTkButton(
            right,
            text="EN" if SETTINGS.get("lang") != "en" else "ไทย",
            width=40,
            height=32,
            corner_radius=9,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=TEXT,
            font=F(12, "bold"),
            command=self.toggle_lang,
        )
        self.b_lang.pack(side="left")
        Tooltip(self.b_lang, _("เปลี่ยนภาษา"))
        self.b_donate = ghost_btn(right, "heart", self.show_donate, _("สนับสนุนผู้พัฒนา (Donate)"))
        self.b_donate.configure(image=icon("heart", 19, ACCENT))
        self.b_donate.pack(side="left")
        self.b_theme = ghost_btn(right, "moon", self.toggle_theme, _("สลับโหมดมืด/สว่าง"))
        self.b_theme.pack(side="left")
        self.b_print = ghost_btn(right, "print", self.print_dialog, _("พิมพ์") + "  " + MOD + "P")
        self.b_print.pack(side="left")
        self.b_more = ghost_btn(right, "more", self.more_menu, _("เพิ่มเติม"))
        self.b_more.pack(side="left", padx=(2, 10))
        secondary_btn(right, _("เปิดไฟล์"), self.open_dialog, "open", width=110).pack(side="left")
        self.b_save = primary_btn(right, _("บันทึก PDF"), self.save, "save", width=128)
        self.b_save.pack(side="left", padx=(8, 0))

    def _build_tool_rail(self):
        """vertical tool bar on the left (edit mode)"""
        self.rail = ctk.CTkFrame(self.leftbox, width=84, corner_radius=0, fg_color=PANEL)
        self.rail.pack_propagate(False)
        self.rail_line = ctk.CTkFrame(self.leftbox, width=1, corner_radius=0, fg_color=BORDER)
        self.tool_btns = {}
        ctk.CTkFrame(self.rail, height=8, fg_color="transparent").pack()
        for key, label, sc, desc in TOOLS:
            b = ctk.CTkButton(
                self.rail,
                text=_(label),
                compound="top",
                width=70,
                height=52,
                corner_radius=11,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED,
                font=F(11),
                image=icon(key, 20),
                command=lambda k=key: self.set_tool(k),
            )
            b.pack(pady=2)
            Tooltip(b, "%s  (%s)" % (_(desc), sc))
            self.tool_btns[key] = b
        ctk.CTkFrame(self.rail, height=1, width=46, fg_color=BORDER).pack(pady=8)
        for key, label, cmd, tip in (
            ("image", _("รูปภาพ"), self.insert_image, _("แทรกรูปภาพ")),
            ("sign", _("ลายเซ็น"), self.insert_signature, _("สร้างลายเซ็น")),
        ):
            b = ctk.CTkButton(
                self.rail,
                text=_(label),
                compound="top",
                width=70,
                height=52,
                corner_radius=11,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED,
                font=F(11),
                image=icon(key, 20),
                command=cmd,
            )
            b.pack(pady=2)
            Tooltip(b, _(tip))

    def _build_pages_panel(self):
        """page thumbnails and page operations"""
        self.pages = ctk.CTkFrame(self.leftbox, width=200, corner_radius=0, fg_color=PANEL)
        self.pages.pack_propagate(False)
        self.pages_line = ctk.CTkFrame(self.leftbox, width=1, corner_radius=0, fg_color=BORDER)
        top = ctk.CTkFrame(self.pages, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text=_("หน้า"), font=F(14, "bold"), text_color=TEXT).pack(side="left")
        self.pcount = ctk.CTkLabel(top, text="", font=F(12), text_color=MUTED)
        self.pcount.pack(side="right")
        self.ops = ops = ctk.CTkFrame(self.pages, fg_color=CARD, corner_radius=10)
        opdefs = [
            ("rotl", _("หมุนซ้าย"), lambda: self.rotate_page(-90)),
            ("rotr", _("หมุนขวา"), lambda: self.rotate_page(90)),
            ("up", _("เลื่อนหน้าขึ้น"), lambda: self.move_page(-1)),
            ("down", _("เลื่อนหน้าลง"), lambda: self.move_page(1)),
            ("blank", _("แทรกหน้าว่าง"), self.insert_blank),
            ("copy", _("ทำสำเนาหน้า"), self.duplicate_page),
            ("extract", _("บันทึกหน้านี้เป็นไฟล์ใหม่"), self.extract_page),
            ("trash", _("ลบหน้า"), self.delete_page),
        ]
        for i, (ic, tip, cmd) in enumerate(opdefs):
            col = (ACCENT, "#ff6b70") if ic == "trash" else None
            b = ctk.CTkButton(
                ops,
                text="",
                image=icon(ic, 17, col),
                width=38,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=HOVER,
                command=cmd,
            )
            b.grid(row=i // 4, column=i % 4, padx=2, pady=2)
            Tooltip(b, _(tip))
        for c in range(4):
            ops.grid_columnconfigure(c, weight=1)
        self.thumb_frame = tf = ctk.CTkFrame(self.pages, fg_color="transparent")
        self.thumbs = tk.Canvas(tf, highlightthickness=0, width=184, bd=0)
        tsb = ctk.CTkScrollbar(tf, command=self.thumbs.yview, width=10)
        self.thumbs.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y", padx=(0, 2))
        self.thumbs.pack(side="left", fill="both", expand=True)
        self.thumbs.bind("<Button-1>", self.on_thumb_click)
        self._bind_wheel(self.thumbs, lambda d: self.thumbs.yview_scroll(d, "units"))

    def _build_properties_panel(self):
        """right-hand panel; its content is created by render_props()"""
        self.props_line = ctk.CTkFrame(self.rightbox, width=1, corner_radius=0, fg_color=BORDER)
        self.props = ctk.CTkFrame(self.rightbox, width=272, corner_radius=0, fg_color=PANEL)
        self.props.pack_propagate(False)
        self.props_in = ctk.CTkScrollableFrame(
            self.props,
            corner_radius=0,
            fg_color=PANEL,
            scrollbar_button_color=PANEL,
            scrollbar_button_hover_color=BORDER,
        )
        self.props_in.pack(fill="both", expand=True)

    def _build_canvas(self):
        """page canvas, home screen and multi-file view share the centre area"""
        self.center = ctk.CTkFrame(self.body, fg_color=CANVAS, corner_radius=0)
        self.center.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(self.center, highlightthickness=0, bd=0)
        vsb = ctk.CTkScrollbar(self.center, command=self.cv.yview, width=12)
        hsb = ctk.CTkScrollbar(self.center, command=self.cv.xview, orientation="horizontal", height=12)
        self.cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self.on_down)
        self.cv.bind("<B1-Motion>", self.on_move)
        self.cv.bind("<ButtonRelease-1>", self.on_up)
        self.cv.bind("<Double-Button-1>", self.on_double)
        self.cv.bind("<Button-3>", self.on_context)
        self.cv.bind("<Button-2>", self.on_context)
        self.cv.bind("<Configure>", self._on_canvas_configure)
        self._bind_wheel(self.cv, self.on_wheel)
        self.home = ctk.CTkFrame(self.center, fg_color=BG, corner_radius=0)
        self.workspace = MultiView(self.center, self)

    def _build_statusbar(self):
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x")
        sb = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=PANEL)
        sb.pack(fill="x")
        sb.pack_propagate(False)
        self.hint = ctk.CTkLabel(sb, text="", text_color=MUTED, font=F(12))
        self.hint.pack(side="left", padx=14)
        self.status = ctk.CTkLabel(sb, text="", text_color=MUTED, font=F(12))
        self.status.pack(side="right", padx=14)

    def _layout(self):
        """show/hide panels for the current state: home · single document (view/edit) · multi-file view"""
        editor = self.has_doc() and not self.show_home and not self.multi
        edit = self.mode == "edit"
        for w in (
            self.rail,
            self.rail_line,
            self.pages,
            self.pages_line,
            self.props_line,
            self.props,
            self.leftbox,
            self.rightbox,
        ):
            w.pack_forget()
        if editor:
            self.leftbox.pack(side="left", fill="y", before=self.center)
            if edit:
                self.rightbox.pack(side="right", fill="y", before=self.center)
                self.rail.pack(side="left", fill="y")
                self.rail_line.pack(side="left", fill="y")
            self.pages.pack(side="left", fill="y")
            self.pages_line.pack(side="left", fill="y")
            self.thumb_frame.pack_forget()
            self.ops.pack_forget()
            if edit:
                self.ops.pack(fill="x", padx=12, pady=(0, 8))
            self.thumb_frame.pack(fill="both", expand=True)
            if edit:
                self.props_line.pack(side="left", fill="y")
                self.props.pack(side="left", fill="y")
        self.home.place_forget()
        self.workspace.place_forget()
        if editor:
            self.mid.grid()
        else:
            self.mid.grid_remove()
            if self.multi and self.docs:
                self.workspace.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.workspace.lift()
                self.after(10, self.workspace.rebuild)
            else:
                self.build_home()
                self.home.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.home.lift()
        self.mode_seg.set(_("แก้ไข") if edit else _("ดู"))
        self.refresh_tabbar()

    def _on_mode_seg(self, v):
        self.set_mode("edit" if v == _("แก้ไข") else "view")

    def set_mode(self, m):
        self.mode = m
        SETTINGS["mode"] = m
        save_settings()
        self.sel = None
        self.pdfsel = None
        if m == "view":
            self.tool = "select"
        self._layout()
        if self.has_doc():
            self.update_idletasks()
            self.render_view(keep_scroll=True)
            self.render_props()
            self.cv.configure(
                cursor="arrow"
                if m == "view"
                else {"edittext": "xterm", "text": "xterm", "select": "arrow"}.get(self.tool, "crosshair")
            )
        self.update_state()

    def _on_canvas_configure(self, _event=None):
        if not self._rebuilding and self.editor_visible():
            self.render_view(keep_scroll=True)

    def toggle_lang(self):
        """switch Thai / English and rebuild every widget (open documents are kept)"""
        SETTINGS["lang"] = "en" if SETTINGS.get("lang") != "en" else "th"
        save_settings()
        self._rebuilding = True
        try:
            for w in self.winfo_children():
                w.destroy()
            clear_icon_cache()
            self._build_ui()
        finally:
            self._rebuilding = False
        self._layout()
        if self.editor_visible():
            self.update_idletasks()
            self.build_thumbs()
            self.render_view(keep_scroll=True)
        self.set_tool(self.tool)
        self.update_state()

    def apply_theme(self, rerender=True):
        self.cv.configure(bg=tc(CANVAS))
        self.thumbs.configure(bg=tc(PANEL))
        self.b_theme.configure(image=icon("sun" if ctk.get_appearance_mode() == "Dark" else "moon", 19))
        if rerender and self.has_doc():
            self.render_view(keep_scroll=True)
            self.build_thumbs()

    def toggle_theme(self):
        m = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(m)
        SETTINGS["theme"] = m
        save_settings()
        self.after(30, self.apply_theme)

    def more_menu(self):
        m = tk.Menu(self, tearoff=0)
        on = "normal" if self.has_doc() else "disabled"
        m.add_command(label=_("หน้าแรก (ไฟล์ล่าสุด)"), command=self.go_home, state=on)
        m.add_command(label=_("เปิดไฟล์…") + "    " + MOD + "O", command=self.open_dialog)
        m.add_command(label=_("สร้างเอกสารเปล่า"), command=self.new_blank)
        m.add_separator()
        m.add_command(label=_("บันทึก") + "    " + MOD + "S", command=self.save, state=on)
        m.add_command(label=_("บันทึกเป็น…") + "    ⇧" + MOD + "S", command=lambda: self.save(as_new=True), state=on)
        m.add_command(label=_("บันทึกหน้านี้เป็นไฟล์ใหม่…"), command=self.extract_page, state=on)
        m.add_command(label=_("พิมพ์…") + "    " + MOD + "P", command=self.print_dialog, state=on)
        m.add_separator()
        m.add_command(label=_("รวมไฟล์ PDF (เพิ่มต่อจากหน้านี้)…"), command=self.merge_dialog, state=on)
        m.add_command(label=_("ส่งออกรูปภาพทั้งหมดในไฟล์…"), command=self.export_all_images, state=on)
        m.add_command(label=_("เพิ่มฟอนต์…"), command=self.add_fonts)
        m.add_separator()
        m.add_command(label=_("สลับโหมดมืด/สว่าง"), command=self.toggle_theme)
        m.add_command(label="English" if SETTINGS.get("lang") != "en" else "ภาษาไทย", command=self.toggle_lang)
        m.add_separator()
        m.add_command(label=_("ตรวจหาอัปเดต…"), command=lambda: self.check_updates(manual=True))
        m.add_command(label=_("สนับสนุนผู้พัฒนา (Donate) ❤"), command=self.show_donate)
        m.add_command(label=_("เกี่ยวกับ PDF PRO (โปรแกรมฟรี)"), command=self.show_about)
        x = self.b_more.winfo_rootx()
        y = self.b_more.winfo_rooty() + self.b_more.winfo_height() + 4
        m.tk_popup(x, y)

    def _bind_wheel(self, widget, fn):
        def wheel(e):
            if sys.platform == "darwin":
                d = -e.delta
            else:
                d = -int(e.delta / 120) if e.delta else 0
            if d:
                fn(int(max(-6, min(6, d))))

        widget.bind("<MouseWheel>", wheel)
        widget.bind("<Button-4>", lambda e: fn(-2))
        widget.bind("<Button-5>", lambda e: fn(2))

    def _bind_keys(self):
        mods = ["Command", "Control"] if sys.platform == "darwin" else ["Control"]
        for m in mods:
            self.bind_all("<%s-o>" % m, lambda e: self.open_dialog())
            self.bind_all("<%s-s>" % m, lambda e: self.save())
            self.bind_all("<%s-S>" % m, lambda e: self.save(as_new=True))
            self.bind_all("<%s-z>" % m, lambda e: self.undo())
            self.bind_all("<%s-Z>" % m, lambda e: self.redo())
            self.bind_all("<%s-y>" % m, lambda e: self.redo())
            self.bind_all("<%s-d>" % m, lambda e: self.duplicate_obj())
            self.bind_all("<%s-p>" % m, lambda e: self.print_dialog())
            self.bind_all("<%s-w>" % m, lambda e: self.close_tab(self.active) if self.active else None)
            self.bind_all("<%s-t>" % m, lambda e: self.open_dialog())
            self.bind_all("<%s-equal>" % m, lambda e: self.set_zoom(self.zoom * 1.2))
            self.bind_all("<%s-plus>" % m, lambda e: self.set_zoom(self.zoom * 1.2))
            self.bind_all("<%s-minus>" % m, lambda e: self.set_zoom(self.zoom / 1.2))
        self.bind_all("<Control-Tab>", lambda e: self.next_tab(1))
        self.bind_all("<Control-Shift-Tab>", lambda e: self.next_tab(-1))
        if sys.platform.startswith("linux"):
            self.bind_all("<Control-ISO_Left_Tab>", lambda e: self.next_tab(-1))
        self.bind("<Key>", self.on_key)

    def set_status(self, msg=""):
        self.status.configure(text=msg)
        if getattr(self, "_status_job", None):
            self.after_cancel(self._status_job)
        if msg:
            self._status_job = self.after(6000, lambda: self.status.configure(text=""))

    def update_state(self):
        on = self.has_doc()
        edit = self.mode == "edit"
        self.b_save.configure(state="normal" if on else "disabled")
        self.b_print.configure(state="normal" if on else "disabled")
        self.b_undo.configure(state="normal" if (self.undo_stack and edit) else "disabled")
        self.b_redo.configure(state="normal" if (self.redo_stack and edit) else "disabled")
        self.b_home.configure(state="normal" if on else "disabled")
        name = os.path.basename(self.path) if self.path else (_("เอกสารใหม่") if on else "")
        self.title(("● " if self.dirty else "") + (name + " — " if name else "") + APP_NAME)
        self.fname.configure(text=(name + ("  •  " + _("ยังไม่บันทึก") if self.dirty else "")) if on else "")
        if on and not edit:
            self.hint.configure(text=_("โหมดดู — กด “แก้ไข” ด้านบนเพื่อเริ่มแก้ไข · ←/→ เปลี่ยนหน้า"))
        else:
            self.hint.configure(text=(_(HINTS.get(self.tool, "")).split("\n")[0]) if on else "")
        if on:
            self.page_var.set(str(self.cur + 1))
            self.page_total.configure(text="/ %d" % self.doc.page_count)
            self.pcount.configure(text=_("%d หน้า") % self.doc.page_count)
        self.zoom_lbl.configure(text="%d%%" % round(self.zoom * 100))


def main() -> None:
    """Entry point: ``python pdf_pro.py [file.pdf]``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )
    init_appearance(SETTINGS.get("theme", "system"))
    path = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    app = PDFProApp(path)
    app.mainloop()
