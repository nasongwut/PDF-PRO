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
        self.suggested_name = ""  # default file name when a new document is saved

    # ------------------------------------------------------------------ info
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def name(self) -> str:
        return os.path.basename(self.path) if self.path else ""

    @property
    def title(self) -> str:
        """file name, or the suggested name of a new document (empty when unknown)"""
        return self.name or self.suggested_name

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


def transfer_pages(src: Document, indices, dst: Document, position: int, copy_pages: bool = False) -> list:
    """Move (or copy) several pages of ``src`` to ``position`` in ``dst``, keeping their order.

    Works inside one document (reorder / duplicate a block) and between documents. Overlay objects
    travel with the pages. Returns the new indices of the pages in ``dst``. No undo snapshots are taken.
    """
    pages = sorted(set(i for i in indices if 0 <= i < src.page_count))
    if not pages:
        return []
    position = max(0, min(position, dst.page_count))
    if src is dst:
        n = src.page_count
        if copy_pages:
            order = list(range(position)) + pages + list(range(position, n))
            first = position
        else:
            rest = [p for p in range(n) if p not in pages]
            first = position - sum(1 for p in pages if p < position)
            order = rest[:first] + pages + rest[first:]
        if order == list(range(n)):
            return pages
        objs = [copy.deepcopy(src.objs[i]) for i in order]
        src.doc.select(order)
        src.objs = objs
        src.structure_changed()
        return list(range(first, first + len(pages)))
    for k, i in enumerate(pages):
        dst.doc.insert_pdf(src.doc, from_page=i, to_page=i, start_at=position + k)
        dst.objs.insert(position + k, copy.deepcopy(src.objs[i]))
    dst.structure_changed()
    if not copy_pages:
        for i in reversed(pages):
            src.doc.delete_page(i)
            src.objs.pop(i)
        src.cur = max(0, min(src.cur, src.page_count - 1))
        src.structure_changed()
    return list(range(position, position + len(pages)))


def extract_pages(src: Document, indices, remove: bool = False) -> Document:
    """New in-memory :class:`Document` made of ``indices`` of ``src`` (optionally removed from ``src``)."""
    pages = sorted(set(i for i in indices if 0 <= i < src.page_count))
    new = Document(fitz.open(), None)
    new.objs = []
    transfer_pages(src, pages, new, 0, copy_pages=not remove)
    base = os.path.splitext(src.title or "document")[0]
    new.suggested_name = "%s-%s.pdf" % (base, page_range_label(pages))
    new.dirty = True
    return new


def page_range_label(pages) -> str:
    """[9, 10, 11, 14] -> 'p10-12,15'"""
    out, start, prev = [], None, None
    for p in sorted(pages):
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(str(start + 1) if start == prev else "%d-%d" % (start + 1, prev + 1))
            start = prev = p
    if start is not None:
        out.append(str(start + 1) if start == prev else "%d-%d" % (start + 1, prev + 1))
    return "p" + ",".join(out)


def parse_page_ranges(text: str, page_count: int) -> list:
    """'10-20, 3' -> [2, 9, 10, …, 19] (0-based, sorted, unique). Raises ValueError on bad input."""
    pages = set()
    for part in text.replace(" ", "").replace("–", "-").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a else 1
            b = int(b) if b else page_count
            if a > b:
                a, b = b, a
            pages.update(range(max(1, a), min(page_count, b) + 1))
        else:
            v = int(part)
            if 1 <= v <= page_count:
                pages.add(v)
    if not pages:
        raise ValueError("no pages")
    return sorted(p - 1 for p in pages)


def duplicate_pages(doc: Document, indices) -> list:
    """insert copies of ``indices`` right after the last of them; returns the new indices"""
    pages = sorted(set(i for i in indices if 0 <= i < doc.page_count))
    if not pages:
        return []
    return transfer_pages(doc, pages, doc, pages[-1] + 1, copy_pages=True)


def delete_pages(doc: Document, indices) -> int:
    """delete ``indices`` (at least one page always remains); returns how many were deleted"""
    pages = set(i for i in indices if 0 <= i < doc.page_count)
    keep = [i for i in range(doc.page_count) if i not in pages]
    if not pages or not keep:
        return 0
    doc.objs = [doc.objs[i] for i in keep]
    doc.doc.select(keep)
    doc.cur = max(0, min(doc.cur, doc.page_count - 1))
    doc.sel = None
    doc.structure_changed()
    return len(pages)


def rotate_pages(doc: Document, indices, degrees: int) -> None:
    for i in set(indices):
        if 0 <= i < doc.page_count:
            p = doc.doc[i]
            p.set_rotation((p.rotation + degrees) % 360)
    doc.structure_changed()
