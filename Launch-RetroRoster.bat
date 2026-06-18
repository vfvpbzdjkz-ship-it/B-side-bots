@echo off
REM Double-click this on Windows to open the RETRO ROSTER graphical interface.
REM (Uses pythonw so no console window lingers; falls back to python if needed.)
cd /d "%~dp0"
start "" pythonw RetroRoster.pyw
if errorlevel 1 python -m retro.gui
