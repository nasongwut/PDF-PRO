import hashlib
import json
import pathlib
import zipfile

import pytest

from pdfpro.core import updater


def test_version_compare():
    assert updater.is_newer("1.0.1", "1.0.0")
    assert updater.is_newer("1.10.0", "1.9.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("1.0", "1.0.0")
    assert updater.parse_version("v2.3.4-beta") == (2, 3, 4)


MANIFEST = {
    "version": "9.9.9",
    "notes": {"th": "ใหม่", "en": "new"},
    "downloads": {"windows": {"url": "https://x/setup.exe", "sha256": "AB"}, "source": {"url": "https://x/s.zip"}},
}


def test_parse_manifest_for_platform():
    info = updater.parse_manifest(MANIFEST, current="1.0.0", key="windows")
    assert info.version == "9.9.9" and info.sha256 == "ab" and info.notes_for("th") == "ใหม่"
    assert updater.parse_manifest(MANIFEST, current="1.0.0", key="mac-arm64") is None  # no build for it
    assert updater.parse_manifest(MANIFEST, current="9.9.9", key="windows") is None  # not newer


def test_fetch_manifest_and_download_from_file(tmp_path):
    payload = tmp_path / "update.bin"
    payload.write_bytes(b"x" * 100_000)
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    man = tmp_path / "latest.json"
    man.write_text(json.dumps(MANIFEST), encoding="utf-8")
    assert updater.fetch_manifest(man.as_uri())["version"] == "9.9.9"
    seen = []
    (tmp_path / "dl").mkdir()
    path = updater.download(payload.as_uri(), str(tmp_path / "dl"), digest, progress=lambda d, t: seen.append(d))
    assert pathlib.Path(path).read_bytes() == payload.read_bytes() and seen[-1] == 100_000
    (tmp_path / "dl2").mkdir()
    with pytest.raises(ValueError):
        updater.download(payload.as_uri(), str(tmp_path / "dl2"), "0" * 64)


def test_install_source_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.subprocess, "run", lambda *a, **k: None)  # no pip in tests
    root = tmp_path / "app"
    (root / "pdfpro").mkdir(parents=True)
    (root / "pdfpro" / "old.py").write_text("old")
    (root / ".venv").mkdir()
    zpath = tmp_path / "src.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("PDF-PRO-9.9.9/pdf_pro.py", "print('new')")
        z.writestr("PDF-PRO-9.9.9/pdfpro/__init__.py", "__version__ = '9.9.9'")
    updater.install_source_zip(str(zpath), str(root))
    assert (root / "pdf_pro.py").read_text() == "print('new')"
    assert (root / "pdfpro" / "__init__.py").exists() and not (root / "pdfpro" / "old.py").exists()
    assert (root / ".venv").exists()
