@echo off
setlocal
title PDFusion — Test Suite

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
  echo Ambiente virtuale non trovato. Esegui prima start.bat.
  pause
  exit /b 1
)

cd /d "%SCRIPT_DIR%"
"%VENV_PYTHON%" -m pytest tests/ -v --tb=short %*
