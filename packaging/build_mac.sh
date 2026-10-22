#!/bin/bash
# Build PDF PRO for macOS: PyInstaller .app + .dmg (for the architecture of this Mac / Python).
# Usage:  bash packaging/build_mac.sh        → dist/PDF-PRO-<version>-mac-<arm64|x64>.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' pdfpro/__init__.py)
PY=${PYTHON:-python3}
ARCH=$($PY -c 'import platform; print("arm64" if platform.machine() == "arm64" else "x64")')
echo "Building PDF PRO $VERSION for macOS $ARCH"

[ -d .build-venv ] || $PY -m venv .build-venv
.build-venv/bin/python -m pip install --upgrade pip
.build-venv/bin/python -m pip install -r requirements.txt "pyinstaller>=6.5"
[ -f LICENSE-AGPL-3.0.txt ] || curl -fsSL https://www.gnu.org/licenses/agpl-3.0.txt -o LICENSE-AGPL-3.0.txt || true

.build-venv/bin/python -m PyInstaller --noconfirm --clean packaging/pdfpro.spec

# ad-hoc signature so Apple Silicon runs the bundle (not notarised: first launch = right-click > Open)
codesign --force --deep --sign - "dist/PDF PRO.app" || true

STAGE=$(mktemp -d)
cp -R "dist/PDF PRO.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/windows/FREE-NOTICE.txt "$STAGE/อ่านก่อน - READ ME (FREE).txt"
cp LICENSE "$STAGE/LICENSE.txt"
DMG="dist/PDF-PRO-$VERSION-mac-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "PDF PRO $VERSION (Free)" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
echo "Done: $DMG"
