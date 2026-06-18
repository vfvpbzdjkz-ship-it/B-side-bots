@echo off
REM lichess-bot wrapper for the copybook engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=copybook
python -m retro.uci %*
