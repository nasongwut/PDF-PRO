"""Opening, creating, merging, saving, printing and closing documents."""

import logging
import os
import tempfile
from tkinter import filedialog, messagebox, simpledialog

import pymupdf as fitz

from pdfpro import APP_NAME
from pdfpro.core.document import Document
from pdfpro.core.fonts import fontbook
from pdfpro.core.overlay import apply_objects
from pdfpro.core.printing import send_to_printer
from pdfpro.i18n import _
from pdfpro.ui.dialogs.print_dialog import PrintDialog

log = logging.getLogger(__name__)


class FilesMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def confirm_discard(self):
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel(APP_NAME, _("มีการแก้ไขที่ยังไม่ได้บันทึก\nต้องการบันทึกก่อนหรือไม่?"))
        if r is None:
            return False
        if r:
            return self.save()
        return True

    def open_dialog(self):
        """open one or more PDFs, each in its own tab"""
        ps = filedialog.askopenfilenames(title=_("เปิดไฟล์ PDF"), filetypes=[("PDF", "*.pdf"), (_("ทุกไฟล์"), "*.*")])
        for p in ps:
            self.open_path(p)

    def open_path(self, p):
        existing = self.find_document(p)
        if existing is not None:
            self.activate(existing)
            return
        try:
            d = fitz.open(p)
            if d.needs_pass:
                pw = simpledialog.askstring(APP_NAME, _("ไฟล์นี้มีรหัสผ่าน กรุณาใส่รหัส:"), show="•", parent=self)
                if not pw or not d.authenticate(pw):
                    messagebox.showerror(APP_NAME, _("รหัสผ่านไม่ถูกต้อง"))
                    return
                d = fitz.open("pdf", d.tobytes(encryption=fitz.PDF_ENCRYPT_NONE))
            if not d.is_pdf:
                d = fitz.open("pdf", d.convert_to_pdf())
        except Exception as e:
            messagebox.showerror(APP_NAME, _("เปิดไฟล์ไม่ได้\n%s") % e)
            return
        self.load_doc(d, p)

    def load_doc(self, d, path):
        """open a PyMuPDF document in a new tab"""
        if path:
            self.add_recent(path)
        self.add_document(Document(d, path))

    def new_blank(self):
        d = fitz.open()
        d.new_page(width=595.28, height=841.89)
        self.load_doc(d, None)
        if self.mode == "view":
            self.set_mode("edit")

    def merge_new(self):
        """combine several PDFs into a new document"""
        ps = filedialog.askopenfilenames(title=_("เลือกไฟล์ PDF ที่จะรวม (เรียงตามลำดับที่เลือก)"), filetypes=[("PDF", "*.pdf")])
        if not ps:
            return
        d = fitz.open()
        try:
            for p in ps:
                d.insert_pdf(fitz.open(p))
        except Exception as e:
            messagebox.showerror(APP_NAME, _("รวมไฟล์ไม่สำเร็จ") + "\n%s" % e)
            return
        self.load_doc(d, None)
        self.dirty = True
        self.update_state()
        self.refresh_tabbar()
        self.set_status(_("รวม %d ไฟล์แล้ว — กดบันทึกเพื่อเก็บเป็นไฟล์ใหม่") % len(ps))

    def build_output(self, pages=None, document=None):
        """a new PyMuPDF document with all overlay objects burnt in (optionally only `pages`)"""
        d = document or self.active
        out = fitz.open("pdf", d.doc.tobytes())
        if pages is not None:
            out.select(pages)
            objs = [d.objs[i] for i in pages]
        else:
            objs = d.objs
        for i, page in enumerate(out):
            apply_objects(page, objs[i], self.images)
        return out

    def save(self, as_new=False):
        if not self.has_doc():
            return False
        path = self.path
        if as_new or not path or not self._saved_once:
            base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
            if not base.endswith(_("-แก้ไข")):
                base += _("-แก้ไข")
            path = filedialog.asksaveasfilename(
                title=_("บันทึกไฟล์ PDF"),
                defaultextension=".pdf",
                initialdir=os.path.dirname(self.path) if self.path else None,
                initialfile=base + ".pdf",
                filetypes=[("PDF", "*.pdf")],
            )
            if not path:
                return False
        try:
            self.configure(cursor="watch")
            self.update()
            data = self.build_output().tobytes(garbage=3, deflate=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            messagebox.showerror(APP_NAME, _("บันทึกไม่สำเร็จ\n%s") % e)
            return False
        finally:
            self.configure(cursor="")
        self.path = path
        self._saved_once = True
        self.dirty = False
        self.add_recent(path)
        self.update_state()
        self.refresh_tabbar()
        self.set_status(_("✓ บันทึกแล้ว: %s") % os.path.basename(path))
        return True

    def merge_dialog(self):
        if not self.has_doc():
            return
        ps = filedialog.askopenfilenames(title=_("เลือกไฟล์ PDF ที่จะเพิ่มต่อจากหน้าปัจจุบัน"), filetypes=[("PDF", "*.pdf")])
        if not ps:
            return
        self.push_undo()
        at = self.cur + 1
        try:
            for p in ps:
                o = fitz.open(p)
                n = o.page_count
                self.doc.insert_pdf(o, start_at=at)
                self.objs[at:at] = [[] for _n in range(n)]
                at += n
        except Exception as e:
            messagebox.showerror(APP_NAME, _("รวมไฟล์ไม่สำเร็จ\n%s") % e)
        self.struct_changed()
        self.build_thumbs()
        self.render_view()
        self.update_state()
        self.set_status(_("เพิ่ม %d ไฟล์แล้ว") % len(ps))

    def add_fonts(self):
        ps = filedialog.askopenfilenames(
            title=_("เลือกไฟล์ฟอนต์"), filetypes=[(_("ฟอนต์"), "*.ttf *.otf *.ttc *.TTF *.OTF *.TTC")]
        )
        added = []
        for p in ps:
            try:
                fam = fontbook().system.install(p)
                if fam:
                    added.append(fam)
            except Exception as e:
                messagebox.showerror(APP_NAME, "%s\n%s" % (os.path.basename(p), e))
        if added:
            messagebox.showinfo(APP_NAME, _("เพิ่มฟอนต์แล้ว") + ":\n" + "\n".join(sorted(set(added))))

    def print_dialog(self):
        if not self.has_doc():
            return
        r = PrintDialog(self, self.doc.page_count, self.cur).run()
        if not r:
            return
        try:
            self.configure(cursor="watch")
            self.update()
            fd, tmp = tempfile.mkstemp(prefix="pdfpro-print-", suffix=".pdf")
            os.close(fd)
            self.build_output(r["pages"]).save(tmp, garbage=3, deflate=True)
        except Exception as e:
            messagebox.showerror(APP_NAME, _("เตรียมงานพิมพ์ไม่สำเร็จ") + "\n%s" % e)
            return
        finally:
            self.configure(cursor="")
        try:
            send_to_printer(tmp, printer=r["printer"], copies=r["copies"], system_dialog=r["system"])
        except Exception as e:
            messagebox.showerror(APP_NAME, _("พิมพ์ไม่สำเร็จ") + "\n%s" % e)
            return
        if r["system"]:
            self.set_status(_("เปิดหน้าต่างพิมพ์ของระบบแล้ว"))
        else:
            self.set_status(_("ส่งงานพิมพ์แล้ว") + " · %d %s" % (len(r["pages"]), _("หน้า")))

    def on_close(self):
        for d in list(self.docs):
            if d.dirty:
                self.activate(d)
                if not self.confirm_discard():
                    return
        self.destroy()
