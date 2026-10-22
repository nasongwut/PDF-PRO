@echo off
rem PDF PRO - Windows 10 / 11 launcher. Double-click to start.
rem The first run creates a private Python environment and installs PyMuPDF, CustomTkinter and Pillow.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title PDF PRO

set "PY="
call :try "py -3"
if not defined PY call :try "python"
if not defined PY call :try "python3"
if not defined PY goto nopython

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import tkinter" >nul 2>nul || rmdir /s /q ".venv"
)
if exist ".venv\Scripts\python.exe" goto havevenv
echo Preparing PDF PRO for the first time...
%PY% -m venv .venv
if errorlevel 1 goto fail
:havevenv
".venv\Scripts\python.exe" -c "import pymupdf, customtkinter, PIL, certifi" >nul 2>nul
if not errorlevel 1 goto run
echo Installing PyMuPDF, CustomTkinter, Pillow and certifi (needs internet)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto fail
:run
start "" ".venv\Scripts\pythonw.exe" "%~dp0pdf_pro.py" %*
exit /b 0

:try
%~1 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 9) and tkinter.TkVersion >= 8.6 else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0

:nopython
echo.
echo  Python 3.9 or newer was not found.
echo  Please install Python from https://www.python.org/downloads/windows/
echo  and tick "Add python.exe to PATH" during setup, then run this file again.
echo.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:fail
echo.
echo  Setup failed. Please check your internet connection and try again.
pause
exit /b 1
