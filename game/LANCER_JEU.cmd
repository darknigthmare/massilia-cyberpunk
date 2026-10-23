@echo off
cd /d "%~dp0"
python tools\serve_game.py
if errorlevel 1 pause
