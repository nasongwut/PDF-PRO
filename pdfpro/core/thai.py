"""Thai text helpers: repair text extracted from PDFs, detect Thai script and Thai-style font names."""

import re

_THAI_PUA = {
    0xF700: "\u0e10",
    0xF701: "\u0e34",
    0xF702: "\u0e35",
    0xF703: "\u0e36",
    0xF704: "\u0e37",
    0xF705: "\u0e48",
    0xF706: "\u0e49",
    0xF707: "\u0e4a",
    0xF708: "\u0e4b",
    0xF709: "\u0e4c",
    0xF70A: "\u0e48",
    0xF70B: "\u0e49",
    0xF70C: "\u0e4a",
    0xF70D: "\u0e4b",
    0xF70E: "\u0e4c",
    0xF70F: "\u0e0d",
    0xF710: "\u0e31",
    0xF711: "\u0e4d",
    0xF712: "\u0e47",
    0xF713: "\u0e48",
    0xF714: "\u0e49",
    0xF715: "\u0e4a",
    0xF716: "\u0e4b",
    0xF717: "\u0e4c",
    0xF718: "\u0e38",
    0xF719: "\u0e39",
    0xF71A: "\u0e3a",
}


def normalize_thai(s):
    """fix text extracted from Thai PDFs (private-use mark glyphs, split SARA AM)"""
    s = s.translate(_THAI_PUA)
    s = re.sub("\u0e4d\u0e32", "\u0e33", s)  # ํ + า  -> ำ
    s = re.sub("([\u0e48-\u0e4b])\u0e4d\u0e32", "\\1\u0e33", s)
    return s


def has_thai(s):
    return any("\u0e00" <= c <= "\u0e7f" for c in s)


TH_STYLE = (
    "thsarabun",
    "sarabunpsk",
    "angsana",
    "cordia",
    "browallia",
    "eucrosia",
    "freesia",
    "iris",
    "jasmine",
    "kodchiang",
    "lily",
    "thniramit",
    "thkodchasal",
    "thchakra",
    "thbaijam",
    "thcharmof",
    "thkrub",
    "thmaliwan",
    "thsrisakdi",
    "thfahkwang",
    "thk2d",
    "thmali",
    "thchamornman",
    "thniramitas",
)
