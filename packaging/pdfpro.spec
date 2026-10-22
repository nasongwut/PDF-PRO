# PyInstaller spec for PDF PRO — used by packaging/build_windows.ps1, packaging/build_mac.sh and CI.
# Build:  pyinstaller --noconfirm --clean packaging/pdfpro.spec
import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = re.search(r'__version__ = "([^"]+)"', open(os.path.join(ROOT, "pdfpro", "__init__.py"), encoding="utf-8").read()).group(1)
ICON_DIR = os.path.join(ROOT, "packaging", "icons")

datas = [(os.path.join(ROOT, "pdfpro", "assets"), "pdfpro/assets")]
datas += collect_data_files("customtkinter")
datas += collect_data_files("certifi")
binaries = collect_dynamic_libs("pymupdf")

version_file = None
if sys.platform == "win32":  # file properties shown in Explorer
    n = ", ".join((VERSION.split(".") + ["0"] * 4)[:4])
    version_file = os.path.join(workpath, "version_info.txt")
    os.makedirs(workpath, exist_ok=True)
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({n}), prodvers=({n}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'nasongwut (github.com/nasongwut/PDF-PRO)'),
    StringStruct('FileDescription', 'PDF PRO - free PDF editor'),
    StringStruct('FileVersion', '{VERSION}'),
    StringStruct('InternalName', 'PDF PRO'),
    StringStruct('LegalCopyright', 'Free software (AGPL-3.0) - https://github.com/nasongwut/PDF-PRO'),
    StringStruct('OriginalFilename', 'PDF PRO.exe'),
    StringStruct('ProductName', 'PDF PRO'),
    StringStruct('ProductVersion', '{VERSION}')])]),
  VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
""")

a = Analysis(
    [os.path.join(ROOT, "pdf_pro.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pymupdf", "PIL._tkinter_finder", "darkdetect"],
    excludes=["pytest", "numpy", "matplotlib", "pandas", "scipy", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDF PRO",
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(ICON_DIR, "icon.icns" if sys.platform == "darwin" else "icon.ico"),
    version=version_file,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PDF PRO")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PDF PRO.app",
        icon=os.path.join(ICON_DIR, "icon.icns"),
        bundle_identifier="com.nasongwut.pdfpro",
        version=VERSION,
        info_plist={
            "CFBundleName": "PDF PRO",
            "CFBundleDisplayName": "PDF PRO",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Free software · https://github.com/nasongwut/PDF-PRO",
            "LSMinimumSystemVersion": "11.0",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "PDF Document",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["com.adobe.pdf"],
                }
            ],
        },
    )
