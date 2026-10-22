#!/bin/bash
# PDF PRO — macOS launcher (Intel และ Apple Silicon M1/M2/M3/M4)
# ดับเบิลคลิกไฟล์นี้เพื่อเปิดโปรแกรม ครั้งแรกจะติดตั้งส่วนประกอบให้อัตโนมัติ
cd "$(dirname "$0")" || exit 1
echo "PDF PRO — $(uname -m) / macOS $(sw_vers -productVersion 2>/dev/null)"

ok_python() {   # Python >= 3.9 with Tk >= 8.6
  "$1" - <<'PY' >/dev/null 2>&1
import sys, tkinter
assert sys.version_info >= (3, 9)
assert tkinter.TkVersion >= 8.6
PY
}

PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.1{4,3,2,1,0}/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  p=$(command -v "$c" 2>/dev/null) || continue
  if ok_python "$p"; then PY="$p"; break; fi
done

if [ -z "$PY" ]; then
  echo ""
  echo "ไม่พบ Python 3.9+ ที่มี Tk 8.6 (Python ที่มากับ macOS ใช้ไม่ได้)"
  echo "กรุณาติดตั้ง Python จาก https://www.python.org/downloads/macos/ (รองรับทั้ง Intel และ M-series)"
  osascript -e 'display dialog "ต้องติดตั้ง Python จาก python.org ก่อน (รองรับทั้ง Intel และ Apple Silicon)\n\nเปิดหน้าดาวน์โหลดเลยหรือไม่?" buttons {"ยกเลิก","เปิดหน้าดาวน์โหลด"} default button 2 with title "PDF PRO"' 2>/dev/null | grep -q "เปิดหน้าดาวน์โหลด" && open "https://www.python.org/downloads/macos/"
  exit 1
fi
echo "ใช้ Python: $PY"

# venv ต้องตรงกับ Python และสถาปัตยกรรมเครื่อง (ถ้าย้ายโฟลเดอร์ข้ามเครื่อง Intel/M-series จะสร้างใหม่ให้)
if [ -x .venv/bin/python ] && ! .venv/bin/python -c "import tkinter" >/dev/null 2>&1; then rm -rf .venv; fi
if [ -x .venv/bin/python ] && [ "$(.venv/bin/python -c 'import platform;print(platform.machine())' 2>/dev/null)" != "$("$PY" -c 'import platform;print(platform.machine())')" ]; then rm -rf .venv; fi
if [ ! -x .venv/bin/python ]; then
  echo "กำลังเตรียมโปรแกรมครั้งแรก…"; "$PY" -m venv .venv || { read -n 1 -s -r -p "สร้าง venv ไม่สำเร็จ กดปุ่มใดก็ได้"; exit 1; }
fi
if ! .venv/bin/python -c "import pymupdf, customtkinter, PIL, certifi" >/dev/null 2>&1; then
  echo "กำลังติดตั้งส่วนประกอบ (PyMuPDF, CustomTkinter, Pillow, certifi)…"
  .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
  .venv/bin/python -m pip install --upgrade -r requirements.txt || { read -n 1 -s -r -p "ติดตั้งไม่สำเร็จ (ตรวจอินเทอร์เน็ต) กดปุ่มใดก็ได้"; exit 1; }
fi
exec .venv/bin/python pdf_pro.py "$@"
