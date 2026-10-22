"""Overlay objects (text, shapes, images, redactions) and how they are burnt into a PDF page.

All coordinates are stored in *unrotated* page space (PyMuPDF default). The same code is used for
the on-screen preview and for saving, so what you see is what you get.
"""

import html
import logging
import math

import pymupdf as fitz

from pdfpro.core.fonts import fontbook
from pdfpro.utils import hex2rgb

log = logging.getLogger(__name__)


def text_size(o):
    """width / height (display orientation) and baseline offset of a text object, in points"""
    fb = fontbook()
    key, _sb, _si = fb.key_for(o)
    f = fb.fz(key)
    fbf = fb.fz(fb.fallback_key(o))
    size = o["size"]
    lines = o["text"].split("\n") or [""]
    w = 0
    for l in lines:
        lw = 0
        for c in l:
            lw += (f if f.has_glyph(ord(c)) or c == " " else fbf).text_length(c, fontsize=size)
        w = max(w, lw)
    lh, base = fb.metrics(key)
    return w * 1.04 + size * 0.9, len(lines) * size * lh + size * 0.35, base * size


def text_html(o, font):
    out = []
    for line in o["text"].split("\n"):
        runs, cur, cov = [], "", None
        for c in line:
            c_cov = c == " " or font.has_glyph(ord(c))
            if "\u0e31" <= c <= "\u0e4e" and cov is not None:  # Thai marks stay with their base char
                c_cov = cov
            if cov is None or c_cov == cov:
                cur += c
            else:
                runs.append((cur, cov))
                cur = c
            cov = c_cov
        if cur:
            runs.append((cur, cov))
        parts = []
        for s, ok in runs:
            esc = html.escape(s).replace("  ", " &nbsp;")
            parts.append(esc if ok else '<span style="font-family:fb">%s</span>' % esc)
        out.append("".join(parts))
    return "<br>".join(out)


def text_css(o, key, fbkey, sb, si):
    fb = fontbook()
    lh, _base = fb.metrics(key)
    return (
        "@font-face{font-family:pf;src:url(%s);}@font-face{font-family:fb;src:url(%s);}"
        "*{margin:0;padding:0;}body{font-family:pf;font-size:%.3fpx;line-height:%.4f;color:%s;"
        "font-weight:%s;font-style:%s;}"
        % (
            fb.reg[key]["file"],
            fb.reg[fbkey]["file"],
            o["size"],
            lh,
            o["color"],
            "bold" if sb else "normal",
            "italic" if si else "normal",
        )
    )


def arrow_head(p1, p2, w):
    a = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    L, W = max(10, w * 4.5), max(5, w * 2.4)
    tip = (p2[0] + math.cos(a) * w * 0.6, p2[1] + math.sin(a) * w * 0.6)
    b1 = (p2[0] - L * math.cos(a) + W * math.sin(a), p2[1] - L * math.sin(a) - W * math.cos(a))
    b2 = (p2[0] - L * math.cos(a) - W * math.sin(a), p2[1] - L * math.sin(a) + W * math.cos(a))
    return [tip, b1, b2]


def apply_objects(page, objs, images):
    """Burn overlay objects into a page (used for preview *and* for saving)."""
    if not objs:
        return
    reds = [o for o in objs if o["type"] == "redact"]
    if reds:
        for o in reds:
            page.add_redact_annot(fitz.Rect(o["rect"]), fill=False)
        try:
            page.apply_redactions(images=0, graphics=0)
        except TypeError:
            page.apply_redactions(images=0)
    fb = fontbook()
    for o in objs:
        t = o["type"]
        try:
            if t == "whiteout":
                page.draw_rect(fitz.Rect(o["rect"]), color=None, fill=hex2rgb(o.get("fill", "#ffffff")), width=0)
            elif t == "highlight":
                a = page.add_highlight_annot(fitz.Rect(o["rect"]))
                a.set_colors(stroke=hex2rgb(o["color"]))
                a.update()
            elif t == "rect":
                fill = hex2rgb(o["fill"]) if o.get("fill") else None
                page.draw_rect(fitz.Rect(o["rect"]), color=hex2rgb(o["color"]), fill=fill, width=o["width"])
            elif t in ("line", "arrow"):
                c = hex2rgb(o["color"])
                page.draw_line(o["p1"], o["p2"], color=c, width=o["width"], lineCap=1)
                if t == "arrow":
                    page.draw_polyline(
                        arrow_head(o["p1"], o["p2"], o["width"]), color=c, fill=c, width=0, closePath=True
                    )
            elif t == "ink":
                pts = o["pts"]
                if len(pts) == 1:
                    pts = [pts[0], (pts[0][0] + 0.1, pts[0][1])]
                page.draw_polyline(pts, color=hex2rgb(o["color"]), width=o["width"], lineCap=1, lineJoin=1)
            elif t == "image":
                page.insert_image(
                    fitz.Rect(o["rect"]), stream=images[o["img"]], rotate=o.get("rot", 0), keep_proportion=False
                )
            elif t == "text" and o["text"].strip():
                key, sb, si = fb.key_for(o)
                fbkey = fb.fallback_key(o)
                arch = fitz.Archive()
                arch.add((fb.reg[key]["buf"], fb.reg[key]["file"]))
                arch.add((fb.reg[fbkey]["buf"], fb.reg[fbkey]["file"]))
                r = fitz.Rect(o["rect"])
                page.insert_htmlbox(
                    r,
                    text_html(o, fb.fz(key)),
                    css=text_css(o, key, fbkey, sb, si),
                    archive=arch,
                    rotate=o.get("rot", 0),
                )
        except Exception as e:  # keep going even if one object fails
            log.warning("cannot draw %s object: %s", t, e)


def obj_bbox(o):
    t = o["type"]
    if t in ("line", "arrow"):
        s = max(o["width"], 4)
        r = fitz.Rect(o["p1"], o["p1"]) | o["p2"]
        return r + (-s, -s, s, s)
    if t == "ink":
        r = fitz.Rect(o["pts"][0], o["pts"][0])
        for p in o["pts"]:
            r |= p
        s = o["width"] / 2
        return r + (-s, -s, s, s)
    return fitz.Rect(o["rect"])


def render_page(doc, objs, images, index, zoom, alpha=False):
    """Render page `index` of `doc` with its overlay objects (the document itself is not modified)."""
    tmp = fitz.open()
    tmp.insert_pdf(doc, from_page=index, to_page=index)
    apply_objects(tmp[0], objs, images)
    return tmp[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), annots=True, alpha=alpha)
