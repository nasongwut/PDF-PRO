"""Behaviour of the main window, split by concern. Each mixin expects to be combined in
:class:`pdfpro.ui.app.PDFProApp` and may use attributes / methods defined by the others."""

from .editing import EditingMixin
from .files import FilesMixin
from .history import HistoryMixin
from .home import HomeMixin
from .images import ImagesMixin
from .pages import PagesMixin
from .properties import PropertiesMixin
from .text import TextMixin
from .viewer import ViewerMixin

__all__ = [
    "EditingMixin",
    "FilesMixin",
    "HistoryMixin",
    "HomeMixin",
    "ImagesMixin",
    "PagesMixin",
    "PropertiesMixin",
    "TextMixin",
    "ViewerMixin",
]
