"""Document tabs: several PDFs open at once, one of them active in the editor."""

import customtkinter as ctk

from pdfpro.core.document import Document
from pdfpro.i18n import _
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, BG, BORDER, CARD, HOVER, MUTED, PANEL, SOFT, TEXT, F
from pdfpro.ui.widgets import Tooltip

# per-document attributes the rest of the UI reads/writes as if they lived on the window
_DOC_ATTRS = {
    "doc": "doc",
    "path": "path",
    "objs": "objs",
    "cur": "cur",
    "zoom": "zoom",
    "undo_stack": "undo_stack",
    "redo_stack": "redo_stack",
    "_docbytes": "docbytes",
    "dirty": "dirty",
    "_saved_once": "saved_once",
    "sel": "sel",
    "pdfsel": "pdfsel",
}
_DEFAULTS = {
    "doc": None,
    "path": None,
    "objs": [],
    "cur": 0,
    "zoom": 1.0,
    "undo_stack": [],
    "redo_stack": [],
    "_docbytes": None,
    "dirty": False,
    "_saved_once": False,
    "sel": None,
    "pdfsel": None,
}


def _delegate(name, attr):
    def getter(self):
        d = self.__dict__.get("active")
        return getattr(d, attr) if d is not None else _DEFAULTS[name]

    def setter(self, value):
        d = self.__dict__.get("active")
        if d is not None:
            setattr(d, attr, value)

    return property(getter, setter)


class TabsMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    for _n, _a in _DOC_ATTRS.items():
        locals()[_n] = _delegate(_n, _a)
    del _n, _a

    # ------------------------------------------------------------------ tab bar
    def build_tabbar(self, parent):
        self.tabbar = ctk.CTkFrame(parent, height=46, corner_radius=0, fg_color=BG)
        self.tabbar.pack_propagate(False)
        self.tabs_box = ctk.CTkScrollableFrame(
            self.tabbar,
            orientation="horizontal",
            height=40,
            fg_color=BG,
            corner_radius=0,
            scrollbar_button_color=BG,
            scrollbar_button_hover_color=BORDER,
        )
        self.tabs_box.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(2, 0))
        right = ctk.CTkFrame(self.tabbar, fg_color="transparent")
        right.pack(side="right", padx=10)
        self.b_multi = ctk.CTkButton(
            right,
            text=_("มุมมองหลายไฟล์"),
            image=icon("columns", 16),
            width=150,
            height=30,
            corner_radius=9,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=TEXT,
            border_width=1,
            border_color=BORDER,
            font=F(12),
            command=self.toggle_multi,
        )
        self.b_multi.pack(side="right")
        Tooltip(self.b_multi, _("แสดงหลายไฟล์เคียงกัน และลากหน้าข้ามไฟล์ได้"))

    def refresh_tabbar(self):
        if not hasattr(self, "tabs_box"):
            return
        for w in self.tabs_box.winfo_children():
            w.destroy()
        for d in self.docs:
            on = d is self.active and not self.show_home and not self.multi
            tab = ctk.CTkFrame(
                self.tabs_box,
                fg_color=PANEL if on else CARD,
                corner_radius=9,
                height=30,
                border_width=1,
                border_color=ACCENT if on else BORDER,
            )
            tab.pack(side="left", padx=(0, 6), pady=2)
            name = d.name or _("เอกสารใหม่")
            label = ctk.CTkLabel(
                tab,
                text=("● " if d.dirty else "") + (name if len(name) <= 28 else name[:26] + "…"),
                font=F(12, "bold" if on else "normal"),
                text_color=TEXT if on else MUTED,
                image=icon("file", 14, ACCENT if on else None),
                compound="left",
                padx=6,
            )
            label.pack(side="left", padx=(8, 0))
            close = ctk.CTkButton(
                tab,
                text="",
                image=icon("close", 12),
                width=22,
                height=22,
                corner_radius=6,
                fg_color="transparent",
                hover_color=SOFT,
                command=lambda d=d: self.close_tab(d),
            )
            close.pack(side="left", padx=(2, 4))
            for w in (tab, label):
                w.bind("<Button-1>", lambda e, d=d: self.activate(d))
                w.bind("<Button-2>", lambda e, d=d: self.close_tab(d))
            if d.path:
                Tooltip(label, d.path)
        add = ctk.CTkButton(
            self.tabs_box,
            text="",
            image=icon("plus", 15),
            width=30,
            height=30,
            corner_radius=9,
            fg_color="transparent",
            hover_color=HOVER,
            command=self.open_dialog,
        )
        add.pack(side="left", pady=2)
        Tooltip(add, _("เปิดไฟล์ในแท็บใหม่"))
        self.b_multi.configure(
            state="normal" if self.docs else "disabled",
            fg_color=SOFT if self.multi else "transparent",
            text_color=ACCENT if self.multi else TEXT,
            image=icon("columns", 16, ACCENT if self.multi else None),
        )

    # ------------------------------------------------------------------ switching
    def add_document(self, doc: Document):
        self.docs.append(doc)
        self.activate(doc)

    def find_document(self, path):
        import os

        p = os.path.abspath(path)
        return next((d for d in self.docs if d.path and os.path.abspath(d.path) == p), None)

    def activate(self, doc: Document):
        """make `doc` the document shown in the editor"""
        if self.active is not None and self.active is not doc and hasattr(self, "cv"):
            self.active.scroll = (self.cv.yview()[0], self.cv.xview()[0])
        self.active = doc
        self.show_home = False
        self.multi = False
        self.drag = None
        self._layout()
        self.update_idletasks()
        if not doc.fitted:
            self.fit_width(render=False)
            doc.fitted = True
        self.build_thumbs()
        self.render_view()
        self.cv.yview_moveto(doc.scroll[0])
        self.cv.xview_moveto(doc.scroll[1])
        self.render_props()
        self.update_state()
        self.refresh_tabbar()

    def close_tab(self, doc: Document):
        if doc.dirty:
            self.activate(doc)
            if not self.confirm_discard():
                return
        i = self.docs.index(doc)
        self.docs.remove(doc)
        if self.active is doc:
            self.active = None
            if self.docs and not self.multi:
                self.activate(self.docs[min(i, len(self.docs) - 1)])
                return
        if not self.docs:
            self.multi = False
        self._layout()
        self.update_state()
        self.refresh_tabbar()

    def next_tab(self, step=1):
        if len(self.docs) > 1 and self.active in self.docs:
            self.activate(self.docs[(self.docs.index(self.active) + step) % len(self.docs)])

    def toggle_multi(self):
        if not self.docs:
            return
        if self.multi:
            self.activate(self.active or self.docs[0])
            return
        if self.active is not None:
            self.active.scroll = (self.cv.yview()[0], self.cv.xview()[0])
        self.multi = True
        self.show_home = False
        self._layout()
        self.update_state()
        self.refresh_tabbar()
