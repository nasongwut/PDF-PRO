"""Undo / redo for the active document (snapshots are kept per document)."""


class HistoryMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def snapshot(self):
        return self.active.snapshot()

    def push_undo(self):
        self.active.push_undo()
        self.update_state()
        self.refresh_tabbar()

    def struct_changed(self):
        self.active.structure_changed()

    def _restore(self, snap):
        rebuild = self.active.restore(snap)
        if rebuild:
            self.build_thumbs()
        else:
            for i in range(len(self.objs)):
                self.update_thumb(i)
        self.render_view(keep_scroll=True)
        self.render_props()
        self.update_state()
        self.refresh_tabbar()

    def undo(self):
        if not self.has_doc() or not self.undo_stack or self.multi:
            return
        self.redo_stack.append(self.snapshot())
        self._restore(self.undo_stack.pop())

    def redo(self):
        if not self.has_doc() or not self.redo_stack or self.multi:
            return
        self.undo_stack.append(self.snapshot())
        self._restore(self.redo_stack.pop())
