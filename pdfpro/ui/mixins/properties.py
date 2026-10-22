"""Right-hand properties panel."""

import customtkinter as ctk

from pdfpro.core.fonts import fontbook
from pdfpro.i18n import _
from pdfpro.ui.constants import HINTS, TOOL_TITLE, TYPE_NAME, orig_prefix
from pdfpro.ui.icons import ICONS, icon
from pdfpro.ui.theme import ACCENT, ACCENT_H, BORDER, CARD, HL_SWATCHES, HOVER, MUTED, PANEL, SOFT, SWATCHES, TEXT, F
from pdfpro.ui.widgets import ColorRow, font_button, primary_btn, secondary_btn


class PropertiesMixin:
    """Mixin for :class:`pdfpro.ui.app.PDFProApp`."""

    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkLabel(f, text=title, font=F(12), text_color=MUTED).pack(anchor="w", pady=(0, 6))
        return f

    def _apply(self, fn, live=False):
        """apply a property change to the selected object (one undo step per gesture)"""
        o = self.sel_obj()
        if not o:
            return
        if not self._prop_armed:
            self.push_undo()
        self._prop_armed = live
        fn(o)
        if live:
            if self._prop_job:
                self.after_cancel(self._prop_job)
            self._prop_job = self.after(120, self._live_refresh)
        else:
            self.refresh()

    def _live_refresh(self):
        self._prop_job = None
        self.render_view(keep_scroll=True)
        self.update_thumb(self.cur)

    def render_props(self):
        if not hasattr(self, "props"):
            return
        for w in self.props_in.winfo_children():
            w.destroy()
        self._prop_armed = False
        if self.pdfsel and self.has_doc():
            self._render_pdfimg_props()
            return
        o = self.sel_obj()
        kind = o["type"] if o else {"edittext": "text"}.get(self.tool, self.tool)
        head = ctk.CTkFrame(self.props_in, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(18, 16))
        ic = {"redact": "edittext", "image": "image"}.get(kind, kind)
        if ic in ICONS:
            badge = ctk.CTkFrame(head, fg_color=SOFT, corner_radius=10, width=38, height=38)
            badge.pack(side="left")
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text="", image=icon(ic, 19, ACCENT)).pack(expand=True)
        tt = ctk.CTkFrame(head, fg_color="transparent")
        tt.pack(side="left", padx=10)
        ctk.CTkLabel(
            tt,
            text=_(TYPE_NAME.get(kind, "")) if o else _(TOOL_TITLE.get(self.tool, "")),
            font=F(15, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(tt, text=_("วัตถุที่เลือก") if o else _("เครื่องมือ"), font=F(12), text_color=MUTED, anchor="w").pack(
            anchor="w"
        )

        if kind == "text":
            sec = self._section(self.props_in, _("สีตัวอักษร"))

            def setc(c):
                self.text_color = c
                self._apply(lambda x: x.__setitem__("color", c))

            ColorRow(sec, SWATCHES[:6], o["color"] if o else self.text_color, setc).pack(anchor="w")
            sec = self._section(self.props_in, _("ขนาดตัวอักษร (pt)"))
            row = ctk.CTkFrame(sec, fg_color="transparent")
            row.pack(fill="x")
            sv = ctk.StringVar(value="%g" % round(o["size"] if o else self.fsize, 1))

            def setsize(v):
                try:
                    v = max(4.0, min(300.0, float(v)))
                except ValueError:
                    return
                sv.set("%g" % v)
                self.fsize = v
                if o:
                    self._apply(lambda x: self._resize_text(x, v))

            ctk.CTkButton(
                row,
                text="−",
                width=34,
                height=32,
                corner_radius=8,
                fg_color=CARD,
                hover_color=HOVER,
                text_color=TEXT,
                font=F(16),
                command=lambda: setsize(float(sv.get() or 16) - 1),
            ).pack(side="left")
            e = ctk.CTkEntry(
                row,
                textvariable=sv,
                width=70,
                height=32,
                corner_radius=8,
                justify="center",
                border_color=BORDER,
                fg_color=CARD,
                font=F(14),
            )
            e.pack(side="left", padx=6)
            e.bind("<Return>", lambda ev: setsize(sv.get()))
            ctk.CTkButton(
                row,
                text="+",
                width=34,
                height=32,
                corner_radius=8,
                fg_color=CARD,
                hover_color=HOVER,
                text_color=TEXT,
                font=F(16),
                command=lambda: setsize(float(sv.get() or 16) + 1),
            ).pack(side="left")
            sec = self._section(self.props_in, _("ฟอนต์"))
            orig = o.get("orig") if o else None
            olabel = (orig_prefix() + orig["font"].split("+", 1)[-1]) if orig else None
            curf = (
                olabel if (o and o.get("from_orig") and olabel) else (o.get("family") if o else self.ffamily)
            ) or "Sarabun"
            fv = ctk.StringVar(value=curf)

            def setfont(v):
                if o:
                    self._apply(
                        lambda x: self._restyle(
                            x, original=v.startswith(orig_prefix()), family=None if v.startswith(orig_prefix()) else v
                        )
                    )
                else:
                    self.ffamily = v

            font_button(
                sec, fv, original=orig["font"].split("+", 1)[-1] if orig else None, on_change=setfont, width=230
            ).pack(anchor="w")
            if o:
                bv = ctk.BooleanVar(value=bool(o.get("bold")))
                iv = ctk.BooleanVar(value=bool(o.get("italic")))
                sec = self._section(self.props_in, _("รูปแบบ"))
                sw = ctk.CTkFrame(sec, fg_color="transparent")
                sw.pack(anchor="w")
                ctk.CTkSwitch(
                    sw,
                    text=_("ตัวหนา"),
                    variable=bv,
                    progress_color=ACCENT,
                    font=F(13),
                    text_color=TEXT,
                    width=100,
                    command=lambda: self._apply(lambda x: self._restyle(x, bold=bv.get())),
                ).pack(side="left")
                ctk.CTkSwitch(
                    sw,
                    text=_("ตัวเอียง"),
                    variable=iv,
                    progress_color=ACCENT,
                    font=F(13),
                    text_color=TEXT,
                    width=100,
                    command=lambda: self._apply(lambda x: self._restyle(x, italic=iv.get())),
                ).pack(side="left")
                if orig:
                    ctk.CTkLabel(
                        sec,
                        text=_("ฟอนต์ที่ใช้จริง: ") + fontbook().reg.get(fontbook().key_for(o)[0], {}).get("label", ""),
                        font=F(11),
                        text_color=MUTED,
                        wraplength=220,
                        justify="left",
                    ).pack(anchor="w", pady=(6, 0))
                primary_btn(
                    self._section(self.props_in, _("เนื้อหา")),
                    _("แก้ไขข้อความ"),
                    lambda: self.edit_text_obj(self.sel),
                    "edit",
                    height=34,
                ).pack(fill="x")

        if kind in ("ink", "line", "arrow", "rect"):
            sec = self._section(self.props_in, _("สีเส้นขอบ") if kind == "rect" else _("สี"))

            def setc(c):
                self.color = c
                self._apply(lambda x: x.__setitem__("color", c))

            ColorRow(sec, SWATCHES[:6], o["color"] if o else self.color, setc).pack(anchor="w")
            val = o["width"] if o else self.stroke
            sec = self._section(self.props_in, _("ความหนาเส้น"))
            row = ctk.CTkFrame(sec, fg_color="transparent")
            row.pack(fill="x")
            lbl = ctk.CTkLabel(row, text="%g pt" % val, width=48, font=F(13), text_color=TEXT)

            def setw(v):
                v = round(float(v) * 2) / 2
                lbl.configure(text="%g pt" % v)
                self.stroke = v
                self._apply(lambda x: x.__setitem__("width", v), live=True)

            sl = ctk.CTkSlider(
                row,
                from_=0.5,
                to=20,
                number_of_steps=39,
                command=setw,
                width=170,
                progress_color=ACCENT,
                button_color=ACCENT,
                button_hover_color=ACCENT_H,
            )
            sl.set(val)
            sl.pack(side="left")
            lbl.pack(side="left", padx=(8, 0))
        if kind == "rect":
            sec = self._section(self.props_in, _("สีพื้น"))

            def setf(c):
                self.fill = c
                self._apply(lambda x: x.__setitem__("fill", c))

            ColorRow(sec, SWATCHES[:5], o.get("fill") if o else self.fill, setf, allow_none=True).pack(anchor="w")
        if kind == "highlight":
            sec = self._section(self.props_in, _("สีไฮไลต์"))

            def seth(c):
                self.hl_color = c
                self._apply(lambda x: x.__setitem__("color", c))

            ColorRow(sec, HL_SWATCHES, o["color"] if o else self.hl_color, seth).pack(anchor="w")
        if kind == "whiteout" and o:
            sec = self._section(self.props_in, _("สีที่ใช้ปิดทับ"))
            ColorRow(
                sec,
                ["#ffffff", "#f3f4f6", "#fef9c3", "#111827"],
                o.get("fill", "#ffffff"),
                lambda c: self._apply(lambda x: x.__setitem__("fill", c)),
            ).pack(anchor="w")

        if o:
            sec = self._section(self.props_in, _("การจัดการ"))
            grid = ctk.CTkFrame(sec, fg_color="transparent")
            grid.pack(fill="x")
            for i, (ic2, t, cmd) in enumerate(
                (
                    ("copy", _("ทำสำเนา"), self.duplicate_obj),
                    ("front", _("ไว้หน้าสุด"), lambda: self.order_obj(True)),
                    ("back", _("ไว้หลังสุด"), lambda: self.order_obj(False)),
                )
            ):
                secondary_btn(grid, t, cmd, ic2, height=34, width=102).grid(
                    row=i // 2, column=i % 2, padx=(0, 6), pady=3, sticky="ew"
                )
            ctk.CTkButton(
                grid,
                text=_("ลบ"),
                image=icon("trash", 17, (ACCENT, "#ff6b70")),
                command=self.delete_obj,
                fg_color=PANEL,
                hover_color=SOFT,
                text_color=(ACCENT, "#ff6b70"),
                border_width=1,
                border_color=BORDER,
                corner_radius=10,
                height=34,
                width=102,
                font=F(13),
            ).grid(row=1, column=1, padx=(0, 6), pady=3, sticky="ew")

        if not o and self.tool == "select" and self.has_doc():
            n_page = len(self.page_images(self.cur))
            n_all = len({x for i in range(self.doc.page_count) for x in self.page_xrefs(i)})
            sec = self._section(self.props_in, _("รูปภาพในเอกสาร"))
            ctk.CTkLabel(
                sec,
                text=_("หน้านี้ %d รูป · ทั้งไฟล์ %d รูป\nคลิกที่รูปในหน้าเพื่อเลือก ลบ หรือแทนที่") % (n_page, n_all),
                font=F(12),
                text_color=MUTED,
                justify="left",
                anchor="w",
                wraplength=210,
            ).pack(anchor="w", pady=(0, 8))
            b = secondary_btn(sec, _("ส่งออกรูปทั้งหมด…"), self.export_all_images, "export", height=34)
            b.pack(fill="x")
            if not n_all:
                b.configure(state="disabled")

        # hint card
        card = ctk.CTkFrame(self.props_in, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkLabel(card, text=_("💡 วิธีใช้"), font=F(12, "bold"), text_color=TEXT).pack(
            anchor="w", padx=14, pady=(12, 2)
        )
        ctk.CTkLabel(
            card,
            text=_(HINTS["select" if o else self.tool]),
            font=F(12),
            text_color=MUTED,
            wraplength=196,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(0, 12))
