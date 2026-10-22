#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF PRO — โปรแกรมเปิดและแก้ไขไฟล์ PDF  (Python · tkinter/CustomTkinter · PyMuPDF)

  • เปิด / บันทึก PDF, ซูม, เลื่อนหน้า, ภาพย่อหน้า, โหมดมืด/สว่าง
  • เพิ่มข้อความภาษาไทย (ฟอนต์ Sarabun ฝังในไฟล์), แก้ข้อความเดิมในไฟล์
  • ลบ/ปิดทับ, ไฮไลต์, ปากกา, กรอบ, เส้น, ลูกศร, แทรกรูปภาพ, ลายเซ็น
  • เลือก ย้าย ปรับขนาด ลบ วัตถุ · เลิกทำ/ทำซ้ำ
  • หมุน ลบ เรียง ทำสำเนา แทรกหน้าว่าง รวมไฟล์ แยกหน้าเป็นไฟล์ใหม่

ติดตั้ง:  pip install pymupdf customtkinter pillow
"""
import copy
import json
import shutil
import subprocess
import tempfile
import time
import html
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, simpledialog

def _fatal(msg):
    r = tk.Tk(); r.withdraw()
    messagebox.showerror("PDF PRO", msg)
    sys.exit(1)

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        _fatal("ยังไม่ได้ติดตั้ง PyMuPDF\n\nเปิด Terminal แล้วพิมพ์:\npip3 install pymupdf customtkinter pillow")
try:
    import customtkinter as ctk
    from PIL import Image
except ImportError:
    _fatal("ยังไม่ได้ติดตั้ง CustomTkinter / Pillow\n\nเปิด Terminal แล้วพิมพ์:\npip3 install customtkinter pillow")

APP = "PDF PRO"
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONT_REG = os.path.join(FONT_DIR, "Sarabun-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Sarabun-Bold.ttf")
HAS_FONT = os.path.exists(FONT_REG)


# ----------------------------------------------------------------------
#   settings (language, theme, recent files) — stored per user
# ----------------------------------------------------------------------
def _config_dir():
    if sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/PDF PRO")
    elif os.name == "nt":
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "PDF PRO")
    else:
        d = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "pdfpro")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.join(HERE, ".pdfpro")
        os.makedirs(d, exist_ok=True)
    return d

CONFIG_DIR = _config_dir()
USER_FONT_DIR = os.path.join(CONFIG_DIR, "fonts")
THUMB_DIR = os.path.join(CONFIG_DIR, "thumbs")
for _d in (USER_FONT_DIR, THUMB_DIR):
    os.makedirs(_d, exist_ok=True)
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
SETTINGS = {"lang": "th", "theme": "system", "recent": [], "mode": "edit"}
try:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as _f:
        SETTINGS.update(json.load(_f))
except Exception:
    pass

def save_settings():
    try:
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=1)
        os.replace(tmp, SETTINGS_PATH)
    except Exception as e:
        print("settings:", e)

EN = {}
def _(s):
    """translate a Thai UI string (the Thai text is the key)"""
    if SETTINGS.get("lang") == "en":
        return EN.get(s, s)
    return s
import re
import struct
import threading

def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def int2hex(c):
    return "#%06x" % (c & 0xFFFFFF)

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

_THAI_PUA = {0xF700: "\u0e10", 0xF701: "\u0e34", 0xF702: "\u0e35", 0xF703: "\u0e36", 0xF704: "\u0e37",
             0xF705: "\u0e48", 0xF706: "\u0e49", 0xF707: "\u0e4a", 0xF708: "\u0e4b", 0xF709: "\u0e4c",
             0xF70A: "\u0e48", 0xF70B: "\u0e49", 0xF70C: "\u0e4a", 0xF70D: "\u0e4b", 0xF70E: "\u0e4c",
             0xF70F: "\u0e0d", 0xF710: "\u0e31", 0xF711: "\u0e4d", 0xF712: "\u0e47", 0xF713: "\u0e48",
             0xF714: "\u0e49", 0xF715: "\u0e4a", 0xF716: "\u0e4b", 0xF717: "\u0e4c", 0xF718: "\u0e38",
             0xF719: "\u0e39", 0xF71A: "\u0e3a"}

def normalize_thai(s):
    """fix text extracted from Thai PDFs (private-use mark glyphs, split SARA AM)"""
    s = s.translate(_THAI_PUA)
    s = re.sub("\u0e4d\u0e32", "\u0e33", s)                       # ํ + า  -> ำ
    s = re.sub("([\u0e48-\u0e4b])\u0e4d\u0e32", "\\1\u0e33", s)
    return s

def has_thai(s):
    return any("\u0e00" <= c <= "\u0e7f" for c in s)


# ======================================================================
#   Fonts: bundled, built-in, installed (Mac / Windows / Linux) and
#   fonts embedded in the PDF itself
# ======================================================================
BUNDLED = {
    "TH Sarabun New": {(0, 0): "THSarabunNew.ttf", (1, 0): "THSarabunNew-Bold.ttf",
                       (0, 1): "THSarabunNew-Italic.ttf", (1, 1): "THSarabunNew-BoldItalic.ttf"},
    "Sarabun": {(0, 0): "Sarabun-Regular.ttf", (1, 0): "Sarabun-Bold.ttf",
                (0, 1): "Sarabun-Italic.ttf", (1, 1): "Sarabun-BoldItalic.ttf"},
}
BUILTIN = {   # PDF base-14 look-alikes shipped with MuPDF
    "Helvetica": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
    "Times": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
    "Courier": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
}
PREFERRED_SYSTEM = ["Tahoma", "Thonburi", "Leelawadee UI", "Leelawadee", "TH SarabunPSK", "TH Sarabun New",
                    "Angsana New", "Cordia New", "Browallia New", "AngsanaUPC", "CordiaUPC", "Krungthep", "Silom",
                    "Ayuthaya", "Sathu", "Sukhumvit Set", "Noto Sans Thai", "Noto Serif Thai", "Arial",
                    "Helvetica Neue", "Times New Roman", "Georgia", "Verdana", "Calibri", "Cambria", "Segoe UI"]
TH_STYLE = ("thsarabun", "sarabunpsk", "angsana", "cordia", "browallia", "eucrosia", "freesia", "iris", "jasmine",
            "kodchiang", "lily", "thniramit", "thkodchasal", "thchakra", "thbaijam", "thcharmof", "thkrub",
            "thmaliwan", "thsrisakdi", "thfahkwang", "thk2d", "thmali", "thchamornman", "thniramitas")


def _font_dirs():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        dirs = ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                os.path.join(home, "Library/Fonts")]
    elif os.name == "nt":
        win = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [os.path.join(win, "Fonts"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    else:
        dirs = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
                os.path.join(home, ".local/share/fonts")]
    return dirs + [USER_FONT_DIR]


def _read_names(path):
    """family / style / postscript / full name and Thai support of a TTF/OTF/TTC (first face)"""
    with open(path, "rb") as f:
        tag = f.read(4)
        off = 0
        if tag == b"ttcf":
            f.read(4); n = struct.unpack(">I", f.read(4))[0]
            if n < 1:
                return None
            off = struct.unpack(">I", f.read(4))[0]
        f.seek(off)
        hdr = f.read(12)
        if len(hdr) < 12:
            return None
        num = struct.unpack(">H", hdr[4:6])[0]
        recs = f.read(16 * num)
        tables = {}
        for i in range(num):
            t, _c, o, l = struct.unpack(">4sIII", recs[i * 16:i * 16 + 16])
            tables[t] = (o, l)
        if b"name" not in tables:
            return None
        f.seek(tables[b"name"][0]); data = f.read(tables[b"name"][1])
        thai = False
        if b"OS/2" in tables:
            f.seek(tables[b"OS/2"][0] + 42)
            r1 = f.read(4)
            if len(r1) == 4:
                thai = bool(struct.unpack(">I", r1)[0] & (1 << 10))
    fmt, count, so = struct.unpack(">HHH", data[:6])
    names = {}
    for i in range(count):
        pid, eid, lid, nid, ln, no = struct.unpack(">HHHHHH", data[6 + 12 * i:18 + 12 * i])
        if nid not in (1, 2, 4, 6, 16, 17):
            continue
        raw = data[so + no:so + no + ln]
        try:
            if pid == 3 or pid == 0:
                s = raw.decode("utf-16-be")
                score = 3 if (pid == 3 and lid == 0x409) else 2
            elif pid == 1 and lid == 0:
                s = raw.decode("mac_roman"); score = 1
            else:
                continue
        except Exception:
            continue
        if nid not in names or names[nid][1] < score:
            names[nid] = (s, score)
    g = lambda k: names[k][0] if k in names else ""
    fam = g(16) or g(1); sty = g(17) or g(2)
    return fam, sty, g(6), g(4), thai


class SystemFonts:
    """index of fonts installed on this computer (+ fonts the user added to PDF PRO).
    Built in a background thread with pure python (no MuPDF calls)."""
    def __init__(self):
        self.families = {}     # norm family -> {"name", "faces": {(b,i): path}, "thai": bool, "user": bool}
        self.ps = {}           # norm postscript/full name -> (path, family, b, i)
        self.lock = threading.Lock()
        self.ready = threading.Event()
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        try:
            for d in _font_dirs():
                if not d or not os.path.isdir(d):
                    continue
                for root, _d, files in os.walk(d):
                    for fn in files:
                        if fn.lower().endswith((".ttf", ".otf", ".ttc")):
                            self.add_file(os.path.join(root, fn))
        finally:
            self.ready.set()

    def add_file(self, p):
        try:
            r = _read_names(p)
        except Exception:
            return None
        if not r or not r[0] or r[0].startswith((".", "CustomTkinter", "LastResort")):
            return None
        fam, sty, ps, full, thai = r
        s = sty.lower()
        b = int(any(k in s for k in ("bold", "black", "heavy", "semibold", "demi")))
        it = int("italic" in s or "oblique" in s)
        with self.lock:
            e = self.families.setdefault(_norm(fam), {"name": fam, "faces": {}, "thai": False, "user": False})
            e["thai"] = e["thai"] or thai
            e["user"] = e["user"] or p.startswith(USER_FONT_DIR)
            if (b, it) not in e["faces"] or s in ("regular", "bold", "italic", "bold italic"):
                e["faces"][(b, it)] = p
            for n in (ps, full):
                if n:
                    self.ps.setdefault(_norm(n), (p, fam, b, it))
        return fam

    def face(self, family, bold, italic):
        e = self.families.get(_norm(family))
        if not e:
            return None
        f = e["faces"]
        for k in ((bold, italic), (bold, 0), (0, italic), (0, 0)):
            if k in f:
                return f[k], k
        p = next(iter(f.items()))
        return p[1], p[0]

    def install(self, src):
        """copy a font file into PDF PRO's own font folder and index it -> family name"""
        dst = os.path.join(USER_FONT_DIR, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        return self.add_file(dst)


class FontBook:
    """registry of font buffers used by text objects (append-only, survives undo)"""
    def __init__(self):
        self.reg = {}          # key -> {"buf", "file", "label"}
        self._fz = {}
        self.system = SystemFonts()

    def add(self, key, buf, label):
        if key not in self.reg:
            self.reg[key] = {"buf": buf, "file": "f%d.ttf" % (len(self.reg) + 1), "label": label}
        return key

    def fz(self, key):
        if key not in self._fz:
            self._fz[key] = fitz.Font(fontbuffer=self.reg[key]["buf"])
        return self._fz[key]

    def family_key(self, family, bold=False, italic=False):
        """-> (key, synth_bold, synth_italic) for a family name"""
        bi = (int(bool(bold)), int(bool(italic)))
        if family in BUNDLED:
            fn = BUNDLED[family][bi]
            p = os.path.join(FONT_DIR, fn)
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return self.add("b:" + fn, f.read(), family), False, False
            family = "Helvetica"
        if family in BUILTIN:
            code = BUILTIN[family][bi]
            return self.add("i:" + code, fitz.Font(code).buffer, family), False, False
        r = self.system.face(family, *bi)
        if r:
            path, got = r
            try:
                with open(path, "rb") as f:
                    buf = f.read()
                key = self.add("s:" + path, buf, family)
                self.fz(key)
                return key, bool(bi[0] and not got[0]), bool(bi[1] and not got[1])
            except Exception:
                pass
        return self.family_key("Sarabun", bold, italic)

    def key_for(self, o):
        if o.get("fontkey") and o["fontkey"] in self.reg:
            return o["fontkey"], False, False
        return self.family_key(o.get("family") or "Sarabun", o.get("bold"), o.get("italic"))

    def fallback_key(self, o):
        fam = "TH Sarabun New" if o.get("thstyle") else "Sarabun"
        return self.family_key(fam, o.get("bold"), o.get("italic"))[0]

    @staticmethod
    def covers(font, text):
        return all(font.has_glyph(ord(c)) for c in text if c not in " \n\t\r\u200b\u200c\u200d")

    def metrics(self, key):
        f = self.fz(key)
        asc, desc = f.ascender, f.descender
        if not (0.5 < asc < 2.5) or not (-1.5 < desc <= 0.05):
            asc, desc = 0.95, -0.25
        lh = max(1.05, min(2.3, asc - desc))
        base = ((lh - (asc - desc)) / 2 + asc)
        return lh, base

    def choices(self, thai_only=False):
        """[(family, supports_thai, kind)] — bundled, built-in, then every installed family A-Z"""
        out = [(f, True, "bundled") for f in BUNDLED] + [(f, False, "builtin") for f in BUILTIN]
        self.system.ready.wait(3.0)
        seen = {_norm(f) for f, _t, _k in out}
        with self.system.lock:
            fams = sorted(self.system.families.values(), key=lambda e: e["name"].lower())
        for e in fams:
            if _norm(e["name"]) in seen:
                continue
            out.append((e["name"], e["thai"], "user" if e["user"] else "system"))
        if thai_only:
            out = [x for x in out if x[1]]
        return out


FONTBOOK = None
def fontbook():
    global FONTBOOK
    if FONTBOOK is None:
        FONTBOOK = FontBook()
    return FONTBOOK


# ======================================================================
#   Engine: applying overlay objects to a PyMuPDF page
#   All coordinates are stored in *unrotated* page space (PyMuPDF default).
# ======================================================================
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
            if "\u0e31" <= c <= "\u0e4e" and cov is not None:   # Thai marks stay with their base char
                c_cov = cov
            if cov is None or c_cov == cov:
                cur += c
            else:
                runs.append((cur, cov)); cur = c
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
    return ("@font-face{font-family:pf;src:url(%s);}@font-face{font-family:fb;src:url(%s);}"
            "*{margin:0;padding:0;}body{font-family:pf;font-size:%.3fpx;line-height:%.4f;color:%s;"
            "font-weight:%s;font-style:%s;}"
            % (fb.reg[key]["file"], fb.reg[fbkey]["file"], o["size"], lh, o["color"],
               "bold" if sb else "normal", "italic" if si else "normal"))

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
                a.set_colors(stroke=hex2rgb(o["color"])); a.update()
            elif t == "rect":
                fill = hex2rgb(o["fill"]) if o.get("fill") else None
                page.draw_rect(fitz.Rect(o["rect"]), color=hex2rgb(o["color"]), fill=fill, width=o["width"])
            elif t in ("line", "arrow"):
                c = hex2rgb(o["color"])
                page.draw_line(o["p1"], o["p2"], color=c, width=o["width"], lineCap=1)
                if t == "arrow":
                    page.draw_polyline(arrow_head(o["p1"], o["p2"], o["width"]), color=c, fill=c, width=0, closePath=True)
            elif t == "ink":
                pts = o["pts"]
                if len(pts) == 1:
                    pts = [pts[0], (pts[0][0] + 0.1, pts[0][1])]
                page.draw_polyline(pts, color=hex2rgb(o["color"]), width=o["width"], lineCap=1, lineJoin=1)
            elif t == "image":
                page.insert_image(fitz.Rect(o["rect"]), stream=images[o["img"]], rotate=o.get("rot", 0),
                                  keep_proportion=False)
            elif t == "text" and o["text"].strip():
                key, sb, si = fb.key_for(o)
                fbkey = fb.fallback_key(o)
                arch = fitz.Archive()
                arch.add((fb.reg[key]["buf"], fb.reg[key]["file"]))
                arch.add((fb.reg[fbkey]["buf"], fb.reg[fbkey]["file"]))
                r = fitz.Rect(o["rect"])
                page.insert_htmlbox(r, text_html(o, fb.fz(key)), css=text_css(o, key, fbkey, sb, si),
                                    archive=arch, rotate=o.get("rot", 0))
        except Exception as e:  # keep going even if one object fails
            print("object error:", t, e)

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


def resolve_span_font(doc, page, span, text, exact=True, bold=None, italic=None):
    """
    Find the best font to re-typeset `text` so it looks like the original span.
    Returns (spec dict, note)
    """
    fb = fontbook()
    base = span["font"].split("+", 1)[-1]
    nb = _norm(base)
    if bold is None:
        bold = bool(span["flags"] & 16) or "bold" in nb or "black" in nb or "heavy" in nb
    if italic is None:
        italic = bool(span["flags"] & 2) or "italic" in nb or "oblique" in nb
    bold, italic = bool(bold), bool(italic)
    thstyle = any(k in nb for k in TH_STYLE)
    spec = dict(bold=bold, italic=italic, thstyle=thstyle, label=base, family=None, fontkey=None)
    # 1) the font embedded in the PDF (exact match) — if it contains every glyph we need
    try:
        for fi in (page.get_fonts(full=True) if exact else []):
            xref, basefont = fi[0], fi[3]
            if basefont.split("+", 1)[-1] != base:
                continue
            name, ext, typ, buf = doc.extract_font(xref)
            if buf and ext not in ("n/a", ""):
                f = fitz.Font(fontbuffer=buf)
                if fb.covers(f, text):
                    key = fb.add("e:%s:%d:%d" % (base, len(buf), hash(buf[:4096])), buf, base)
                    spec["fontkey"] = key
                    return spec, _("ใช้ฟอนต์เดิมจากไฟล์ (%s)") % base
            break
    except Exception as e:
        print("embedded font:", e)
    # 2) the same font installed on this computer
    fb.system.ready.wait(3.0)
    hit = fb.system.ps.get(nb) if exact else None
    if not hit and exact:
        stripped = re.sub(r"(mt|ps|psmt)$", "", nb)
        hit = fb.system.ps.get(stripped)
    if hit:
        path, fam, b, it = hit
        try:
            with open(path, "rb") as fh:
                buf = fh.read()
            key = fb.add("s:" + path, buf, fam)
            if fb.covers(fb.fz(key), text):
                spec["fontkey"] = key; spec["label"] = fam
                return spec, _("ใช้ฟอนต์ %s จากเครื่องนี้") % fam
        except Exception:
            pass
    # 3) closest family
    fam = None
    for name, keys in (("TH Sarabun New", ("thsarabun", "sarabunpsk", "sarabunnew")), ("Sarabun", ("sarabun",)),
                       ("Helvetica", ("helvetica", "arial", "liberationsans", "nimbussans")),
                       ("Times", ("times", "liberationserif", "nimbusroman")),
                       ("Courier", ("courier", "liberationmono", "nimbusmono"))):
        if any(k in nb for k in keys):
            fam = name; break
    if fam is None:
        famname = re.sub(r"[-,](bold|italic|regular|oblique|black|medium|light|semibold|bolditalic).*$", "",
                         base, flags=re.I)
        if fb.system.families.get(_norm(famname)):
            fam = fb.system.families[_norm(famname)]["name"]
    if fam is None:
        if thstyle:
            fam = "TH Sarabun New"
        elif has_thai(text):
            fam = "Sarabun"
        else:
            fam = "Times" if span["flags"] & 4 else ("Courier" if span["flags"] & 8 else "Helvetica")
    spec["family"] = fam; spec["label"] = fam
    same = _norm(fam) in nb or nb.startswith(_norm(fam)) or (fam == "Helvetica" and "helvetica" in nb) \
        or (fam == "Times" and "times" in nb) or (fam == "Courier" and "courier" in nb)
    if fam in ("Helvetica", "Times", "Courier") and has_thai(text):
        note = _("ฟอนต์เดิมไม่มีตัวอักษรไทย — ใช้ %s คู่กับ %s") % (fam, "TH Sarabun New" if thstyle else "Sarabun")
    elif same:
        note = _("ใช้ฟอนต์ %s (ตรงกับต้นฉบับ)") % fam
    else:
        note = _("ไม่พบฟอนต์ %s ในเครื่อง — ใช้ %s ที่ใกล้เคียงแทน") % (base, fam)
    return spec, note

# ======================================================================
#   English translations (Thai text is the key)
# ======================================================================
EN.update({
    "ฟอนต์เดิมไม่มีตัวอักษรไทย — ใช้ %s คู่กับ %s": "Original font has no Thai glyphs — using %s with %s",
    "ใช้ฟอนต์ %s (ตรงกับต้นฉบับ)": "Using %s (same as original)",
    "ไม่พบฟอนต์ %s ในเครื่อง — ใช้ %s ที่ใกล้เคียงแทน": "Font %s not found on this computer — using similar %s",
    "ใช้ฟอนต์ %s จากเครื่องนี้": "Using %s installed on this computer",
    "ใช้ฟอนต์เดิมจากไฟล์ (%s)": "Using the font embedded in the file (%s)",
    "เลือกสีอื่น": "More colors", "ลายเซ็น": "Signature", "เลือกฟอนต์": "Choose font", "พิมพ์": "Print",
    "หน้าแรก": "Home", "เปลี่ยนภาษา": "Change language", "สลับโหมดมืด/สว่าง": "Toggle dark / light mode",
    "เพิ่มเติม": "More", "บันทึก PDF": "Save PDF",
    "ล้างรายการไฟล์ล่าสุดทั้งหมดหรือไม่?": "Clear the whole recent files list?",
    "มีการแก้ไขที่ยังไม่ได้บันทึก\nต้องการบันทึกก่อนหรือไม่?": "You have unsaved changes.\nSave them first?",
    "ลบหน้าแล้ว — กด ⌘Z / Ctrl+Z เพื่อเลิกทำ": "Page deleted — press ⌘Z / Ctrl+Z to undo",
    "แก้ไขข้อความ": "Edit text", "การจัดการรูป": "Image actions", "ทั้งเอกสาร": "Whole document",
    "ลบรูปแล้ว — กด ⌘Z / Ctrl+Z เพื่อเลิกทำ": "Image deleted — press ⌘Z / Ctrl+Z to undo",
    "แทนที่รูปแล้ว — ย้ายหรือปรับขนาดได้ (Shift ค้างขณะลากมุม = ยืดอิสระ)":
        "Image replaced — move or resize it (hold Shift while dragging a corner to stretch)",
    "กรุณาเซ็นชื่อก่อน": "Please sign first", "ค้นหาฟอนต์…": "Search fonts…", "มากับโปรแกรม": "Bundled with PDF PRO",
    "ฟอนต์มาตรฐาน PDF": "Standard PDF font", "ฟอนต์ที่เพิ่มเอง": "Font you added", "ติดตั้งในเครื่อง": "Installed on this computer",
    "เลือกไฟล์ฟอนต์": "Choose font files", "ช่วงหน้าไม่ถูกต้อง": "Invalid page range", "รูปภาพ": "Image",
    "แทรกรูปภาพ": "Insert image", "สร้างลายเซ็น": "Create signature", "หมุนซ้าย": "Rotate left", "หมุนขวา": "Rotate right",
    "เลื่อนหน้าขึ้น": "Move page up", "เลื่อนหน้าลง": "Move page down", "แทรกหน้าว่าง": "Insert blank page",
    "ทำสำเนาหน้า": "Duplicate page", "บันทึกหน้านี้เป็นไฟล์ใหม่": "Save this page as a new file", "ลบหน้า": "Delete page",
    "เปิดไฟล์ PDF": "Open PDF", "เลือกไฟล์จากเครื่อง": "Choose a file on this computer",
    "สร้างเอกสารเปล่า": "New blank document", "เริ่มจากหน้าว่าง A4": "Start from a blank A4 page",
    "รวมไฟล์ PDF": "Merge PDFs", "รวมหลายไฟล์เป็นไฟล์เดียว": "Combine several files into one",
    "แก้ไข": "Edit", "ดู": "View", "หน้าแรก (ไฟล์ล่าสุด)": "Home (recent files)",
    "บันทึกหน้านี้เป็นไฟล์ใหม่…": "Save this page as a new file…",
    "รวมไฟล์ PDF (เพิ่มต่อจากหน้านี้)…": "Merge PDF (insert after this page)…",
    "ส่งออกรูปภาพทั้งหมดในไฟล์…": "Export all images in this file…", "เพิ่มฟอนต์…": "Add fonts…",
    "เอกสารใหม่": "New document", "เลือกไฟล์ PDF ที่จะรวม (เรียงตามลำดับที่เลือก)": "Choose PDFs to merge (in selection order)",
    "รวม %d ไฟล์แล้ว — กดบันทึกเพื่อเก็บเป็นไฟล์ใหม่": "Merged %d files — press Save to keep the new file",
    "-แก้ไข": "-edited", "✓ บันทึกแล้ว: %s": "✓ Saved: %s",
    "เลือกไฟล์ PDF ที่จะเพิ่มต่อจากหน้าปัจจุบัน": "Choose PDFs to insert after the current page",
    "เพิ่ม %d ไฟล์แล้ว": "Added %d files", "เอกสารต้องมีอย่างน้อย 1 หน้า": "A document needs at least one page",
    "สีตัวอักษร": "Text color", "ขนาดตัวอักษร (pt)": "Font size (pt)", "ฟอนต์": "Font", "ความหนาเส้น": "Line width",
    "สีพื้น": "Fill color", "สีไฮไลต์": "Highlight color", "สีที่ใช้ปิดทับ": "Cover color", "การจัดการ": "Actions",
    "รูปภาพในเอกสาร": "Images in document", "ส่งออกรูปทั้งหมด…": "Export all images…", "ทำสำเนา": "Duplicate",
    "ไว้หน้าสุด": "Bring to front", "ไว้หลังสุด": "Send to back", "ลบ": "Delete",
    "ไม่พบข้อความตรงจุดที่คลิก (ไฟล์อาจเป็นภาพสแกน) — ใช้ “ปิดทับ” + “ข้อความ” แทน":
        "No text found here (the file may be a scan) — use “Cover” + “Text” instead",
    "รูปนี้ใช้ร่วมกันใน %d หน้า (หน้า %s)\n%sรูปนี้ในทุกหน้าหรือไม่?":
        "This image is shared by %d pages (pages %s)\n%s it on every page?",
    "เลือกรูปใหม่": "Choose the new image", "แทนที่รูปในทุกหน้าแล้ว": "Image replaced on every page",
    "บันทึกรูป": "Save image", "✓ บันทึกรูปแล้ว: %s": "✓ Image saved: %s", "ไม่พบรูปภาพในไฟล์นี้": "No images in this file",
    "-รูปภาพ": "-images", "✓ ส่งออก %d รูป ไปที่ %s": "✓ Exported %d images to %s",
    "ส่งออก %d รูปเรียบร้อย\n\n%s\n\nเปิดโฟลเดอร์เลยหรือไม่?": "Exported %d images\n\n%s\n\nOpen the folder now?",
    "เลือกรูปภาพ": "Choose an image", "ตกลง": "OK", "ยกเลิก": "Cancel", "ใช้ลายเซ็นนี้": "Use signature", "ล้าง": "Clear",
    "เพิ่มฟอนต์จากไฟล์…": "Add font from file…", "เลือก": "Select",
    "ใช้ฟอนต์เดิมของข้อความในไฟล์ (หรือฟอนต์ที่ใกล้เคียงที่สุด)": "Use the text's original font (or the closest match)",
    "ย่อ": "Zoom out", "ขยาย": "Zoom in", "พอดีความกว้าง": "Fit width", "หน้าก่อนหน้า": "Previous page",
    "หน้าถัดไป": "Next page", "ไทย": "ไทย", "เปิดไฟล์": "Open", "ลบออกจากรายการ": "Remove from list",
    "เปิดหน้าต่างพิมพ์ของระบบแล้ว": "System print dialog opened",
    "โหมดดู — กด “แก้ไข” ด้านบนเพื่อเริ่มแก้ไข · ←/→ เปลี่ยนหน้า": "View mode — click “Edit” above to start editing · ←/→ change page",
    "ไฟล์นี้มีรหัสผ่าน กรุณาใส่รหัส:": "This file is password protected. Enter the password:",
    "บันทึกไฟล์ PDF": "Save PDF", "หน้า %d จาก %d": "Page %d of %d", "%s-หน้า%d.pdf": "%s-page%d.pdf",
    "✓ บันทึกหน้า %d แล้ว": "✓ Saved page %d", "รูปแบบ": "Style", "สีเส้นขอบ": "Border color", "สี": "Color",
    "รูปในไฟล์": "PDF image", "แก้ไขข้อความ…": "Edit text…", "แก้ข้อความเดิม": "Edit existing text",
    "เปิดรูปภาพนี้ไม่ได้": "Can't open this image", "แทนที่": "Replace", "%s-หน้า%d-รูป.%s": "%s-page%d-image.%s",
    "เลือกโฟลเดอร์สำหรับเก็บรูป (%d รูป)": "Choose a folder for the images (%d images)",
    "กด Enter เพื่อขึ้นบรรทัดใหม่ · ⌘/Ctrl + Enter เพื่อบันทึก": "Enter = new line · ⌘/Ctrl + Enter = done",
    "ขนาด": "Size", "ตัวหนา": "Bold", "ตัวเอียง": "Italic", "วาดลายเซ็นของคุณ": "Draw your signature",
    "ใช้เมาส์หรือแทร็กแพดเซ็นชื่อในกรอบด้านล่าง": "Sign in the box below with your mouse or trackpad",
    "ฟอนต์ทั้งหมดที่ติดตั้งในเครื่องนี้ + ฟอนต์ที่เพิ่มเข้า PDF PRO": "Every font installed on this computer + fonts added to PDF PRO",
    "เฉพาะที่รองรับภาษาไทย": "Thai-capable only", "เพิ่มฟอนต์แล้ว": "Fonts added", "พิมพ์เอกสาร": "Print document",
    "งานที่แก้ไขไว้ทั้งหมดจะถูกพิมพ์ด้วย": "All your edits are included in the printout",
    "เครื่องพิมพ์เริ่มต้น": "Default printer", "เครื่องพิมพ์": "Printer", "หน้า": "Pages", "กำหนดเอง": "Custom",
    "จำนวนชุด": "Copies", "ใช้หน้าต่างพิมพ์ของระบบ…": "Use system print dialog…", "เลิกทำ": "Undo", "ทำซ้ำ": "Redo",
    "ยินดีต้อนรับสู่ PDF PRO": "Welcome to PDF PRO",
    "เปิด แก้ไข และพิมพ์ไฟล์ PDF — ทุกอย่างทำงานในเครื่องของคุณ": "Open, edit and print PDFs — everything stays on your computer",
    "ไฟล์ล่าสุด": "Recent files", "ไม่พบไฟล์": "File not found", "เปิด": "Open", "แสดงในโฟลเดอร์": "Show in folder",
    "เตรียมงานพิมพ์ไม่สำเร็จ": "Couldn't prepare the print job", "ส่งงานพิมพ์แล้ว": "Sent to printer",
    "พิมพ์ไม่สำเร็จ": "Printing failed", "%d หน้า": "%d pages", "ทุกไฟล์": "All files",
    "รหัสผ่านไม่ถูกต้อง": "Wrong password", "เปิดไฟล์ไม่ได้\n%s": "Can't open the file\n%s",
    "รวมไฟล์ไม่สำเร็จ": "Merge failed", "บันทึกไม่สำเร็จ\n%s": "Save failed\n%s", "รวมไฟล์ไม่สำเร็จ\n%s": "Merge failed\n%s",
    "เอกสาร.pdf": "document.pdf", "💡 วิธีใช้": "💡 How to", "เพิ่มข้อความ": "Add text", "รูปในไฟล์ PDF": "Image in PDF",
    "บันทึกรูปนี้…": "Save this image…", "แทนที่ด้วยรูปอื่น…": "Replace with another image…",
    "Delete = ลบรูป · คลิกที่ว่างเพื่อยกเลิกการเลือก\nรูปที่แทนที่จะวางพอดีกรอบเดิมโดยรักษาสัดส่วน แล้วย้าย/ปรับขนาดต่อได้":
        "Delete = remove image · click empty space to deselect\nA replacement keeps its proportions inside the old box and can be moved/resized",
    "ลบรูปไม่สำเร็จ\n%s": "Couldn't delete the image\n%s", "   ไทย": "   Thai", "แสดงตัวอย่างไม่ได้": "Preview unavailable",
    "ทั้งหมด": "All", "หน้าปัจจุบัน": "Current page",
    "ไม่พบรายชื่อเครื่องพิมพ์ — จะใช้หน้าต่างพิมพ์ของระบบ": "No printers listed — the system print dialog will be used",
    "ล้างรายการ": "Clear list", "ยังไม่มีไฟล์ที่เปิดล่าสุด": "No recent files yet",
    "ไฟล์ที่คุณเปิดจะแสดงที่นี่ เพื่อเปิดซ้ำได้ในคลิกเดียว": "Files you open will appear here for one-click access",
    "เปิดไฟล์…": "Open…", "บันทึก": "Save", "บันทึกเป็น…": "Save as…", "พิมพ์…": "Print…",
    "วัตถุที่เลือก": "Selected object", "เครื่องมือ": "Tool",
    "รูปชนิดฝังในเนื้อหา (inline) แก้ไขไม่ได้ — ใช้ “ปิดทับ” แทน": "Inline images can't be edited — use “Cover” instead",
    "ลบรูปนี้": "Delete image", "รองรับภาษาไทย": "Supports Thai",
    "ไม่มีอักษรไทย (จะใช้ฟอนต์ไทยเสริมให้อัตโนมัติ)": "No Thai glyphs (a Thai font is added automatically)",
    "ยังไม่บันทึก": "unsaved", "เนื้อหา": "Content",
    "หน้านี้ %d รูป · ทั้งไฟล์ %d รูป\nคลิกที่รูปในหน้าเพื่อเลือก ลบ หรือแทนที่":
        "This page: %d · whole file: %d\nClick an image on the page to select, delete or replace it",
    "⚠️ รูปนี้ใช้ร่วมกันใน %d หน้า — การลบ/แทนที่จะมีผลทุกหน้า": "⚠️ Shared by %d pages — delete/replace affects every page",
    "หน้า%03d-รูป%02d.%s": "page%03d-image%02d.%s", "ฟอนต์ที่ใช้จริง: ": "Font in use: ",
    "เลือก / ย้าย / ปรับขนาด": "Select / move / resize", "ข้อความ": "Text", "แก้ข้อความ": "Edit text",
    "แก้ข้อความเดิมในไฟล์": "Edit existing text in the file", "ปิดทับ": "Cover", "ลบ / ปิดทับด้วยสีขาว": "Erase / cover with white",
    "ปากกา": "Pen", "ปากกา วาดอิสระ": "Freehand pen", "ไฮไลต์": "Highlight", "กรอบ": "Box", "กรอบสี่เหลี่ยม": "Rectangle",
    "เส้น": "Line", "เส้นตรง": "Straight line", "ลูกศร": "Arrow", "เส้นปากกา": "Pen stroke", "ส่วนที่ลบออก": "Removed text",
    "คลิกวัตถุเพื่อเลือก ลากเพื่อย้าย ลากมุมเพื่อปรับขนาด ดับเบิลคลิกข้อความเพื่อแก้ไข\n\nDelete = ลบ · ปุ่มลูกศร = เลื่อนทีละนิด · คลิกขวา = เมนู":
        "Click an object to select, drag to move, drag a corner to resize, double-click text to edit\n\nDelete = remove · arrow keys = nudge · right-click = menu",
    "คลิกตรงตำแหน่งบนหน้าที่ต้องการเพิ่มข้อความ แล้วพิมพ์ในหน้าต่างที่เปิดขึ้น (รองรับภาษาไทย)":
        "Click where you want the text, then type it in the window that opens (Thai supported)",
    "คลิกที่ข้อความเดิมในไฟล์ ข้อความเดิมจะถูกลบออกจริง แล้วแทนด้วยข้อความใหม่\n\nใช้ได้กับ PDF ที่มีข้อความจริง ถ้าเป็นภาพสแกนให้ใช้ “ปิดทับ” + “ข้อความ”":
        "Click existing text in the file — it is really removed and replaced by your new text\n\nWorks on PDFs with real text; for scans use “Cover” + “Text”",
    "ลากคลุมส่วนที่ต้องการลบ จะถูกปิดด้วยสีขาว (เลือกสีอื่นได้หลังวาด)": "Drag over what you want to hide — it is covered with white (color can be changed)",
    "กดค้างแล้วลากเพื่อวาดหรือเขียนอิสระ": "Press and drag to draw or write freely",
    "ลากคลุมข้อความที่ต้องการเน้น": "Drag over the text to highlight",
    "ลากเพื่อวาดกรอบ เลือกสีเส้น ความหนา และสีพื้นได้": "Drag to draw a box — choose border color, width and fill",
    "ลากเพื่อวาดเส้น · กด Shift ค้างเพื่อล็อกมุม": "Drag to draw a line · hold Shift to snap the angle",
    "ลากเพื่อวาดลูกศร · กด Shift ค้างเพื่อล็อกมุม": "Drag to draw an arrow · hold Shift to snap the angle",
    "ฟอนต์เดิม · ": "Original font · ",
})

# ======================================================================
#   Design system
# ======================================================================
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

ACCENT = "#e03c43"
ACCENT_H = "#c4323a"
BG = ("#f3f4f6", "#0f1115")
PANEL = ("#ffffff", "#181b21")
BORDER = ("#e6e8ec", "#272b33")
TEXT = ("#111827", "#e7e9ec")
MUTED = ("#6b7280", "#9aa1ad")
HOVER = ("#f1f2f5", "#23272e")
SOFT = ("#fdecec", "#3a1e22")
CANVAS = ("#e7e9ee", "#0b0d10")
SHADOW = ("#d3d6dc", "#050607")
CARD = ("#f6f7f9", "#20242b")
SEL = "#3b82f6"
MOD = "⌘" if sys.platform == "darwin" else "Ctrl+"
SWATCHES = ["#111827", "#e03c43", "#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#ffffff"]
HL_SWATCHES = ["#fde047", "#86efac", "#7dd3fc", "#f9a8d4", "#fdba74"]

def tc(pair):
    if isinstance(pair, str):
        return pair
    return pair[0] if ctk.get_appearance_mode() == "Light" else pair[1]

def F(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)

ICONS = {
    "select": '<path d="M5 3l6 17 2.5-7 7-2.5z"/>',
    "text": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "edittext": '<path d="M3 7V5h11v2M8.5 5v12M6.5 17h4"/><path d="M13.5 21l.8-3.3 5.7-5.7 2.5 2.5-5.7 5.7z"/>',
    "whiteout": '<path d="M7 20h12"/><path d="M5.2 14.8l8.6-8.6a1.8 1.8 0 012.5 0l2.5 2.5a1.8 1.8 0 010 2.5L11 19H8.4l-3.2-3.2a.9.9 0 010-1z"/>',
    "ink": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
    "highlight": '<path d="M9 11l-5 5v3h3l5-5"/><path d="M9 11l6-6 4 4-6 6z"/><path d="M14 21h7"/>',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="2"/>',
    "line": '<path d="M5 19L19 5"/>',
    "arrow": '<path d="M5 19L19 5M9 5h10v10"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5L6 20"/>',
    "sign": '<path d="M3 17c3 0 4-9 6-9s1 8 3 8 2-4 4-4 1 3 5 3"/><path d="M3 21h18"/>',
    "open": '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    "save": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 000 12h3"/>',
    "minus": '<path d="M6 12h12"/>',
    "plus": '<path d="M12 6v12M6 12h12"/>',
    "fit": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "left": '<path d="M15 6l-6 6 6 6"/>',
    "right": '<path d="M9 6l6 6-6 6"/>',
    "moon": '<path d="M20.5 13.2A8.5 8.5 0 1110.8 3.5a6.6 6.6 0 009.7 9.7z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M2.5 12h2M19.5 12h2M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "more": '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
    "rotl": '<path d="M3 4v5h5"/><path d="M3.6 9a8.5 8.5 0 112 8.6"/>',
    "rotr": '<path d="M21 4v5h-5"/><path d="M20.4 9a8.5 8.5 0 10-2 8.6"/>',
    "up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "blank": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>',
    "extract": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M12 10v7M9 14l3 3 3-3"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "merge": '<path d="M14 3H8a2 2 0 00-2 2v11a2 2 0 002 2h9a2 2 0 002-2V8z"/><path d="M14 3v5h5"/><path d="M3 8v11a2 2 0 002 2h9"/>',
    "file": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "front": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 012-2h10"/>',
    "back": '<rect x="4" y="4" width="12" height="12" rx="2"/><path d="M20 8v10a2 2 0 01-2 2H8"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "print": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "export": '<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 14v5a2 2 0 002 2h10a2 2 0 002-2v-5"/>',
    "replace": '<path d="M4 7h11l-3-3M20 17H9l3 3"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
}

_svg_cache = {}
def _svg(name, color, px):
    key = (name, color, px)
    if key not in _svg_cache:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
               'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>') % (color, ICONS[name])
        pix = fitz.open("svg", svg.encode())[0].get_pixmap(matrix=fitz.Matrix(px / 24, px / 24), alpha=True)
        _svg_cache[key] = Image.frombytes("RGBa", (pix.width, pix.height), pix.samples).convert("RGBA")
    return _svg_cache[key]

def icon(name, size=20, color=None):
    """CTkImage for both themes (rendered at 3x for sharp Retina display)"""
    if color is None:
        light, dark = "#374151", "#d4d7dd"
    elif isinstance(color, tuple):
        light, dark = color
    else:
        light = dark = color
    return ctk.CTkImage(light_image=_svg(name, light, size * 3), dark_image=_svg(name, dark, size * 3), size=(size, size))


class Tooltip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, e=None):
        self.job = self.w.after(450, self._show)

    def _leave(self, e=None):
        if self.job:
            self.w.after_cancel(self.job); self.job = None
        if self.tip:
            self.tip.destroy(); self.tip = None

    def _show(self):
        if self.tip:
            return
        x = self.w.winfo_rootx() + self.w.winfo_width() // 2
        y = self.w.winfo_rooty() + self.w.winfo_height() + 6
        self.tip = tk.Toplevel(self.w); self.tip.wm_overrideredirect(True)
        self.tip.configure(bg="#111827")
        tk.Label(self.tip, text=self.text, bg="#111827", fg="#ffffff", padx=8, pady=4,
                 font=("Helvetica", 12)).pack()
        self.tip.update_idletasks()
        self.tip.geometry("+%d+%d" % (x - self.tip.winfo_width() // 2, y))


def ghost_btn(master, ico, cmd, tip=None, size=34, isz=19):
    b = ctk.CTkButton(master, text="", image=icon(ico, isz), width=size, height=size, corner_radius=9,
                      fg_color="transparent", hover_color=HOVER, command=cmd)
    if tip:
        Tooltip(b, tip)
    return b

def primary_btn(master, text, cmd, ico=None, **kw):
    return ctk.CTkButton(master, text=text, image=icon(ico, 18, "#ffffff") if ico else None, command=cmd,
                         fg_color=ACCENT, hover_color=ACCENT_H, text_color="#ffffff", corner_radius=10,
                         height=kw.pop("height", 36), font=F(14, "bold"), **kw)

def secondary_btn(master, text, cmd, ico=None, **kw):
    return ctk.CTkButton(master, text=text, image=icon(ico, 18) if ico else None, command=cmd,
                         fg_color=PANEL, hover_color=HOVER, text_color=TEXT, border_width=1, border_color=BORDER,
                         corner_radius=10, height=kw.pop("height", 36), font=F(13), **kw)


# ======================================================================
#   Dialogs
# ======================================================================
class _Modal(ctk.CTkToplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=PANEL)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.bind("<Escape>", lambda e: self.destroy())

    def run(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + m.winfo_width() // 2 - self.winfo_reqwidth() // 2
        y = m.winfo_rooty() + max(80, m.winfo_height() // 2 - self.winfo_reqheight() // 2 - 60)
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        self.after(60, self._grab)
        self.wait_window()
        return self.result

    def _grab(self):
        try:
            self.lift(); self.focus_force(); self.grab_set()
        except tk.TclError:
            pass


class ColorRow(ctk.CTkFrame):
    def __init__(self, master, colors, current, on_pick, allow_none=False):
        super().__init__(master, fg_color="transparent")
        self.on_pick = on_pick
        self.current = current
        self.btns = {}
        if allow_none:
            b = ctk.CTkButton(self, text="⌀", width=24, height=24, corner_radius=12, fg_color=PANEL, hover_color=HOVER,
                              text_color=MUTED, border_width=2, font=F(13),
                              border_color=ACCENT if current is None else BORDER, command=lambda: self.pick(None))
            b.pack(side="left", padx=(0, 5)); self.btns[None] = b
        for c in colors:
            b = ctk.CTkButton(self, text="", width=24, height=24, corner_radius=12, fg_color=c, hover_color=c,
                              border_width=2, command=lambda c=c: self.pick(c))
            b.pack(side="left", padx=(0, 5)); self.btns[c] = b
        more = ctk.CTkButton(self, text="", image=icon("plus", 13), width=24, height=24, corner_radius=12,
                             fg_color=CARD, hover_color=HOVER, command=self.custom)
        more.pack(side="left"); Tooltip(more, _("เลือกสีอื่น"))
        self.refresh()

    def refresh(self):
        for c, b in self.btns.items():
            on = (c or "").lower() == (self.current or "").lower() if c is not None else self.current is None
            if c is None:
                b.configure(border_color=ACCENT if on else BORDER)
            else:
                b.configure(border_color=SEL if on else BORDER)

    def pick(self, c):
        self.current = c; self.refresh(); self.on_pick(c)

    def custom(self):
        c = colorchooser.askcolor(self.current or "#000000", parent=self)[1]
        if c:
            self.pick(c)


ORIG_PREFIX_TH = "ฟอนต์เดิม · "
def orig_prefix():
    return _(ORIG_PREFIX_TH)

class TextDialog(_Modal):
    """spec: text,size,color,bold,italic,family ; fonts: list of family names ; original: label of the PDF font"""
    def __init__(self, master, title, spec, fonts=None, original=None):
        super().__init__(master, title)
        self.color = spec.get("color", "#111827")
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(padx=20, pady=18, fill="both")
        ctk.CTkLabel(body, text=title, font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("กด Enter เพื่อขึ้นบรรทัดใหม่ · ⌘/Ctrl + Enter เพื่อบันทึก"), font=F(12),
                     text_color=MUTED).pack(anchor="w", pady=(0, 10))
        self.txt = ctk.CTkTextbox(body, width=480, height=140, corner_radius=10, border_width=1,
                                  border_color=BORDER, fg_color=CARD, text_color=TEXT, font=F(16), wrap="word")
        self.txt.pack(fill="both")
        self.txt.insert("1.0", spec.get("text", ""))

        frow = ctk.CTkFrame(body, fg_color="transparent"); frow.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(frow, text=_("ฟอนต์"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        cur = orig_prefix() + original if original and spec.get("from_orig", True) else (spec.get("family") or "Sarabun")
        self.font = ctk.StringVar(value=cur)
        font_button(frow, self.font, original=original).pack(side="left")

        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text=_("ขนาด"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        self.size = ctk.StringVar(value=("%g" % round(spec.get("size", 16), 1)))
        ctk.CTkButton(row, text="−", width=28, height=28, corner_radius=8, fg_color=CARD, hover_color=HOVER,
                      text_color=TEXT, command=lambda: self._step(-1)).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(row, textvariable=self.size, width=56, height=28, corner_radius=8, justify="center",
                     border_color=BORDER, fg_color=CARD).pack(side="left")
        ctk.CTkButton(row, text="+", width=28, height=28, corner_radius=8, fg_color=CARD, hover_color=HOVER,
                      text_color=TEXT, command=lambda: self._step(1)).pack(side="left", padx=(2, 18))
        self.bold = ctk.BooleanVar(value=bool(spec.get("bold")))
        self.italic = ctk.BooleanVar(value=bool(spec.get("italic")))
        ctk.CTkSwitch(row, text=_("ตัวหนา"), variable=self.bold, progress_color=ACCENT, font=F(13),
                      text_color=TEXT, width=90).pack(side="left")
        ctk.CTkSwitch(row, text=_("ตัวเอียง"), variable=self.italic, progress_color=ACCENT, font=F(13),
                      text_color=TEXT, width=90).pack(side="left", padx=(8, 0))
        crow = ctk.CTkFrame(body, fg_color="transparent"); crow.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(crow, text=_("สี"), font=F(13), text_color=MUTED, width=44, anchor="w").pack(side="left")
        ColorRow(crow, SWATCHES[:6], self.color, self._setc).pack(side="left")
        btns = ctk.CTkFrame(body, fg_color="transparent"); btns.pack(fill="x", pady=(20, 0))
        primary_btn(btns, _("ตกลง"), self.ok, width=96).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=90).pack(side="right", padx=8)
        for k in ("<Command-Return>", "<Control-Return>"):
            self.bind(k, lambda e: (self.ok(), "break")[1])
        self.after(120, self._focus)

    def _focus(self):
        try:
            self.txt.focus_set(); self.txt.tag_add("sel", "1.0", "end-1c")
        except tk.TclError:
            pass

    def _setc(self, c):
        if c:
            self.color = c

    def _step(self, d):
        try:
            v = float(self.size.get())
        except ValueError:
            v = 16
        self.size.set("%g" % max(4, min(300, v + d)))

    def ok(self):
        try:
            size = max(4.0, min(300.0, float(self.size.get())))
        except ValueError:
            size = 16.0
        f = self.font.get()
        self.result = dict(text=self.txt.get("1.0", "end-1c").rstrip("\n"), size=size, color=self.color,
                           bold=self.bold.get(), italic=self.italic.get(),
                           original=f.startswith(orig_prefix()), family=None if f.startswith(orig_prefix()) else f)
        self.destroy()


class SignatureDialog(_Modal):
    def __init__(self, master):
        super().__init__(master, _("ลายเซ็น"))
        self.strokes = []; self.color = "#1e3a8a"
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(padx=20, pady=18)
        ctk.CTkLabel(body, text=_("วาดลายเซ็นของคุณ"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("ใช้เมาส์หรือแทร็กแพดเซ็นชื่อในกรอบด้านล่าง"), font=F(12),
                     text_color=MUTED).pack(anchor="w", pady=(0, 10))
        holder = ctk.CTkFrame(body, fg_color="#ffffff", corner_radius=12, border_width=1, border_color=BORDER)
        holder.pack()
        self.cv = tk.Canvas(holder, width=560, height=220, bg="#ffffff", highlightthickness=0, cursor="crosshair")
        self.cv.pack(padx=6, pady=6)
        self.cv.create_line(30, 170, 530, 170, fill="#e5e7eb", dash=(4, 4))
        self.cv.create_text(36, 186, text="✕", fill="#cbd5e1", anchor="w")
        self.cv.bind("<ButtonPress-1>", self.down); self.cv.bind("<B1-Motion>", self.move)
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=(14, 0))
        ColorRow(row, ["#111827", "#1e3a8a", "#2563eb", "#e03c43"], self.color, self.setc).pack(side="left")
        primary_btn(row, _("ใช้ลายเซ็นนี้"), self.ok, width=120).pack(side="right")
        secondary_btn(row, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        secondary_btn(row, _("ล้าง"), self.clear, width=70).pack(side="right")

    def setc(self, c):
        if c:
            self.color = c; self.cv.itemconfigure("ink", fill=c)

    def down(self, e):
        self.strokes.append([(e.x, e.y)])

    def move(self, e):
        if not self.strokes:
            return
        s = self.strokes[-1]; x0, y0 = s[-1]
        if abs(e.x - x0) + abs(e.y - y0) < 1:
            return
        s.append((e.x, e.y))
        self.cv.create_line(x0, y0, e.x, e.y, fill=self.color, width=2.6, capstyle="round", smooth=True, tags="ink")

    def clear(self):
        self.strokes = []; self.cv.delete("ink")

    def ok(self):
        pts = [p for s in self.strokes for p in s]
        if not pts:
            messagebox.showinfo(APP, _("กรุณาเซ็นชื่อก่อน"), parent=self); return
        x0 = min(p[0] for p in pts) - 6; y0 = min(p[1] for p in pts) - 6
        x1 = max(p[0] for p in pts) + 6; y1 = max(p[1] for p in pts) + 6
        d = fitz.open(); pg = d.new_page(width=x1 - x0, height=y1 - y0)
        col = hex2rgb(self.color)
        for s in self.strokes:
            pp = [(x - x0, y - y0) for x, y in s]
            if len(pp) == 1:
                pp.append((pp[0][0] + 0.1, pp[0][1]))
            pg.draw_polyline(pp, color=col, width=2.6, lineCap=1, lineJoin=1)
        pix = pg.get_pixmap(matrix=fitz.Matrix(4, 4), alpha=True)
        self.result = (pix.tobytes("png"), x1 - x0, y1 - y0)
        self.destroy()


def reveal(path):
    """show a file in Finder / Explorer"""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass

def open_folder(path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class FontPicker(_Modal):
    """searchable list of every font on this computer, with live preview and 'add font' button"""
    SAMPLE = "กขค ภาษาไทย สวัสดีครับ  AaBbCc 123"

    def __init__(self, master, current=None, original=None):
        super().__init__(master, _("เลือกฟอนต์"))
        self.original = original
        self.result = None
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(padx=20, pady=18, fill="both", expand=True)
        ctk.CTkLabel(body, text=_("เลือกฟอนต์"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("ฟอนต์ทั้งหมดที่ติดตั้งในเครื่องนี้ + ฟอนต์ที่เพิ่มเข้า PDF PRO"), font=F(12),
                     text_color=MUTED).pack(anchor="w", pady=(0, 10))
        top = ctk.CTkFrame(body, fg_color="transparent"); top.pack(fill="x")
        self.q = ctk.StringVar()
        e = ctk.CTkEntry(top, textvariable=self.q, placeholder_text=_("ค้นหาฟอนต์…"), height=32, width=300,
                         corner_radius=8, border_color=BORDER, fg_color=CARD, font=F(13))
        e.pack(side="left")
        self.thai = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text=_("เฉพาะที่รองรับภาษาไทย"), variable=self.thai, command=self.fill,
                        fg_color=ACCENT, hover_color=ACCENT_H, font=F(12), text_color=TEXT).pack(side="left", padx=12)
        self.q.trace_add("write", lambda *a: self.fill())
        mid = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10); mid.pack(fill="both", expand=True, pady=(10, 0))
        self.lb = tk.Listbox(mid, height=14, width=58, activestyle="none", borderwidth=0, highlightthickness=0,
                             font=("Helvetica", 13), selectbackground=ACCENT, selectforeground="white",
                             bg=tc(CARD), fg=tc(TEXT), exportselection=False)
        sb = ctk.CTkScrollbar(mid, command=self.lb.yview, width=10)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=2, pady=4); self.lb.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.preview())
        self.lb.bind("<Double-Button-1>", lambda e: self.ok())
        self.prev = ctk.CTkLabel(body, text="", fg_color="#ffffff", corner_radius=10, height=74)
        self.prev.pack(fill="x", pady=(10, 0))
        self.info = ctk.CTkLabel(body, text="", font=F(11), text_color=MUTED, anchor="w")
        self.info.pack(fill="x", pady=(4, 0))
        btns = ctk.CTkFrame(body, fg_color="transparent"); btns.pack(fill="x", pady=(14, 0))
        secondary_btn(btns, _("เพิ่มฟอนต์จากไฟล์…"), self.add_font, "plus", width=170).pack(side="left")
        primary_btn(btns, _("เลือก"), self.ok, width=90).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        self.items = []
        self.current = current
        self.fill(select=current)
        self.after(150, e.focus_set)

    def fill(self, select=None):
        q = self.q.get().strip().lower()
        allf = fontbook().choices(thai_only=self.thai.get())
        self.items = []
        if self.original:
            self.items.append((orig_prefix() + self.original, True, "orig"))
        self.items += [x for x in allf if not q or q in x[0].lower()]
        self.lb.delete(0, "end")
        tags = {"bundled": "  ★", "user": "  ＋", "orig": "  ↺"}
        for name, thai, kind in self.items:
            self.lb.insert("end", "  %s%s%s" % (name, _("   ไทย") if thai and kind != "orig" else "", tags.get(kind, "")))
        sel = select or self.current
        idx = next((i for i, x in enumerate(self.items) if x[0] == sel), 0 if self.items else None)
        if idx is not None:
            self.lb.selection_clear(0, "end"); self.lb.selection_set(idx); self.lb.see(idx)
            self.preview()

    def chosen(self):
        s = self.lb.curselection()
        return self.items[s[0]] if s else None

    def preview(self):
        it = self.chosen()
        if not it:
            return
        name, thai, kind = it
        if kind == "orig":
            self.prev.configure(image=None, text=_("ใช้ฟอนต์เดิมของข้อความในไฟล์ (หรือฟอนต์ที่ใกล้เคียงที่สุด)"),
                                text_color="#374151", font=F(13))
            self.info.configure(text="")
            return
        try:
            fb = fontbook()
            key, _sb, _si = fb.family_key(name)
            d = fitz.open(); pg = d.new_page(width=520, height=64)
            arch = fitz.Archive(); arch.add((fb.reg[key]["buf"], fb.reg[key]["file"]))
            fbk = fb.family_key("Sarabun")[0]; arch.add((fb.reg[fbk]["buf"], fb.reg[fbk]["file"]))
            o = dict(text=self.SAMPLE, size=24, color="#111827")
            pg.insert_htmlbox(fitz.Rect(10, 8, 510, 60), text_html(o, fb.fz(key)), css=text_css(o, key, fbk, False, False),
                              archive=arch)
            pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            self.prev.configure(text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=(520, 64)))
            kinds = {"bundled": _("มากับโปรแกรม"), "builtin": _("ฟอนต์มาตรฐาน PDF"), "user": _("ฟอนต์ที่เพิ่มเอง"),
                     "system": _("ติดตั้งในเครื่อง")}
            self.info.configure(text="%s · %s" % (kinds.get(kind, ""), _("รองรับภาษาไทย") if thai or kind == "bundled"
                                                  else _("ไม่มีอักษรไทย (จะใช้ฟอนต์ไทยเสริมให้อัตโนมัติ)")))
        except Exception as e:
            self.prev.configure(image=None, text=_("แสดงตัวอย่างไม่ได้") + ": %s" % e, text_color="#b91c1c")

    def add_font(self):
        ps = filedialog.askopenfilenames(parent=self, title=_("เลือกไฟล์ฟอนต์"),
                                         filetypes=[(_("ฟอนต์"), "*.ttf *.otf *.ttc *.TTF *.OTF *.TTC")])
        added = []
        for p in ps:
            try:
                fam = fontbook().system.install(p)
                if fam:
                    added.append(fam)
            except Exception as e:
                messagebox.showerror(APP, "%s\n%s" % (os.path.basename(p), e), parent=self)
        if added:
            self.q.set("")
            self.fill(select=added[0])
            messagebox.showinfo(APP, _("เพิ่มฟอนต์แล้ว") + ":\n" + "\n".join(sorted(set(added))), parent=self)

    def ok(self):
        it = self.chosen()
        if it:
            self.result = it[0]
        self.destroy()


def font_button(master, value_var, original=None, on_change=None, width=300):
    """a button that shows the current font and opens the FontPicker"""
    def pick():
        cur = value_var.get()
        r = FontPicker(master.winfo_toplevel(), current=cur,
                       original=original).run()
        if r:
            value_var.set(r); btn.configure(text=_short(r))
            if on_change:
                on_change(r)
    def _short(v):
        return v if len(v) <= 34 else v[:32] + "…"
    btn = ctk.CTkButton(master, text=_short(value_var.get()), command=pick, width=width, height=32, corner_radius=8,
                        fg_color=CARD, hover_color=HOVER, text_color=TEXT, font=F(13), anchor="w",
                        image=icon("text", 15), compound="left", border_width=1, border_color=BORDER)
    return btn


class PrintDialog(_Modal):
    def __init__(self, master, n_pages, cur):
        super().__init__(master, _("พิมพ์"))
        self.n = n_pages
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(padx=22, pady=18, fill="both")
        ctk.CTkLabel(body, text=_("พิมพ์เอกสาร"), font=F(17, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text=_("งานที่แก้ไขไว้ทั้งหมดจะถูกพิมพ์ด้วย"), font=F(12), text_color=MUTED).pack(anchor="w", pady=(0, 14))
        self.printers, default = list_printers()
        self.printer = ctk.StringVar(value=default or (self.printers[0] if self.printers else _("เครื่องพิมพ์เริ่มต้น")))
        r1 = ctk.CTkFrame(body, fg_color="transparent"); r1.pack(fill="x", pady=4)
        ctk.CTkLabel(r1, text=_("เครื่องพิมพ์"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(side="left")
        ctk.CTkOptionMenu(r1, values=self.printers or [_("เครื่องพิมพ์เริ่มต้น")], variable=self.printer, width=300, height=32,
                          corner_radius=8, fg_color=CARD, button_color=CARD, button_hover_color=HOVER, text_color=TEXT,
                          dropdown_fg_color=PANEL, dropdown_text_color=TEXT, dropdown_hover_color=HOVER,
                          font=F(13)).pack(side="left")
        r2 = ctk.CTkFrame(body, fg_color="transparent"); r2.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(r2, text=_("หน้า"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(side="left", anchor="n")
        opts = ctk.CTkFrame(r2, fg_color="transparent"); opts.pack(side="left")
        self.which = ctk.StringVar(value="all")
        ctk.CTkRadioButton(opts, text=_("ทั้งหมด") + " (%d)" % n_pages, variable=self.which, value="all",
                           fg_color=ACCENT, font=F(13), text_color=TEXT).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(opts, text=_("หน้าปัจจุบัน") + " (%d)" % (cur + 1), variable=self.which, value="cur",
                           fg_color=ACCENT, font=F(13), text_color=TEXT).pack(anchor="w", pady=2)
        rr = ctk.CTkFrame(opts, fg_color="transparent"); rr.pack(anchor="w", pady=2)
        ctk.CTkRadioButton(rr, text=_("กำหนดเอง"), variable=self.which, value="range", fg_color=ACCENT, font=F(13),
                           text_color=TEXT).pack(side="left")
        self.range = ctk.StringVar(value="1-%d" % n_pages)
        re_ = ctk.CTkEntry(rr, textvariable=self.range, width=130, height=28, corner_radius=7, border_color=BORDER,
                           fg_color=CARD, placeholder_text="1-3, 5")
        re_.pack(side="left", padx=6); re_.bind("<FocusIn>", lambda e: self.which.set("range"))
        self.cur = cur
        r3 = ctk.CTkFrame(body, fg_color="transparent"); r3.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(r3, text=_("จำนวนชุด"), width=96, anchor="w", font=F(13), text_color=MUTED).pack(side="left")
        self.copies = ctk.StringVar(value="1")
        ctk.CTkEntry(r3, textvariable=self.copies, width=60, height=28, corner_radius=7, justify="center",
                     border_color=BORDER, fg_color=CARD).pack(side="left")
        btns = ctk.CTkFrame(body, fg_color="transparent"); btns.pack(fill="x", pady=(20, 0))
        primary_btn(btns, _("พิมพ์"), lambda: self.done(False), "print", width=100).pack(side="right")
        secondary_btn(btns, _("ยกเลิก"), self.destroy, width=80).pack(side="right", padx=8)
        ctk.CTkButton(btns, text=_("ใช้หน้าต่างพิมพ์ของระบบ…"), command=lambda: self.done(True), fg_color="transparent",
                      hover_color=HOVER, text_color=("#2563eb", "#7aa7ff"), font=F(12), width=10).pack(side="left")
        if not self.printers:
            ctk.CTkLabel(body, text=_("ไม่พบรายชื่อเครื่องพิมพ์ — จะใช้หน้าต่างพิมพ์ของระบบ"), font=F(11),
                         text_color=MUTED).pack(anchor="w", pady=(8, 0))

    def pages(self):
        w = self.which.get()
        if w == "all":
            return list(range(self.n))
        if w == "cur":
            return [self.cur]
        out = []
        for part in self.range.get().replace(" ", "").split(","):
            if not part:
                continue
            try:
                if "-" in part:
                    a, b = part.split("-", 1)
                    a = int(a) if a else 1; b = int(b) if b else self.n
                    out += list(range(max(1, a), min(self.n, b) + 1))
                else:
                    out.append(int(part))
            except ValueError:
                return None
        out = [p - 1 for p in out if 1 <= p <= self.n]
        return out or None

    def done(self, system):
        pages = self.pages()
        if not pages:
            messagebox.showerror(APP, _("ช่วงหน้าไม่ถูกต้อง"), parent=self); return
        try:
            copies = max(1, min(99, int(self.copies.get())))
        except ValueError:
            copies = 1
        self.result = dict(pages=pages, copies=copies, system=system or not self.printers,
                           printer=self.printer.get() if self.printers else None)
        self.destroy()


def list_printers():
    """-> (names, default)  — CUPS on macOS/Linux, PowerShell/WMIC on Windows"""
    names, default = [], None
    try:
        if os.name == "nt":
            flags = 0x08000000  # CREATE_NO_WINDOW
            try:
                out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                      "Get-CimInstance Win32_Printer | ForEach-Object { $_.Name + '|' + $_.Default }"],
                                     capture_output=True, text=True, timeout=8, creationflags=flags).stdout
                for line in out.splitlines():
                    if "|" in line:
                        n, d = line.rsplit("|", 1)
                        names.append(n.strip())
                        if d.strip().lower() == "true":
                            default = n.strip()
            except Exception:
                pass
        else:
            out = subprocess.run(["lpstat", "-e"], capture_output=True, text=True, timeout=5).stdout
            names = [l.strip() for l in out.splitlines() if l.strip()]
            d = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=5).stdout
            if ":" in d:
                default = d.split(":", 1)[1].strip() or None
    except Exception:
        pass
    return names, default


# ======================================================================
#   Main application
# ======================================================================
TOOLS = [
    ("select", "เลือก", "V", "เลือก / ย้าย / ปรับขนาด"),
    ("text", "ข้อความ", "T", "เพิ่มข้อความ"),
    ("edittext", "แก้ข้อความ", "E", "แก้ข้อความเดิมในไฟล์"),
    ("whiteout", "ปิดทับ", "W", "ลบ / ปิดทับด้วยสีขาว"),
    ("ink", "ปากกา", "P", "ปากกา วาดอิสระ"),
    ("highlight", "ไฮไลต์", "H", "ไฮไลต์"),
    ("rect", "กรอบ", "R", "กรอบสี่เหลี่ยม"),
    ("line", "เส้น", "L", "เส้นตรง"),
    ("arrow", "ลูกศร", "A", "ลูกศร"),
]
TOOL_TITLE = {k: d for k, _l, _s, d in TOOLS}
HINTS = {
    "select": "คลิกวัตถุเพื่อเลือก ลากเพื่อย้าย ลากมุมเพื่อปรับขนาด ดับเบิลคลิกข้อความเพื่อแก้ไข\n\nDelete = ลบ · ปุ่มลูกศร = เลื่อนทีละนิด · คลิกขวา = เมนู",
    "text": "คลิกตรงตำแหน่งบนหน้าที่ต้องการเพิ่มข้อความ แล้วพิมพ์ในหน้าต่างที่เปิดขึ้น (รองรับภาษาไทย)",
    "edittext": "คลิกที่ข้อความเดิมในไฟล์ ข้อความเดิมจะถูกลบออกจริง แล้วแทนด้วยข้อความใหม่\n\nใช้ได้กับ PDF ที่มีข้อความจริง ถ้าเป็นภาพสแกนให้ใช้ “ปิดทับ” + “ข้อความ”",
    "whiteout": "ลากคลุมส่วนที่ต้องการลบ จะถูกปิดด้วยสีขาว (เลือกสีอื่นได้หลังวาด)",
    "ink": "กดค้างแล้วลากเพื่อวาดหรือเขียนอิสระ",
    "highlight": "ลากคลุมข้อความที่ต้องการเน้น",
    "rect": "ลากเพื่อวาดกรอบ เลือกสีเส้น ความหนา และสีพื้นได้",
    "line": "ลากเพื่อวาดเส้น · กด Shift ค้างเพื่อล็อกมุม",
    "arrow": "ลากเพื่อวาดลูกศร · กด Shift ค้างเพื่อล็อกมุม",
}
TYPE_NAME = {"text": "ข้อความ", "rect": "กรอบ", "whiteout": "ปิดทับ", "highlight": "ไฮไลต์", "ink": "เส้นปากกา",
             "line": "เส้นตรง", "arrow": "ลูกศร", "image": "รูปภาพ", "redact": "ส่วนที่ลบออก"}
MARGIN = 28


class PDFPro(ctk.CTk):
    def __init__(self, path=None):
        super().__init__()
        self.title(APP)
        self.geometry("1360x880")
        self.minsize(1040, 700)
        self.configure(fg_color=BG)
        self.doc = None
        self.path = None
        self.objs = []
        self.images = {}
        self.cur = 0
        self.zoom = 1.0
        self.undo_stack, self.redo_stack = [], []
        self._docbytes = None
        self.dirty = False
        self._saved_once = False
        self.sel = None
        self.pdfsel = None            # selected image that is part of the PDF itself
        self.drag = None
        self.thumb_imgs = {}
        self._thumb_pos = []
        self._thumb_job = None
        self.page_img = None
        self.ox = self.oy = MARGIN

        self.tool = "select"
        self.color = "#e03c43"
        self.text_color = "#111827"
        self.hl_color = "#fde047"
        self.stroke = 2.0
        self.fsize = 16.0
        self.ffamily = "TH Sarabun New"
        self.fill = None
        self._prop_armed = False
        self._prop_job = None
        self.mode = SETTINGS.get("mode", "edit") if SETTINGS.get("mode") in ("edit", "view") else "edit"
        if SETTINGS.get("theme") in ("light", "dark"):
            ctk.set_appearance_mode(SETTINGS["theme"])

        self._build_ui()
        self._layout()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.set_tool("select")
        self.update_state()
        if path:
            self.after(150, lambda: self.open_path(path))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # ---------- header
        hdr = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=PANEL)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x")
        hdr.grid_columnconfigure(1, weight=1)
        left = ctk.CTkFrame(hdr, fg_color="transparent"); left.grid(row=0, column=0, sticky="w", padx=(16, 0), pady=12)
        logo = ctk.CTkFrame(left, fg_color="transparent", cursor="hand2"); logo.pack(side="left")
        l1 = ctk.CTkLabel(logo, text="PDF", fg_color=ACCENT, text_color="#ffffff", corner_radius=7, width=42, height=28,
                          font=F(13, "bold")); l1.pack(side="left")
        l2 = ctk.CTkLabel(logo, text="PRO", text_color=TEXT, font=F(18, "bold")); l2.pack(side="left", padx=(7, 10))
        for w in (logo, l1, l2):
            w.bind("<Button-1>", lambda e: self.go_home())
        self.b_home = ghost_btn(left, "home", self.go_home, _("หน้าแรก"))
        self.b_home.pack(side="left", padx=(0, 8))
        self.fname = ctk.CTkLabel(left, text="", text_color=MUTED, font=F(13), anchor="w")
        self.fname.pack(side="left")

        self.mid = mid = ctk.CTkFrame(hdr, fg_color="transparent"); mid.grid(row=0, column=1, pady=12)
        self.mode_seg = ctk.CTkSegmentedButton(mid, values=[_("ดู"), _("แก้ไข")], command=self._on_mode_seg,
                                               selected_color=ACCENT, selected_hover_color=ACCENT_H,
                                               unselected_color=CARD, unselected_hover_color=HOVER,
                                               fg_color=CARD, text_color=TEXT, font=F(13, "bold"), height=32, width=150,
                                               dynamic_resizing=False)
        self.mode_seg.pack(side="left", padx=(0, 14))
        self.b_undo = ghost_btn(mid, "undo", self.undo, _("เลิกทำ") + "  " + MOD + "Z"); self.b_undo.pack(side="left")
        self.b_redo = ghost_btn(mid, "redo", self.redo, _("ทำซ้ำ") + "  ⇧" + MOD + "Z"); self.b_redo.pack(side="left", padx=(2, 12))
        zp = ctk.CTkFrame(mid, fg_color=CARD, corner_radius=10); zp.pack(side="left", padx=4)
        ghost_btn(zp, "minus", lambda: self.set_zoom(self.zoom / 1.2), _("ย่อ"), 30, 16).pack(side="left", padx=2, pady=2)
        self.zoom_lbl = ctk.CTkLabel(zp, text="100%", width=52, font=F(13), text_color=TEXT); self.zoom_lbl.pack(side="left")
        ghost_btn(zp, "plus", lambda: self.set_zoom(self.zoom * 1.2), _("ขยาย"), 30, 16).pack(side="left", padx=2)
        ghost_btn(zp, "fit", lambda: self.fit_width(), _("พอดีความกว้าง"), 30, 16).pack(side="left", padx=(0, 2))
        pp = ctk.CTkFrame(mid, fg_color=CARD, corner_radius=10); pp.pack(side="left", padx=8)
        ghost_btn(pp, "left", lambda: self.goto(self.cur - 1), _("หน้าก่อนหน้า"), 30, 16).pack(side="left", padx=2, pady=2)
        self.page_var = ctk.StringVar(value="–")
        ent = ctk.CTkEntry(pp, textvariable=self.page_var, width=44, height=26, corner_radius=7, justify="center",
                           border_width=0, fg_color=PANEL, font=F(13))
        ent.pack(side="left"); ent.bind("<Return>", lambda e: self._goto_entry())
        self.page_total = ctk.CTkLabel(pp, text="/ –", font=F(13), text_color=MUTED, width=40)
        self.page_total.pack(side="left", padx=(4, 0))
        ghost_btn(pp, "right", lambda: self.goto(self.cur + 1), _("หน้าถัดไป"), 30, 16).pack(side="left", padx=2)

        right = ctk.CTkFrame(hdr, fg_color="transparent"); right.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=12)
        self.b_lang = ctk.CTkButton(right, text="EN" if SETTINGS.get("lang") != "en" else _("ไทย"), width=40, height=32,
                                    corner_radius=9, fg_color="transparent", hover_color=HOVER, text_color=TEXT,
                                    font=F(12, "bold"), command=self.toggle_lang)
        self.b_lang.pack(side="left"); Tooltip(self.b_lang, _("เปลี่ยนภาษา"))
        self.b_theme = ghost_btn(right, "moon", self.toggle_theme, _("สลับโหมดมืด/สว่าง")); self.b_theme.pack(side="left")
        self.b_print = ghost_btn(right, "print", self.print_dialog, _("พิมพ์") + "  " + MOD + "P"); self.b_print.pack(side="left")
        self.b_more = ghost_btn(right, "more", self.more_menu, _("เพิ่มเติม")); self.b_more.pack(side="left", padx=(2, 10))
        secondary_btn(right, _("เปิดไฟล์"), self.open_dialog, "open", width=110).pack(side="left")
        self.b_save = primary_btn(right, _("บันทึก PDF"), self.save, "save", width=128)
        self.b_save.pack(side="left", padx=(8, 0))

        # ---------- body
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0); body.pack(fill="both", expand=True)
        self.body = body
        self.leftbox = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0, width=1)
        self.leftbox.pack(side="left", fill="y")
        self.rightbox = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0, width=1)
        self.rightbox.pack(side="right", fill="y")
        # tool rail
        self.rail = ctk.CTkFrame(self.leftbox, width=84, corner_radius=0, fg_color=PANEL)
        self.rail.pack_propagate(False)
        self.rail_line = ctk.CTkFrame(self.leftbox, width=1, corner_radius=0, fg_color=BORDER)
        self.tool_btns = {}
        ctk.CTkFrame(self.rail, height=8, fg_color="transparent").pack()
        for key, label, sc, desc in TOOLS:
            b = ctk.CTkButton(self.rail, text=_(label), compound="top", width=70, height=52, corner_radius=11,
                              fg_color="transparent", hover_color=HOVER, text_color=MUTED, font=F(11),
                              image=icon(key, 20), command=lambda k=key: self.set_tool(k))
            b.pack(pady=2)
            Tooltip(b, "%s  (%s)" % (_(desc), sc))
            self.tool_btns[key] = b
        ctk.CTkFrame(self.rail, height=1, width=46, fg_color=BORDER).pack(pady=8)
        for key, label, cmd, tip in (("image", _("รูปภาพ"), self.insert_image, _("แทรกรูปภาพ")),
                                     ("sign", _("ลายเซ็น"), self.insert_signature, _("สร้างลายเซ็น"))):
            b = ctk.CTkButton(self.rail, text=_(label), compound="top", width=70, height=52, corner_radius=11,
                              fg_color="transparent", hover_color=HOVER, text_color=MUTED, font=F(11),
                              image=icon(key, 20), command=cmd)
            b.pack(pady=2); Tooltip(b, _(tip))

        # pages panel
        self.pages = ctk.CTkFrame(self.leftbox, width=200, corner_radius=0, fg_color=PANEL)
        self.pages.pack_propagate(False)
        self.pages_line = ctk.CTkFrame(self.leftbox, width=1, corner_radius=0, fg_color=BORDER)
        top = ctk.CTkFrame(self.pages, fg_color="transparent"); top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text=_("หน้า"), font=F(14, "bold"), text_color=TEXT).pack(side="left")
        self.pcount = ctk.CTkLabel(top, text="", font=F(12), text_color=MUTED); self.pcount.pack(side="right")
        self.ops = ops = ctk.CTkFrame(self.pages, fg_color=CARD, corner_radius=10)
        opdefs = [("rotl", _("หมุนซ้าย"), lambda: self.rotate_page(-90)), ("rotr", _("หมุนขวา"), lambda: self.rotate_page(90)),
                  ("up", _("เลื่อนหน้าขึ้น"), lambda: self.move_page(-1)), ("down", _("เลื่อนหน้าลง"), lambda: self.move_page(1)),
                  ("blank", _("แทรกหน้าว่าง"), self.insert_blank), ("copy", _("ทำสำเนาหน้า"), self.duplicate_page),
                  ("extract", _("บันทึกหน้านี้เป็นไฟล์ใหม่"), self.extract_page), ("trash", _("ลบหน้า"), self.delete_page)]
        for i, (ic, tip, cmd) in enumerate(opdefs):
            col = (ACCENT, "#ff6b70") if ic == "trash" else None
            b = ctk.CTkButton(ops, text="", image=icon(ic, 17, col), width=38, height=32, corner_radius=8,
                              fg_color="transparent", hover_color=HOVER, command=cmd)
            b.grid(row=i // 4, column=i % 4, padx=2, pady=2); Tooltip(b, _(tip))
        for c in range(4):
            ops.grid_columnconfigure(c, weight=1)
        self.thumb_frame = tf = ctk.CTkFrame(self.pages, fg_color="transparent")
        self.thumbs = tk.Canvas(tf, highlightthickness=0, width=184, bd=0)
        tsb = ctk.CTkScrollbar(tf, command=self.thumbs.yview, width=10)
        self.thumbs.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y", padx=(0, 2)); self.thumbs.pack(side="left", fill="both", expand=True)
        self.thumbs.bind("<Button-1>", self.on_thumb_click)
        self._bind_wheel(self.thumbs, lambda d: self.thumbs.yview_scroll(d, "units"))

        # properties panel
        self.props_line = ctk.CTkFrame(self.rightbox, width=1, corner_radius=0, fg_color=BORDER)
        self.props = ctk.CTkFrame(self.rightbox, width=272, corner_radius=0, fg_color=PANEL)
        self.props.pack_propagate(False)
        self.props_in = ctk.CTkScrollableFrame(self.props, corner_radius=0, fg_color=PANEL,
                                               scrollbar_button_color=PANEL, scrollbar_button_hover_color=BORDER)
        self.props_in.pack(fill="both", expand=True)

        # canvas
        self.center = ctk.CTkFrame(body, fg_color=CANVAS, corner_radius=0)
        self.center.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(self.center, highlightthickness=0, bd=0)
        vsb = ctk.CTkScrollbar(self.center, command=self.cv.yview, width=12)
        hsb = ctk.CTkScrollbar(self.center, command=self.cv.xview, orientation="horizontal", height=12)
        self.cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y"); hsb.pack(side="bottom", fill="x")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self.on_down)
        self.cv.bind("<B1-Motion>", self.on_move)
        self.cv.bind("<ButtonRelease-1>", self.on_up)
        self.cv.bind("<Double-Button-1>", self.on_double)
        self.cv.bind("<Button-3>", self.on_context); self.cv.bind("<Button-2>", self.on_context)
        self.cv.bind("<Configure>", lambda e: self.render_view(keep_scroll=True) if self.has_doc() else None)
        self._bind_wheel(self.cv, self.on_wheel)
        self.home = ctk.CTkFrame(self.center, fg_color=BG, corner_radius=0)

        # ---------- status bar
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x")
        sb = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=PANEL); sb.pack(fill="x"); sb.pack_propagate(False)
        self.hint = ctk.CTkLabel(sb, text="", text_color=MUTED, font=F(12)); self.hint.pack(side="left", padx=14)
        self.status = ctk.CTkLabel(sb, text="", text_color=MUTED, font=F(12)); self.status.pack(side="right", padx=14)
        self.apply_theme(rerender=False)

    # ------------------------------------------------------------------ home screen (recent files)
    def build_home(self):
        for w in self.home.winfo_children():
            w.destroy()
        wrap = ctk.CTkScrollableFrame(self.home, fg_color=BG, corner_radius=0,
                                      scrollbar_button_color=BG, scrollbar_button_hover_color=BORDER)
        wrap.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(wrap, fg_color="transparent"); inner.pack(fill="x", padx=48, pady=(36, 30))
        ctk.CTkLabel(inner, text=_("ยินดีต้อนรับสู่ PDF PRO"), font=F(26, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(inner, text=_("เปิด แก้ไข และพิมพ์ไฟล์ PDF — ทุกอย่างทำงานในเครื่องของคุณ"), font=F(14),
                     text_color=MUTED).pack(anchor="w", pady=(2, 22))
        acts = ctk.CTkFrame(inner, fg_color="transparent"); acts.pack(fill="x")
        for ic, title, sub, cmd, accent in (("open", _("เปิดไฟล์ PDF"), _("เลือกไฟล์จากเครื่อง"), self.open_dialog, True),
                                            ("blank", _("สร้างเอกสารเปล่า"), _("เริ่มจากหน้าว่าง A4"), self.new_blank, False),
                                            ("merge", _("รวมไฟล์ PDF"), _("รวมหลายไฟล์เป็นไฟล์เดียว"), self.merge_new, False)):
            card = ctk.CTkFrame(acts, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER,
                                width=250, height=92, cursor="hand2")
            card.pack(side="left", padx=(0, 14)); card.pack_propagate(False)
            badge = ctk.CTkFrame(card, fg_color=ACCENT if accent else SOFT, corner_radius=12, width=48, height=48)
            badge.pack(side="left", padx=(18, 12)); badge.pack_propagate(False)
            ctk.CTkLabel(badge, text="", image=icon(ic, 22, "#ffffff" if accent else ACCENT)).pack(expand=True)
            tx = ctk.CTkFrame(card, fg_color="transparent"); tx.pack(side="left")
            a = ctk.CTkLabel(tx, text=_(title), font=F(15, "bold"), text_color=TEXT, anchor="w"); a.pack(anchor="w")
            b = ctk.CTkLabel(tx, text=_(sub), font=F(12), text_color=MUTED, anchor="w"); b.pack(anchor="w")
            for w in (card, badge, tx, a, b):
                w.bind("<Button-1>", lambda e, c=cmd: c())
            for w in badge.winfo_children():
                w.bind("<Button-1>", lambda e, c=cmd: c())

        rec = [r for r in SETTINGS.get("recent", []) if isinstance(r, dict) and r.get("path")]
        row = ctk.CTkFrame(inner, fg_color="transparent"); row.pack(fill="x", pady=(34, 12))
        ctk.CTkLabel(row, text=_("ไฟล์ล่าสุด"), font=F(18, "bold"), text_color=TEXT).pack(side="left")
        if rec:
            ctk.CTkButton(row, text=_("ล้างรายการ"), width=90, height=28, corner_radius=8, fg_color="transparent",
                          hover_color=HOVER, text_color=MUTED, font=F(12), command=self.clear_recent).pack(side="right")
        if not rec:
            empty = ctk.CTkFrame(inner, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
            empty.pack(fill="x")
            ctk.CTkLabel(empty, text="", image=icon("file", 34, MUTED)).pack(pady=(30, 6))
            ctk.CTkLabel(empty, text=_("ยังไม่มีไฟล์ที่เปิดล่าสุด"), font=F(14, "bold"), text_color=TEXT).pack()
            ctk.CTkLabel(empty, text=_("ไฟล์ที่คุณเปิดจะแสดงที่นี่ เพื่อเปิดซ้ำได้ในคลิกเดียว"), font=F(12),
                         text_color=MUTED).pack(pady=(2, 30))
            return
        grid = ctk.CTkFrame(inner, fg_color="transparent"); grid.pack(fill="x")
        cols = max(2, min(6, (self.center.winfo_width() - 96) // 196 or 4))
        for i, r in enumerate(rec[:18]):
            self._recent_card(grid, r).grid(row=i // cols, column=i % cols, padx=(0, 16), pady=(0, 16), sticky="n")

    def _recent_card(self, master, r):
        path = r["path"]; exists = os.path.exists(path)
        card = ctk.CTkFrame(master, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER, width=180,
                            height=262, cursor="hand2" if exists else "")
        card.pack_propagate(False)
        holder = ctk.CTkFrame(card, fg_color=CARD, corner_radius=10, width=156, height=170)
        holder.pack(pady=(12, 8)); holder.pack_propagate(False)
        img = self._recent_thumb(path) if exists else None
        if img is not None:
            lab = ctk.CTkLabel(holder, text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=img.size))
        else:
            lab = ctk.CTkLabel(holder, text=_("ไม่พบไฟล์") if not exists else "", image=icon("file", 34, MUTED),
                               compound="top", font=F(11), text_color=MUTED)
        lab.pack(expand=True)
        name = os.path.basename(path)
        n = ctk.CTkLabel(card, text=name if len(name) <= 24 else name[:22] + "…", font=F(13, "bold"),
                         text_color=TEXT if exists else MUTED, anchor="w")
        n.pack(fill="x", padx=12)
        folder = os.path.basename(os.path.dirname(path)) or os.path.dirname(path)
        when = time.strftime("%d/%m/%Y %H:%M", time.localtime(r.get("t", 0))) if r.get("t") else ""
        m = ctk.CTkLabel(card, text="📁 %s\n%s" % (folder[:22], when), font=F(11), text_color=MUTED, anchor="w",
                         justify="left")
        m.pack(fill="x", padx=12, pady=(2, 0))
        Tooltip(card, path)
        def openit(e=None):
            if exists:
                self.open_path(path)
            else:
                self.remove_recent(path)
        def menu(e):
            mm = tk.Menu(self, tearoff=0)
            if exists:
                mm.add_command(label=_("เปิด"), command=openit)
                mm.add_command(label=_("แสดงในโฟลเดอร์"), command=lambda: reveal(path))
            mm.add_command(label=_("ลบออกจากรายการ"), command=lambda: self.remove_recent(path))
            mm.tk_popup(e.x_root, e.y_root)
        for w in (card, holder, lab, n, m):
            w.bind("<Button-1>", openit)
            w.bind("<Button-3>", menu); w.bind("<Button-2>", menu)
        return card

    def _thumb_path(self, path):
        try:
            st = os.stat(path)
        except OSError:
            return None
        import hashlib
        h = hashlib.md5(("%s|%s|%s" % (path, st.st_mtime, st.st_size)).encode("utf-8")).hexdigest()
        return os.path.join(THUMB_DIR, h + ".png")

    def _recent_thumb(self, path):
        tp = self._thumb_path(path)
        if not tp:
            return None
        try:
            if not os.path.exists(tp):
                d = fitz.open(path)
                if d.needs_pass:
                    return None
                pg = d[0]; s = min(150 / pg.rect.width, 164 / pg.rect.height)
                pg.get_pixmap(matrix=fitz.Matrix(s * 2, s * 2), alpha=False).save(tp)
            img = Image.open(tp); img.load()
            w, h = img.size
            sc = min(150 / w, 164 / h)
            img = img.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS) if sc < 1 else img
            return img
        except Exception:
            return None

    def add_recent(self, path):
        if not path:
            return
        path = os.path.abspath(path)
        rec = [r for r in SETTINGS.get("recent", []) if isinstance(r, dict) and r.get("path") != path]
        rec.insert(0, {"path": path, "t": time.time()})
        SETTINGS["recent"] = rec[:30]
        save_settings()

    def remove_recent(self, path):
        SETTINGS["recent"] = [r for r in SETTINGS.get("recent", []) if r.get("path") != path]
        save_settings(); self.build_home()

    def clear_recent(self):
        if messagebox.askyesno(APP, _("ล้างรายการไฟล์ล่าสุดทั้งหมดหรือไม่?")):
            SETTINGS["recent"] = []; save_settings(); self.build_home()

    def go_home(self):
        if not self.has_doc():
            return
        if not self.confirm_discard():
            return
        self.doc = None; self.path = None; self.objs = []; self.sel = None; self.pdfsel = None
        self.undo_stack.clear(); self.redo_stack.clear(); self.dirty = False
        self.cv.delete("all"); self.thumbs.delete("all")
        self._layout(); self.update_state()

    # ------------------------------------------------------------------ layout / modes
    def _layout(self):
        doc = self.has_doc(); edit = self.mode == "edit"
        for w in (self.rail, self.rail_line, self.pages, self.pages_line, self.props_line, self.props,
                  self.leftbox, self.rightbox):
            w.pack_forget()
        if doc:
            self.leftbox.pack(side="left", fill="y", before=self.center)
        if doc and edit:
            self.rightbox.pack(side="right", fill="y", before=self.center)
        if doc and edit:
            self.rail.pack(side="left", fill="y"); self.rail_line.pack(side="left", fill="y")
        if doc:
            self.pages.pack(side="left", fill="y"); self.pages_line.pack(side="left", fill="y")
            self.thumb_frame.pack_forget(); self.ops.pack_forget()
            if edit:
                self.ops.pack(fill="x", padx=12, pady=(0, 8))
            self.thumb_frame.pack(fill="both", expand=True)
        if doc and edit:
            self.props_line.pack(side="left", fill="y"); self.props.pack(side="left", fill="y")
        if doc:
            self.home.place_forget()
            self.mid.grid()
        else:
            self.mid.grid_remove()
            self.build_home()
            self.home.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.home.lift()
        self.mode_seg.set(_("แก้ไข") if edit else _("ดู"))

    def _on_mode_seg(self, v):
        self.set_mode("edit" if v == _("แก้ไข") else "view")

    def set_mode(self, m):
        self.mode = m
        SETTINGS["mode"] = m; save_settings()
        self.sel = None; self.pdfsel = None
        if m == "view":
            self.tool = "select"
        self._layout()
        if self.has_doc():
            self.update_idletasks()
            self.render_view(keep_scroll=True); self.render_props()
            self.cv.configure(cursor="arrow" if m == "view" else {"edittext": "xterm", "text": "xterm",
                                                                    "select": "arrow"}.get(self.tool, "crosshair"))
        self.update_state()

    def toggle_lang(self):
        SETTINGS["lang"] = "en" if SETTINGS.get("lang") != "en" else "th"
        save_settings()
        for w in self.winfo_children():
            w.destroy()
        _svg_cache.clear()
        self._build_ui()
        self._layout()
        if self.has_doc():
            self.update_idletasks()
            self.build_thumbs(); self.render_view(keep_scroll=True)
        self.set_tool(self.tool)
        self.update_state()

    def apply_theme(self, rerender=True):
        self.cv.configure(bg=tc(CANVAS))
        self.thumbs.configure(bg=tc(PANEL))
        self.b_theme.configure(image=icon("sun" if ctk.get_appearance_mode() == "Dark" else "moon", 19))
        if rerender and self.has_doc():
            self.render_view(keep_scroll=True)
            self.build_thumbs()

    def toggle_theme(self):
        m = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(m)
        SETTINGS["theme"] = m; save_settings()
        self.after(30, self.apply_theme)

    def more_menu(self):
        m = tk.Menu(self, tearoff=0)
        on = "normal" if self.has_doc() else "disabled"
        m.add_command(label=_("หน้าแรก (ไฟล์ล่าสุด)"), command=self.go_home, state=on)
        m.add_command(label=_("เปิดไฟล์…") + "    " + MOD + "O", command=self.open_dialog)
        m.add_command(label=_("สร้างเอกสารเปล่า"), command=self.new_blank)
        m.add_separator()
        m.add_command(label=_("บันทึก") + "    " + MOD + "S", command=self.save, state=on)
        m.add_command(label=_("บันทึกเป็น…") + "    ⇧" + MOD + "S", command=lambda: self.save(as_new=True), state=on)
        m.add_command(label=_("บันทึกหน้านี้เป็นไฟล์ใหม่…"), command=self.extract_page, state=on)
        m.add_command(label=_("พิมพ์…") + "    " + MOD + "P", command=self.print_dialog, state=on)
        m.add_separator()
        m.add_command(label=_("รวมไฟล์ PDF (เพิ่มต่อจากหน้านี้)…"), command=self.merge_dialog, state=on)
        m.add_command(label=_("ส่งออกรูปภาพทั้งหมดในไฟล์…"), command=self.export_all_images, state=on)
        m.add_command(label=_("เพิ่มฟอนต์…"), command=self.add_fonts)
        m.add_separator()
        m.add_command(label=_("สลับโหมดมืด/สว่าง"), command=self.toggle_theme)
        m.add_command(label="English" if SETTINGS.get("lang") != "en" else _("ภาษาไทย"), command=self.toggle_lang)
        x = self.b_more.winfo_rootx(); y = self.b_more.winfo_rooty() + self.b_more.winfo_height() + 4
        m.tk_popup(x, y)

    def add_fonts(self):
        ps = filedialog.askopenfilenames(title=_("เลือกไฟล์ฟอนต์"),
                                         filetypes=[(_("ฟอนต์"), "*.ttf *.otf *.ttc *.TTF *.OTF *.TTC")])
        added = []
        for p in ps:
            try:
                fam = fontbook().system.install(p)
                if fam:
                    added.append(fam)
            except Exception as e:
                messagebox.showerror(APP, "%s\n%s" % (os.path.basename(p), e))
        if added:
            messagebox.showinfo(APP, _("เพิ่มฟอนต์แล้ว") + ":\n" + "\n".join(sorted(set(added))))

    # ------------------------------------------------------------------ printing
    def print_dialog(self):
        if not self.has_doc():
            return
        r = PrintDialog(self, self.doc.page_count, self.cur).run()
        if not r:
            return
        try:
            self.configure(cursor="watch"); self.update()
            out = self.build_output(r["pages"])
            fd, tmp = tempfile.mkstemp(prefix="pdfpro-print-", suffix=".pdf"); os.close(fd)
            out.save(tmp, garbage=3, deflate=True)
        except Exception as e:
            self.configure(cursor="")
            messagebox.showerror(APP, _("เตรียมงานพิมพ์ไม่สำเร็จ") + "\n%s" % e); return
        self.configure(cursor="")
        ok = False
        try:
            if r["system"]:
                if sys.platform == "darwin":
                    p = subprocess.run(["osascript", "-e", 'tell application "Preview" to activate', "-e",
                                        'tell application "Preview" to print (POSIX file "%s") with print dialog' % tmp],
                                       capture_output=True, timeout=60)
                    ok = p.returncode == 0
                    if not ok:
                        subprocess.Popen(["open", "-a", "Preview", tmp]); ok = True
                elif os.name == "nt":
                    try:
                        os.startfile(tmp, "print"); ok = True
                    except OSError:
                        os.startfile(tmp); ok = True
                else:
                    subprocess.Popen(["xdg-open", tmp]); ok = True
                self.set_status(_("เปิดหน้าต่างพิมพ์ของระบบแล้ว"))
            else:
                if os.name == "nt":
                    for _i in range(r["copies"]):
                        try:
                            os.startfile(tmp, "printto", '"%s"' % r["printer"])
                        except (OSError, TypeError):
                            os.startfile(tmp, "print")
                    ok = True
                else:
                    cmd = ["lp", "-n", str(r["copies"])]
                    if r["printer"]:
                        cmd += ["-d", r["printer"]]
                    p = subprocess.run(cmd + [tmp], capture_output=True, text=True, timeout=30)
                    ok = p.returncode == 0
                    if not ok:
                        raise RuntimeError(p.stderr.strip() or "lp error")
                self.set_status(_("ส่งงานพิมพ์แล้ว") + " · %d %s" % (len(r["pages"]), _("หน้า")))
        except Exception as e:
            messagebox.showerror(APP, _("พิมพ์ไม่สำเร็จ") + "\n%s" % e)

    def _bind_wheel(self, widget, fn):
        def wheel(e):
            if sys.platform == "darwin":
                d = -e.delta
            else:
                d = -int(e.delta / 120) if e.delta else 0
            if d:
                fn(int(max(-6, min(6, d))))
        widget.bind("<MouseWheel>", wheel)
        widget.bind("<Button-4>", lambda e: fn(-2))
        widget.bind("<Button-5>", lambda e: fn(2))

    def _bind_keys(self):
        mods = ["Command", "Control"] if sys.platform == "darwin" else ["Control"]
        for m in mods:
            self.bind_all("<%s-o>" % m, lambda e: self.open_dialog())
            self.bind_all("<%s-s>" % m, lambda e: self.save())
            self.bind_all("<%s-S>" % m, lambda e: self.save(as_new=True))
            self.bind_all("<%s-z>" % m, lambda e: self.undo())
            self.bind_all("<%s-Z>" % m, lambda e: self.redo())
            self.bind_all("<%s-y>" % m, lambda e: self.redo())
            self.bind_all("<%s-d>" % m, lambda e: self.duplicate_obj())
            self.bind_all("<%s-p>" % m, lambda e: self.print_dialog())
            self.bind_all("<%s-equal>" % m, lambda e: self.set_zoom(self.zoom * 1.2))
            self.bind_all("<%s-plus>" % m, lambda e: self.set_zoom(self.zoom * 1.2))
            self.bind_all("<%s-minus>" % m, lambda e: self.set_zoom(self.zoom / 1.2))
        self.bind("<Key>", self.on_key)

    # ------------------------------------------------------------ helpers
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
        a = self.to_disp((r.x0, r.y0)); b = self.to_disp((r.x1, r.y1))
        return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])

    def page_rect_from_disp(self, x0, y0, x1, y1):
        a = self.to_page(x0, y0); b = self.to_page(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    def evpt(self, e):
        return self.cv.canvasx(e.x), self.cv.canvasy(e.y)

    def set_status(self, msg=""):
        self.status.configure(text=msg)
        if getattr(self, "_status_job", None):
            self.after_cancel(self._status_job)
        if msg:
            self._status_job = self.after(6000, lambda: self.status.configure(text=""))

    # ------------------------------------------------------------ undo
    def snapshot(self):
        if self._docbytes is None:
            self._docbytes = self.doc.tobytes()
        return (self._docbytes, copy.deepcopy(self.objs), self.cur)

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True
        self.update_state()

    def struct_changed(self):
        self._docbytes = None

    def _restore(self, snap):
        data, objs, cur = snap
        rebuild = data is not self._docbytes or len(objs) != len(self.objs)
        if data is not self._docbytes:
            self.doc = fitz.open("pdf", data)
            self._docbytes = data
        self.objs = objs
        self.cur = min(cur, self.doc.page_count - 1)
        self.sel = None; self.pdfsel = None
        self.dirty = True
        if rebuild:
            self.build_thumbs()
        else:
            for i in range(len(objs)):
                self.update_thumb(i)
        self.render_view(keep_scroll=True)
        self.render_props()
        self.update_state()

    def undo(self):
        if not self.has_doc() or not self.undo_stack:
            return
        self.redo_stack.append(self.snapshot())
        self._restore(self.undo_stack.pop())

    def redo(self):
        if not self.has_doc() or not self.redo_stack:
            return
        self.undo_stack.append(self.snapshot())
        self._restore(self.redo_stack.pop())

    def update_state(self):
        on = self.has_doc()
        edit = self.mode == "edit"
        self.b_save.configure(state="normal" if on else "disabled")
        self.b_print.configure(state="normal" if on else "disabled")
        self.b_undo.configure(state="normal" if (self.undo_stack and edit) else "disabled")
        self.b_redo.configure(state="normal" if (self.redo_stack and edit) else "disabled")
        self.b_home.configure(state="normal" if on else "disabled")
        name = os.path.basename(self.path) if self.path else (_("เอกสารใหม่") if on else "")
        self.title(("● " if self.dirty else "") + (name + " — " if name else "") + APP)
        self.fname.configure(text=(name + ("  •  " + _("ยังไม่บันทึก") if self.dirty else "")) if on else "")
        if on and not edit:
            self.hint.configure(text=_("โหมดดู — กด “แก้ไข” ด้านบนเพื่อเริ่มแก้ไข · ←/→ เปลี่ยนหน้า"))
        else:
            self.hint.configure(text=(_(HINTS.get(self.tool, "")).split("\n")[0]) if on else "")
        if on:
            self.page_var.set(str(self.cur + 1)); self.page_total.configure(text="/ %d" % self.doc.page_count)
            self.pcount.configure(text=_("%d หน้า") % self.doc.page_count)
        self.zoom_lbl.configure(text="%d%%" % round(self.zoom * 100))

    # ------------------------------------------------------------ files
    def confirm_discard(self):
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel(APP, _("มีการแก้ไขที่ยังไม่ได้บันทึก\nต้องการบันทึกก่อนหรือไม่?"))
        if r is None:
            return False
        if r:
            return self.save()
        return True

    def open_dialog(self):
        if not self.confirm_discard():
            return
        p = filedialog.askopenfilename(title=_("เปิดไฟล์ PDF"), filetypes=[("PDF", "*.pdf"), (_("ทุกไฟล์"), "*.*")])
        if p:
            self.open_path(p)

    def open_path(self, p):
        try:
            d = fitz.open(p)
            if d.needs_pass:
                pw = simpledialog.askstring(APP, _("ไฟล์นี้มีรหัสผ่าน กรุณาใส่รหัส:"), show="•", parent=self)
                if not pw or not d.authenticate(pw):
                    messagebox.showerror(APP, _("รหัสผ่านไม่ถูกต้อง")); return
                d = fitz.open("pdf", d.tobytes(encryption=fitz.PDF_ENCRYPT_NONE))
            if not d.is_pdf:
                d = fitz.open("pdf", d.convert_to_pdf())
        except Exception as e:
            messagebox.showerror(APP, _("เปิดไฟล์ไม่ได้\n%s") % e); return
        self.load_doc(d, p)

    def load_doc(self, d, path):
        self.doc = d
        self.path = path
        if path:
            self.add_recent(path)
        self._saved_once = False
        self.objs = [[] for _n in range(d.page_count)]
        self.images = {}
        self.cur = 0; self.sel = None
        self.undo_stack.clear(); self.redo_stack.clear()
        self._docbytes = None; self.dirty = False
        self._layout()
        self.update_idletasks()
        self.fit_width(render=False)
        self.build_thumbs()
        self.render_view()
        self.render_props()
        self.update_state()

    def new_blank(self):
        if not self.confirm_discard():
            return
        d = fitz.open(); d.new_page(width=595.28, height=841.89)
        self.load_doc(d, None)
        if self.mode == "view":
            self.set_mode("edit")

    def merge_new(self):
        """combine several PDFs into a new document"""
        if not self.confirm_discard():
            return
        ps = filedialog.askopenfilenames(title=_("เลือกไฟล์ PDF ที่จะรวม (เรียงตามลำดับที่เลือก)"),
                                         filetypes=[("PDF", "*.pdf")])
        if not ps:
            return
        d = fitz.open()
        try:
            for p in ps:
                d.insert_pdf(fitz.open(p))
        except Exception as e:
            messagebox.showerror(APP, _("รวมไฟล์ไม่สำเร็จ") + "\n%s" % e); return
        self.load_doc(d, None)
        self.dirty = True; self.update_state()
        self.set_status(_("รวม %d ไฟล์แล้ว — กดบันทึกเพื่อเก็บเป็นไฟล์ใหม่") % len(ps))

    def build_output(self, pages=None):
        out = fitz.open("pdf", self.doc.tobytes())
        if pages is not None:
            out.select(pages)
            objs = [self.objs[i] for i in pages]
        else:
            objs = self.objs
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
            path = filedialog.asksaveasfilename(title=_("บันทึกไฟล์ PDF"), defaultextension=".pdf",
                                                initialdir=os.path.dirname(self.path) if self.path else None,
                                                initialfile=base + ".pdf", filetypes=[("PDF", "*.pdf")])
            if not path:
                return False
        try:
            self.configure(cursor="watch"); self.update()
            data = self.build_output().tobytes(garbage=3, deflate=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            messagebox.showerror(APP, _("บันทึกไม่สำเร็จ\n%s") % e); return False
        finally:
            self.configure(cursor="")
        self.path = path; self._saved_once = True; self.dirty = False
        self.add_recent(path)
        self.update_state()
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
                o = fitz.open(p); n = o.page_count
                self.doc.insert_pdf(o, start_at=at)
                self.objs[at:at] = [[] for _n in range(n)]
                at += n
        except Exception as e:
            messagebox.showerror(APP, _("รวมไฟล์ไม่สำเร็จ\n%s") % e)
        self.struct_changed()
        self.build_thumbs(); self.render_view(); self.update_state()
        self.set_status(_("เพิ่ม %d ไฟล์แล้ว") % len(ps))

    def on_close(self):
        if self.confirm_discard():
            self.destroy()

    # ------------------------------------------------------------ rendering
    def render_page_pix(self, i, zoom):
        tmp = fitz.open()
        tmp.insert_pdf(self.doc, from_page=i, to_page=i)
        apply_objects(tmp[0], self.objs[i], self.images)
        return tmp[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), annots=True, alpha=False)

    def render_view(self, keep_scroll=False):
        if not self.has_doc():
            return
        yv = self.cv.yview()[0] if keep_scroll else 0
        xv = self.cv.xview()[0] if keep_scroll else 0
        pix = self.render_page_pix(self.cur, self.zoom)
        self.page_img = tk.PhotoImage(data=pix.tobytes("ppm"))
        cw = self.cv.winfo_width()
        self.ox = max(MARGIN, (cw - pix.width) / 2); self.oy = MARGIN
        self.cv.delete("all")
        sh = tc(SHADOW)
        for i, off in enumerate((6, 3)):
            self.cv.create_rectangle(self.ox - off + 2, self.oy - off + 4, self.ox + pix.width + off - 2,
                                     self.oy + pix.height + off + 2, fill=sh if i else tc(CANVAS), outline=sh if i == 0 else "",
                                     width=1)
        self.cv.create_image(self.ox, self.oy, image=self.page_img, anchor="nw", tags="page")
        self.cv.create_text(self.ox + pix.width / 2, self.oy + pix.height + 14,
                            text=_("หน้า %d จาก %d") % (self.cur + 1, self.doc.page_count), fill=tc(MUTED),
                            font=("Helvetica", 11))
        self.cv.configure(scrollregion=(0, 0, max(cw, pix.width + 2 * MARGIN), pix.height + 2 * MARGIN + 10))
        self.cv.yview_moveto(yv); self.cv.xview_moveto(xv)
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
        self.cur = i; self.sel = None; self.pdfsel = None
        self.render_view()
        if not top:
            self.cv.yview_moveto(1.0)
        self.highlight_thumb(); self.scroll_thumb_into_view(); self.render_props()

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

    # ------------------------------------------------------------ thumbnails
    TW = 128

    def build_thumbs(self):
        if not self.has_doc():
            return
        self.thumbs.configure(bg=tc(PANEL))
        self.thumbs.delete("all"); self.thumb_imgs = {}
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
            self.thumbs.create_text(92, y + h + 13, text=str(i + 1), fill=tc(MUTED), font=("Helvetica", 11),
                                    tags="num%d" % i)
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
                self._thumb_job = None; return
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
        for i, (x0, y0, w, h, s) in enumerate(self._thumb_pos):
            if y0 - 8 <= y <= y0 + h + 24:
                self.goto(i); return

    # ------------------------------------------------------------ page ops
    def _after_struct(self, scroll=True):
        self.pdfsel = None
        self.struct_changed()
        self.build_thumbs(); self.render_view(); self.render_props()
        if scroll:
            self.scroll_thumb_into_view()

    def rotate_page(self, d):
        if not self.has_doc():
            return
        self.push_undo()
        p = self.page(); p.set_rotation((p.rotation + d) % 360)
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
            messagebox.showinfo(APP, _("เอกสารต้องมีอย่างน้อย 1 หน้า")); return
        self.push_undo()
        self.doc.delete_page(self.cur); self.objs.pop(self.cur)
        self.cur = min(self.cur, self.doc.page_count - 1); self.sel = None
        self._after_struct()
        self.set_status(_("ลบหน้าแล้ว — กด ⌘Z / Ctrl+Z เพื่อเลิกทำ"))

    def insert_blank(self):
        if not self.has_doc():
            return
        self.push_undo()
        r = self.page().mediabox; rot = self.page().rotation
        np_ = self.doc.new_page(self.cur + 1, width=r.width, height=r.height)
        if rot:
            np_.set_rotation(rot)
        self.objs.insert(self.cur + 1, [])
        self.cur += 1; self.sel = None
        self._after_struct()

    def duplicate_page(self):
        if not self.has_doc():
            return
        self.push_undo()
        to = self.cur + 1
        self.doc.fullcopy_page(self.cur, to if to < self.doc.page_count else -1)
        self.objs.insert(to, copy.deepcopy(self.objs[self.cur]))
        self.cur = to; self.sel = None
        self._after_struct()

    def extract_page(self):
        if not self.has_doc():
            return
        base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
        path = filedialog.asksaveasfilename(title=_("บันทึกหน้านี้เป็นไฟล์ใหม่"), defaultextension=".pdf",
                                            initialfile=_("%s-หน้า%d.pdf") % (base, self.cur + 1),
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self.build_output([self.cur]).save(path, garbage=3, deflate=True)
            self.set_status(_("✓ บันทึกหน้า %d แล้ว") % (self.cur + 1))
        except Exception as e:
            messagebox.showerror(APP, _("บันทึกไม่สำเร็จ\n%s") % e)

    # ------------------------------------------------------------ tools
    def set_tool(self, t):
        self.tool = t
        self.pdfsel = None
        for k, b in self.tool_btns.items():
            on = k == t
            b.configure(fg_color=SOFT if on else "transparent", text_color=ACCENT if on else MUTED,
                        image=icon(k, 20, ACCENT if on else None), font=F(11, "bold" if on else "normal"))
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

    # ------------------------------------------------------------ properties panel
    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkLabel(f, text=title, font=F(12), text_color=MUTED).pack(anchor="w", pady=(0, 6))
        return f

    def _apply(self, fn, live=False):
        """apply a property change to the selected object (one undo step per gesture)"""
        o = self.sel_obj()
        if not o:
            return
        if not self._prop_armed:
            self.push_undo()
        self._prop_armed = live
        fn(o)
        if live:
            if self._prop_job:
                self.after_cancel(self._prop_job)
            self._prop_job = self.after(120, self._live_refresh)
        else:
            self.refresh()

    def _live_refresh(self):
        self._prop_job = None
        self.render_view(keep_scroll=True); self.update_thumb(self.cur)

    def render_props(self):
        if not hasattr(self, "props"):
            return
        for w in self.props_in.winfo_children():
            w.destroy()
        self._prop_armed = False
        if self.pdfsel and self.has_doc():
            self._render_pdfimg_props(); return
        o = self.sel_obj()
        kind = o["type"] if o else {"edittext": "text"}.get(self.tool, self.tool)
        head = ctk.CTkFrame(self.props_in, fg_color="transparent"); head.pack(fill="x", padx=18, pady=(18, 16))
        ic = {"redact": "edittext", "image": "image"}.get(kind, kind)
        if ic in ICONS:
            badge = ctk.CTkFrame(head, fg_color=SOFT, corner_radius=10, width=38, height=38)
            badge.pack(side="left"); badge.pack_propagate(False)
            ctk.CTkLabel(badge, text="", image=icon(ic, 19, ACCENT)).pack(expand=True)
        tt = ctk.CTkFrame(head, fg_color="transparent"); tt.pack(side="left", padx=10)
        ctk.CTkLabel(tt, text=_(TYPE_NAME.get(kind, "")) if o else _(TOOL_TITLE.get(self.tool, "")), font=F(15, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(tt, text=_("วัตถุที่เลือก") if o else _("เครื่องมือ"), font=F(12), text_color=MUTED,
                     anchor="w").pack(anchor="w")

        if kind == "text":
            sec = self._section(self.props_in, _("สีตัวอักษร"))
            def setc(c):
                self.text_color = c; self._apply(lambda x: x.__setitem__("color", c))
            ColorRow(sec, SWATCHES[:6], o["color"] if o else self.text_color, setc).pack(anchor="w")
            sec = self._section(self.props_in, _("ขนาดตัวอักษร (pt)"))
            row = ctk.CTkFrame(sec, fg_color="transparent"); row.pack(fill="x")
            sv = ctk.StringVar(value="%g" % round(o["size"] if o else self.fsize, 1))
            def setsize(v):
                try:
                    v = max(4.0, min(300.0, float(v)))
                except ValueError:
                    return
                sv.set("%g" % v); self.fsize = v
                if o:
                    self._apply(lambda x: self._resize_text(x, v))
            ctk.CTkButton(row, text="−", width=34, height=32, corner_radius=8, fg_color=CARD, hover_color=HOVER,
                          text_color=TEXT, font=F(16), command=lambda: setsize(float(sv.get() or 16) - 1)).pack(side="left")
            e = ctk.CTkEntry(row, textvariable=sv, width=70, height=32, corner_radius=8, justify="center",
                             border_color=BORDER, fg_color=CARD, font=F(14))
            e.pack(side="left", padx=6); e.bind("<Return>", lambda ev: setsize(sv.get()))
            ctk.CTkButton(row, text="+", width=34, height=32, corner_radius=8, fg_color=CARD, hover_color=HOVER,
                          text_color=TEXT, font=F(16), command=lambda: setsize(float(sv.get() or 16) + 1)).pack(side="left")
            sec = self._section(self.props_in, _("ฟอนต์"))
            orig = o.get("orig") if o else None
            olabel = (orig_prefix() + orig["font"].split("+", 1)[-1]) if orig else None
            curf = (olabel if (o and o.get("from_orig") and olabel) else (o.get("family") if o else self.ffamily)) or "Sarabun"
            fv = ctk.StringVar(value=curf)
            def setfont(v):
                if o:
                    self._apply(lambda x: self._restyle(x, original=v.startswith(orig_prefix()),
                                                        family=None if v.startswith(orig_prefix()) else v))
                else:
                    self.ffamily = v
            font_button(sec, fv, original=orig["font"].split("+", 1)[-1] if orig else None, on_change=setfont,
                        width=230).pack(anchor="w")
            if o:
                bv = ctk.BooleanVar(value=bool(o.get("bold"))); iv = ctk.BooleanVar(value=bool(o.get("italic")))
                sec = self._section(self.props_in, _("รูปแบบ"))
                sw = ctk.CTkFrame(sec, fg_color="transparent"); sw.pack(anchor="w")
                ctk.CTkSwitch(sw, text=_("ตัวหนา"), variable=bv, progress_color=ACCENT, font=F(13), text_color=TEXT, width=100,
                              command=lambda: self._apply(lambda x: self._restyle(x, bold=bv.get()))).pack(side="left")
                ctk.CTkSwitch(sw, text=_("ตัวเอียง"), variable=iv, progress_color=ACCENT, font=F(13), text_color=TEXT, width=100,
                              command=lambda: self._apply(lambda x: self._restyle(x, italic=iv.get()))).pack(side="left")
                if orig:
                    ctk.CTkLabel(sec, text=_("ฟอนต์ที่ใช้จริง: ") + fontbook().reg.get(fontbook().key_for(o)[0], {}).get("label", ""),
                                 font=F(11), text_color=MUTED, wraplength=220, justify="left").pack(anchor="w", pady=(6, 0))
                primary_btn(self._section(self.props_in, _("เนื้อหา")), _("แก้ไขข้อความ"), lambda: self.edit_text_obj(self.sel),
                            "edit", height=34).pack(fill="x")

        if kind in ("ink", "line", "arrow", "rect"):
            sec = self._section(self.props_in, _("สีเส้นขอบ") if kind == "rect" else _("สี"))
            def setc(c):
                self.color = c; self._apply(lambda x: x.__setitem__("color", c))
            ColorRow(sec, SWATCHES[:6], o["color"] if o else self.color, setc).pack(anchor="w")
            val = o["width"] if o else self.stroke
            sec = self._section(self.props_in, _("ความหนาเส้น"))
            row = ctk.CTkFrame(sec, fg_color="transparent"); row.pack(fill="x")
            lbl = ctk.CTkLabel(row, text="%g pt" % val, width=48, font=F(13), text_color=TEXT)
            def setw(v):
                v = round(float(v) * 2) / 2; lbl.configure(text="%g pt" % v); self.stroke = v
                self._apply(lambda x: x.__setitem__("width", v), live=True)
            sl = ctk.CTkSlider(row, from_=0.5, to=20, number_of_steps=39, command=setw, width=170,
                               progress_color=ACCENT, button_color=ACCENT, button_hover_color=ACCENT_H)
            sl.set(val); sl.pack(side="left"); lbl.pack(side="left", padx=(8, 0))
        if kind == "rect":
            sec = self._section(self.props_in, _("สีพื้น"))
            def setf(c):
                self.fill = c; self._apply(lambda x: x.__setitem__("fill", c))
            ColorRow(sec, SWATCHES[:5], o.get("fill") if o else self.fill, setf, allow_none=True).pack(anchor="w")
        if kind == "highlight":
            sec = self._section(self.props_in, _("สีไฮไลต์"))
            def seth(c):
                self.hl_color = c; self._apply(lambda x: x.__setitem__("color", c))
            ColorRow(sec, HL_SWATCHES, o["color"] if o else self.hl_color, seth).pack(anchor="w")
        if kind == "whiteout" and o:
            sec = self._section(self.props_in, _("สีที่ใช้ปิดทับ"))
            ColorRow(sec, ["#ffffff", "#f3f4f6", "#fef9c3", "#111827"], o.get("fill", "#ffffff"),
                     lambda c: self._apply(lambda x: x.__setitem__("fill", c))).pack(anchor="w")

        if o:
            sec = self._section(self.props_in, _("การจัดการ"))
            grid = ctk.CTkFrame(sec, fg_color="transparent"); grid.pack(fill="x")
            for i, (ic2, t, cmd) in enumerate((("copy", _("ทำสำเนา"), self.duplicate_obj),
                                               ("front", _("ไว้หน้าสุด"), lambda: self.order_obj(True)),
                                               ("back", _("ไว้หลังสุด"), lambda: self.order_obj(False)))):
                secondary_btn(grid, t, cmd, ic2, height=34, width=102).grid(row=i // 2, column=i % 2, padx=(0, 6), pady=3, sticky="ew")
            ctk.CTkButton(grid, text=_("ลบ"), image=icon("trash", 17, (ACCENT, "#ff6b70")), command=self.delete_obj,
                          fg_color=PANEL, hover_color=SOFT, text_color=(ACCENT, "#ff6b70"), border_width=1,
                          border_color=BORDER, corner_radius=10, height=34, width=102,
                          font=F(13)).grid(row=1, column=1, padx=(0, 6), pady=3, sticky="ew")

        if not o and self.tool == "select" and self.has_doc():
            n_page = len(self.page_images(self.cur))
            n_all = len({x for i in range(self.doc.page_count) for x in self.page_xrefs(i)})
            sec = self._section(self.props_in, _("รูปภาพในเอกสาร"))
            ctk.CTkLabel(sec, text=_("หน้านี้ %d รูป · ทั้งไฟล์ %d รูป\nคลิกที่รูปในหน้าเพื่อเลือก ลบ หรือแทนที่") % (n_page, n_all),
                         font=F(12), text_color=MUTED, justify="left", anchor="w", wraplength=210).pack(anchor="w", pady=(0, 8))
            b = secondary_btn(sec, _("ส่งออกรูปทั้งหมด…"), self.export_all_images, "export", height=34)
            b.pack(fill="x")
            if not n_all:
                b.configure(state="disabled")

        # hint card
        card = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkLabel(card, text=_("💡 วิธีใช้"), font=F(12, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card, text=_(HINTS["select" if o else self.tool]), font=F(12), text_color=MUTED, wraplength=196,
                     justify="left", anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

    # ------------------------------------------------------------ objects
    def add_obj(self, o, select=True):
        self.push_undo()
        self.objs[self.cur].append(o)
        if select:
            self.sel = len(self.objs[self.cur]) - 1
        self.refresh()

    TEXT_KEYS = ("text", "size", "color", "bold", "italic", "family", "fontkey", "thstyle", "label", "orig", "from_orig")

    def make_text(self, spec, cx, cy, rot=None, baseline=False):
        """text object whose display top-left (or first baseline when baseline=True) is at canvas (cx, cy)"""
        o = dict(type="text")
        o.update({k: spec[k] for k in self.TEXT_KEYS if k in spec})
        o.setdefault("bold", False); o.setdefault("italic", False)
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
        spec = dict(text=r["text"], size=r["size"], color=r["color"], bold=r["bold"], italic=r["italic"],
                    orig=orig, fontkey=None, family=None)
        note = ""
        if r.get("original") and orig:
            exact = r["bold"] == orig["bold"] and r["italic"] == orig["italic"]
            rs, note = resolve_span_font(self.doc, self.page(), orig, r["text"], exact=exact,
                                         bold=r["bold"], italic=r["italic"])
            spec.update(rs)
            spec["bold"], spec["italic"], spec["from_orig"] = r["bold"], r["italic"], True
        else:
            fam = r.get("family") or "Sarabun"
            spec.update(family=fam, label=fam, from_orig=False,
                        thstyle=any(k in _norm(fam) for k in TH_STYLE))
        return spec, note

    def _restyle(self, o, **ch):
        """change text properties while keeping the first baseline in place"""
        r = dict(text=o["text"], size=o["size"], color=o["color"], bold=o.get("bold", False),
                 italic=o.get("italic", False), original=bool(o.get("from_orig")), family=o.get("family"))
        r.update(ch)
        spec, note = self._spec_from_result(r, o.get("orig"))
        cx, bl = self._baseline_anchor(o)
        n = self.make_text(spec, cx, bl, rot=o.get("rot", 0), baseline=True)
        o.clear(); o.update(n)
        if note:
            self.set_status(note)

    def _resize_text(self, o, size):
        self._restyle(o, size=size)

    def _dialog_for(self, title, o):
        orig = o.get("orig")
        label = orig["font"].split("+", 1)[-1] if orig else None
        spec = dict(o); spec.setdefault("from_orig", bool(orig))
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
            self.objs[self.cur].pop(idx); self.sel = None
        else:
            spec, note = self._spec_from_result(r, o.get("orig"))
            cx, bl = self._baseline_anchor(o)
            n = self.make_text(spec, cx, bl, rot=o.get("rot", 0), baseline=True)
            o.clear(); o.update(n)
            self.text_color = r["color"]; self.fsize = r["size"]
            if note:
                self.set_status(note)
        self.refresh()

    def delete_obj(self):
        if self.sel_obj() is None:
            return
        self.push_undo()
        self.objs[self.cur].pop(self.sel); self.sel = None
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
        lst = self.objs[self.cur]; lst.pop(self.sel)
        if front:
            lst.append(o); self.sel = len(lst) - 1
        else:
            lst.insert(0, o); self.sel = 0
        self.refresh()

    @staticmethod
    def _move(o, dx, dy):
        t = o["type"]
        if t in ("line", "arrow"):
            o["p1"] = (o["p1"][0] + dx, o["p1"][1] + dy); o["p2"] = (o["p2"][0] + dx, o["p2"][1] + dy)
        elif t == "ink":
            o["pts"] = [(x + dx, y + dy) for x, y in o["pts"]]
        else:
            r = o["rect"]; o["rect"] = [r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy]

    def hit(self, cx, cy):
        objs = self.objs[self.cur]
        for i in range(len(objs) - 1, -1, -1):
            o = objs[i]
            if o["type"] in ("line", "arrow"):
                a = self.to_disp(o["p1"]); b = self.to_disp(o["p2"])
                if self._seg_dist((cx, cy), a, b) <= max(6, o["width"] * self.zoom / 2 + 3):
                    return i
                continue
            x0, y0, x1, y1 = self.disp_rect(obj_bbox(o))
            if x0 - 3 <= cx <= x1 + 3 and y0 - 3 <= cy <= y1 + 3:
                return i
        return None

    @staticmethod
    def _seg_dist(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def draw_selection(self):
        self.cv.delete("sel")
        if self.pdfsel and self.has_doc():
            x0, y0, x1, y1 = self.disp_rect(fitz.Rect(self.pdfsel["bbox"]))
            self.cv.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline="#f59e0b", width=2.5, dash=(6, 4), tags="sel")
            lx, ly = max(x0, self.ox), max(y0, self.oy)
            self.cv.create_rectangle(lx, ly, lx + 96, ly + 22, fill="#f59e0b", outline="", tags="sel")
            self.cv.create_text(lx + 48, ly + 11, text=_("รูปในไฟล์"), fill="white", font=("Helvetica", 11, "bold"), tags="sel")
        o = self.sel_obj()
        if not o:
            return
        if o["type"] in ("line", "arrow"):
            for k in ("p1", "p2"):
                x, y = self.to_disp(o[k])
                self.cv.create_oval(x - 7, y - 7, x + 7, y + 7, fill="white", outline=SEL, width=2, tags=("sel", "h_" + k))
            return
        x0, y0, x1, y1 = self.disp_rect(obj_bbox(o))
        self.cv.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=SEL, width=1.5, tags="sel")
        for k, (x, y) in {"nw": (x0 - 3, y0 - 3), "ne": (x1 + 3, y0 - 3), "sw": (x0 - 3, y1 + 3), "se": (x1 + 3, y1 + 3)}.items():
            self.cv.create_oval(x - 6, y - 6, x + 6, y + 6, fill="white", outline=SEL, width=2, tags=("sel", "h_" + k))

    def handle_at(self, cx, cy):
        for item in self.cv.find_overlapping(cx - 3, cy - 3, cx + 3, cy + 3):
            for t in self.cv.gettags(item):
                if t.startswith("h_"):
                    return t[2:]
        return None

    # ------------------------------------------------------------ mouse
    def on_down(self, e):
        self.cv.focus_set()
        if not self.has_doc() or self.mode == "view":
            return
        cx, cy = self.evpt(e)
        tool = self.tool
        self.drag = None
        if tool == "select":
            h = self.handle_at(cx, cy) if self.sel_obj() else None
            if h:
                o = self.sel_obj()
                self.drag = dict(kind="resize", h=h, start=(cx, cy), orig=copy.deepcopy(o),
                                 box=self.disp_rect(obj_bbox(o)), moved=False)
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
                self.sel = i; self.draw_selection(); self.edit_text_obj(i); return
            r = TextDialog(self, _("เพิ่มข้อความ"), dict(text="", size=self.fsize, color=self.text_color,
                           family=self.ffamily)).run()
            if r and r["text"].strip():
                self.text_color = r["color"]; self.fsize = r["size"]; self.ffamily = r["family"] or self.ffamily
                spec, _note = self._spec_from_result(r)
                self.add_obj(self.make_text(spec, cx, cy - r["size"] * 0.7 * self.zoom))
            return
        if tool == "edittext":
            self.edit_existing(cx, cy); return
        if tool == "ink":
            self.drag = dict(kind="ink", pts=[(cx, cy)], last=(cx, cy))
            return
        self.drag = dict(kind="shape", start=(cx, cy), end=(cx, cy))

    def on_move(self, e):
        if not self.drag:
            return
        cx, cy = self.evpt(e)
        d = self.drag; k = d["kind"]
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
            self.cv.create_line(lx, ly, cx, cy, fill=self.color, width=max(1, self.stroke * z),
                                capstyle="round", smooth=True, tags="draft")
            d["pts"].append((cx, cy)); d["last"] = (cx, cy)
        elif k == "shape":
            sx, sy = d["start"]
            t = self.tool
            if e.state & 0x1 and t in ("line", "arrow"):
                a = round(math.atan2(cy - sy, cx - sx) / (math.pi / 4)) * (math.pi / 4)
                L = math.hypot(cx - sx, cy - sy); cx, cy = sx + L * math.cos(a), sy + L * math.sin(a)
            d["end"] = (cx, cy)
            self.cv.delete("draft")
            w = max(1, self.stroke * z)
            if t in ("line", "arrow"):
                self.cv.create_line(sx, sy, cx, cy, fill=self.color, width=w, capstyle="round",
                                    arrow="last" if t == "arrow" else None,
                                    arrowshape=(max(10, w * 4.5), max(10, w * 4.5), max(5, w * 2.4)), tags="draft")
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
        d = self.drag; self.drag = None
        if not d:
            return
        k = d["kind"]
        if k == "move":
            if d["moved"]:
                o = self.sel_obj()
                a = self.to_page(*d["start"]); b = self.to_page(*d["last"])
                self.push_undo(); self._move(o, b[0] - a[0], b[1] - a[1]); self.refresh()
            return
        if k == "resize":
            if d["moved"]:
                o = self.sel_obj(); new = copy.deepcopy(o)
                o.clear(); o.update(d["orig"])
                self.push_undo()
                o.clear(); o.update(new)
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
            self.add_obj(dict(type=t, p1=self.to_page(sx, sy), p2=self.to_page(ex, ey), color=self.color,
                              width=self.stroke))
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
        orig = d["orig"]; h = d["h"]
        if h in ("p1", "p2"):
            o[h] = self.to_page(cx, cy); return
        bx0, by0, bx1, by1 = d["box"]
        x0, y0, x1, y1 = bx0, by0, bx1, by1
        if "e" in h: x1 = cx
        if "w" in h: x0 = cx
        if "s" in h: y1 = cy
        if "n" in h: y0 = cy
        bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
        keep = o["type"] == "text" or (o["type"] == "image") != bool(shift)
        if keep:
            s = max((x1 - x0) / bw, (y1 - y0) / bh, 0.05)
            nw, nh = bw * s, bh * s
            if "w" in h: x0 = x1 - nw
            else: x1 = x0 + nw
            if "n" in h: y0 = y1 - nh
            else: y1 = y0 + nh
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
            spec = dict(orig); spec["size"] = size
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
        if not self.has_doc() or self.mode == "view":
            return
        cx, cy = self.evpt(e)
        i = self.hit(cx, cy)
        if i is None:
            return
        self.sel = i; self.draw_selection(); self.render_props()
        m = tk.Menu(self, tearoff=0)
        if self.objs[self.cur][i]["type"] == "text":
            m.add_command(label=_("แก้ไขข้อความ…"), command=lambda: self.edit_text_obj(i))
        m.add_command(label=_("ทำสำเนา"), command=self.duplicate_obj)
        m.add_command(label=_("ไว้หน้าสุด"), command=lambda: self.order_obj(True))
        m.add_command(label=_("ไว้หลังสุด"), command=lambda: self.order_obj(False))
        m.add_separator()
        m.add_command(label=_("ลบ"), command=self.delete_obj)
        m.tk_popup(e.x_root, e.y_root)

    # ------------------------------------------------------------ edit existing text
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
        base = sp["font"].split("+", 1)[-1]; nb = _norm(base)
        ob = bool(sp["flags"] & 16) or any(k in nb for k in ("bold", "black", "heavy"))
        oi = bool(sp["flags"] & 2) or "italic" in nb or "oblique" in nb
        orig = dict(font=sp["font"], flags=sp["flags"], bold=ob, italic=oi)
        spec0 = dict(text=normalize_thai(sp["text"]).strip(), size=round(sp["size"], 2), color=int2hex(sp["color"]),
                     bold=ob, italic=oi, from_orig=True)
        r = TextDialog(self, _("แก้ข้อความเดิม"), spec0, None, original=base).run()
        if not r:
            return
        self.push_undo()
        bb = fitz.Rect(sp["bbox"]); h = bb.height
        self.objs[self.cur].append(dict(type="redact", rect=[bb.x0 + 0.3, bb.y0 + h * 0.2, bb.x1 - 0.3, bb.y1 - h * 0.2]))
        self.sel = None
        if r["text"].strip():
            spec, note = self._spec_from_result(r, orig)
            ox, oy = self.to_disp(sp["origin"])
            self.objs[self.cur].append(self.make_text(spec, ox, oy, baseline=True))
            self.sel = len(self.objs[self.cur]) - 1
            if note:
                self.set_status(note)
        self.refresh()

    # ------------------------------------------------------------ images that are part of the PDF
    def page_xrefs(self, i):
        return [im[0] for im in self.doc[i].get_images(full=True) if im[0] > 0 and not (im[2] <= 1 and im[3] <= 1)]

    def page_images(self, i):
        """placements of images on page i: list of dict(xref, bbox, w, h)"""
        out = []
        try:
            for k, info in enumerate(self.doc[i].get_image_info(xrefs=True)):
                r = fitz.Rect(info["bbox"])
                if r.is_empty or r.width < 2 or r.height < 2 or (info.get("width", 9) <= 1 and info.get("height", 9) <= 1):
                    continue
                out.append(dict(xref=info.get("xref", 0), bbox=tuple(r), w=info.get("width"), h=info.get("height"),
                                key="%d:%d:%d" % (i, info.get("xref", 0), k)))
        except Exception as e:
            print("image info:", e)
        return out

    def hit_pdf_image(self, cx, cy):
        px, py = self.to_page(cx, cy)
        hits = [im for im in self.page_images(self.cur) if fitz.Rect(im["bbox"]).contains(fitz.Point(px, py))]
        if not hits:
            return None
        return min(hits, key=lambda im: fitz.Rect(im["bbox"]).get_area())    # smallest = top-most in practice

    def _image_pixmap(self, xref):
        pix = fitz.Pixmap(self.doc, xref)
        smask = 0
        for im in self.doc[self.cur].get_images(full=True) + [x for i in range(self.doc.page_count) for x in self.doc[i].get_images(full=True)]:
            if im[0] == xref:
                smask = im[1]; break
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
        if info and info.get("ext") in ("jpeg", "jpg", "png") and not info.get("smask") \
                and info.get("colorspace", 3) in (1, 3):
            return info["image"], "jpg" if info["ext"] in ("jpeg", "jpg") else "png"
        return self._image_pixmap(xref).tobytes("png"), "png"

    def _render_pdfimg_props(self):
        im = self.pdfsel
        head = ctk.CTkFrame(self.props_in, fg_color="transparent"); head.pack(fill="x", padx=18, pady=(18, 16))
        badge = ctk.CTkFrame(head, fg_color=("#fef3c7", "#3a2e12"), corner_radius=10, width=38, height=38)
        badge.pack(side="left"); badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon("image", 19, "#d97706")).pack(expand=True)
        tt = ctk.CTkFrame(head, fg_color="transparent"); tt.pack(side="left", padx=10)
        ctk.CTkLabel(tt, text=_("รูปในไฟล์ PDF"), font=F(15, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(tt, text="%s × %s px" % (im.get("w") or "?", im.get("h") or "?"), font=F(12), text_color=MUTED,
                     anchor="w").pack(anchor="w")
        # preview
        try:
            pix = self._image_pixmap(im["xref"])
            img = Image.frombytes("RGBA" if pix.alpha else "RGB", (pix.width, pix.height), pix.samples)
            img.thumbnail((228, 170))
            prev = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
            prev.pack(fill="x", padx=18, pady=(0, 16))
            ctk.CTkLabel(prev, text="", image=ctk.CTkImage(light_image=img, dark_image=img, size=img.size)).pack(padx=10, pady=10)
        except Exception as e:
            print("preview:", e)
        sec = self._section(self.props_in, _("การจัดการรูป"))
        if not im["xref"]:
            ctk.CTkLabel(sec, text=_("รูปชนิดฝังในเนื้อหา (inline) แก้ไขไม่ได้ — ใช้ “ปิดทับ” แทน"), font=F(12),
                         text_color=MUTED, wraplength=220, justify="left").pack(anchor="w")
        else:
            secondary_btn(sec, _("บันทึกรูปนี้…"), self.save_pdf_image, "export", height=34).pack(fill="x", pady=3)
            secondary_btn(sec, _("แทนที่ด้วยรูปอื่น…"), self.replace_pdf_image, "replace", height=34).pack(fill="x", pady=3)
            ctk.CTkButton(sec, text=_("ลบรูปนี้"), image=icon("trash", 17, (ACCENT, "#ff6b70")), command=self.delete_pdf_image,
                          fg_color=PANEL, hover_color=SOFT, text_color=(ACCENT, "#ff6b70"), border_width=1,
                          border_color=BORDER, corner_radius=10, height=34, font=F(13)).pack(fill="x", pady=3)
            shared = self._pages_using(im["xref"])
            if len(shared) > 1:
                ctk.CTkLabel(sec, text=_("⚠️ รูปนี้ใช้ร่วมกันใน %d หน้า — การลบ/แทนที่จะมีผลทุกหน้า") % len(shared),
                             font=F(12), text_color=("#b45309", "#fbbf24"), wraplength=220, justify="left").pack(anchor="w", pady=(8, 0))
        sec = self._section(self.props_in, _("ทั้งเอกสาร"))
        secondary_btn(sec, _("ส่งออกรูปทั้งหมด…"), self.export_all_images, "export", height=34).pack(fill="x")
        card = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkLabel(card, text=_("💡 วิธีใช้"), font=F(12, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card, text=_("Delete = ลบรูป · คลิกที่ว่างเพื่อยกเลิกการเลือก\nรูปที่แทนที่จะวางพอดีกรอบเดิมโดยรักษาสัดส่วน แล้วย้าย/ปรับขนาดต่อได้"),
                     font=F(12), text_color=MUTED, wraplength=196, justify="left", anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

    def _pages_using(self, xref):
        return [i for i in range(self.doc.page_count) if xref in self.page_xrefs(i)]

    def _confirm_shared(self, xref, action):
        pages = self._pages_using(xref)
        if len(pages) <= 1:
            return True
        return messagebox.askyesno(APP, _("รูปนี้ใช้ร่วมกันใน %d หน้า (หน้า %s)\n%sรูปนี้ในทุกหน้าหรือไม่?")
                                   % (len(pages), ", ".join(str(p + 1) for p in pages[:12]) + ("…" if len(pages) > 12 else ""), action))

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
            messagebox.showerror(APP, _("ลบรูปไม่สำเร็จ\n%s") % e); return
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
        p = filedialog.askopenfilename(title=_("เลือกรูปใหม่"),
                                       filetypes=[(_("รูปภาพ"), "*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp"), (_("ทุกไฟล์"), "*.*")])
        if not p:
            return
        try:
            with open(p, "rb") as f:
                data = f.read()
            pix = fitz.Pixmap(data)
            if not p.lower().endswith((".png", ".jpg", ".jpeg")):
                data = pix.tobytes("png")
        except Exception:
            messagebox.showerror(APP, _("เปิดรูปภาพนี้ไม่ได้")); return
        shared = len(self._pages_using(im["xref"])) > 1
        if shared:
            if not self._confirm_shared(im["xref"], _("แทนที่")):
                return
            self.push_undo()
            self.page().replace_image(im["xref"], stream=data)      # same box on every page
            self.pdfsel = None; self.struct_changed()
            self.render_view(keep_scroll=True)
            for i in range(self.doc.page_count):
                self.update_thumb(i)
            self.render_props(); self.set_status(_("แทนที่รูปในทุกหน้าแล้ว"))
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
        self.objs[self.cur].append(dict(type="image", img=key, rect=self.page_rect_from_disp(nx, ny, nx + w, ny + h),
                                        rot=self.page().rotation))
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
        path = filedialog.asksaveasfilename(title=_("บันทึกรูป"), defaultextension="." + ext,
                                            initialfile=_("%s-หน้า%d-รูป.%s") % (base, self.cur + 1, ext),
                                            filetypes=[(_("รูปภาพ"), "*." + ext)])
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
                    seen.add(x); items.append((i, x))
        if not items:
            messagebox.showinfo(APP, _("ไม่พบรูปภาพในไฟล์นี้")); return
        folder = filedialog.askdirectory(title=_("เลือกโฟลเดอร์สำหรับเก็บรูป (%d รูป)") % len(items))
        if not folder:
            return
        base = os.path.splitext(os.path.basename(self.path or _("เอกสาร.pdf")))[0]
        out = os.path.join(folder, base + _("-รูปภาพ"))
        n, k = 2, out
        while os.path.exists(k):
            k = "%s (%d)" % (out, n); n += 1
        out = k
        os.makedirs(out, exist_ok=True)
        ok = 0
        self.configure(cursor="watch"); self.update()
        try:
            counter = {}
            for i, x in items:
                try:
                    data, ext = self._image_bytes(x)
                    if len(data) < 120:          # skip blank placeholders (e.g. deleted images)
                        continue
                    counter[i] = counter.get(i, 0) + 1
                    with open(os.path.join(out, _("หน้า%03d-รูป%02d.%s") % (i + 1, counter[i], ext)), "wb") as f:
                        f.write(data)
                    ok += 1
                except Exception as e:
                    print("export image", x, e)
        finally:
            self.configure(cursor="")
        self.set_status(_("✓ ส่งออก %d รูป ไปที่ %s") % (ok, out))
        if messagebox.askyesno(APP, _("ส่งออก %d รูปเรียบร้อย\n\n%s\n\nเปิดโฟลเดอร์เลยหรือไม่?") % (ok, out)):
            try:
                if sys.platform == "darwin":
                    import subprocess; subprocess.Popen(["open", out])
                elif os.name == "nt":
                    os.startfile(out)
                else:
                    import subprocess; subprocess.Popen(["xdg-open", out])
            except Exception:
                pass

    # ------------------------------------------------------------ images
    def place_image(self, data, w_hint=None):
        try:
            pix = fitz.Pixmap(data); iw, ih = pix.width, pix.height
        except Exception:
            messagebox.showerror(APP, _("เปิดรูปภาพนี้ไม่ได้")); return
        key = "img%d" % (len(self.images) + 1)
        while key in self.images:
            key += "_"
        self.images[key] = data
        pr = self.page().rect
        w = min(w_hint or 220, pr.width * 0.6); h = w * ih / iw
        if h > pr.height * 0.6:
            h = pr.height * 0.6; w = h * iw / ih
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
        p = filedialog.askopenfilename(title=_("เลือกรูปภาพ"),
                                       filetypes=[(_("รูปภาพ"), "*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp"), (_("ทุกไฟล์"), "*.*")])
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

    # ------------------------------------------------------------ keyboard
    def on_key(self, e):
        if not self.has_doc():
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
            self.delete_obj(); return
        if k in ("Delete", "BackSpace") and self.pdfsel:
            self.delete_pdf_image(); return
        if k == "Escape":
            self.set_tool("select"); return
        if k == "Prior":
            self.goto(self.cur - 1); return
        if k == "Next":
            self.goto(self.cur + 1); return
        if k in ("Left", "Right", "Up", "Down"):
            o = self.sel_obj()
            if not o:
                self.goto(self.cur - 1 if k in ("Left", "Up") else self.cur + 1)
                return
            st = 10 if e.state & 0x1 else 1
            dx = {"Left": -st, "Right": st}.get(k, 0)
            dy = {"Up": -st, "Down": st}.get(k, 0)
            a = self.to_page(self.ox, self.oy); b = self.to_page(self.ox + dx, self.oy + dy)
            self.push_undo(); self._move(o, b[0] - a[0], b[1] - a[1]); self.refresh(); return
        mods = 0x4 | (0x18 if sys.platform == "darwin" else 0x8)
        if e.state & mods:
            return
        keymap = {sc.lower(): key for key, _l, sc, _d in TOOLS}
        if e.char and e.char.lower() in keymap:
            self.set_tool(keymap[e.char.lower()])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    app = PDFPro(path)
    app.mainloop()


if __name__ == "__main__":
    main()
