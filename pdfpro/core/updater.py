"""Check for new versions and install them.

The update *manifest* is a small JSON file (see ``server/latest.json``)::

    {
      "version": "2.1.0",
      "released": "2026-10-22",
      "notes": {"th": "...", "en": "..."},
      "downloads": {
        "windows":   {"url": ".../PDF-PRO-2.1.0-windows-setup.exe", "sha256": "..."},
        "mac-arm64": {"url": ".../PDF-PRO-2.1.0-mac-arm64.dmg",      "sha256": "..."},
        "mac-x64":   {"url": ".../PDF-PRO-2.1.0-mac-x64.dmg",        "sha256": "..."},
        "source":    {"url": ".../v2.1.0.zip",                       "sha256": ""}
      },
      "donate": [{"label": "GitHub Sponsors", "url": "..."}]
    }

Three ways of running PDF PRO are supported:

* **Windows installer build** – download ``setup.exe`` and run it silently; it closes and relaunches the app.
* **macOS app build** – download the ``.dmg``, a helper script replaces the ``.app`` and relaunches it.
* **from source** (``pdf_pro.py`` + launcher) – download the source zip and copy the new files over.

Nothing here touches the UI; callbacks report progress.
"""

import hashlib
import json
import logging
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Optional

from pdfpro import UPDATE_URL, __version__

log = logging.getLogger(__name__)

TIMEOUT = 15
USER_AGENT = "PDF-PRO/%s (%s)" % (__version__, platform.platform(terse=True))
#: files and folders replaced when updating a source install
SOURCE_ITEMS = (
    "pdfpro",
    "pdf_pro.py",
    "requirements.txt",
    "README.txt",
    "README.md",
    "LICENSE",
    "เปิด PDF PRO.command",
    "เปิด PDF PRO (Windows).bat",
)


# ---------------------------------------------------------------------- versions
def parse_version(v: str) -> tuple:
    """'2.10.1-beta' -> (2, 10, 1)"""
    nums = re.findall(r"\d+", str(v).split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


# ---------------------------------------------------------------------- environment
def install_kind() -> str:
    """'windows' / 'mac' for packaged builds, 'source' when running pdf_pro.py"""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return "mac"
        if os.name == "nt":
            return "windows"
    return "source"


def platform_key() -> str:
    """key in manifest['downloads'] for this computer"""
    kind = install_kind()
    if kind == "mac":
        return "mac-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "mac-x64"
    return kind


def manifest_url() -> str:
    return os.environ.get("PDFPRO_UPDATE_URL") or UPDATE_URL


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # certifi missing: fall back to the system store
        return ssl.create_default_context()


def _open(url: str, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    if url.startswith("file:"):
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


# ---------------------------------------------------------------------- manifest
@dataclass
class UpdateInfo:
    version: str
    notes: dict = field(default_factory=dict)
    released: str = ""
    url: str = ""
    sha256: str = ""
    page: str = ""
    raw: dict = field(default_factory=dict)

    def notes_for(self, lang: str) -> str:
        if isinstance(self.notes, str):
            return self.notes
        return self.notes.get(lang) or self.notes.get("en") or self.notes.get("th") or ""


def fetch_manifest(url: Optional[str] = None) -> dict:
    with _open(url or manifest_url()) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not isinstance(data, dict) or "version" not in data:
        raise ValueError("invalid update manifest")
    return data


def parse_manifest(data: dict, current: str = __version__, key: Optional[str] = None) -> Optional[UpdateInfo]:
    """UpdateInfo when the manifest offers a newer version that has a download for this platform"""
    version = str(data.get("version", ""))
    if not is_newer(version, current):
        return None
    downloads = data.get("downloads") or {}
    entry = downloads.get(key or platform_key()) or {}
    if not entry.get("url"):
        return None
    return UpdateInfo(
        version=version,
        notes=data.get("notes") or {},
        released=str(data.get("released", "")),
        url=entry["url"],
        sha256=(entry.get("sha256") or "").lower(),
        page=data.get("page") or data.get("homepage") or "",
        raw=data,
    )


def check_for_update(url: Optional[str] = None, current: str = __version__) -> Optional[UpdateInfo]:
    """network call — run it in a background thread"""
    return parse_manifest(fetch_manifest(url), current)


def donate_links(manifest: Optional[dict], fallback: str) -> list:
    links = (manifest or {}).get("donate") or []
    links = [d for d in links if isinstance(d, dict) and d.get("url")]
    return links or [{"label": "Donate", "url": fallback}]


# ---------------------------------------------------------------------- download
def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(
    url: str,
    dest_dir: Optional[str] = None,
    sha256: str = "",
    progress: Optional[Callable[[int, int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> str:
    """download to a temp folder, verify the checksum when given; returns the file path"""
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="pdfpro-update-")
    name = os.path.basename(url.split("?")[0]) or "update.bin"
    path = os.path.join(dest_dir, name)
    with _open(url, timeout=60) as r, open(path, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancelled and cancelled():
                raise InterruptedError("cancelled")
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if sha256 and sha256_of(path) != sha256.lower():
        os.remove(path)
        raise ValueError("checksum mismatch — the download is damaged, please try again")
    return path


# ---------------------------------------------------------------------- install
def app_root() -> str:
    """folder that contains pdf_pro.py (source installs)"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def install_source_zip(zip_path: str, root: Optional[str] = None) -> None:
    """replace the program files of a source install with the ones from a GitHub source zip"""
    root = root or app_root()
    tmp = tempfile.mkdtemp(prefix="pdfpro-src-")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    # GitHub zips contain one top folder (PDF-PRO-2.1.0/)
    entries = [os.path.join(tmp, e) for e in os.listdir(tmp)]
    src = entries[0] if len(entries) == 1 and os.path.isdir(entries[0]) else tmp
    if not os.path.isfile(os.path.join(src, "pdf_pro.py")):
        raise ValueError("the downloaded archive is not a PDF PRO source package")
    for item in SOURCE_ITEMS:
        s, d = os.path.join(src, item), os.path.join(root, item)
        if not os.path.exists(s):
            continue
        if os.path.isdir(s):
            backup = d + ".old"
            if os.path.exists(backup):
                shutil.rmtree(backup, ignore_errors=True)
            if os.path.exists(d):
                os.replace(d, backup)
            shutil.copytree(s, d)
            shutil.rmtree(backup, ignore_errors=True)
        else:
            shutil.copy2(s, d)
    req = os.path.join(root, "requirements.txt")
    if os.path.exists(req):  # new dependencies, if any
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req], check=False, timeout=600)


def restart_source() -> None:
    script = os.path.join(app_root(), "pdf_pro.py")
    subprocess.Popen([sys.executable, script])


def run_windows_installer(installer: str) -> None:
    """start the Inno Setup installer silently; it closes PDF PRO and starts the new version"""
    subprocess.Popen(
        [installer, "/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART"], close_fds=True
    )


def mac_app_bundle() -> Optional[str]:
    """…/PDF PRO.app for a frozen macOS build"""
    p = os.path.abspath(sys.executable)
    while p and p != "/":
        if p.endswith(".app"):
            return p
        p = os.path.dirname(p)
    return None


def run_mac_update(dmg: str) -> None:
    """mount the dmg, then a detached shell script swaps the .app once this process has exited"""
    bundle = mac_app_bundle()
    if not bundle:
        subprocess.Popen(["open", dmg])
        return
    script = os.path.join(tempfile.mkdtemp(prefix="pdfpro-swap-"), "swap.sh")
    with open(script, "w") as f:
        f.write(f"""#!/bin/bash
PID={os.getpid()}
while kill -0 $PID 2>/dev/null; do sleep 0.5; done
MNT=$(mktemp -d /tmp/pdfpro-dmg.XXXX)
hdiutil attach -nobrowse -quiet -mountpoint "$MNT" "{dmg}" || {{ open "{dmg}"; exit 1; }}
NEW=$(ls -d "$MNT"/*.app | head -1)
rm -rf "{bundle}.old"
mv "{bundle}" "{bundle}.old" && ditto "$NEW" "{bundle}" && rm -rf "{bundle}.old" || mv "{bundle}.old" "{bundle}"
hdiutil detach -quiet "$MNT"
xattr -dr com.apple.quarantine "{bundle}" 2>/dev/null
open "{bundle}"
""")
    os.chmod(script, 0o755)
    subprocess.Popen(["/bin/bash", script], start_new_session=True, close_fds=True)


def install(path: str) -> str:
    """install a downloaded update; returns 'quit' when the app must exit, 'restart' for source installs"""
    kind = install_kind()
    log.info("installing %s update from %s", kind, path)
    if kind == "windows":
        run_windows_installer(path)
        return "quit"
    if kind == "mac":
        run_mac_update(path)
        return "quit"
    install_source_zip(path)
    return "restart"


__all__ = [
    "UpdateInfo",
    "check_for_update",
    "download",
    "install",
    "is_newer",
    "parse_manifest",
    "platform_key",
    "install_kind",
    "donate_links",
    "fetch_manifest",
    "restart_source",
]
