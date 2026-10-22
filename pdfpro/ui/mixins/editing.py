"""Tools, selection and mouse / keyboard interaction with overlay objects."""

import copy
import math
import sys
import tkinter as tk

import pymupdf as fitz

from pdfpro.core.overlay import obj_bbox
from pdfpro.i18n import _
from pdfpro.ui.constants import TOOLS
from pdfpro.ui.dialogs.text_dialog import TextDialog
from pdfpro.ui.icons import icon
from pdfpro.ui.theme import ACCENT, MUTED, SEL, SOFT, F


class EditingMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def set_tool(self, t):
        self.tool = t
        self.pdfsel = None
        for k, b in self.tool_btns.items():
            on = k == t
            b.configure(
                fg_color=SOFT if on else "transparent",
                text_color=ACCENT if on else MUTED,
                image=icon(k, 20, ACCENT if on else None),
                font=F(11, "bold" if on else "normal"),
            )
        self.sel = None
        self.draw_selection()
        cur = {"edittext": "xterm", "text": "xterm", "select": "arrow"}.get(t, "crosshair")
        self.cv.configure(cursor=cur)
        self.render_props()
        self.update_state()

    def sel_obj(self):
        if self.sel is None or not self.has_doc():
            return None
        objs = self.objs[self.cur]
        return objs[self.sel] if 0 <= self.sel < len(objs) else None

    def add_obj(self, o, select=True):
        self.push_undo()
        self.objs[self.cur].append(o)
        if select:
            self.sel = len(self.objs[self.cur]) - 1
        self.refresh()

    def delete_obj(self):
        if self.sel_obj() is None:
            return
        self.push_undo()
        self.objs[self.cur].pop(self.sel)
        self.sel = None
        self.refresh()

    def duplicate_obj(self):
        o = self.sel_obj()
        if not o:
            return
        c = copy.deepcopy(o)
        self._move(c, 12, 12)
        self.add_obj(c)

    def order_obj(self, front):
        o = self.sel_obj()
        if not o:
            return
        self.push_undo()
        lst = self.objs[self.cur]
        lst.pop(self.sel)
        if front:
            lst.append(o)
            self.sel = len(lst) - 1
        else:
            lst.insert(0, o)
            self.sel = 0
        self.refresh()

    @staticmethod
    def _move(o, dx, dy):
        t = o["type"]
        if t in ("line", "arrow"):
            o["p1"] = (o["p1"][0] + dx, o["p1"][1] + dy)
            o["p2"] = (o["p2"][0] + dx, o["p2"][1] + dy)
        elif t == "ink":
            o["pts"] = [(x + dx, y + dy) for x, y in o["pts"]]
        else:
            r = o["rect"]
            o["rect"] = [r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy]

    def hit(self, cx, cy):
        objs = self.objs[self.cur]
        for i in range(len(objs) - 1, -1, -1):
            o = objs[i]
            if o["type"] in ("line", "arrow"):
                a = self.to_disp(o["p1"])
                b = self.to_disp(o["p2"])
                if self._seg_dist((cx, cy), a, b) <= max(6, o["width"] * self.zoom / 2 + 3):
                    return i
                continue
            x0, y0, x1, y1 = self.disp_rect(obj_bbox(o))
            if x0 - 3 <= cx <= x1 + 3 and y0 - 3 <= cy <= y1 + 3:
                return i
        return None

    @staticmethod
    def _seg_dist(p, a, b):
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def draw_selection(self):
        self.cv.delete("sel")
        if self.pdfsel and self.has_doc():
            x0, y0, x1, y1 = self.disp_rect(fitz.Rect(self.pdfsel["bbox"]))
            self.cv.create_rectangle(
                x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline="#f59e0b", width=2.5, dash=(6, 4), tags="sel"
            )
            lx, ly = max(x0, self.ox), max(y0, self.oy)
            self.cv.create_rectangle(lx, ly, lx + 96, ly + 22, fill="#f59e0b", outline="", tags="sel")
            self.cv.create_text(
                lx + 48, ly + 11, text=_("รูปในไฟล์"), fill="white", font=("Helvetica", 11, "bold"), tags="sel"
            )
        o = self.sel_obj()
        if not o:
            return
        if o["type"] in ("line", "arrow"):
            for k in ("p1", "p2"):
                x, y = self.to_disp(o[k])
                self.cv.create_oval(
                    x - 7, y - 7, x + 7, y + 7, fill="white", outline=SEL, width=2, tags=("sel", "h_" + k)
                )
            return
        x0, y0, x1, y1 = self.disp_rect(obj_bbox(o))
        self.cv.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=SEL, width=1.5, tags="sel")
        for k, (x, y) in {
            "nw": (x0 - 3, y0 - 3),
            "ne": (x1 + 3, y0 - 3),
            "sw": (x0 - 3, y1 + 3),
            "se": (x1 + 3, y1 + 3),
        }.items():
            self.cv.create_oval(x - 6, y - 6, x + 6, y + 6, fill="white", outline=SEL, width=2, tags=("sel", "h_" + k))

    def handle_at(self, cx, cy):
        for item in self.cv.find_overlapping(cx - 3, cy - 3, cx + 3, cy + 3):
            for t in self.cv.gettags(item):
                if t.startswith("h_"):
                    return t[2:]
        return None

    def on_down(self, e):
        self.cv.focus_set()
        if not self.editor_visible() or self.mode == "view":
            return
        cx, cy = self.evpt(e)
        tool = self.tool
        self.drag = None
        if tool == "select":
            h = self.handle_at(cx, cy) if self.sel_obj() else None
            if h:
                o = self.sel_obj()
                self.drag = dict(
                    kind="resize",
                    h=h,
                    start=(cx, cy),
                    orig=copy.deepcopy(o),
                    box=self.disp_rect(obj_bbox(o)),
                    moved=False,
                )
                return
            i = self.hit(cx, cy)
            pi = None if i is not None else self.hit_pdf_image(cx, cy)
            changed = i != self.sel or (pi or {}).get("key") != (self.pdfsel or {}).get("key")
            self.sel = i
            self.pdfsel = pi
            self.draw_selection()
            if changed:
                self.render_props()
            if i is not None:
                self.drag = dict(kind="move", start=(cx, cy), last=(cx, cy), moved=False)
            return
        if tool == "text":
            i = self.hit(cx, cy)
            if i is not None and self.objs[self.cur][i]["type"] == "text":
                self.sel = i
                self.draw_selection()
                self.edit_text_obj(i)
                return
            r = TextDialog(
                self, _("เพิ่มข้อความ"), dict(text="", size=self.fsize, color=self.text_color, family=self.ffamily)
            ).run()
            if r and r["text"].strip():
                self.text_color = r["color"]
                self.fsize = r["size"]
                self.ffamily = r["family"] or self.ffamily
                spec, _note = self._spec_from_result(r)
                self.add_obj(self.make_text(spec, cx, cy - r["size"] * 0.7 * self.zoom))
            return
        if tool == "edittext":
            self.edit_existing(cx, cy)
            return
        if tool == "ink":
            self.drag = dict(kind="ink", pts=[(cx, cy)], last=(cx, cy))
            return
        self.drag = dict(kind="shape", start=(cx, cy), end=(cx, cy))

    def on_move(self, e):
        if not self.drag:
            return
        cx, cy = self.evpt(e)
        d = self.drag
        k = d["kind"]
        z = self.zoom
        if k == "move":
            if not d["moved"] and math.hypot(cx - d["start"][0], cy - d["start"][1]) < 3:
                return
            d["moved"] = True
            self.cv.move("sel", cx - d["last"][0], cy - d["last"][1])
            d["last"] = (cx, cy)
        elif k == "resize":
            d["moved"] = True
            self._apply_resize(self.sel_obj(), d, cx, cy, e.state & 0x1)
            self.draw_selection()
        elif k == "ink":
            lx, ly = d["last"]
            if abs(cx - lx) + abs(cy - ly) < 1.2:
                return
            self.cv.create_line(
                lx,
                ly,
                cx,
                cy,
                fill=self.color,
                width=max(1, self.stroke * z),
                capstyle="round",
                smooth=True,
                tags="draft",
            )
            d["pts"].append((cx, cy))
            d["last"] = (cx, cy)
        elif k == "shape":
            sx, sy = d["start"]
            t = self.tool
            if e.state & 0x1 and t in ("line", "arrow"):
                a = round(math.atan2(cy - sy, cx - sx) / (math.pi / 4)) * (math.pi / 4)
                L = math.hypot(cx - sx, cy - sy)
                cx, cy = sx + L * math.cos(a), sy + L * math.sin(a)
            d["end"] = (cx, cy)
            self.cv.delete("draft")
            w = max(1, self.stroke * z)
            if t in ("line", "arrow"):
                self.cv.create_line(
                    sx,
                    sy,
                    cx,
                    cy,
                    fill=self.color,
                    width=w,
                    capstyle="round",
                    arrow="last" if t == "arrow" else None,
                    arrowshape=(max(10, w * 4.5), max(10, w * 4.5), max(5, w * 2.4)),
                    tags="draft",
                )
            else:
                opts = dict(outline=SEL, dash=(4, 3))
                if t == "whiteout":
                    opts = dict(outline="#9ca3af", fill="white", dash=(4, 3))
                elif t == "highlight":
                    opts = dict(outline="", fill=self.hl_color, stipple="gray50")
                elif t == "rect":
                    opts = dict(outline=self.color, width=w, fill=self.fill or "")
                self.cv.create_rectangle(sx, sy, cx, cy, tags="draft", **opts)

    def on_up(self, e):
        d = self.drag
        self.drag = None
        if not d:
            return
        k = d["kind"]
        if k == "move":
            if d["moved"]:
                o = self.sel_obj()
                a = self.to_page(*d["start"])
                b = self.to_page(*d["last"])
                self.push_undo()
                self._move(o, b[0] - a[0], b[1] - a[1])
                self.refresh()
            return
        if k == "resize":
            if d["moved"]:
                o = self.sel_obj()
                new = copy.deepcopy(o)
                o.clear()
                o.update(d["orig"])
                self.push_undo()
                o.clear()
                o.update(new)
                self.refresh()
            return
        self.cv.delete("draft")
        if k == "ink":
            pts = [self.to_page(x, y) for x, y in d["pts"]]
            self.add_obj(dict(type="ink", pts=pts, color=self.color, width=self.stroke), select=False)
            return
        (sx, sy), (ex, ey) = d["start"], d["end"]
        t = self.tool
        if t in ("line", "arrow"):
            if math.hypot(ex - sx, ey - sy) < 4:
                return
            self.add_obj(
                dict(type=t, p1=self.to_page(sx, sy), p2=self.to_page(ex, ey), color=self.color, width=self.stroke)
            )
            return
        if abs(ex - sx) < 3 or abs(ey - sy) < 3:
            return
        rect = self.page_rect_from_disp(min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
        if t == "whiteout":
            self.add_obj(dict(type="whiteout", rect=rect, fill="#ffffff"))
        elif t == "highlight":
            self.add_obj(dict(type="highlight", rect=rect, color=self.hl_color), select=False)
        elif t == "rect":
            self.add_obj(dict(type="rect", rect=rect, color=self.color, width=self.stroke, fill=self.fill))

    def _apply_resize(self, o, d, cx, cy, shift):
        orig = d["orig"]
        h = d["h"]
        if h in ("p1", "p2"):
            o[h] = self.to_page(cx, cy)
            return
        bx0, by0, bx1, by1 = d["box"]
        x0, y0, x1, y1 = bx0, by0, bx1, by1
        if "e" in h:
            x1 = cx
        if "w" in h:
            x0 = cx
        if "s" in h:
            y1 = cy
        if "n" in h:
            y0 = cy
        bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
        keep = o["type"] == "text" or (o["type"] == "image") != bool(shift)
        if keep:
            s = max((x1 - x0) / bw, (y1 - y0) / bh, 0.05)
            nw, nh = bw * s, bh * s
            if "w" in h:
                x0 = x1 - nw
            else:
                x1 = x0 + nw
            if "n" in h:
                y0 = y1 - nh
            else:
                y1 = y0 + nh
        if x1 - x0 < 4 or y1 - y0 < 4:
            return
        sx, sy = (x1 - x0) / bw, (y1 - y0) / bh

        def mp(pt):
            dx, dy = self.to_disp(pt)
            return self.to_page(x0 + (dx - bx0) * sx, y0 + (dy - by0) * sy)

        t = o["type"]
        if t == "ink":
            o["pts"] = [mp(p) for p in orig["pts"]]
        elif t == "text":
            size = max(4, orig["size"] * sy)
            spec = dict(orig)
            spec["size"] = size
            n = self.make_text(spec, x0, y0, rot=orig.get("rot", 0))
            o.update(size=size, rect=n["rect"])
        else:
            o["rect"] = self.page_rect_from_disp(x0, y0, x1, y1)

    def on_double(self, e):
        if not self.has_doc() or self.tool != "select" or self.mode == "view":
            return
        cx, cy = self.evpt(e)
        i = self.hit(cx, cy)
        if i is not None and self.objs[self.cur][i]["type"] == "text":
            self.drag = None
            self.edit_text_obj(i)

    def on_context(self, e):
        if not self.editor_visible() or self.mode == "view":
            return
        cx, cy = self.evpt(e)
        i = self.hit(cx, cy)
        if i is None:
            return
        self.sel = i
        self.draw_selection()
        self.render_props()
        m = tk.Menu(self, tearoff=0)
        if self.objs[self.cur][i]["type"] == "text":
            m.add_command(label=_("แก้ไขข้อความ…"), command=lambda: self.edit_text_obj(i))
        m.add_command(label=_("ทำสำเนา"), command=self.duplicate_obj)
        m.add_command(label=_("ไว้หน้าสุด"), command=lambda: self.order_obj(True))
        m.add_command(label=_("ไว้หลังสุด"), command=lambda: self.order_obj(False))
        m.add_separator()
        m.add_command(label=_("ลบ"), command=self.delete_obj)
        m.tk_popup(e.x_root, e.y_root)

    def on_key(self, e):
        if not self.editor_visible():
            return
        if isinstance(self.focus_get(), (tk.Entry, tk.Text)):
            return
        k = e.keysym
        if self.mode == "view":
            if k in ("Left", "Up", "Prior"):
                self.goto(self.cur - 1)
            elif k in ("Right", "Down", "Next", "space"):
                self.goto(self.cur + 1)
            elif k == "Home":
                self.goto(0)
            elif k == "End":
                self.goto(self.doc.page_count - 1)
            return
        if k in ("Delete", "BackSpace") and self.sel_obj():
            self.delete_obj()
            return
        if k in ("Delete", "BackSpace") and self.pdfsel:
            self.delete_pdf_image()
            return
        if k == "Escape":
            self.set_tool("select")
            return
        if k == "Prior":
            self.goto(self.cur - 1)
            return
        if k == "Next":
            self.goto(self.cur + 1)
            return
        if k in ("Left", "Right", "Up", "Down"):
            o = self.sel_obj()
            if not o:
                self.goto(self.cur - 1 if k in ("Left", "Up") else self.cur + 1)
                return
            st = 10 if e.state & 0x1 else 1
            dx = {"Left": -st, "Right": st}.get(k, 0)
            dy = {"Up": -st, "Down": st}.get(k, 0)
            a = self.to_page(self.ox, self.oy)
            b = self.to_page(self.ox + dx, self.oy + dy)
            self.push_undo()
            self._move(o, b[0] - a[0], b[1] - a[1])
            self.refresh()
            return
        mods = 0x4 | (0x18 if sys.platform == "darwin" else 0x8)
        if e.state & mods:
            return
        keymap = {sc.lower(): key for key, _l, sc, _d in TOOLS}
        if e.char and e.char.lower() in keymap:
            self.set_tool(keymap[e.char.lower()])
