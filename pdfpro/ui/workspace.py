"""Multi-file view: every open document side by side as a column of pages.

Pages can be dragged within a column (reorder) or onto another column (move between files).
Holding Alt / Option (or Ctrl) while dropping copies the page instead of moving it.
"""

import logging
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from pdfpro import APP_NAME
from pdfpro.core.document import Document, transfer_page
from pdfpro.core.overlay import render_page
from pdfpro.i18n import _
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, BG, BORDER, CANVAS, CARD, HOVER, MUTED, PANEL, SEL, SHADOW, SOFT, TEXT, F, tc
from pdfpro.ui.widgets import Tooltip, secondary_btn

log = logging.getLogger(__name__)

PAGE_GAP = 30  # vertical space between pages (incl. page number)
TOP_PAD = 14
MIN_COL_W = 200
MAX_PAGE_W = 260

# modifier bits meaning "copy instead of move" (Tk event.state)
if sys.platform == "darwin":
    COPY_MASK = 0x10 | 0x8  # Option, Command
elif sys.platform.startswith("win"):
    COPY_MASK = 0x20000 | 0x4  # Alt, Control
else:
    COPY_MASK = 0x8 | 0x4  # Alt (Mod1), Control


class PageColumn(ctk.CTkFrame):
    """One document: header + scrollable vertical strip of page thumbnails."""

    def __init__(self, view: "MultiView", doc: Document, width: int):
        super().__init__(view.cols, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        self.view, self.app, self.doc = view, view.app, doc
        self.images = {}
        self.slots = []  # [(y0, y1)] canvas extent of each page
        self._queue, self._job = [], None
        self._build_header()
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self.canvas = tk.Canvas(holder, width=width, highlightthickness=0, bd=0, bg=tc(CANVAS))
        sb = ctk.CTkScrollbar(holder, command=self.canvas.yview, width=10)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.column = self  # lets the drop logic find the column under the pointer
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", self._open_page)
        self.canvas.bind("<Configure>", lambda e: self._maybe_relayout(e.width))
        self.app._bind_wheel(self.canvas, lambda d: self.canvas.yview_scroll(d, "units"))
        self.col_w = width

    # ------------------------------------------------------------------ header
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 8))
        name = self.doc.name or _("เอกสารใหม่")
        title = ctk.CTkLabel(
            head,
            text=("● " if self.doc.dirty else "") + (name if len(name) <= 26 else name[:24] + "…"),
            font=F(13, "bold"),
            text_color=TEXT,
            anchor="w",
        )
        title.pack(side="left", fill="x", expand=True)
        if self.doc.path:
            Tooltip(title, self.doc.path)
        ctk.CTkButton(
            head,
            text="",
            image=icon("close", 13),
            width=24,
            height=24,
            corner_radius=6,
            fg_color="transparent",
            hover_color=SOFT,
            command=lambda: self.app.close_tab(self.doc),
        ).pack(side="right")
        b = ctk.CTkButton(
            head,
            text=_("แก้ไข"),
            image=icon("edit", 14),
            width=64,
            height=24,
            corner_radius=7,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            font=F(11),
            command=lambda: self.app.activate(self.doc),
        )
        b.pack(side="right", padx=4)
        Tooltip(b, _("เปิดไฟล์นี้ในโหมดแก้ไข"))
        sub = ctk.CTkFrame(self, fg_color="transparent")
        sub.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(sub, text=_("%d หน้า") % self.doc.page_count, font=F(11), text_color=MUTED).pack(side="left")
        ctk.CTkButton(
            sub,
            text=_("บันทึก"),
            width=52,
            height=22,
            corner_radius=6,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=ACCENT,
            font=F(11, "bold"),
            command=self._save,
        ).pack(side="right")

    def _save(self):
        self.app.activate(self.doc)
        self.app.save()

    # ------------------------------------------------------------------ layout & rendering
    def layout(self):
        c = self.canvas
        c.delete("all")
        self.images.clear()
        self.slots = []
        w = max(MIN_COL_W - 30, min(MAX_PAGE_W, self.col_w - 34))
        y = TOP_PAD
        self._geo = []
        for i in range(self.doc.page_count):
            r = self.doc.doc[i].rect
            s = w / r.width
            h = r.height * s
            x = (self.col_w - w) / 2
            c.create_rectangle(x + 2, y + 3, x + w + 2, y + h + 3, fill=tc(SHADOW), outline="")
            c.create_rectangle(x, y, x + w, y + h, fill="white", outline=tc(BORDER), tags=("pg%d" % i,))
            c.create_text(self.col_w / 2, y + h + 12, text=str(i + 1), fill=tc(MUTED), font=("Helvetica", 11))
            self.slots.append((y, y + h))
            self._geo.append((x, y, w, h, s))
            y += h + PAGE_GAP
        c.configure(scrollregion=(0, 0, self.col_w, y))
        self._queue = list(range(self.doc.page_count))
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(5, self._render_some)

    def _maybe_relayout(self, width):
        if abs(width - self.col_w) > 8:
            self.col_w = width
            self.layout()

    def _render_some(self):
        for _n in range(3):
            if not self._queue:
                self._job = None
                return
            i = self._queue.pop(0)
            if i >= len(self._geo):
                continue
            x, y, w, h, s = self._geo[i]
            try:
                pix = render_page(self.doc.doc, self.doc.objs[i], self.app.images, i, s)
                img = tk.PhotoImage(data=pix.tobytes("ppm"))
            except Exception as e:
                log.warning("render page %d: %s", i, e)
                continue
            self.images[i] = img
            self.canvas.create_image(x, y, image=img, anchor="nw", tags=("img%d" % i,))
        self._job = self.after(5, self._render_some)

    # ------------------------------------------------------------------ hit testing
    def page_at(self, y):
        for i, (y0, y1) in enumerate(self.slots):
            if y0 - 4 <= y <= y1 + 4:
                return i
        return None

    def insert_index(self, y):
        """position a dropped page would get when released at canvas-y"""
        for i, (y0, y1) in enumerate(self.slots):
            if y < (y0 + y1) / 2:
                return i
        return len(self.slots)

    def show_indicator(self, index):
        c = self.canvas
        c.delete("ins")
        if index < len(self.slots):
            y = self.slots[index][0] - PAGE_GAP / 2 + 4
        elif self.slots:
            y = self.slots[-1][1] + PAGE_GAP / 2 + 4
        else:
            y = TOP_PAD
        c.create_line(10, y, self.col_w - 10, y, fill=ACCENT, width=4, capstyle="round", tags="ins")
        c.create_oval(4, y - 6, 16, y + 6, fill=ACCENT, outline="", tags="ins")

    def hide_indicator(self):
        self.canvas.delete("ins")

    # ------------------------------------------------------------------ drag & drop
    def _press(self, e):
        y = self.canvas.canvasy(e.y)
        i = self.page_at(y)
        self.view.drag = None
        if i is not None:
            self.view.drag = dict(src=self, index=i, x=e.x_root, y=e.y_root, started=False)
            self.view.select(self, i)

    def _motion(self, e):
        self.view.drag_motion(e)

    def _release(self, e):
        self.view.drag_release(e)

    def _open_page(self, e):
        i = self.page_at(self.canvas.canvasy(e.y))
        if i is not None:
            self.doc.cur = i
            self.doc.scroll = (0.0, 0.0)
            self.app.activate(self.doc)


class MultiView(ctk.CTkFrame):
    """Container of :class:`PageColumn` — one per open document."""

    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        self.columns = []
        self.drag = None
        self.ghost = None
        self.selected = None
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(top, text=_("มุมมองหลายไฟล์"), font=F(16, "bold"), text_color=TEXT).pack(side="left")
        self.hint = ctk.CTkLabel(
            top,
            text=_("ลากหน้าไปวางในไฟล์อื่นเพื่อย้าย · กด %s ค้างขณะปล่อยเพื่อคัดลอก · ดับเบิลคลิกเพื่อแก้ไขหน้านั้น")
            % ("⌥ Option" if sys.platform == "darwin" else "Alt / Ctrl"),
            font=F(12),
            text_color=MUTED,
        )
        self.hint.pack(side="left", padx=14)
        secondary_btn(top, _("เปิดไฟล์เพิ่ม…"), self.app.open_dialog, "plus", height=30, width=130).pack(side="right")
        self.scroller = ctk.CTkScrollableFrame(
            self,
            orientation="horizontal",
            fg_color=BG,
            corner_radius=0,
            scrollbar_button_color=BG,
            scrollbar_button_hover_color=BORDER,
        )
        self.scroller.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.cols = self.scroller
        self.bind("<Configure>", lambda e: self._resize_columns())

    # ------------------------------------------------------------------ build
    def rebuild(self):
        for col in self.columns:
            col.destroy()
        self.columns = []
        docs = self.app.docs
        if not docs:
            return
        width = self._column_width(len(docs))
        height = max(300, self.winfo_height() - 90)
        for d in docs:
            col = PageColumn(self, d, width)
            col.configure(height=height)
            col.pack(side="left", fill="y", padx=6, pady=4)
            col.canvas.configure(height=height - 90)
            self.columns.append(col)
        self.update_idletasks()
        for col in self.columns:
            col.layout()

    def _column_width(self, n):
        avail = max(400, self.winfo_width() - 40)
        return int(max(MIN_COL_W, min(MAX_PAGE_W + 60, avail / max(1, n) - 16)))

    def _resize_columns(self):
        if not self.columns:
            return
        height = max(300, self.winfo_height() - 90)
        for col in self.columns:
            col.configure(height=height)
            col.canvas.configure(height=height - 90)

    def refresh_doc(self, doc):
        for col in self.columns:
            if col.doc is doc:
                col.layout()

    def select(self, col, index):
        for c in self.columns:
            c.canvas.delete("selbox")
        if index is None or index >= len(col._geo):
            return
        x, y, w, h, s = col._geo[index]
        col.canvas.create_rectangle(x - 4, y - 4, x + w + 4, y + h + 4, outline=SEL, width=2.5, tags="selbox")
        self.selected = (col, index)

    # ------------------------------------------------------------------ drag & drop
    def _column_under(self, x_root, y_root):
        w = self.winfo_containing(x_root, y_root)
        while w is not None:
            if hasattr(w, "column"):
                return w.column
            w = getattr(w, "master", None)
        return None

    def drag_motion(self, e):
        d = self.drag
        if not d:
            return
        if not d["started"]:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 6:
                return
            d["started"] = True
            self._make_ghost(d["src"], d["index"])
        if self.ghost:
            self.ghost.geometry("+%d+%d" % (e.x_root + 12, e.y_root + 8))
        target = self._column_under(e.x_root, e.y_root)
        for col in self.columns:
            if col is not target:
                col.hide_indicator()
        d["target"] = None
        if target is not None:
            cy = target.canvas.canvasy(e.y_root - target.canvas.winfo_rooty())
            idx = target.insert_index(cy)
            target.show_indicator(idx)
            d["target"] = (target, idx)
            # auto-scroll near the edges
            rel = (e.y_root - target.canvas.winfo_rooty()) / max(1, target.canvas.winfo_height())
            if rel < 0.08:
                target.canvas.yview_scroll(-1, "units")
            elif rel > 0.92:
                target.canvas.yview_scroll(1, "units")
        copy_mode = bool(e.state & COPY_MASK)
        if self.ghost is not None:
            self._ghost_label.configure(
                text=(_("คัดลอก") if copy_mode else _("ย้าย")) + " · " + _("หน้า") + " %d" % (d["index"] + 1)
            )

    def _make_ghost(self, col, index):
        self.ghost = tk.Toplevel(self)
        self.ghost.wm_overrideredirect(True)
        try:
            self.ghost.attributes("-alpha", 0.85)
            self.ghost.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.ghost.configure(bg=ACCENT)
        img = col.images.get(index)
        if img is not None:
            factor = max(1, int(max(img.width() / 110, img.height() / 140)) + 1)
            small = img.subsample(factor, factor)
            self._ghost_img = small
            tk.Label(self.ghost, image=small, bd=0).pack(padx=2, pady=(2, 0))
        self._ghost_label = tk.Label(self.ghost, text="", bg=ACCENT, fg="white", font=("Helvetica", 11, "bold"))
        self._ghost_label.pack(fill="x", padx=2, pady=2)

    def _end_drag(self):
        if self.ghost is not None:
            self.ghost.destroy()
            self.ghost = None
        for col in self.columns:
            col.hide_indicator()

    def drag_release(self, e):
        d, self.drag = self.drag, None
        self._end_drag()
        if not d or not d.get("started") or not d.get("target"):
            return
        target, idx = d["target"]
        src = d["src"]
        copy_mode = bool(e.state & COPY_MASK)
        self.drop(src.doc, d["index"], target.doc, idx, copy_mode)

    def drop(self, src: Document, index: int, dst: Document, position: int, copy_mode: bool = False):
        """perform a page move/copy with undo snapshots on the affected documents"""
        if src is not dst and not copy_mode and src.page_count <= 1:
            if not messagebox.askyesno(APP_NAME, _("ไฟล์ต้นทางมีหน้าเดียว — คัดลอกหน้านี้แทนการย้ายหรือไม่?")):
                return
            copy_mode = True
        if src is dst and not copy_mode and position in (index, index + 1):
            return
        src.push_undo()
        if dst is not src:
            dst.push_undo()
        try:
            new = transfer_page(src, index, dst, position, copy_page=copy_mode)
        except Exception as e:
            messagebox.showerror(APP_NAME, _("ย้ายหน้าไม่สำเร็จ") + "\n%s" % e)
            return
        self.refresh_doc(src)
        if dst is not src:
            self.refresh_doc(dst)
        for col in self.columns:
            col_dirty_title(col)
        self.app.refresh_tabbar()
        self.app.set_status(
            (_("คัดลอกหน้าแล้ว") if copy_mode else _("ย้ายหน้าแล้ว"))
            + " → %s · %s %d" % (dst.name or _("เอกสารใหม่"), _("หน้า"), new + 1)
        )
        for col in self.columns:
            if col.doc is dst:
                self.after(60, lambda c=col, n=new: self.select(c, n))


def col_dirty_title(col: PageColumn):
    """refresh the ● unsaved marker and page count in a column header"""
    head = col.winfo_children()
    if len(head) < 2:
        return
    title_row, sub_row = head[0], head[1]
    for w in title_row.winfo_children():
        if isinstance(w, ctk.CTkLabel):
            name = col.doc.name or _("เอกสารใหม่")
            w.configure(text=("● " if col.doc.dirty else "") + (name if len(name) <= 26 else name[:24] + "…"))
            break
    for w in sub_row.winfo_children():
        if isinstance(w, ctk.CTkLabel):
            w.configure(text=_("%d หน้า") % col.doc.page_count)
            break
