"""Start-up checks that must run before any third-party import."""

import sys

REQUIRED = (("pymupdf", "PyMuPDF"), ("customtkinter", "CustomTkinter"), ("PIL", "Pillow"))
MIN_PYTHON = (3, 9)


def missing_packages() -> list:
    out = []
    for module, name in REQUIRED:
        try:
            __import__(module)
        except ImportError:
            out.append(name)
    return out


def check_environment() -> None:
    """Show a friendly message (Thai + English) and exit when the environment is not usable."""
    problems = []
    if sys.version_info < MIN_PYTHON:
        problems.append("Python %d.%d+ required (found %s)" % (MIN_PYTHON + (sys.version.split()[0],)))
    try:
        import tkinter

        if tkinter.TkVersion < 8.6:
            problems.append("Tk 8.6+ required (found %s) — install Python from python.org" % tkinter.TkVersion)
    except ImportError:
        problems.append("tkinter is missing — install Python from python.org")
        _print_and_exit(problems)
    missing = missing_packages()
    if missing:
        problems.append("ยังไม่ได้ติดตั้ง / missing: %s\n\npip install pymupdf customtkinter pillow" % ", ".join(missing))
    if problems:
        _print_and_exit(problems)


def _print_and_exit(problems):
    msg = "\n\n".join(problems)
    print(msg, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("PDF PRO", msg)
    except Exception:
        pass
    sys.exit(1)
