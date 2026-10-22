"""Shared fixtures: small PDFs generated on the fly (no binary test files in the repo)."""

import os
import sys

import pymupdf as fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfpro.config import FONT_DIR  # noqa: E402


@pytest.fixture
def latin_pdf():
    d = fitz.open()
    for i in range(3):
        p = d.new_page()
        p.insert_text((72, 80), "Page %d — Total amount: 9,999.00" % (i + 1), fontsize=14, fontname="helv")
    return d


@pytest.fixture
def thai_pdf():
    d = fitz.open()
    p = d.new_page()
    arch = fitz.Archive(FONT_DIR)
    css = "@font-face{font-family:th;src:url(THSarabunNew.ttf);} body{font-family:th;font-size:16px}"
    p.insert_htmlbox(fitz.Rect(72, 72, 520, 120), "ส่วนราชการ กองคลัง โทร. 0 2123 4567", css=css, archive=arch)
    d.subset_fonts()
    return fitz.open("pdf", d.tobytes())
