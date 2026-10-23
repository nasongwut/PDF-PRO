"""Page context menu and page clipboard: duplicate · cut · copy · paste · rotate · split · delete.

Used by the page thumbnails of the editor and by the columns of the multi-file view. The clipboard
is a small in-memory :class:`~pdfpro.core.document.Document`, so pages can be pasted into any open
file (overlay objects travel with them).
"""

import sys
import tkinter as tk
from tkinter import messagebox

from pdfpro import APP_NAME
from pdfpro.core.document import (
    Document,
    delete_pages,
    duplicate_pages,
    extract_pages,
    page_range_label,
    rotate_pages,
    transfer_pages,
)
from pdfpro.i18n import _

ACCEL = "⌘" if sys.platform == "darwin" else "Ctrl+"
DEL_KEY = "⌫" if sys.platform == "darwin" else "Del"
#: right mouse button (macOS: Button-2 and Control+click)
RIGHT_CLICK = ("<Button-2>", "<Control-Button-1>") if sys.platform == "darwin" else ("<Button-3>",)


class PageActionsMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    page_clipboard = None  # Document holding cut / copied pages

    # ------------------------------------------------------------------ menu
    def page_menu(self, event, doc: Document, pages, index):
        """right-click menu for ``pages`` of ``doc``; ``index`` is the page under the mouse"""
        pages = sorted(pages) or [index]
        n = len(pages)
        what = _("หน้า %d") % (pages[0] + 1) if n == 1 else _("%d หน้า") % n
        clip = self.page_clipboard
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="%s  (%s)" % (_("หน้าที่เลือก"), what), state="disabled")
        m.add_separator()
        m.add_command(
            label=_("ทำสำเนา (Duplicate)"), accelerator=ACCEL + "D", command=lambda: self.pages_duplicate(doc, pages)
        )
        m.add_command(label=_("ตัด (Cut)"), accelerator=ACCEL + "X", command=lambda: self.pages_cut(doc, pages))
        m.add_command(label=_("คัดลอก (Copy)"), accelerator=ACCEL + "C", command=lambda: self.pages_copy(doc, pages))
        paste_state = "normal" if clip is not None else "disabled"
        count = (" (%s)" % (_("%d หน้า") % clip.page_count)) if clip is not None else ""
        m.add_command(label=_("วางก่อนหน้านี้") + count, state=paste_state, command=lambda: self.pages_paste(doc, pages[0]))
        m.add_command(
            label=_("วางหลังหน้านี้") + count,
            accelerator=ACCEL + "V",
            state=paste_state,
            command=lambda: self.pages_paste(doc, pages[-1] + 1),
        )
        m.add_separator()
        m.add_command(label=_("หมุนซ้าย"), command=lambda: self.pages_rotate(doc, pages, -90))
        m.add_command(label=_("หมุนขวา"), command=lambda: self.pages_rotate(doc, pages, 90))
        m.add_command(label=_("แยกเป็นไฟล์ใหม่"), command=lambda: self.pages_split(doc, pages))
        m.add_separator()
        m.add_command(
            label=_("ลบ (Delete)"),
            accelerator=DEL_KEY,
            command=lambda: self.pages_delete(doc, pages),
            state="normal" if n < doc.page_count else "disabled",
        )
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ------------------------------------------------------------------ actions
    def pages_duplicate(self, doc, pages):
        doc.push_undo()
        new = duplicate_pages(doc, pages)
        self.pages_changed(doc, select=new)
        self.set_status(_("ทำสำเนาแล้ว") + " · " + page_range_label(new))

    def pages_copy(self, doc, pages):
        self.page_clipboard = extract_pages(doc, pages, remove=False)
        self.set_status(_("คัดลอก %d หน้าแล้ว — คลิกขวาที่หน้าอื่นแล้วเลือก “วาง”") % len(pages))

    def pages_cut(self, doc, pages):
        if len(pages) >= doc.page_count:
            messagebox.showinfo(APP_NAME, _("เอกสารต้องมีอย่างน้อย 1 หน้า — ใช้ “คัดลอก” แทน"))
            return
        self.page_clipboard = extract_pages(doc, pages, remove=False)
        doc.push_undo()
        delete_pages(doc, pages)
        self.pages_changed(doc, select=[])
        self.set_status(_("ตัด %d หน้าแล้ว — คลิกขวาที่หน้าอื่นแล้วเลือก “วาง”") % len(pages))

    def pages_paste(self, doc, position):
        clip = self.page_clipboard
        if clip is None:
            return
        doc.push_undo()
        new = transfer_pages(clip, range(clip.page_count), doc, position, copy_pages=True)
        self.pages_changed(doc, select=new)
        self.set_status(_("วาง %d หน้าแล้ว") % len(new) + " → " + (doc.title or _("เอกสารใหม่")))

    def pages_rotate(self, doc, pages, degrees):
        doc.push_undo()
        rotate_pages(doc, pages, degrees)
        self.pages_changed(doc, select=pages)

    def pages_delete(self, doc, pages):
        if len(pages) >= doc.page_count:
            messagebox.showinfo(APP_NAME, _("เอกสารต้องมีอย่างน้อย 1 หน้า"))
            return
        if len(pages) > 1 and not messagebox.askyesno(APP_NAME, _("ลบ %d หน้าที่เลือกหรือไม่?") % len(pages)):
            return
        doc.push_undo()
        delete_pages(doc, pages)
        self.pages_changed(doc, select=[])
        self.set_status(_("ลบ %d หน้าแล้ว — กด %sZ เพื่อเลิกทำ") % (len(pages), ACCEL))

    def pages_split(self, doc, pages):
        if not self.multi:
            self.toggle_multi()
        self.after(50, lambda: self.workspace.split_to_new(doc, pages, copy_mode=True))

    # ------------------------------------------------------------------ refresh
    def pages_changed(self, doc, select=None):
        """redraw whatever shows `doc` after its pages changed"""
        doc.dirty = True
        if self.multi:
            col = self.workspace.column_of(doc)
            if col is not None:
                if select is not None:
                    col.selection = set(select)
                    if select:
                        col.anchor = select[0]
                col.layout()
        elif doc is self.active:
            if select:
                doc.cur = select[0]
            doc.sel = None
            doc.pdfsel = None
            self.build_thumbs()
            self.render_view(keep_scroll=True)
            self.render_props()
            self.scroll_thumb_into_view()
        self.update_state()
        self.refresh_tabbar()

    # ------------------------------------------------------------------ keyboard
    def bind_page_keys(self, widget, get_target):
        """⌘/Ctrl + D X C V and Delete on a page list; ``get_target()`` -> (doc, pages) or None"""

        def run(action):
            t = get_target()
            if not t or not t[1]:
                return "break"
            doc, pages = t
            {
                "dup": lambda: self.pages_duplicate(doc, pages),
                "cut": lambda: self.pages_cut(doc, pages),
                "copy": lambda: self.pages_copy(doc, pages),
                "paste": lambda: self.pages_paste(doc, max(pages) + 1),
                "del": lambda: self.pages_delete(doc, pages),
            }[action]()
            return "break"

        mods = ("Command", "Control") if sys.platform == "darwin" else ("Control",)
        for mod in mods:
            for key, action in (("d", "dup"), ("x", "cut"), ("c", "copy"), ("v", "paste")):
                widget.bind("<%s-%s>" % (mod, key), lambda e, a=action: run(a))
        for key in ("<Delete>", "<BackSpace>"):
            widget.bind(key, lambda e: run("del"))
