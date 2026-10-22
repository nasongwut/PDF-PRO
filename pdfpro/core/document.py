"""State of one open document (one tab) and operations that move pages between documents."""

import copy
import os
from typing import Optional

import pymupdf as fitz

MAX_UNDO = 60


class Document:
    """Everything that belongs to one open PDF: the PyMuPDF document, overlay objects per page,
    undo/redo history and view state.

    Overlay objects (``objs[page]``) are plain dicts, see :mod:`pdfpro.core.overlay`.
    """

    def __init__(self, doc: fitz.Document, path: Optional[str] = None):
        self.doc = doc
        self.path = path
        self.objs: list = [[] for _n in range(doc.page_count)]
        self.cur = 0  # current page index
        self.zoom = 1.0
        self.undo_stack: list = []
        self.redo_stack: list = []
        self.docbytes: Optional[bytes] = None  # cached serialisation of `doc` for undo snapshots
        self.dirty = False
        self.saved_once = False
        self.sel: Optional[int] = None  # selected overlay object index on the current page
        self.pdfsel: Optional[dict] = None  # selected image that is part of the PDF
        self.scroll = (0.0, 0.0)
        self.fitted = False

    # ------------------------------------------------------------------ info
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def name(self) -> str:
        return os.path.basename(self.path) if self.path else ""

    # ------------------------------------------------------------------ history
    def snapshot(self):
        if self.docbytes is None:
            self.docbytes = self.doc.tobytes()
        return (self.docbytes, copy.deepcopy(self.objs), self.cur)

    def push_undo(self) -> None:
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def structure_changed(self) -> None:
        """call after changing the PyMuPDF document itself (pages, images…)"""
        self.docbytes = None

    def restore(self, snap) -> bool:
        """apply a snapshot; returns True when the page structure changed"""
        data, objs, cur = snap
        rebuild = data is not self.docbytes or len(objs) != len(self.objs)
        if data is not self.docbytes:
            self.doc = fitz.open("pdf", data)
            self.docbytes = data
        self.objs = objs
        self.cur = min(cur, self.doc.page_count - 1)
        self.sel = None
        self.pdfsel = None
        self.dirty = True
        return rebuild


def transfer_page(src: Document, index: int, dst: Document, position: int, copy_page: bool = False) -> int:
    """Move (or copy) page ``index`` of ``src`` to ``position`` in ``dst``.

    Works inside one document (reorder) and between documents. Overlay objects travel with the page.
    Returns the final index of the page in ``dst``. The caller is responsible for undo snapshots.
    """
    position = max(0, min(position, dst.page_count))
    if src is dst:
        if copy_page:
            src.doc.fullcopy_page(index, position if position < src.page_count else -1)
            src.objs.insert(position, copy.deepcopy(src.objs[index]))
            src.structure_changed()
            return position
        if position in (index, index + 1):
            return index
        src.doc.move_page(index, position if position < src.page_count else -1)
        objs = src.objs.pop(index)
        new = position - 1 if position > index else position
        src.objs.insert(new, objs)
        src.structure_changed()
        return new
    dst.doc.insert_pdf(src.doc, from_page=index, to_page=index, start_at=position)
    dst.objs.insert(position, copy.deepcopy(src.objs[index]))
    dst.structure_changed()
    if not copy_page:
        src.doc.delete_page(index)
        src.objs.pop(index)
        src.cur = min(src.cur, src.page_count - 1)
        src.structure_changed()
    return position
