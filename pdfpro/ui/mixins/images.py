"""Images: inserting pictures / signatures and managing images embedded in the PDF."""

import logging
import os
import sys
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pymupdf as fitz
from PIL import Image

from pdfpro import APP_NAME
from pdfpro.i18n import _
from pdfpro.ui.dialogs.signature import SignatureDialog
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, BORDER, CARD, MUTED, PANEL, SOFT, TEXT, F
from pdfpro.ui.widgets import secondary_btn

log = logging.getLogger(__name__)


class ImagesMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def page_xrefs(self, i):
        return [im[0] for im in self.doc[i].get_images(full=True) if im[0] > 0 and not (im[2] <= 1 and im[3] <= 1)]

    def page_images(self, i):
        """placements of images on page i: list of dict(xref, bbox, w, h)"""
        out = []
        try:
            for k, info in enumerate(self.doc[i].get_image_info(xrefs=True)):
                r = fitz.Rect(info["bbox"])
                if (
                    r.is_empty
                    or r.width < 2
                    or r.height < 2
                    or (info.get("width", 9) <= 1 and info.get("height", 9) <= 1)
                ):
                    continue
                out.append(
                    dict(
                        xref=info.get("xref", 0),
                        bbox=tuple(r),
                        w=info.get("width"),
                        h=info.get("height"),
                        key="%d:%d:%d" % (i, info.get("xref", 0), k),
                    )
                )
        except Exception as e:
            log.warning("image info: %s", e)
        return out

    def hit_pdf_image(self, cx, cy):
        px, py = self.to_page(cx, cy)
        hits = [im for im in self.page_images(self.cur) if fitz.Rect(im["bbox"]).contains(fitz.Point(px, py))]
        if not hits:
            return None
        return min(hits, key=lambda im: fitz.Rect(im["bbox"]).get_area())  # smallest = top-most in practice

    def _image_pixmap(self, xref):
        pix = fitz.Pixmap(self.doc, xref)
        smask = 0
        for im in self.doc[self.cur].get_images(full=True) + [
            x for i in range(self.doc.page_count) for x in self.doc[i].get_images(full=True)
        ]:
            if im[0] == xref:
                smask = im[1]
                break
        if smask:
            try:
                pix = fitz.Pixmap(pix, fitz.Pixmap(self.doc, smask))
            except Exception:
                pass
        if pix.colorspace and pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return pix

    def _image_bytes(self, xref):
        """(bytes, ext) of an image, keeping JPEG/PNG originals when possible"""
        try:
            info = self.doc.extract_image(xref)
        except Exception:
            info = None
        if (
            info
            and info.get("ext") in ("jpeg", "jpg", "png")
            and not info.get("smask")
            and info.get("colorspace", 3) in (1, 3)
        ):
            return info["image"], "jpg" if info["ext"] in ("jpeg", "jpg") else "png"
        return self._image_pixmap(xref).tobytes("png"), "png"

    def _render_pdfimg_props(self):
        im = self.pdfsel
        head = ctk.CTkFrame(self.props_in, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(18, 16))
        badge = ctk.CTkFrame(head, fg_color=("#fef3c7", "#3a2e12"), corner_radius=10, width=38, height=38)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon("image", 19, "#d97706")).pack(expand=True)
        tt = ctk.CTkFrame(head, fg_color="transparent")
        tt.pack(side="left", padx=10)
        ctk.CTkLabel(tt, text=_("รูปในไฟล์ PDF"), font=F(15, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            tt, text="%s × %s px" % (im.get("w") or "?", im.get("h") or "?"), font=F(12), text_color=MUTED, anchor="w"
        ).pack(anchor="w")
        # preview
        try:
            pix = self._image_pixmap(im["xref"])
            img = Image.frombytes("RGBA" if pix.alpha else "RGB", (pix.width, pix.height), pix.samples)
            img.thumbnail((228, 170))
            prev = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
            prev.pack(fill="x", padx=18, pady=(0, 16))
            ctk.CTkLabel(prev, text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=img.size)).pack(
                padx=10, pady=10
            )
        except Exception as e:
            log.warning("image preview: %s", e)
        sec = self._section(self.props_in, _("การจัดการรูป"))
        if not im["xref"]:
            ctk.CTkLabel(
                sec,
                text=_("รูปชนิดฝังในเนื้อหา (inline) แก้ไขไม่ได้ — ใช้ “ปิดทับ” แทน"),
                font=F(12),
                text_color=MUTED,
                wraplength=220,
                justify="left",
            ).pack(anchor="w")
        else:
            secondary_btn(sec, _("บันทึกรูปนี้…"), self.save_pdf_image, "export", height=34).pack(fill="x", pady=3)
            secondary_btn(sec, _("แทนที่ด้วยรูปอื่น…"), self.replace_pdf_image, "replace", height=34).pack(fill="x", pady=3)
            ctk.CTkButton(
                sec,
                text=_("ลบรูปนี้"),
                image=icon("trash", 17, (ACCENT, "#ff6b70")),
                command=self.delete_pdf_image,
                fg_color=PANEL,
                hover_color=SOFT,
                text_color=(ACCENT, "#ff6b70"),
                border_width=1,
                border_color=BORDER,
                corner_radius=10,
                height=34,
                font=F(13),
            ).pack(fill="x", pady=3)
            shared = self._pages_using(im["xref"])
            if len(shared) > 1:
                ctk.CTkLabel(
                    sec,
                    text=_("⚠️ รูปนี้ใช้ร่วมกันใน %d หน้า — การลบ/แทนที่จะมีผลทุกหน้า") % len(shared),
                    font=F(12),
                    text_color=("#b45309", "#fbbf24"),
                    wraplength=220,
                    justify="left",
                ).pack(anchor="w", pady=(8, 0))
        sec = self._section(self.props_in, _("ทั้งเอกสาร"))
        secondary_btn(sec, _("ส่งออกรูปทั้งหมด…"), self.export_all_images, "export", height=34).pack(fill="x")
        card = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkLabel(card, text=_("💡 วิธีใช้"), font=F(12, "bold"), text_color=TEXT).pack(
            anchor="w", padx=14, pady=(12, 2)
        )
        ctk.CTkLabel(
            card,
            text=_("Delete = ลบรูป · คลิกที่ว่างเพื่อยกเลิกการเลือก\nรูปที่แทนที่จะวางพอดีกรอบเดิมโดยรักษาสัดส่วน แล้วย้าย/ปรับขนาดต่อได้"),
            font=F(12),
            text_color=MUTED,
            wraplength=196,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def _pages_using(self, xref):
        return [i for i in range(self.doc.page_count) if xref in self.page_xrefs(i)]

    def _confirm_shared(self, xref, action):
        pages = self._pages_using(xref)
        if len(pages) <= 1:
            return True
        return messagebox.askyesno(
            APP_NAME,
            _("รูปนี้ใช้ร่วมกันใน %d หน้า (หน้า %s)\n%sรูปนี้ในทุกหน้าหรือไม่?")
            % (len(pages), ", ".join(str(p + 1) for p in pages[:12]) + ("…" if len(pages) > 12 else ""), action),
        )

    def delete_pdf_image(self):
        im = self.pdfsel
        if not im or not im["xref"]:
            return
        if not self._confirm_shared(im["xref"], _("ลบ")):
            return
        self.push_undo()
        try:
            self.page().delete_image(im["xref"])
        except Exception as e:
            messagebox.showerror(APP_NAME, _("ลบรูปไม่สำเร็จ\n%s") % e)
            return
        self.pdfsel = None
        self.struct_changed()
        self.render_view(keep_scroll=True)
        for i in range(self.doc.page_count):
            self.update_thumb(i)
        self.render_props()
        self.set_status(_("ลบรูปแล้ว — กด ⌘Z / Ctrl+Z เพื่อเลิกทำ"))

    def replace_pdf_image(self):
        im = self.pdfsel
        if not im or not im["xref"]:
            return
        p = filedialog.askopenfilename(
            title=_("เลือกรูปใหม่"),
            filetypes=[(_("รูปภาพ"), "*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp"), (_("ทุกไฟล์"), "*.*")],
        )
        if not p:
            return
        try:
            with open(p, "rb") as f:
                data = f.read()
            pix = fitz.Pixmap(data)
            if not p.lower().endswith((".png", ".jpg", ".jpeg")):
                data = pix.tobytes("png")
        except Exception:
            messagebox.showerror(APP_NAME, _("เปิดรูปภาพนี้ไม่ได้"))
            return
        shared = len(self._pages_using(im["xref"])) > 1
        if shared:
            if not self._confirm_shared(im["xref"], _("แทนที่")):
                return
            self.push_undo()
            self.page().replace_image(im["xref"], stream=data)  # same box on every page
            self.pdfsel = None
            self.struct_changed()
            self.render_view(keep_scroll=True)
            for i in range(self.doc.page_count):
                self.update_thumb(i)
            self.render_props()
            self.set_status(_("แทนที่รูปในทุกหน้าแล้ว"))
            return
        # single use: remove the original and place the new picture as an editable object, fitted into the old box
        self.push_undo()
        self.page().delete_image(im["xref"])
        self.struct_changed()
        key = "img%d" % (len(self.images) + 1)
        while key in self.images:
            key += "_"
        self.images[key] = data
        x0, y0, x1, y1 = self.disp_rect(fitz.Rect(im["bbox"]))
        bw, bh = x1 - x0, y1 - y0
        s = min(bw / pix.width, bh / pix.height)
        w, h = pix.width * s, pix.height * s
        nx, ny = x0 + (bw - w) / 2, y0 + (bh - h) / 2
        self.objs[self.cur].append(
            dict(type="image", img=key, rect=self.page_rect_from_disp(nx, ny, nx + w, ny + h), rot=self.page().rotation)
        )
        self.pdfsel = None
        self.set_tool("select")
        self.sel = len(self.objs[self.cur]) - 1
        self.refresh()
        self.set_status(_("แทนที่รูปแล้ว — ย้ายหรือปรับขนาดได้ (Shift ค้างขณะลากมุม = ยืดอิสระ)"))

    def save_pdf_image(self):
        im = self.pdfsel
        if not im or not im["xref"]:
            return
        data, ext = self._image_bytes(im["xref"])
        base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
        path = filedialog.asksaveasfilename(
            title=_("บันทึกรูป"),
            defaultextension="." + ext,
            initialfile=_("%s-หน้า%d-รูป.%s") % (base, self.cur + 1, ext),
            filetypes=[(_("รูปภาพ"), "*." + ext)],
        )
        if not path:
            return
        with open(path, "wb") as f:
            f.write(data)
        self.set_status(_("✓ บันทึกรูปแล้ว: %s") % os.path.basename(path))

    def export_all_images(self):
        if not self.has_doc():
            return
        seen, items = set(), []
        for i in range(self.doc.page_count):
            for x in self.page_xrefs(i):
                if x not in seen:
                    seen.add(x)
                    items.append((i, x))
        if not items:
            messagebox.showinfo(APP_NAME, _("ไม่พบรูปภาพในไฟล์นี้"))
            return
        folder = filedialog.askdirectory(title=_("เลือกโฟลเดอร์สำหรับเก็บรูป (%d รูป)") % len(items))
        if not folder:
            return
        base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
        out = os.path.join(folder, base + _("-รูปภาพ"))
        n, k = 2, out
        while os.path.exists(k):
            k = "%s (%d)" % (out, n)
            n += 1
        out = k
        os.makedirs(out, exist_ok=True)
        ok = 0
        self.configure(cursor="watch")
        self.update()
        try:
            counter = {}
            for i, x in items:
                try:
                    data, ext = self._image_bytes(x)
                    if len(data) < 120:  # skip blank placeholders (e.g. deleted images)
                        continue
                    counter[i] = counter.get(i, 0) + 1
                    with open(os.path.join(out, _("หน้า%03d-รูป%02d.%s") % (i + 1, counter[i], ext)), "wb") as f:
                        f.write(data)
                    ok += 1
                except Exception as e:
                    log.warning("export image %s: %s", x, e)
        finally:
            self.configure(cursor="")
        self.set_status(_("✓ ส่งออก %d รูป ไปที่ %s") % (ok, out))
        if messagebox.askyesno(APP_NAME, _("ส่งออก %d รูปเรียบร้อย\n\n%s\n\nเปิดโฟลเดอร์เลยหรือไม่?") % (ok, out)):
            try:
                if sys.platform == "darwin":
                    import subprocess

                    subprocess.Popen(["open", out])
                elif os.name == "nt":
                    os.startfile(out)
                else:
                    import subprocess

                    subprocess.Popen(["xdg-open", out])
            except Exception:
                pass

    def place_image(self, data, w_hint=None):
        try:
            pix = fitz.Pixmap(data)
            iw, ih = pix.width, pix.height
        except Exception:
            messagebox.showerror(APP_NAME, _("เปิดรูปภาพนี้ไม่ได้"))
            return
        key = "img%d" % (len(self.images) + 1)
        while key in self.images:
            key += "_"
        self.images[key] = data
        pr = self.page().rect
        w = min(w_hint or 220, pr.width * 0.6)
        h = w * ih / iw
        if h > pr.height * 0.6:
            h = pr.height * 0.6
            w = h * iw / ih
        top, bot = self.cv.yview()
        vis_cy = (top + bot) / 2 * float(str(self.cv.cget("scrollregion")).split()[3])
        dcx = (pr.width - w) / 2
        dcy = max(0, min(pr.height - h, (vis_cy - self.oy) / self.zoom - h / 2))
        x0, y0 = self.ox + dcx * self.zoom, self.oy + dcy * self.zoom
        rect = self.page_rect_from_disp(x0, y0, x0 + w * self.zoom, y0 + h * self.zoom)
        self.set_tool("select")
        self.add_obj(dict(type="image", img=key, rect=rect, rot=self.page().rotation))

    def insert_image(self):
        if not self.has_doc():
            return
        p = filedialog.askopenfilename(
            title=_("เลือกรูปภาพ"),
            filetypes=[(_("รูปภาพ"), "*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp"), (_("ทุกไฟล์"), "*.*")],
        )
        if not p:
            return
        with open(p, "rb") as f:
            data = f.read()
        try:
            pix = fitz.Pixmap(data)
            if not p.lower().endswith((".png", ".jpg", ".jpeg")):
                data = pix.tobytes("png")
        except Exception:
            pass
        self.place_image(data)

    def insert_signature(self):
        if not self.has_doc():
            return
        r = SignatureDialog(self).run()
        if r:
            png, w, h = r
            self.place_image(png, min(180, w * 0.6))
