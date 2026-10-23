"""PDF PRO — open, edit and print PDF files (Thai / English).

Package layout::

    pdfpro/
        config.py          paths and persistent user settings
        i18n.py            translation helper ``_`` (Thai source strings, English catalogue in locales/)
        utils.py           small shared helpers
        core/              document logic — no UI code, unit-tested
            fonts.py       font discovery / matching
            overlay.py     overlay objects and how they are burnt into pages
            thai.py        Thai text helpers
            printing.py    printer discovery and printing
        ui/                CustomTkinter user interface
            app.py         main window (composition of mixins)
            mixins/        window behaviour split by concern
            dialogs/       modal dialogs
            theme.py, icons.py, widgets.py, constants.py
"""

__all__ = ["APP_NAME", "APP_ID", "__version__", "REPO_URL", "UPDATE_URL", "DONATE_URL", "LICENSE_NAME"]

APP_NAME = "PDF PRO"
APP_ID = "com.nasongwut.pdfpro"
__version__ = "1.1.0"

#: project home — shown as credit in the app and in the installer
REPO_URL = "https://github.com/nasongwut/PDF-PRO"
#: update manifest (see ``server/``); can be overridden with the PDFPRO_UPDATE_URL environment variable
UPDATE_URL = "https://raw.githubusercontent.com/nasongwut/PDF-PRO/main/server/latest.json"
#: fallback donate page when the manifest has no "donate" entries
DONATE_URL = "https://github.com/sponsors/nasongwut"
LICENSE_NAME = "GNU AGPL-3.0 (free & open source)"
