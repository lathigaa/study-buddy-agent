@echo off
REM Double-click this file to start Study Buddy on Windows.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed. Get it from https://www.python.org/downloads/
    echo During install, tick "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist .venv (
    echo First run: setting things up, this takes a minute...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo Starting Study Buddy... your browser will open. Close this window to stop it.
python -m streamlit run app.py
pause
