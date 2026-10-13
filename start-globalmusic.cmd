@echo off
cd /d "%~dp0integrations\globalmusic"
if not exist .venv\Scripts\python.exe (
 python -m venv .venv
 if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe -c "import spotipy, ytmusicapi" >nul 2>nul
if errorlevel 1 (
 .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
 if errorlevel 1 (
  pause
  exit /b 1
 )
)
.venv\Scripts\python.exe server.py
pause
