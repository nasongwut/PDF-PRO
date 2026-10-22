#!/usr/bin/env python3
"""Create / update ``server/latest.json`` — the file PDF PRO reads to find new versions.

Used by the GitHub release workflow, but can be run by hand::

    python server/make_manifest.py --version 1.0.1 --dist dist --notes-th "..." --notes-en "..."

Download URLs point to the GitHub release ``v<version>``; SHA-256 checksums are computed from the
files found in ``--dist`` (missing files are listed without a checksum).
"""

import argparse
import datetime
import hashlib
import json
import os

REPO = "nasongwut/PDF-PRO"
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "windows": "PDF-PRO-{v}-windows-setup.exe",
    "mac-arm64": "PDF-PRO-{v}-mac-arm64.dmg",
    "mac-x64": "PDF-PRO-{v}-mac-x64.dmg",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", required=True)
    ap.add_argument("--dist", default="dist", help="folder with the built installers")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--notes-th", default="")
    ap.add_argument("--notes-en", default="")
    ap.add_argument("--output", default=os.path.join(HERE, "latest.json"))
    a = ap.parse_args()

    def notes_file(lang):
        p = os.path.join(HERE, "release_notes", "%s.%s.md" % (a.version, lang))
        return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""

    a.notes_th = a.notes_th or notes_file("th")
    a.notes_en = a.notes_en or notes_file("en")
    old = {}
    if os.path.exists(a.output):
        with open(a.output, encoding="utf-8") as f:
            old = json.load(f)
    base = "https://github.com/%s/releases/download/v%s/" % (a.repo, a.version)
    downloads = {}
    for key, pattern in FILES.items():
        name = pattern.format(v=a.version)
        path = os.path.join(a.dist, name)
        downloads[key] = {"url": base + name, "sha256": sha256(path) if os.path.exists(path) else ""}
    downloads["source"] = {"url": "https://github.com/%s/archive/refs/tags/v%s.zip" % (a.repo, a.version), "sha256": ""}
    manifest = {
        "name": "PDF PRO",
        "version": a.version,
        "released": datetime.date.today().isoformat(),
        "notes": {
            "th": a.notes_th or old.get("notes", {}).get("th", ""),
            "en": a.notes_en or old.get("notes", {}).get("en", ""),
        },
        "page": "https://github.com/%s/releases/tag/v%s" % (a.repo, a.version),
        "homepage": "https://github.com/%s" % a.repo,
        "downloads": downloads,
        # edit freely — shown in the app's "Donate" dialog without releasing a new version
        "donate": old.get("donate")
        or [
            {"label": "GitHub Sponsors", "url": "https://github.com/sponsors/nasongwut"},
        ],
    }
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote", a.output)


if __name__ == "__main__":
    main()
