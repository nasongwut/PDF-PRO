"""Page operations: rotate, move, delete, insert, duplicate, extract."""

import copy
import logging
import os
from tkinter import filedialog, messagebox

from pdfpro import APP_NAME
from pdfpro.i18n import _

log = logging.getLogger(__name__)


class PagesMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def _after_struct(self, scroll=True):
        self.pdfsel = None
        self.struct_changed()
        self.build_thumbs()
        self.render_view()
        self.render_props()
        if scroll:
            self.scroll_thumb_into_view()

    def rotate_page(self, d):
        if not self.has_doc():
            return
        self.push_undo()
        p = self.page()
        p.set_rotation((p.rotation + d) % 360)
        self._after_struct()

    def move_page(self, d):
        if not self.has_doc():
            return
        i, j = self.cur, self.cur + d
        if j < 0 or j >= self.doc.page_count:
            return
        self.push_undo()
        if d < 0:
            self.doc.move_page(i, j)
        else:
            self.doc.move_page(i, j + 1 if j + 1 < self.doc.page_count else -1)
        self.objs.insert(j, self.objs.pop(i))
        self.cur = j
        self._after_struct()

    def delete_page(self):
        if not self.has_doc():
            return
        if self.doc.page_count <= 1:
            messagebox.showinfo(APP_NAME, _("เอกสารต้องมีอย่างน้อย 1 หน้า"))
            return
        self.push_undo()
        self.doc.delete_page(self.cur)
        self.objs.pop(self.cur)
        self.cur = min(self.cur, self.doc.page_count - 1)
        self.sel = None
        self._after_struct()
        self.set_status(_("ลบหน้าแล้ว — กด ⌘Z / Ctrl+Z เพื่อเลิกทำ"))

    def insert_blank(self):
        if not self.has_doc():
            return
        self.push_undo()
        r = self.page().mediabox
        rot = self.page().rotation
        np_ = self.doc.new_page(self.cur + 1, width=r.width, height=r.height)
        if rot:
            np_.set_rotation(rot)
        self.objs.insert(self.cur + 1, [])
        self.cur += 1
        self.sel = None
        self._after_struct()

    def duplicate_page(self):
        if not self.has_doc():
            return
        self.push_undo()
        to = self.cur + 1
        self.doc.fullcopy_page(self.cur, to if to < self.doc.page_count else -1)
        self.objs.insert(to, copy.deepcopy(self.objs[self.cur]))
        self.cur = to
        self.sel = None
        self._after_struct()

    def extract_page(self):
        if not self.has_doc():
            return
        base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
        path = filedialog.asksaveasfilename(
            title=_("บันทึกหน้านี้เป็นไฟล์ใหม่"),
            defaultextension=".pdf",
            initialfile=_("%s-หน้า%d.pdf") % (base, self.cur + 1),
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        try:
            self.build_output([self.cur]).save(path, garbage=3, deflate=True)
            self.set_status(_("✓ บันทึกหน้า %d แล้ว") % (self.cur + 1))
        except Exception as e:
            messagebox.showerror(APP_NAME, _("บันทึกไม่สำเร็จ\n%s") % e)
