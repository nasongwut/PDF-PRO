# PDF PRO

**โปรแกรมฟรี 100% · Free & open source (AGPL-3.0)** — [ดาวน์โหลดเวอร์ชันล่าสุด / Download](https://github.com/nasongwut/PDF-PRO/releases/latest)

โปรแกรมเปิด แก้ไข และพิมพ์ไฟล์ PDF บนเดสก์ท็อป (ภาษาไทย / English)
รองรับ **Windows 10 / 11** และ **macOS (Intel และ Apple Silicon)** · Python 3.9+ · CustomTkinter · PyMuPDF

> วิธีใช้งานสำหรับผู้ใช้ทั่วไปอยู่ใน `README.txt`

## เริ่มใช้งาน

| ระบบ | วิธีเปิด |
|---|---|
| macOS | ดับเบิลคลิก `เปิด PDF PRO.command` |
| Windows | ดับเบิลคลิก `เปิด PDF PRO (Windows).bat` |
| นักพัฒนา | `python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python pdf_pro.py` |

ตัวเปิดโปรแกรมจะสร้าง `.venv` และติดตั้ง dependency ให้เองในครั้งแรก

## โครงสร้างโค้ด

```
PDF PRO/
├── pdf_pro.py                 จุดเริ่มโปรแกรม (ตรวจ environment แล้วเรียก pdfpro.ui.app.main)
├── pdfpro/                    แพ็กเกจหลัก
│   ├── __init__.py            ชื่อและเวอร์ชันโปรแกรม
│   ├── __main__.py            รองรับ `python -m pdfpro`
│   ├── bootstrap.py           ตรวจ Python / Tk / dependency ก่อน import อย่างอื่น
│   ├── config.py              path ต่าง ๆ และค่าตั้งของผู้ใช้ (settings.json)
│   ├── i18n.py                ฟังก์ชันแปลภาษา `_()`
│   ├── utils.py               helper ทั่วไป (สี, ชื่อ, เปิดโฟลเดอร์)
│   ├── locales/en.py          คำแปลภาษาอังกฤษ (key = ข้อความภาษาไทย)
│   ├── assets/fonts/          ฟอนต์ที่มากับโปรแกรม (TH Sarabun New, Sarabun)
│   ├── core/                  ตรรกะเอกสาร — ไม่มีโค้ด UI, มี unit test
│   │   ├── document.py        สถานะของเอกสาร 1 แท็บ (undo/redo) + ย้าย/คัดลอกหน้าระหว่างไฟล์
│   │   ├── overlay.py         วัตถุที่เพิ่มบนหน้า (ข้อความ รูป รูปทรง) และการเขียนลง PDF
│   │   ├── fonts.py           ค้นหาฟอนต์ในเครื่อง / ฟอนต์ที่ฝังในไฟล์ / จับคู่ฟอนต์เดิม
│   │   ├── thai.py            แก้ข้อความไทยที่ดึงจาก PDF
│   │   └── printing.py        รายชื่อเครื่องพิมพ์และสั่งพิมพ์ (CUPS / Windows)
│   └── ui/                    ส่วนติดต่อผู้ใช้ (CustomTkinter)
│       ├── app.py             หน้าต่างหลัก: สร้าง widget, layout, โหมดดู/แก้ไข, ภาษา, ธีม
│       ├── workspace.py       มุมมองหลายไฟล์ + ลากหน้าข้ามไฟล์
│       ├── theme.py           สีและฟอนต์ของ UI (light / dark)
│       ├── icons.py           ไอคอน SVG
│       ├── widgets.py         widget ที่ใช้ซ้ำ (ปุ่ม, tooltip, ตัวเลือกสี, ปุ่มเลือกฟอนต์)
│       ├── constants.py       รายการเครื่องมือและข้อความช่วยเหลือ
│       ├── dialogs/           หน้าต่าง modal (ข้อความ, ลายเซ็น, เลือกฟอนต์, พิมพ์)
│       └── mixins/            พฤติกรรมของหน้าต่างหลัก แยกตามหน้าที่
│           ├── tabs.py        หลายแท็บ / สลับเอกสาร
│           ├── home.py        หน้าแรก + ไฟล์ล่าสุด
│           ├── files.py       เปิด สร้าง รวม บันทึก พิมพ์
│           ├── history.py     เลิกทำ / ทำซ้ำ
│           ├── viewer.py      แสดงผลหน้า ซูม เลื่อนหน้า ภาพย่อ
│           ├── pages.py       หมุน เรียง ลบ แทรก ทำสำเนา แยกหน้า
│           ├── editing.py     เครื่องมือ การเลือก เมาส์ และคีย์บอร์ด
│           ├── text.py        วัตถุข้อความ + แก้ข้อความเดิมในไฟล์
│           ├── properties.py  แผงคุณสมบัติด้านขวา
│           └── images.py      รูปภาพ ลายเซ็น และรูปที่อยู่ใน PDF
├── packaging/                 การ build: pdfpro.spec (PyInstaller), build_mac.sh, build_windows.ps1,
│                              windows/installer.iss (Inno Setup wizard), icons/
├── server/                    ช่องทางอัปเดต: latest.json (manifest), make_manifest.py, release_notes/
├── .github/workflows/         release.yml — build อัตโนมัติ + ออก release
├── tests/                     pytest สำหรับ core และความครบของคำแปล
├── pyproject.toml             metadata, dependency, ตั้งค่า ruff / pytest
├── requirements.txt           dependency สำหรับใช้งาน
└── requirements-dev.txt       dependency สำหรับพัฒนา (pytest, ruff)
```

### หลักการออกแบบ

- **แยก core กับ UI** — `pdfpro.core` ไม่ import tkinter จึงทดสอบได้โดยไม่ต้องเปิดหน้าต่าง
- **เอกสารแต่ละแท็บเป็นอ็อบเจกต์ `Document`** — เก็บไฟล์ วัตถุที่เพิ่ม ประวัติ undo และตำแหน่งที่ดูอยู่
  หน้าต่างหลักเข้าถึงเอกสารที่เปิดอยู่ผ่าน property (`self.doc`, `self.objs`, …) ใน `TabsMixin`
- **หน้าต่างหลักแบ่งเป็น mixin ตามหน้าที่** — แต่ละไฟล์สั้นและหาโค้ดง่าย
- **แก้ไขแบบไม่ทำลายต้นฉบับ** — สิ่งที่เพิ่มเก็บเป็น overlay แล้วค่อยเขียนลงไฟล์ตอนบันทึก
  ใช้โค้ดเดียวกันทั้งตอนแสดงผลและตอนบันทึก (`core.overlay.apply_objects`) จึงเห็นแบบไหนได้แบบนั้น
- **ข้อความ UI เขียนเป็นภาษาไทยแล้วครอบด้วย `_()`** — คำแปลอยู่ที่ `locales/en.py` และมี test ตรวจว่าแปลครบ

## Build และออกเวอร์ชันใหม่ (อัตโนมัติ)

ทุกครั้งที่ `git push` ขึ้น `main` GitHub Actions (`.github/workflows/release.yml`) จะ

1. รัน lint + unit test
2. build **Windows** (PyInstaller + ตัวติดตั้ง Inno Setup wizard) และ **macOS** ทั้ง Apple Silicon (arm64) และ Intel (x64) เป็น `.dmg`
3. ถ้าเวอร์ชันใน `pdfpro/__init__.py` ยังไม่มี release → สร้าง GitHub Release `v<version>` พร้อมไฟล์ทั้งหมด
   และอัปเดต `server/latest.json` (ลิงก์ + SHA-256) ให้โปรแกรมที่ติดตั้งไว้แจ้งเตือนอัปเดต

ออกเวอร์ชันใหม่ = แก้ `__version__` + เพิ่ม `server/release_notes/<version>.th.md` / `.en.md` แล้ว push

Build เองในเครื่อง: `bash packaging/build_mac.sh` (macOS) หรือ
`powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1` (Windows, ต้องมี Inno Setup 6)

ไฟล์ที่ build ยังไม่ได้ลงนาม (code signing) — macOS ให้เปิดครั้งแรกด้วยคลิกขวา > Open, Windows SmartScreen ให้กด More info > Run anyway

## พัฒนาและทดสอบ

```bash
pip install -r requirements-dev.txt
pytest            # unit tests
ruff check .      # lint
ruff format .     # จัดรูปแบบโค้ด
```

ค่าตั้ง ไฟล์ล่าสุด ฟอนต์ที่เพิ่ม และ log (`pdfpro.log`) อยู่ที่
`~/Library/Application Support/PDF PRO` (macOS) หรือ `%APPDATA%\PDF PRO` (Windows)
