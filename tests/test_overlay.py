import pymupdf as fitz

from pdfpro.core.overlay import apply_objects, obj_bbox, render_page, text_size


def _text(text, family="Sarabun", size=16):
    o = dict(type="text", text=text, size=size, color="#111827", family=family, bold=False, italic=False)
    w, h, _base = text_size(o)
    o["rect"] = [72, 200, 72 + w, 200 + h]
    o["rot"] = 0
    return o


def test_text_object_is_written_and_searchable(latin_pdf):
    page = latin_pdf[0]
    apply_objects(page, [_text("สวัสดีครับ ทดสอบ")], {})
    assert "สวัสดี" in page.get_text()


def test_redaction_removes_original_text(latin_pdf):
    page = latin_pdf[0]
    hit = page.search_for("Total amount")[0]
    apply_objects(page, [dict(type="redact", rect=list(hit))], {})
    assert "Total amount" not in page.get_text()


def test_shapes_and_bbox(latin_pdf):
    objs = [
        dict(type="rect", rect=[10, 10, 100, 60], color="#ff0000", width=2, fill=None),
        dict(type="line", p1=(10, 10), p2=(100, 100), color="#000000", width=3),
        dict(type="ink", pts=[(5, 5), (20, 30), (40, 10)], color="#2563eb", width=2),
    ]
    apply_objects(latin_pdf[1], objs, {})
    assert obj_bbox(objs[0]) == fitz.Rect(10, 10, 100, 60)
    assert obj_bbox(objs[2]).contains(fitz.Point(20, 30))


def test_render_page_does_not_modify_document(latin_pdf):
    before = latin_pdf[0].get_text()
    pix = render_page(latin_pdf, [_text("ทดสอบ")], {}, 0, 0.5)
    assert pix.width > 0
    assert latin_pdf[0].get_text() == before
