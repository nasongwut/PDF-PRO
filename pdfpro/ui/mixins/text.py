"""Text objects and editing text that already exists in the PDF."""

import pymupdf as fitz

from pdfpro.core.fonts import resolve_span_font
from pdfpro.core.overlay import text_size
from pdfpro.core.thai import TH_STYLE, normalize_thai
from pdfpro.i18n import _
from pdfpro.ui.dialogs.text_dialog import TextDialog
from pdfpro.utils import int2hex, norm_name


class TextMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    TEXT_KEYS = (
        "text",
        "size",
        "color",
        "bold",
        "italic",
        "family",
        "fontkey",
        "thstyle",
        "label",
        "orig",
        "from_orig",
    )

    def make_text(self, spec, cx, cy, rot=None, baseline=False):
        """text object whose display top-left (or first baseline when baseline=True) is at canvas (cx, cy)"""
        o = dict(type="text")
        o.update({k: spec[k] for k in self.TEXT_KEYS if k in spec})
        o.setdefault("bold", False)
        o.setdefault("italic", False)
        w, h, base = text_size(o)
        if baseline:
            cy -= base * self.zoom
        o["rect"] = self.page_rect_from_disp(cx, cy, cx + w * self.zoom, cy + h * self.zoom)
        o["rot"] = self.page().rotation if rot is None else rot
        return o

    def _text_anchor(self, o):
        x0, y0, x1, y1 = self.disp_rect(fitz.Rect(o["rect"]))
        return x0, y0

    def _baseline_anchor(self, o):
        cx, cy = self._text_anchor(o)
        return cx, cy + text_size(o)[2] * self.zoom

    def _spec_from_result(self, r, orig=None):
        spec = dict(
            text=r["text"],
            size=r["size"],
            color=r["color"],
            bold=r["bold"],
            italic=r["italic"],
            orig=orig,
            fontkey=None,
            family=None,
        )
        note = ""
        if r.get("original") and orig:
            exact = r["bold"] == orig["bold"] and r["italic"] == orig["italic"]
            rs, note = resolve_span_font(
                self.doc, self.page(), orig, r["text"], exact=exact, bold=r["bold"], italic=r["italic"]
            )
            spec.update(rs)
            spec["bold"], spec["italic"], spec["from_orig"] = r["bold"], r["italic"], True
        else:
            fam = r.get("family") or "Sarabun"
            spec.update(family=fam, label=fam, from_orig=False, thstyle=any(k in norm_name(fam) for k in TH_STYLE))
        return spec, note

    def _restyle(self, o, **ch):
        """change text properties while keeping the first baseline in place"""
        r = dict(
            text=o["text"],
            size=o["size"],
            color=o["color"],
            bold=o.get("bold", False),
            italic=o.get("italic", False),
            original=bool(o.get("from_orig")),
            family=o.get("family"),
        )
        r.update(ch)
        spec, note = self._spec_from_result(r, o.get("orig"))
        cx, bl = self._baseline_anchor(o)
        n = self.make_text(spec, cx, bl, rot=o.get("rot", 0), baseline=True)
        o.clear()
        o.update(n)
        if note:
            self.set_status(note)

    def _resize_text(self, o, size):
        self._restyle(o, size=size)

    def _dialog_for(self, title, o):
        orig = o.get("orig")
        label = orig["font"].split("+", 1)[-1] if orig else None
        spec = dict(o)
        spec.setdefault("from_orig", bool(orig))
        return TextDialog(self, title, spec, None, original=label).run()

    def edit_text_obj(self, idx):
        if idx is None:
            return
        o = self.objs[self.cur][idx]
        r = self._dialog_for(_("แก้ไขข้อความ"), o)
        if not r:
            return
        self.push_undo()
        if not r["text"].strip():
            self.objs[self.cur].pop(idx)
            self.sel = None
        else:
            spec, note = self._spec_from_result(r, o.get("orig"))
            cx, bl = self._baseline_anchor(o)
            n = self.make_text(spec, cx, bl, rot=o.get("rot", 0), baseline=True)
            o.clear()
            o.update(n)
            self.text_color = r["color"]
            self.fsize = r["size"]
            if note:
                self.set_status(note)
        self.refresh()

    def edit_existing(self, cx, cy):
        px, py = self.to_page(cx, cy)
        best = None
        for b in self.page().get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    r = fitz.Rect(sp["bbox"])
                    if sp["text"].strip() and r.x0 - 1 <= px <= r.x1 + 1 and r.y0 - 1 <= py <= r.y1 + 1:
                        best = sp
        if not best:
            self.set_status(_("ไม่พบข้อความตรงจุดที่คลิก (ไฟล์อาจเป็นภาพสแกน) — ใช้ “ปิดทับ” + “ข้อความ” แทน"))
            return
        sp = best
        base = sp["font"].split("+", 1)[-1]
        nb = norm_name(base)
        ob = bool(sp["flags"] & 16) or any(k in nb for k in ("bold", "black", "heavy"))
        oi = bool(sp["flags"] & 2) or "italic" in nb or "oblique" in nb
        orig = dict(font=sp["font"], flags=sp["flags"], bold=ob, italic=oi)
        spec0 = dict(
            text=normalize_thai(sp["text"]).strip(),
            size=round(sp["size"], 2),
            color=int2hex(sp["color"]),
            bold=ob,
            italic=oi,
            from_orig=True,
        )
        r = TextDialog(self, _("แก้ข้อความเดิม"), spec0, None, original=base).run()
        if not r:
            return
        self.push_undo()
        bb = fitz.Rect(sp["bbox"])
        h = bb.height
        self.objs[self.cur].append(
            dict(type="redact", rect=[bb.x0 + 0.3, bb.y0 + h * 0.2, bb.x1 - 0.3, bb.y1 - h * 0.2])
        )
        self.sel = None
        if r["text"].strip():
            spec, note = self._spec_from_result(r, orig)
            ox, oy = self.to_disp(sp["origin"])
            self.objs[self.cur].append(self.make_text(spec, ox, oy, baseline=True))
            self.sel = len(self.objs[self.cur]) - 1
            if note:
                self.set_status(note)
        self.refresh()
