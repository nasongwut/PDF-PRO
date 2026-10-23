import pymupdf as fitz

from pdfpro.core.document import Document, transfer_page


def _doc(n, tag):
    d = fitz.open()
    for i in range(n):
        d.new_page().insert_text((72, 72), "%s%d" % (tag, i + 1))
    return Document(d)


def _texts(doc):
    return [doc.doc[i].get_text().strip() for i in range(doc.page_count)]


def test_reorder_within_document():
    a = _doc(3, "A")
    transfer_page(a, 0, a, 3)
    assert _texts(a) == ["A2", "A3", "A1"]


def test_move_between_documents_keeps_overlays():
    a, b = _doc(2, "A"), _doc(1, "B")
    a.objs[1].append({"type": "rect", "rect": [0, 0, 10, 10], "color": "#000000", "width": 1})
    pos = transfer_page(a, 1, b, 0)
    assert pos == 0
    assert _texts(a) == ["A1"] and _texts(b) == ["A2", "B1"]
    assert b.objs[0] and not any(a.objs)


def test_copy_between_documents():
    a, b = _doc(1, "A"), _doc(1, "B")
    transfer_page(a, 0, b, 1, copy_page=True)
    assert _texts(a) == ["A1"] and _texts(b) == ["B1", "A1"]


def test_undo_restores_structure():
    a = _doc(2, "A")
    a.push_undo()
    a.doc.delete_page(0)
    a.objs.pop(0)
    a.structure_changed()
    assert a.restore(a.undo_stack.pop())
    assert _texts(a) == ["A1", "A2"]


def test_transfer_block_between_documents():
    from pdfpro.core.document import transfer_pages

    a, b = _doc(5, "A"), _doc(1, "B")
    new = transfer_pages(a, [3, 1, 2], b, 1)
    assert new == [1, 2, 3]
    assert _texts(b) == ["B1", "A2", "A3", "A4"] and _texts(a) == ["A1", "A5"]


def test_reorder_block_within_document():
    from pdfpro.core.document import transfer_pages

    a = _doc(6, "A")
    assert transfer_pages(a, [0, 1], a, 4) == [2, 3]
    assert _texts(a) == ["A3", "A4", "A1", "A2", "A5", "A6"]
    transfer_pages(a, [0], a, 6, copy_pages=True)
    assert _texts(a)[-1] == "A3" and a.page_count == 7 and len(a.objs) == 7


def test_extract_pages_as_new_document():
    from pdfpro.core.document import extract_pages, parse_page_ranges

    a = _doc(20, "A")
    a.path = "/tmp/report.pdf"
    pages = parse_page_ranges("10-20", a.page_count)
    new = extract_pages(a, pages, remove=True)
    assert new.page_count == 11 and _texts(new)[0] == "A10" and a.page_count == 9
    assert new.suggested_name == "report-p10-20.pdf" and new.dirty


def test_parse_page_ranges():
    from pdfpro.core.document import page_range_label, parse_page_ranges

    assert parse_page_ranges("3, 1-2, 9-", 10) == [0, 1, 2, 8, 9]
    assert page_range_label([0, 1, 2, 5]) == "p1-3,6"


def test_duplicate_delete_rotate():
    from pdfpro.core.document import delete_pages, duplicate_pages, rotate_pages

    a = _doc(4, "A")
    assert duplicate_pages(a, [1, 2]) == [3, 4]
    assert _texts(a) == ["A1", "A2", "A3", "A2", "A3", "A4"]
    assert delete_pages(a, [0, 5]) == 2
    assert _texts(a) == ["A2", "A3", "A2", "A3"] and len(a.objs) == 4
    assert delete_pages(a, range(4)) == 0  # never delete every page
    rotate_pages(a, [0], 90)
    assert a.doc[0].rotation == 90
