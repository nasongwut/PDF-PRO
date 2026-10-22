from pdfpro.core.fonts import fontbook, resolve_span_font


def test_bundled_fonts_available():
    names = [n for n, _thai, _kind in fontbook().choices()]
    assert names[:2] == ["TH Sarabun New", "Sarabun"]


def test_th_sarabun_is_matched_by_name(thai_pdf):
    page = thai_pdf[0]
    span = next(s for b in page.get_text("dict")["blocks"] for line in b.get("lines", []) for s in line["spans"])
    spec, note = resolve_span_font(thai_pdf, page, span, "ทดสอบใหม่ 12,000 บาท")
    assert spec["family"] == "TH Sarabun New" or spec["fontkey"]
    assert note


def test_latin_base14_maps_to_builtin(latin_pdf):
    page = latin_pdf[0]
    span = page.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]
    spec, _note = resolve_span_font(latin_pdf, page, span, "Total 12,500.00")
    assert spec["family"] == "Helvetica"
