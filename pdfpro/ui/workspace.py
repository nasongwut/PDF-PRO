"""Multi-file view: every open document side by side as a column of pages.

* Click a page to select it · Shift+click selects a range · Ctrl/⌘+click adds or removes a page
  · Ctrl/⌘+A selects every page of the column.
* Drag the selection within a column (reorder), onto another column (move between files) or onto
  the **"new file"** card (split the pages off into a new document).
* Holding Alt / ⌥ Option while dropping copies instead of moving.
"""

import logging
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from pdfpro import APP_NAME
from pdfpro.core.document import Document, extract_pages, page_range_label, parse_page_ranges, transfer_pages
from pdfpro.core.overlay import render_page
from pdfpro.i18n import _
from pdfpro.ui.icons import icon
from pdfpro.ui.mixins.page_actions import RIGHT_CLICK
from pdfpro.ui.theme import ACCENT, BG, BORDER, CANVAS, CARD, HOVER, MUTED, PANEL, SEL, SHADOW, SOFT, TEXT, F, tc
from pdfpro.ui.widgets import Tooltip, secondary_btn

log = logging.getLogger(__name__)

PAGE_GAP = 30  # vertical space between pages (incl. page number)
TOP_PAD = 14
MIN_COL_W = 200
MAX_PAGE_W = 260
SHIFT = 0x1

# Tk event.state bits: "copy instead of move" when dropping, "toggle selection" when clicking
if sys.platform == "darwin":
    COPY_MASK = 0x10  # Option
    TOGGLE_MASK = 0x8  # Command
    MOD_LABEL, COPY_LABEL = "⌘", "⌥ Option"
elif sys.platform.startswith("win"):
    COPY_MASK = 0x20000  # Alt
    TOGGLE_MASK = 0x4  # Control
    MOD_LABEL, COPY_LABEL = "Ctrl", "Alt"
else:
    COPY_MASK = 0x8  # Alt (Mod1)
    TOGGLE_MASK = 0x4  # Control
    MOD_LABEL, COPY_LABEL = "Ctrl", "Alt"


def _short(name, n=26):
    return name if len(name) <= n else name[: n - 2] + "…"


class PageColumn(ctk.CTkFrame):
    """One document: header + scrollable vertical strip of page thumbnails with multi-selection."""

    def __init__(self, view: "MultiView", doc: Document, width: int):
        super().__init__(view.cols, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        self.view, self.app, self.doc = view, view.app, doc
        self.images = {}
        self.slots = []  # [(y0, y1)] canvas extent of each page
        self._geo = []
        self.selection = set()
        self.anchor = None
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
        for seq in ("<Control-a>", "<Command-a>"):
            try:
                self.canvas.bind(seq, lambda e: self.select_all())
            except tk.TclError:
                pass
        self.canvas.bind("<Escape>", lambda e: self.set_selection(set()))
        for seq in RIGHT_CLICK:
            self.canvas.bind(seq, self._context_menu)
        self.app.bind_page_keys(self.canvas, lambda: (self.doc, sorted(self.selection)))
        self.app._bind_wheel(self.canvas, lambda d: self.canvas.yview_scroll(d, "units"))
        self.col_w = width

    # ------------------------------------------------------------------ header
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        self.title = ctk.CTkLabel(head, text="", font=F(13, "bold"), text_color=TEXT, anchor="w")
        self.title.pack(side="left", fill="x", expand=True)
        if self.doc.path:
            Tooltip(self.title, self.doc.path)
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
        sub.pack(fill="x", padx=12, pady=(0, 2))
        self.info = ctk.CTkLabel(sub, text="", font=F(11), text_color=MUTED)
        self.info.pack(side="left")
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

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=10, pady=(0, 6))
        b = ctk.CTkButton(
            tools,
            text=_("แยกหน้าเป็นไฟล์ใหม่…"),
            image=icon("extract", 14),
            height=24,
            corner_radius=7,
            fg_color=CARD,
            hover_color=HOVER,
            text_color=TEXT,
            font=F(11),
            command=self.split_dialog,
        )
        b.pack(side="left", fill="x", expand=True)
        Tooltip(b, _("พิมพ์ช่วงหน้า เช่น 10-20 แล้วแยกออกมาเป็นไฟล์ใหม่"))
        b = ctk.CTkButton(
            tools,
            text=_("เลือกทั้งหมด"),
            height=24,
            width=10,
            corner_radius=7,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=TEXT,
            font=F(11),
            command=self.select_all,
        )
        b.pack(side="left", padx=(4, 0))
        self.refresh_header()

    def refresh_header(self):
        self.title.configure(text=("● " if self.doc.dirty else "") + _short(self.doc.title or _("เอกสารใหม่")))
        text = _("%d หน้า") % self.doc.page_count
        if self.selection:
            text += "  ·  " + _("เลือก %d หน้า") % len(self.selection)
        self.info.configure(text=text, text_color=SEL if self.selection else MUTED)

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
            c.create_text(
                self.col_w / 2, y + h + 12, text=str(i + 1), fill=tc(MUTED), font=("Helvetica", 11), tags=("num%d" % i,)
            )
            self.slots.append((y, y + h))
            self._geo.append((x, y, w, h, s))
            y += h + PAGE_GAP
        c.configure(scrollregion=(0, 0, self.col_w, y))
        self.selection = {i for i in self.selection if i < self.doc.page_count}
        self.draw_selection()
        self.refresh_header()
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
            self.canvas.tag_raise("sel")
        self._job = self.after(5, self._render_some)

    # ------------------------------------------------------------------ selection
    def draw_selection(self):
        c = self.canvas
        c.delete("sel")
        for i in sorted(self.selection):
            if i >= len(self._geo):
                continue
            x, y, w, h, _s = self._geo[i]
            c.create_rectangle(x - 4, y - 4, x + w + 4, y + h + 4, outline=SEL, width=3, tags="sel")
            c.create_rectangle(x + w - 22, y + 6, x + w - 6, y + 22, fill=SEL, outline="", tags="sel")
            c.create_text(x + w - 14, y + 14, text="✓", fill="white", font=("Helvetica", 10, "bold"), tags="sel")
        for i in range(len(self._geo)):
            c.itemconfigure("num%d" % i, fill=SEL if i in self.selection else tc(MUTED))

    def set_selection(self, pages, anchor=None):
        self.selection = set(pages)
        if anchor is not None:
            self.anchor = anchor
        self.draw_selection()
        self.refresh_header()
        if self.selection:
            self.view.clear_other_selections(self)

    def select_all(self):
        self.set_selection(range(self.doc.page_count), 0)

    def click_select(self, i, state):
        if state & SHIFT and self.anchor is not None:
            a, b = sorted((self.anchor, i))
            self.set_selection(set(range(a, b + 1)) | (self.selection if state & TOGGLE_MASK else set()))
        elif state & TOGGLE_MASK:
            self.set_selection(self.selection ^ {i}, i)
        elif i not in self.selection:
            self.set_selection({i}, i)
        else:
            self.anchor = i  # keep a multi-selection so it can be dragged

    # ------------------------------------------------------------------ hit testing
    def page_at(self, y):
        for i, (y0, y1) in enumerate(self.slots):
            if y0 - 4 <= y <= y1 + 4:
                return i
        return None

    def insert_index(self, y):
        """position the dropped pages would get when released at canvas-y"""
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

    # ------------------------------------------------------------------ mouse
    def _press(self, e):
        self.canvas.focus_set()
        i = self.page_at(self.canvas.canvasy(e.y))
        self.view.drag = None
        if i is None:
            if not e.state & (SHIFT | TOGGLE_MASK):
                self.set_selection(set())
            return
        was_selected = i in self.selection and len(self.selection) > 1
        self.click_select(i, e.state)
        if i in self.selection:
            self.view.drag = dict(
                src=self,
                index=i,
                pages=sorted(self.selection),
                x=e.x_root,
                y=e.y_root,
                started=False,
                collapse=was_selected and not e.state & (SHIFT | TOGGLE_MASK),
            )

    def _motion(self, e):
        self.view.drag_motion(e)

    def _release(self, e):
        d = self.view.drag
        if d and not d["started"] and d.get("collapse"):  # plain click inside a multi-selection
            self.set_selection({d["index"]}, d["index"])
        self.view.drag_release(e)

    def _context_menu(self, e):
        self.canvas.focus_set()
        i = self.page_at(self.canvas.canvasy(e.y))
        if i is None:
            return "break"
        if i not in self.selection:
            self.set_selection({i}, i)
        self.view.drag = None
        self.app.page_menu(e, self.doc, sorted(self.selection), i)
        return "break"

    def _open_page(self, e):
        i = self.page_at(self.canvas.canvasy(e.y))
        if i is not None:
            self.doc.cur = i
            self.doc.scroll = (0.0, 0.0)
            self.app.activate(self.doc)

    # ------------------------------------------------------------------ split by typing a range
    def split_dialog(self):
        initial = page_range_label(sorted(self.selection))[1:] if self.selection else "1-%d" % self.doc.page_count
        text = simpledialog.askstring(
            _("แยกหน้าเป็นไฟล์ใหม่"),
            _("ไฟล์ %s มี %d หน้า\nพิมพ์หน้าที่ต้องการแยก เช่น 10-20 หรือ 1,3,5-7")
            % (_short(self.doc.title or _("เอกสารใหม่"), 40), self.doc.page_count),
            initialvalue=initial,
            parent=self,
        )
        if not text:
            return
        try:
            pages = parse_page_ranges(text, self.doc.page_count)
        except ValueError:
            messagebox.showerror(APP_NAME, _("ช่วงหน้าไม่ถูกต้อง"), parent=self)
            return
        remove = False
        if len(pages) < self.doc.page_count:
            ans = messagebox.askyesnocancel(
                APP_NAME,
                _("แยกหน้า %s (%d หน้า) เป็นไฟล์ใหม่\n\nYes = ย้ายออกจากไฟล์เดิม\nNo = คัดลอก (ไฟล์เดิมไม่เปลี่ยน)")
                % (page_range_label(pages)[1:], len(pages)),
                parent=self,
            )
            if ans is None:
                return
            remove = bool(ans)
        self.view.split_to_new(self.doc, pages, copy_mode=not remove)


class NewFileZone(ctk.CTkFrame):
    """Dashed drop target at the end of the columns: dropping pages here creates a new document."""

    def __init__(self, view: "MultiView", height: int):
        super().__init__(
            view.cols, fg_color=BG, corner_radius=14, border_width=2, border_color=BORDER, width=190, height=height
        )
        self.pack_propagate(False)
        self.view = view
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.42, anchor="center")
        self.badge = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=18, width=60, height=60)
        self.badge.pack()
        self.badge.pack_propagate(False)
        ctk.CTkLabel(self.badge, text="", image=icon("blank", 28, MUTED)).pack(expand=True)
        self.label = ctk.CTkLabel(
            inner, text=_("ลากหน้ามาวางที่นี่\nเพื่อแยกเป็นไฟล์ใหม่"), font=F(13, "bold"), text_color=TEXT, justify="center"
        )
        self.label.pack(pady=(12, 4))
        ctk.CTkLabel(
            inner,
            text=_("เลือกหลายหน้าด้วย Shift / %s + คลิก") % MOD_LABEL,
            font=F(11),
            text_color=MUTED,
            justify="center",
            wraplength=160,
        ).pack()
        for w in (self, inner, self.badge, self.label):
            w.newfile_zone = self

    def highlight(self, on):
        self.configure(border_color=ACCENT if on else BORDER, fg_color=SOFT if on else BG)


class MultiView(ctk.CTkFrame):
    """Container of :class:`PageColumn` — one per open document — plus the new-file drop zone."""

    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        self.columns = []
        self.zone = None
        self.drag = None
        self.ghost = None
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(top, text=_("มุมมองหลายไฟล์"), font=F(16, "bold"), text_color=TEXT).pack(side="left")
        self.hint = ctk.CTkLabel(
            top,
            text=_(
                "Shift / %s + คลิก = เลือกหลายหน้า · ลากไปไฟล์อื่น = ย้าย (กด %s ค้าง = คัดลอก) · "
                "ลากไปช่องขวาสุด = แยกเป็นไฟล์ใหม่ · ดับเบิลคลิก = แก้ไข"
            )
            % (MOD_LABEL, COPY_LABEL),
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
        keep = {col.doc: set(col.selection) for col in self.columns}
        for col in self.columns:
            col.destroy()
        if self.zone is not None:
            self.zone.destroy()
            self.zone = None
        self.columns = []
        docs = self.app.docs
        if not docs:
            return
        width = self._column_width(len(docs) + 1)
        height = self._height()
        for d in docs:
            col = PageColumn(self, d, width)
            col.selection = keep.get(d, set())
            col.configure(height=height)
            col.pack(side="left", fill="y", padx=6, pady=4)
            col.canvas.configure(height=height - 120)
            self.columns.append(col)
        self.zone = NewFileZone(self, height)
        self.zone.pack(side="left", fill="y", padx=6, pady=4)
        self.update_idletasks()
        for col in self.columns:
            col.layout()

    def _height(self):
        return max(320, self.winfo_height() - 90)

    def _column_width(self, n):
        avail = max(400, self.winfo_width() - 40)
        return int(max(MIN_COL_W, min(MAX_PAGE_W + 60, avail / max(1, n) - 16)))

    def _resize_columns(self):
        height = self._height()
        for col in self.columns:
            col.configure(height=height)
            col.canvas.configure(height=height - 120)
        if self.zone is not None:
            self.zone.configure(height=height)

    def refresh_doc(self, doc):
        for col in self.columns:
            if col.doc is doc:
                col.layout()

    def column_of(self, doc):
        return next((c for c in self.columns if c.doc is doc), None)

    def clear_other_selections(self, keep):
        for col in self.columns:
            if col is not keep and col.selection:
                col.selection = set()
                col.draw_selection()
                col.refresh_header()

    # ------------------------------------------------------------------ drag & drop
    def _target_under(self, x_root, y_root):
        """(column, None) / (None, zone) / (None, None) under the pointer"""
        w = self.winfo_containing(x_root, y_root)
        while w is not None:
            if hasattr(w, "column"):
                return w.column, None
            if hasattr(w, "newfile_zone"):
                return None, w.newfile_zone
            w = getattr(w, "master", None)
        return None, None

    def drag_motion(self, e):
        d = self.drag
        if not d:
            return
        if not d["started"]:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 6:
                return
            d["started"] = True
            self._make_ghost(d["src"], d["index"], len(d["pages"]))
        if self.ghost:
            self.ghost.geometry("+%d+%d" % (e.x_root + 12, e.y_root + 8))
        target, zone = self._target_under(e.x_root, e.y_root)
        for col in self.columns:
            if col is not target:
                col.hide_indicator()
        if self.zone is not None:
            self.zone.highlight(zone is not None)
        d["target"] = None
        if zone is not None:
            d["target"] = ("new", None)
        elif target is not None:
            cy = target.canvas.canvasy(e.y_root - target.canvas.winfo_rooty())
            idx = target.insert_index(cy)
            target.show_indicator(idx)
            d["target"] = (target, idx)
            rel = (e.y_root - target.canvas.winfo_rooty()) / max(1, target.canvas.winfo_height())
            if rel < 0.08:
                target.canvas.yview_scroll(-1, "units")
            elif rel > 0.92:
                target.canvas.yview_scroll(1, "units")
        if self.ghost is not None:
            n = len(d["pages"])
            what = _("หน้า %d") % (d["pages"][0] + 1) if n == 1 else _("%d หน้า") % n
            verb = _("คัดลอก") if e.state & COPY_MASK else _("ย้าย")
            if zone is not None:
                verb = _("แยกเป็นไฟล์ใหม่") + (" (" + _("คัดลอก") + ")" if e.state & COPY_MASK else "")
            self._ghost_label.configure(text="%s · %s" % (verb, what))

    def _make_ghost(self, col, index, count):
        self.ghost = tk.Toplevel(self)
        self.ghost.wm_overrideredirect(True)
        try:
            self.ghost.attributes("-alpha", 0.88)
            self.ghost.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.ghost.configure(bg=ACCENT)
        img = col.images.get(index)
        if img is not None:
            factor = max(1, int(max(img.width() / 110, img.height() / 140)) + 1)
            small = img.subsample(factor, factor)
            self._ghost_img = small
            holder = tk.Frame(self.ghost, bg=ACCENT)
            holder.pack(padx=2, pady=(2, 0))
            if count > 1:  # stacked look for several pages
                tk.Frame(holder, bg="white", width=small.width(), height=6).pack(padx=(8, 0), anchor="e")
            tk.Label(holder, image=small, bd=0).pack()
        self._ghost_label = tk.Label(self.ghost, text="", bg=ACCENT, fg="white", font=("Helvetica", 11, "bold"))
        self._ghost_label.pack(fill="x", padx=4, pady=3)

    def _end_drag(self):
        if self.ghost is not None:
            self.ghost.destroy()
            self.ghost = None
        for col in self.columns:
            col.hide_indicator()
        if self.zone is not None:
            self.zone.highlight(False)

    def drag_release(self, e):
        d, self.drag = self.drag, None
        self._end_drag()
        if not d or not d.get("started") or not d.get("target"):
            return
        target, idx = d["target"]
        copy_mode = bool(e.state & COPY_MASK)
        if target == "new":
            self.split_to_new(d["src"].doc, d["pages"], copy_mode)
        else:
            self.drop(d["src"].doc, d["pages"], target.doc, idx, copy_mode)

    # ------------------------------------------------------------------ operations
    def _must_copy(self, src, pages, copy_mode):
        """moving every page out of a file is not allowed — offer to copy instead; None = cancel"""
        if copy_mode or len(pages) < src.page_count:
            return copy_mode
        if messagebox.askyesno(APP_NAME, _("ไม่สามารถย้ายทุกหน้าออกจากไฟล์ได้ — คัดลอกแทนหรือไม่?")):
            return True
        return None

    def drop(self, src: Document, pages, dst: Document, position: int, copy_mode: bool = False):
        """move/copy `pages` of `src` to `position` in `dst` (undo snapshots on both documents)"""
        if src is not dst:
            copy_mode = self._must_copy(src, pages, copy_mode)
            if copy_mode is None:
                return
        src.push_undo()
        if dst is not src:
            dst.push_undo()
        try:
            new = transfer_pages(src, pages, dst, position, copy_pages=copy_mode)
        except Exception as e:
            messagebox.showerror(APP_NAME, _("ย้ายหน้าไม่สำเร็จ") + "\n%s" % e)
            return
        if src is not dst:
            src_col = self.column_of(src)
            if src_col:
                src_col.selection = set()
        self.refresh_doc(src)
        if dst is not src:
            self.refresh_doc(dst)
        self.app.refresh_tabbar()
        self.app.set_status(
            (_("คัดลอกหน้าแล้ว") if copy_mode else _("ย้ายหน้าแล้ว"))
            + " → %s · %s" % (dst.title or _("เอกสารใหม่"), page_range_label(new))
        )
        col = self.column_of(dst)
        if col is not None:
            self.after(60, lambda: col.set_selection(new, new[0] if new else None))

    def split_to_new(self, src: Document, pages, copy_mode: bool = False):
        """pages of `src` -> a new document (new tab + column), moved or copied"""
        copy_mode = self._must_copy(src, pages, copy_mode)
        if copy_mode is None:
            return
        if not copy_mode:
            src.push_undo()
        try:
            new = extract_pages(src, pages, remove=not copy_mode)
        except Exception as e:
            messagebox.showerror(APP_NAME, _("แยกไฟล์ไม่สำเร็จ") + "\n%s" % e)
            return
        new.fitted = False
        self.app.docs.append(new)
        src_col = self.column_of(src)
        if src_col:
            src_col.selection = set()
        self.rebuild()
        self.app.refresh_tabbar()
        self.app.set_status(
            _("สร้างไฟล์ใหม่ %s (%d หน้า) — กด “บันทึก” ใต้ชื่อไฟล์เพื่อเก็บ") % (new.suggested_name, new.page_count)
        )
        self.after(150, self._scroll_to_end)

    def _scroll_to_end(self):
        try:
            self.scroller._parent_canvas.xview_moveto(1.0)  # CTkScrollableFrame internals
        except (AttributeError, tk.TclError):
            pass
