@echo off
setlocal
set "GENERATOR_DIR=%~dp0"
set "PROJECT_DIR=%GENERATOR_DIR%..\Paralate-free"
set "PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "PARALATE_SOURCE_DIR=%PROJECT_DIR%"
set "PYTHONUTF8=1"

if not exist "%PYTHON%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python bulunamadi. ParaLate proje sanal ortamini kurun veya Python'u PATH'e ekleyin.
    pause
    exit /b 1
  )
  set "PYTHON=python"
)

"%PYTHON%" "%GENERATOR_DIR%generate_premium_key.py"
if errorlevel 1 echo Lisans uretilemedi.
pause
