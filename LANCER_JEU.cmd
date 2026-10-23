@echo off
cd /d "%~dp0"
python lancer.py
if errorlevel 1 pause
