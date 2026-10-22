"""Page rendering, coordinate mapping, zoom, navigation and thumbnails."""

import tkinter as tk

import pymupdf as fitz

from pdfpro.core.overlay import render_page
from pdfpro.i18n import _
from pdfpro.ui.constants import MARGIN
from pdfpro.ui.theme import ACCENT, BORDER, CANVAS, MUTED, PANEL, SHADOW, tc


class ViewerMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    TW = 128  # thumbnail width in px

    def has_doc(self):
        return self.doc is not None and self.doc.page_count > 0

    def page(self):
        return self.doc[self.cur]

    def to_disp(self, pt):
        p = fitz.Point(pt) * self.page().rotation_matrix
        return self.ox + p.x * self.zoom, self.oy + p.y * self.zoom

    def to_page(self, cx, cy):
        p = fitz.Point((cx - self.ox) / self.zoom, (cy - self.oy) / self.zoom) * self.page().derotation_matrix
        return (p.x, p.y)

    def disp_rect(self, r):
        a = self.to_disp((r.x0, r.y0))
        b = self.to_disp((r.x1, r.y1))
        return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])

    def page_rect_from_disp(self, x0, y0, x1, y1):
        a = self.to_page(x0, y0)
        b = self.to_page(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    def evpt(self, e):
        return self.cv.canvasx(e.x), self.cv.canvasy(e.y)

    def editor_visible(self):
        """True when a document is shown in the single-document editor (not home / multi-file view)"""
        return self.has_doc() and not self.show_home and not self.multi

    def render_page_pix(self, i, zoom):
        return render_page(self.doc, self.objs[i], self.images, i, zoom)

    def render_view(self, keep_scroll=False):
        if not self.has_doc():
            return
        yv = self.cv.yview()[0] if keep_scroll else 0
        xv = self.cv.xview()[0] if keep_scroll else 0
        pix = self.render_page_pix(self.cur, self.zoom)
        self.page_img = tk.PhotoImage(data=pix.tobytes("ppm"))
        cw = self.cv.winfo_width()
        self.ox = max(MARGIN, (cw - pix.width) / 2)
        self.oy = MARGIN
        self.cv.delete("all")
        sh = tc(SHADOW)
        for i, off in enumerate((6, 3)):
            self.cv.create_rectangle(
                self.ox - off + 2,
                self.oy - off + 4,
                self.ox + pix.width + off - 2,
                self.oy + pix.height + off + 2,
                fill=sh if i else tc(CANVAS),
                outline=sh if i == 0 else "",
                width=1,
            )
        self.cv.create_image(self.ox, self.oy, image=self.page_img, anchor="nw", tags="page")
        self.cv.create_text(
            self.ox + pix.width / 2,
            self.oy + pix.height + 14,
            text=_("หน้า %d จาก %d") % (self.cur + 1, self.doc.page_count),
            fill=tc(MUTED),
            font=("Helvetica", 11),
        )
        self.cv.configure(scrollregion=(0, 0, max(cw, pix.width + 2 * MARGIN), pix.height + 2 * MARGIN + 10))
        self.cv.yview_moveto(yv)
        self.cv.xview_moveto(xv)
        self.draw_selection()
        self.update_state()

    def refresh(self):
        self.render_view(keep_scroll=True)
        self.update_thumb(self.cur)
        self.render_props()

    def set_zoom(self, z):
        if not self.has_doc():
            return
        self.zoom = max(0.2, min(5.0, z))
        self.render_view(keep_scroll=True)

    def fit_width(self, render=True):
        if not self.has_doc():
            return
        w = self.cv.winfo_width() - 2 * MARGIN - 10
        pw = self.page().rect.width
        self.zoom = max(0.3, min(3.0, w / pw if w > 100 else 1.0))
        if render:
            self.render_view()

    def goto(self, i, top=True):
        if not self.has_doc():
            return
        i = max(0, min(self.doc.page_count - 1, i))
        if i == self.cur:
            return
        self.cur = i
        self.sel = None
        self.pdfsel = None
        self.render_view()
        if not top:
            self.cv.yview_moveto(1.0)
        self.highlight_thumb()
        self.scroll_thumb_into_view()
        self.render_props()

    def _goto_entry(self):
        try:
            self.goto(int(self.page_var.get()) - 1)
        except ValueError:
            pass
        self.focus_set()

    def on_wheel(self, d):
        if not self.has_doc():
            return
        top, bot = self.cv.yview()
        if d > 0 and bot >= 0.999:
            if self.cur < self.doc.page_count - 1:
                self.goto(self.cur + 1)
            return
        if d < 0 and top <= 0.001:
            if self.cur > 0:
                self.goto(self.cur - 1, top=False)
            return
        self.cv.yview_scroll(d, "units")

    def build_thumbs(self):
        if not self.has_doc():
            return
        self.thumbs.configure(bg=tc(PANEL))
        self.thumbs.delete("all")
        self.thumb_imgs = {}
        self._thumb_pos = []
        y = 12
        for i in range(self.doc.page_count):
            r = self.doc[i].rect
            s = min(self.TW / r.width, 160 / r.height)
            w, h = r.width * s, r.height * s
            x = (184 - w) / 2
            self._thumb_pos.append((x, y, w, h, s))
            self.thumbs.create_rectangle(x + 1, y + 2, x + w + 1, y + h + 2, fill=tc(SHADOW), outline="")
            self.thumbs.create_rectangle(x, y, x + w, y + h, fill="white", outline=tc(BORDER), tags=("tb%d" % i,))
            self.thumbs.create_text(
                92, y + h + 13, text=str(i + 1), fill=tc(MUTED), font=("Helvetica", 11), tags="num%d" % i
            )
            y += h + 34
        self.thumbs.configure(scrollregion=(0, 0, 184, y))
        self._thumb_queue = list(range(self.doc.page_count))
        if self._thumb_job:
            self.after_cancel(self._thumb_job)
        self._thumb_job = self.after(10, self._thumb_worker)
        self.highlight_thumb()

    def _thumb_worker(self):
        for _n in range(4):
            if not self._thumb_queue:
                self._thumb_job = None
                return
            self.update_thumb(self._thumb_queue.pop(0))
        self._thumb_job = self.after(5, self._thumb_worker)

    def update_thumb(self, i):
        if not self.has_doc() or i >= len(self._thumb_pos):
            return
        x, y, w, h, s = self._thumb_pos[i]
        try:
            pix = self.render_page_pix(i, s)
        except Exception:
            return
        img = tk.PhotoImage(data=pix.tobytes("ppm"))
        self.thumb_imgs[i] = img
        self.thumbs.delete("img%d" % i)
        self.thumbs.create_image(x, y, image=img, anchor="nw", tags=("img%d" % i,))
        self.thumbs.delete("badge%d" % i)
        if self.objs[i]:
            self.thumbs.create_oval(x + w - 9, y + 4, x + w - 3, y + 10, fill=ACCENT, outline="", tags="badge%d" % i)
        self.thumbs.tag_raise("hl")

    def highlight_thumb(self):
        self.thumbs.delete("hl")
        if not self.has_doc() or self.cur >= len(self._thumb_pos):
            return
        x, y, w, h, s = self._thumb_pos[self.cur]
        self.thumbs.create_rectangle(x - 4, y - 4, x + w + 4, y + h + 4, outline=ACCENT, width=2.5, tags="hl")
        for i in range(len(self._thumb_pos)):
            self.thumbs.itemconfigure("num%d" % i, fill=ACCENT if i == self.cur else tc(MUTED))

    def scroll_thumb_into_view(self):
        if not self._thumb_pos:
            return
        x, y, w, h, s = self._thumb_pos[self.cur]
        total = self.thumbs.bbox("all")
        if not total:
            return
        H = total[3] + 12
        top, bot = self.thumbs.yview()
        if y / H < top or (y + h) / H > bot:
            self.thumbs.yview_moveto(max(0, (y - 40) / H))

    def on_thumb_click(self, e):
        if not self.has_doc():
            return
        y = self.thumbs.canvasy(e.y)
        for i, (_x0, y0, _w, h, _s) in enumerate(self._thumb_pos):
            if y0 - 8 <= y <= y0 + h + 24:
                self.goto(i)
                return
