"""Font discovery and resolution.

Bundled fonts, MuPDF built-in fonts, fonts installed on the computer (macOS / Windows / Linux),
fonts the user added to PDF PRO, and fonts embedded in the PDF being edited.
"""

import logging
import os
import re
import shutil
import struct
import sys
import threading

import pymupdf as fitz

from pdfpro.config import FONT_DIR, USER_FONT_DIR
from pdfpro.core.thai import TH_STYLE, has_thai
from pdfpro.i18n import _
from pdfpro.utils import norm_name

log = logging.getLogger(__name__)


BUNDLED = {
    "TH Sarabun New": {
        (0, 0): "THSarabunNew.ttf",
        (1, 0): "THSarabunNew-Bold.ttf",
        (0, 1): "THSarabunNew-Italic.ttf",
        (1, 1): "THSarabunNew-BoldItalic.ttf",
    },
    "Sarabun": {
        (0, 0): "Sarabun-Regular.ttf",
        (1, 0): "Sarabun-Bold.ttf",
        (0, 1): "Sarabun-Italic.ttf",
        (1, 1): "Sarabun-BoldItalic.ttf",
    },
}


BUILTIN = {  # PDF base-14 look-alikes shipped with MuPDF
    "Helvetica": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
    "Times": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
    "Courier": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
}


PREFERRED_SYSTEM = [
    "Tahoma",
    "Thonburi",
    "Leelawadee UI",
    "Leelawadee",
    "TH SarabunPSK",
    "TH Sarabun New",
    "Angsana New",
    "Cordia New",
    "Browallia New",
    "AngsanaUPC",
    "CordiaUPC",
    "Krungthep",
    "Silom",
    "Ayuthaya",
    "Sathu",
    "Sukhumvit Set",
    "Noto Sans Thai",
    "Noto Serif Thai",
    "Arial",
    "Helvetica Neue",
    "Times New Roman",
    "Georgia",
    "Verdana",
    "Calibri",
    "Cambria",
    "Segoe UI",
]


def _font_dirs():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        dirs = [
            "/System/Library/Fonts",
            "/System/Library/Fonts/Supplemental",
            "/Library/Fonts",
            os.path.join(home, "Library/Fonts"),
        ]
    elif os.name == "nt":
        win = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [
            os.path.join(win, "Fonts"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
        ]
    else:
        dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.join(home, ".fonts"),
            os.path.join(home, ".local/share/fonts"),
        ]
    return dirs + [USER_FONT_DIR]


def _read_names(path):
    """family / style / postscript / full name and Thai support of a TTF/OTF/TTC (first face)"""
    with open(path, "rb") as f:
        tag = f.read(4)
        off = 0
        if tag == b"ttcf":
            f.read(4)
            n = struct.unpack(">I", f.read(4))[0]
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
            t, _c, o, l = struct.unpack(">4sIII", recs[i * 16 : i * 16 + 16])
            tables[t] = (o, l)
        if b"name" not in tables:
            return None
        f.seek(tables[b"name"][0])
        data = f.read(tables[b"name"][1])
        thai = False
        if b"OS/2" in tables:
            f.seek(tables[b"OS/2"][0] + 42)
            r1 = f.read(4)
            if len(r1) == 4:
                thai = bool(struct.unpack(">I", r1)[0] & (1 << 10))
    fmt, count, so = struct.unpack(">HHH", data[:6])
    names = {}
    for i in range(count):
        pid, eid, lid, nid, ln, no = struct.unpack(">HHHHHH", data[6 + 12 * i : 18 + 12 * i])
        if nid not in (1, 2, 4, 6, 16, 17):
            continue
        raw = data[so + no : so + no + ln]
        try:
            if pid == 3 or pid == 0:
                s = raw.decode("utf-16-be")
                score = 3 if (pid == 3 and lid == 0x409) else 2
            elif pid == 1 and lid == 0:
                s = raw.decode("mac_roman")
                score = 1
            else:
                continue
        except Exception:
            continue
        if nid not in names or names[nid][1] < score:
            names[nid] = (s, score)

    def g(k):
        return names[k][0] if k in names else ""

    fam = g(16) or g(1)
    sty = g(17) or g(2)
    return fam, sty, g(6), g(4), thai


class SystemFonts:
    """index of fonts installed on this computer (+ fonts the user added to PDF PRO).
    Built in a background thread with pure python (no MuPDF calls)."""

    def __init__(self):
        self.families = {}  # norm family -> {"name", "faces": {(b,i): path}, "thai": bool, "user": bool}
        self.ps = {}  # norm postscript/full name -> (path, family, b, i)
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
            e = self.families.setdefault(norm_name(fam), {"name": fam, "faces": {}, "thai": False, "user": False})
            e["thai"] = e["thai"] or thai
            e["user"] = e["user"] or p.startswith(USER_FONT_DIR)
            if (b, it) not in e["faces"] or s in ("regular", "bold", "italic", "bold italic"):
                e["faces"][(b, it)] = p
            for n in (ps, full):
                if n:
                    self.ps.setdefault(norm_name(n), (p, fam, b, it))
        return fam

    def face(self, family, bold, italic):
        e = self.families.get(norm_name(family))
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
        self.reg = {}  # key -> {"buf", "file", "label"}
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
        base = (lh - (asc - desc)) / 2 + asc
        return lh, base

    def choices(self, thai_only=False):
        """[(family, supports_thai, kind)] — bundled, built-in, then every installed family A-Z"""
        out = [(f, True, "bundled") for f in BUNDLED] + [(f, False, "builtin") for f in BUILTIN]
        self.system.ready.wait(3.0)
        seen = {norm_name(f) for f, _t, _k in out}
        with self.system.lock:
            fams = sorted(self.system.families.values(), key=lambda e: e["name"].lower())
        for e in fams:
            if norm_name(e["name"]) in seen:
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


def resolve_span_font(doc, page, span, text, exact=True, bold=None, italic=None):
    """
    Find the best font to re-typeset `text` so it looks like the original span.
    Returns (spec dict, note)
    """
    fb = fontbook()
    base = span["font"].split("+", 1)[-1]
    nb = norm_name(base)
    if bold is None:
        bold = bool(span["flags"] & 16) or "bold" in nb or "black" in nb or "heavy" in nb
    if italic is None:
        italic = bool(span["flags"] & 2) or "italic" in nb or "oblique" in nb
    bold, italic = bool(bold), bool(italic)
    thstyle = any(k in nb for k in TH_STYLE)
    spec = dict(bold=bold, italic=italic, thstyle=thstyle, label=base, family=None, fontkey=None)
    # 1) the font embedded in the PDF (exact match) — if it contains every glyph we need
    try:
        for fi in page.get_fonts(full=True) if exact else []:
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
        log.warning("embedded font: %s", e)
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
                spec["fontkey"] = key
                spec["label"] = fam
                return spec, _("ใช้ฟอนต์ %s จากเครื่องนี้") % fam
        except Exception:
            pass
    # 3) closest family
    fam = None
    for name, keys in (
        ("TH Sarabun New", ("thsarabun", "sarabunpsk", "sarabunnew")),
        ("Sarabun", ("sarabun",)),
        ("Helvetica", ("helvetica", "arial", "liberationsans", "nimbussans")),
        ("Times", ("times", "liberationserif", "nimbusroman")),
        ("Courier", ("courier", "liberationmono", "nimbusmono")),
    ):
        if any(k in nb for k in keys):
            fam = name
            break
    if fam is None:
        famname = re.sub(
            r"[-,](bold|italic|regular|oblique|black|medium|light|semibold|bolditalic).*$", "", base, flags=re.I
        )
        if fb.system.families.get(norm_name(famname)):
            fam = fb.system.families[norm_name(famname)]["name"]
    if fam is None:
        if thstyle:
            fam = "TH Sarabun New"
        elif has_thai(text):
            fam = "Sarabun"
        else:
            fam = "Times" if span["flags"] & 4 else ("Courier" if span["flags"] & 8 else "Helvetica")
    spec["family"] = fam
    spec["label"] = fam
    same = (
        norm_name(fam) in nb
        or nb.startswith(norm_name(fam))
        or (fam == "Helvetica" and "helvetica" in nb)
        or (fam == "Times" and "times" in nb)
        or (fam == "Courier" and "courier" in nb)
    )
    if fam in ("Helvetica", "Times", "Courier") and has_thai(text):
        note = _("ฟอนต์เดิมไม่มีตัวอักษรไทย — ใช้ %s คู่กับ %s") % (fam, "TH Sarabun New" if thstyle else "Sarabun")
    elif same:
        note = _("ใช้ฟอนต์ %s (ตรงกับต้นฉบับ)") % fam
    else:
        note = _("ไม่พบฟอนต์ %s ในเครื่อง — ใช้ %s ที่ใกล้เคียงแทน") % (base, fam)
    return spec, note
