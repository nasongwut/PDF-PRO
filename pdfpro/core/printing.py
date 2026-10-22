"""Printer discovery and sending PDF files to a printer (CUPS on macOS/Linux, shell verbs on Windows)."""

import os
import subprocess
import sys


def list_printers():
    """-> (names, default)  — CUPS on macOS/Linux, PowerShell/WMIC on Windows"""
    names, default = [], None
    try:
        if os.name == "nt":
            flags = 0x08000000  # CREATE_NO_WINDOW
            try:
                out = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        "Get-CimInstance Win32_Printer | ForEach-Object { $_.Name + '|' + $_.Default }",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    creationflags=flags,
                ).stdout
                for line in out.splitlines():
                    if "|" in line:
                        n, d = line.rsplit("|", 1)
                        names.append(n.strip())
                        if d.strip().lower() == "true":
                            default = n.strip()
            except Exception:
                pass
        else:
            out = subprocess.run(["lpstat", "-e"], capture_output=True, text=True, timeout=5).stdout
            names = [l.strip() for l in out.splitlines() if l.strip()]
            d = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=5).stdout
            if ":" in d:
                default = d.split(":", 1)[1].strip() or None
    except Exception:
        pass
    return names, default


def send_to_printer(path: str, printer=None, copies: int = 1, system_dialog: bool = False) -> None:
    """Print a PDF file.

    * ``system_dialog``: show the operating system's print dialog (macOS: Preview, Windows: default PDF app).
    * otherwise print directly: ``lp`` on macOS/Linux, the ``printto``/``print`` shell verb on Windows.
    Raises ``RuntimeError`` when printing fails.
    """
    if system_dialog:
        if sys.platform == "darwin":
            p = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "Preview" to activate',
                    "-e",
                    'tell application "Preview" to print (POSIX file "%s") with print dialog' % path,
                ],
                capture_output=True,
                timeout=60,
            )
            if p.returncode != 0:
                subprocess.Popen(["open", "-a", "Preview", path])
        elif os.name == "nt":
            try:
                os.startfile(path, "print")
            except OSError:
                os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return
    if os.name == "nt":
        for _i in range(max(1, copies)):
            try:
                os.startfile(path, "printto", '"%s"' % printer) if printer else os.startfile(path, "print")
            except (OSError, TypeError):  # TypeError: Python < 3.10 has no `arguments`
                os.startfile(path, "print")
        return
    cmd = ["lp", "-n", str(max(1, copies))]
    if printer:
        cmd += ["-d", printer]
    p = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "lp failed")
