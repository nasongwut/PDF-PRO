# Build PDF PRO for Windows: PyInstaller app + Inno Setup installer wizard.
# Usage (PowerShell, from the project folder):   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$version = (Select-String -Path "pdfpro\__init__.py" -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "Building PDF PRO $version for Windows"

if (-not (Test-Path ".build-venv")) { python -m venv .build-venv }
& .build-venv\Scripts\python.exe -m pip install --upgrade pip
& .build-venv\Scripts\python.exe -m pip install -r requirements.txt "pyinstaller>=6.5"

if (-not (Test-Path "LICENSE-AGPL-3.0.txt")) {
    try { Invoke-WebRequest "https://www.gnu.org/licenses/agpl-3.0.txt" -OutFile "LICENSE-AGPL-3.0.txt" } catch { Write-Warning "could not download the AGPL text" }
}

& .build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging\pdfpro.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 is not installed (https://jrsoftware.org/isdl.php or: choco install innosetup)" }
& $iscc "/DAppVersion=$version" "/DSourceDir=..\..\dist\PDF PRO" "/DOutputDir=..\..\dist" packaging\windows\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Done: dist\PDF-PRO-$version-windows-setup.exe"
