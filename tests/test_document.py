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
