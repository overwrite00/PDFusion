@echo off
setlocal EnableDelayedExpansion
title PDFusion

:: --- Lingua ---
for /f "tokens=2 delims==" %%L in (
  'wmic os get MUILanguages /value 2^>nul ^| find "="'
) do set "_UILANG=%%L"

if /i "!_UILANG:~0,2!"=="it" (
  set "MSG_CHECKING=Controllo ambiente..."
  set "MSG_PYTHON_FOUND=Python trovato:"
  set "MSG_PYTHON_NOT=Python 3.11-3.13 non trovato. Installa Python 3.13 da python.org e riprova."
  set "MSG_VENV=Creazione ambiente virtuale..."
  set "MSG_PIP_UPGRADE=Aggiornamento pip..."
  set "MSG_DEPS=Installazione dipendenze..."
  set "MSG_UP=Dipendenze già installate."
  set "MSG_START=Avvio PDFusion..."
) else (
  set "MSG_CHECKING=Checking environment..."
  set "MSG_PYTHON_FOUND=Python found:"
  set "MSG_PYTHON_NOT=Python 3.11-3.13 not found. Install Python 3.13 from python.org and retry."
  set "MSG_VENV=Creating virtual environment..."
  set "MSG_PIP_UPGRADE=Upgrading pip..."
  set "MSG_DEPS=Installing dependencies..."
  set "MSG_UP=Dependencies already installed."
  set "MSG_START=Starting PDFusion..."
)

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
set "PYTHON_BIN="

echo !MSG_CHECKING!

:: --- Trova Python (Launcher py prima, poi python.exe) ---
where py >nul 2>&1
if %errorlevel%==0 (
  for %%V in (3.13 3.12 3.11) do (
    if not defined PYTHON_BIN (
      py -%%V --version >nul 2>&1
      if !errorlevel!==0 (
        set "PYTHON_BIN=py -%%V"
      )
    )
  )
)

if not defined PYTHON_BIN (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python -c "import sys; v=sys.version_info; exit(0 if 11<=v.minor<=13 else 1)" >nul 2>&1
    if !errorlevel!==0 set "PYTHON_BIN=python"
  )
)

if not defined PYTHON_BIN (
  echo !MSG_PYTHON_NOT! >&2
  pause
  exit /b 1
)

echo !MSG_PYTHON_FOUND! !PYTHON_BIN!

:: --- Ambiente virtuale ---
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo !MSG_VENV!
  !PYTHON_BIN! -m venv "%VENV_DIR%"
)

set "PYTHON_VENV=%VENV_DIR%\Scripts\python.exe"
set "PIP_VENV=%VENV_DIR%\Scripts\pip.exe"

:: --- Dipendenze (controlla hash) ---
set "REQ_HASH_FILE=%VENV_DIR%\.req_hash"
set "SAVED_HASH="
if exist "%REQ_HASH_FILE%" set /p SAVED_HASH=<"%REQ_HASH_FILE%"

:: Calcola hash con CertUtil
for /f "skip=1 tokens=* delims=" %%H in (
  'certutil -hashfile "%REQ_FILE%" SHA256 2^>nul'
) do (
  if not defined REQ_HASH set "REQ_HASH=%%H"
)
set "REQ_HASH=!REQ_HASH: =!"

:: --- Upgrade pip (sempre) ---
echo !MSG_PIP_UPGRADE!
"%PIP_VENV%" install --quiet --upgrade pip

:: --- Installa dipendenze (se necessario) ---
if "!REQ_HASH!"=="!SAVED_HASH!" (
  echo !MSG_UP!
) else (
  echo !MSG_DEPS!
  "%PIP_VENV%" install --quiet -r "%REQ_FILE%"
  echo !REQ_HASH!>"%REQ_HASH_FILE%"
)

:: --- Avvio ---
echo !MSG_START!
cd /d "%SCRIPT_DIR%"
"%PYTHON_VENV%" -m src.main %*
