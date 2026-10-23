@echo off
cd /d "%~dp0"
python tools\verify_release.py
if errorlevel 1 pause
